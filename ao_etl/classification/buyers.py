"""Phase 8 du pipeline : Classification déterministe + LLM des acheteurs.

Séquence canonique complète :
  DISCOVERY → RECONCILE → EXTRACT → MERGE → VALIDATE → EXPORT
  → [CONSOLIDATE] → [CLASSIFY_BUYERS]

Ce module fournit trois fonctions publiques :
  - classify_buyers_rule_based(input_csv, output_csv)
  - classify_buyers_llm_enrichment(input_csv, output_csv, acheteur_db)
  - report_buyer_classification_quality(csv_path, report_path, bad_csv_path)

Architecture :
  1. La couche RÈGLES est purement déterministe (pas de réseau, pas de LLM).
     Elle normalise et enrichit `type_acheteur` / `fonction_publique` à partir
     du libellé `acheteur` et de listes de mots-clés explicites.
  2. La couche LLM est optionnelle et ne traite que les lignes résiduelles
     (type_acheteur == "inconnu").  Elle prend en entrée un dictionnaire
     `acheteur_db` alimenté en amont (par recherche web, API LLM, etc.).
  3. Le rapport QA valide le vocabulaire, produit des distributions et une
     matrice croisée.
"""

from __future__ import annotations

import csv
import logging
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional

from ao_etl.llm.backend import LLMDisabledError

log = logging.getLogger(__name__)

# Valeurs autorisées dans la colonne finale 'Fonction publique' du CSV
_FP_EXPORT_ALLOWED = frozenset(["etat", "territoriale", "hospitaliere"])


def _normalize_fp_for_export(rows: list) -> None:
    """Normalise la colonne 'fonction_publique' avant export CSV final.

    Toute valeur hors domaine strict (hors_fonction_publique, inconnue,
    toute valeur absente ou non reconnue) est remplacee par '-'.
    Opertion in-place sur la liste de dicts.
    """
    for row in rows:
        fp = row.get("fonction_publique", "")
        if fp not in _FP_EXPORT_ALLOWED:
            row["fonction_publique"] = "-"

# ═══════════════════════════════════════════════════════════════════════════
# CONTRATS : VOCABULAIRE AUTORISÉ (source unique de vérité)
# ═══════════════════════════════════════════════════════════════════════════

ALLOWED_TYPE_ACHETEUR: FrozenSet[str] = frozenset([
    "etat",
    "collectivite_territoriale",
    "etablissement_public",
    "entreprise_privee",
    "organisme_prive_interet_general",
    "inconnu",
])

ALLOWED_FONCTION_PUBLIQUE: FrozenSet[str] = frozenset([
    "etat",
    "territoriale",
    "hospitaliere",
    "hors_fonction_publique",
    "inconnue",
])

ALLOWED_SOURCE: FrozenSet[str] = frozenset([
    "original",
    "rule",
    "llm",
])

# ═══════════════════════════════════════════════════════════════════════════
# CONTRATS : SCHÉMA D'ENTRÉE
# ═══════════════════════════════════════════════════════════════════════════

REQUIRED_INPUT_COLUMNS: FrozenSet[str] = frozenset([
    "reference",
    "titre",
    "acheteur",
    "type_acheteur",
    "fonction_publique",
])

# ═══════════════════════════════════════════════════════════════════════════
# CONTRATS : NOMS CANONIQUES DES FICHIERS DE SORTIE
# ═══════════════════════════════════════════════════════════════════════════

CANONICAL_RULE_CSV = "classified-rule.csv"
CANONICAL_CLASSIFIED_CSV = "classified.csv"
CANONICAL_BAD_CSV = "classified-bad.csv"
CANONICAL_REPORT_MD = "classification-quality.md"

# Colonnes supprimées du CSV final.
# - *_source, classification_commentaire : traçabilité interne de la classification.
# - sous_type_fonction_publique, procedure_label : supprimées du schéma métier.
# Elles restent présentes dans les CSV intermédiaires (*-rule.csv) et dans le rapport QA.
_COLUMNS_TO_STRIP: FrozenSet[str] = frozenset([
    "type_acheteur_source",
    "fonction_publique_source",
    "classification_commentaire",
    "sous_type_fonction_publique",
    "procedure_label",
])


class ClassificationInputError(ValueError):
    """Raised when the input CSV is missing or has an invalid schema."""


def _resolve_output_path(base_dir: Path, suffix: str, input_stem: str) -> Path:
    """Construit un chemin de sortie canonique : <input_stem>-<suffix>."""
    return base_dir / f"{input_stem}-{suffix}"


def _strip_internal_columns(rows: list[dict], fieldnames: list[str]) -> list[str]:
    """Retire les colonnes internes des fieldnames et des rows (in-place).

    Returns:
        Nouveau fieldnames sans les colonnes internes.
    """
    clean_fn = [c for c in fieldnames if c not in _COLUMNS_TO_STRIP]
    for row in rows:
        for col in _COLUMNS_TO_STRIP:
            row.pop(col, None)
    return clean_fn

# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _norm(text: str) -> str:
    """Minuscule + sans accent + espaces normalisés."""
    return " ".join(_strip_accents(text).lower().split())


def _contains_any(haystack: str, keywords: list[str]) -> bool:
    return any(kw in haystack for kw in keywords)


def _starts_with_any(haystack: str, prefixes: list[str]) -> bool:
    return any(haystack.startswith(p) for p in prefixes)


def _validate_input_csv(csv_path: Path) -> list[str]:
    """Vérifie l'existence et le schéma du CSV. Retourne les fieldnames.

    Raises:
        ClassificationInputError: si le fichier n'existe pas ou si des
            colonnes requises sont absentes.
    """
    if not csv_path.is_file():
        raise ClassificationInputError(
            f"Fichier introuvable : {csv_path}"
        )
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])

    present = frozenset(fieldnames)
    missing = REQUIRED_INPUT_COLUMNS - present
    if missing:
        raise ClassificationInputError(
            f"Colonnes requises manquantes dans {csv_path.name} : "
            + ", ".join(sorted(missing))
        )
    return fieldnames


def _safe_write(path: Path, *, overwrite: bool) -> None:
    """Vérifie qu'on ne va pas écraser silencieusement un fichier existant.

    Raises:
        FileExistsError: si le fichier existe et overwrite=False.
    """
    if path.is_file() and not overwrite:
        raise FileExistsError(
            f"Le fichier {path} existe déjà. Passer overwrite=True pour l'écraser."
        )


# ═══════════════════════════════════════════════════════════════════════════
# MOTS-CLÉS (tous normalisés une seule fois à l'import)
# ═══════════════════════════════════════════════════════════════════════════

# Marqueurs « État »
_ETAT_KW = [_norm(k) for k in [
    "Ministère", "Ministre", "Direction générale", "DGFiP", "DGFIP",
    "Ministère des Armées", "Ministère de la Justice",
    "Direction du numérique", "DNUM",
    "Préfecture", "Service de l'État",
    "INSEE",
    "MINARM", "MINDEF", "DIRISI",
    "IFCE",
]]

# Collectivités territoriales — préfixes
_CT_PREFIXES = [_norm(p) for p in [
    "Ville de", "Commune de", "Mairie de",
]]

# Collectivités territoriales — mots-clés
_CT_KW = [_norm(k) for k in [
    "Conseil départemental", "Conseil régional",
    "Région ",
    "Communauté de communes", "Communauté d'agglomération",
    "Communauté d agglomération",
    "Métropole",
    "Syndicat intercommunal", "Syndicat mixte",
    "VILLE de",
    "Agglo",
    "Communauté",
]]

# SPL (Société publique locale) → CT
_SPL_KW = [_norm(k) for k in [
    "SPL ",
    "Société publique locale",
]]

# SEM (Société d'économie mixte) → entreprise_privee
_SEM_KW = [_norm(k) for k in [
    "Société d'économie mixte", "Societe d'economie mixte",
    "Société d economie mixte",
    "SA d'économie mixte", "SA d economie mixte",
    "SEM ",
]]

# Marqueurs hospitaliers
_HOPITAL_KW = [_norm(k) for k in [
    "Centre hospitalier", "CHU ", "CHU-", "GHT ",
    "Hôpital", "Hopital",
    "Hospices civils", "AP-HP", "APHP",
    "GCS-UNIHA", "GCS UNIHA", "UNIHA",
]]

# Établissements publics (non hospitaliers, rattachés à l'État)
_EP_ETAT_KW = [_norm(k) for k in [
    "Conservatoire national des arts et métiers", "Cnam",
    "Institut géographique national", "IGN",
    "Institut Français",
    "Haute Autorité de Santé",
    "Académie",
    "UGAP", "Union des Groupements d'Achats Publics",
    "BRGM", "Bureau de Recherche",
    "Agence de l'Eau", "Agence de l eau",
    "Synchrotron",
    "ESADMM",
    "EPPGHV",
    "Supélec", "Supelec", "CentraleSupélec", "CentraleSupelec", "Centrale Supelec",
    "Université", "Universite", "COMUE",
    "CEA ", "CEA/",
    "CNRS",
    "CNAF",
    "SHOM",
    "EOESRI",
]]

# Entités privées / hors FP (fallback)
_PRIVE_KW = [_norm(k) for k in [
    " SA ", " SAS ", " GIP ",
    "SA en son nom",
    "Intercommunale",
    "Parlement Wallon",
    "Association ",
    "Compagnie Nationale du Rhône",
    "UNICANCER",
    "Organisation qui passe un marché subventionné",
]]


# ═══════════════════════════════════════════════════════════════════════════
# CLASSIFICATION PAR RÈGLES
# ═══════════════════════════════════════════════════════════════════════════

def _classify_row_rule(row: dict) -> dict:
    """Applique les règles déterministes sur une ligne CSV (dict).

    Modifie en place et retourne ``row`` avec les colonnes mises à jour :
    type_acheteur, fonction_publique, type_acheteur_source, fonction_publique_source.
    """
    acheteur_n = _norm(row.get("acheteur", ""))
    ta_orig = row.get("type_acheteur", "").strip()
    fp_orig = row.get("fonction_publique", "").strip()

    # Normalisation des valeurs non-standard
    ta = ta_orig
    if ta.lower() == "hopital":
        ta = "etablissement_public"
    fp = fp_orig
    if fp.lower() == "etat":
        fp = "etat"

    # ── Cascade de classification type_acheteur ──────────────────────────
    if _contains_any(acheteur_n, _HOPITAL_KW):
        ta = "etablissement_public"
    elif _contains_any(acheteur_n, _EP_ETAT_KW):
        ta = "etablissement_public"
    elif _contains_any(acheteur_n, _ETAT_KW):
        ta = "etat"
    elif _starts_with_any(acheteur_n, _CT_PREFIXES) or _contains_any(acheteur_n, _CT_KW):
        ta = "collectivite_territoriale"
    elif _contains_any(acheteur_n, _SPL_KW):
        ta = "collectivite_territoriale"
    elif _contains_any(acheteur_n, _SEM_KW):
        ta = "entreprise_privee"
    elif _contains_any(acheteur_n, _PRIVE_KW):
        ta = "inconnu"

    if not ta:
        ta = "inconnu"

    # ── Déduction fonction_publique ──────────────────────────────────────
    is_hospital = _contains_any(acheteur_n, _HOPITAL_KW)
    is_prive = _contains_any(acheteur_n, _PRIVE_KW) and not is_hospital
    is_sem = _contains_any(acheteur_n, _SEM_KW)

    if ta == "collectivite_territoriale":
        fp = "territoriale"
    elif ta == "etat":
        fp = "etat"
    elif ta == "etablissement_public":
        fp = "hospitaliere" if is_hospital else "etat"
    elif ta == "entreprise_privee" or is_prive or is_sem:
        fp = "hors_fonction_publique"

    if not fp or fp.lower() in ("", "inconnue", "inconnu"):
        fp = "inconnue"

    # ── Source tracking ──────────────────────────────────────────────────
    row["type_acheteur"] = ta
    row["fonction_publique"] = fp
    row["type_acheteur_source"] = "original" if ta == ta_orig else "rule"
    row["fonction_publique_source"] = "original" if fp == fp_orig else "rule"
    return row


def classify_buyers_rule_based(
    input_csv: Path,
    output_csv: Path,
    *,
    overwrite: bool = True,
) -> Dict[str, Any]:
    """Classification par règles déterministes.

    Args:
        input_csv:  CSV d'entrée (ex: final-v3-consolidated.csv).
        output_csv: CSV de sortie enrichi.
        overwrite:  Autoriser l'écrasement du fichier de sortie.

    Returns:
        Statistiques : {total, ta_changed, fp_changed, ta_dist, fp_dist}.

    Raises:
        ClassificationInputError: CSV absent ou schéma invalide.
        FileExistsError: fichier de sortie existant et overwrite=False.
    """
    input_csv, output_csv = Path(input_csv), Path(output_csv)
    log.info("classify_buyers_rule_based: entrée=%s", input_csv)

    fieldnames = _validate_input_csv(input_csv)
    _safe_write(output_csv, overwrite=overwrite)

    with open(input_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Ajouter les colonnes source si absentes
    for col in ("type_acheteur_source", "fonction_publique_source"):
        if col not in fieldnames:
            fieldnames.append(col)

    classified = [_classify_row_rule(row) for row in rows]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(classified)

    ta_changed = sum(1 for r in classified if r["type_acheteur_source"] == "rule")
    fp_changed = sum(1 for r in classified if r["fonction_publique_source"] == "rule")

    stats = {
        "total": len(classified),
        "ta_changed": ta_changed,
        "fp_changed": fp_changed,
        "ta_dist": dict(Counter(r["type_acheteur"] for r in classified)),
        "fp_dist": dict(Counter(r["fonction_publique"] for r in classified)),
    }

    log.info(
        "classify_buyers_rule_based: %d lignes, %d ta modifiés, %d fp modifiés → %s",
        stats["total"], ta_changed, fp_changed, output_csv,
    )
    return stats


# ═══════════════════════════════════════════════════════════════════════════
# ENRICHISSEMENT LLM (optionnel)
# ═══════════════════════════════════════════════════════════════════════════

# Type attendu pour la base de connaissances acheteur
# Clé = libellé acheteur normalisé (lower stripped)
# Valeur = dict avec type_acheteur, fonction_publique, commentaire, urls
AcheteurDB = Dict[str, Dict[str, Any]]


def classify_buyers_llm_enrichment(
    input_csv: Path,
    output_csv: Path,
    acheteur_db: AcheteurDB,
    *,
    overwrite: bool = True,
) -> Dict[str, Any]:
    """Enrichit les lignes résiduelles (type_acheteur=inconnu) via une base LLM.

    La base ``acheteur_db`` est un dictionnaire pré-calculé (par appel LLM
    externe, recherche web, etc.).  Ce module ne fait PAS d'appel réseau
    lui-même : il applique uniquement le dictionnaire fourni.

    Args:
        input_csv:    CSV issu de classify_buyers_rule_based.
        output_csv:   CSV enrichi final.
        acheteur_db:  Base {acheteur_norm: {type_acheteur, fonction_publique, commentaire, urls}}.
        overwrite:    Autoriser l'écrasement du fichier de sortie.

    Returns:
        Statistiques : {total, ta_llm, fp_llm, still_unknown, skipped_bad_vocab}.

    Raises:
        ClassificationInputError: CSV absent ou schéma invalide.
        FileExistsError: fichier de sortie existant et overwrite=False.
    """
    input_csv, output_csv = Path(input_csv), Path(output_csv)
    log.info("classify_buyers_llm_enrichment: entrée=%s, db=%d entrées", input_csv, len(acheteur_db))

    fieldnames = _validate_input_csv(input_csv)
    _safe_write(output_csv, overwrite=overwrite)

    with open(input_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if "classification_commentaire" not in fieldnames:
        fieldnames.append("classification_commentaire")

    ta_llm = 0
    fp_llm = 0
    skipped_bad_vocab = 0

    for row in rows:
        if "classification_commentaire" not in row:
            row["classification_commentaire"] = ""

        key = row["acheteur"].strip().lower()
        match = acheteur_db.get(key)
        if not match:
            continue

        # Valider que les valeurs LLM respectent le vocabulaire autorisé
        proposed_ta = match.get("type_acheteur", "inconnu")
        proposed_fp = match.get("fonction_publique", row["fonction_publique"])
        if proposed_ta not in ALLOWED_TYPE_ACHETEUR or proposed_fp not in ALLOWED_FONCTION_PUBLIQUE:
            skipped_bad_vocab += 1
            log.warning(
                "LLM db: valeur hors vocabulaire pour '%s' → ta='%s', fp='%s' — ignorée",
                key[:40], proposed_ta, proposed_fp,
            )
            continue

        # Ne modifier que les lignes encore « inconnu »
        ta_changed = False
        fp_changed = False

        if row["type_acheteur"] == "inconnu" and proposed_ta != "inconnu":
            row["type_acheteur"] = proposed_ta
            row["type_acheteur_source"] = "llm"
            ta_changed = True
            ta_llm += 1

        if row["fonction_publique"] in ("inconnue", "hors_fonction_publique"):
            if proposed_fp != row["fonction_publique"]:
                row["fonction_publique"] = proposed_fp
                row["fonction_publique_source"] = "llm"
                fp_changed = True
                fp_llm += 1

        if ta_changed or fp_changed:
            urls = " ; ".join(match.get("urls", [])) or "N/A"
            row["classification_commentaire"] = (
                f"{match.get('commentaire', '')} Sources: {urls}"
            )

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    still_unknown = sum(
        1 for r in rows
        if r["type_acheteur"] == "inconnu" or r["fonction_publique"] == "inconnue"
    )

    stats = {
        "total": len(rows),
        "ta_llm": ta_llm,
        "fp_llm": fp_llm,
        "still_unknown": still_unknown,
        "skipped_bad_vocab": skipped_bad_vocab,
    }

    log.info(
        "classify_buyers_llm_enrichment: %d ta, %d fp modifiés, %d inconnus, %d ignorés (vocab) → %s",
        ta_llm, fp_llm, still_unknown, skipped_bad_vocab, output_csv,
    )
    return stats


# ═══════════════════════════════════════════════════════════════════════════
# RAPPORT QA
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ClassificationQAReport:
    """Résultat du rapport QA de classification."""
    total: int = 0
    bad_count: int = 0
    ta_dist: Dict[str, int] = field(default_factory=dict)
    fp_dist: Dict[str, int] = field(default_factory=dict)
    ta_source_dist: Dict[str, int] = field(default_factory=dict)
    fp_source_dist: Dict[str, int] = field(default_factory=dict)
    unknowns_ta: List[Dict[str, str]] = field(default_factory=list)
    unknowns_fp: List[Dict[str, str]] = field(default_factory=list)
    bad_rows: List[Dict[str, str]] = field(default_factory=list)
    markdown: str = ""


def report_buyer_classification_quality(
    csv_path: Path,
    report_path: Optional[Path] = None,
    bad_csv_path: Optional[Path] = None,
    *,
    overwrite: bool = True,
) -> ClassificationQAReport:
    """Valide le vocabulaire et génère un rapport QA Markdown.

    Args:
        csv_path:     CSV classifié à auditer.
        report_path:  Chemin .md pour le rapport (None = pas d'écriture).
        bad_csv_path: Chemin .csv pour les anomalies (None = pas d'écriture).
        overwrite:    Autoriser l'écrasement des fichiers de sortie.

    Returns:
        ClassificationQAReport avec toutes les métriques.

    Raises:
        ClassificationInputError: CSV absent ou schéma invalide.
        FileExistsError: fichier de sortie existant et overwrite=False.
    """
    csv_path = Path(csv_path)
    log.info("report_buyer_classification_quality: source=%s", csv_path)

    fieldnames = _validate_input_csv(csv_path)
    if report_path:
        _safe_write(Path(report_path), overwrite=overwrite)
    if bad_csv_path:
        _safe_write(Path(bad_csv_path), overwrite=overwrite)

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    n = len(rows)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Validation vocabulaire (type_acheteur, fonction_publique, *_source) ──
    bad_rows = []
    for row in rows:
        reasons = []
        ta = row.get("type_acheteur", "")
        fp = row.get("fonction_publique", "")
        ta_src = row.get("type_acheteur_source", "")
        fp_src = row.get("fonction_publique_source", "")
        if ta not in ALLOWED_TYPE_ACHETEUR:
            reasons.append(f"type_acheteur='{ta}' hors vocabulaire")
        if fp not in ALLOWED_FONCTION_PUBLIQUE:
            reasons.append(f"fonction_publique='{fp}' hors vocabulaire")
        if ta_src and ta_src not in ALLOWED_SOURCE:
            reasons.append(f"type_acheteur_source='{ta_src}' hors vocabulaire")
        if fp_src and fp_src not in ALLOWED_SOURCE:
            reasons.append(f"fonction_publique_source='{fp_src}' hors vocabulaire")
        if reasons:
            bad_rows.append({**row, "violation": " ; ".join(reasons)})

    if bad_rows and bad_csv_path:
        bad_csv_path = Path(bad_csv_path)
        bad_fields = fieldnames + (["violation"] if "violation" not in fieldnames else [])
        with open(bad_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=bad_fields)
            writer.writeheader()
            writer.writerows(bad_rows)
        log.warning("Vocabulaire: %d ligne(s) hors norme → %s", len(bad_rows), bad_csv_path)

    # ── Distributions ───────────────────────────────────────────────────
    ta_dist = dict(Counter(r.get("type_acheteur", "") for r in rows))
    fp_dist = dict(Counter(r.get("fonction_publique", "") for r in rows))
    ta_src = dict(Counter(r.get("type_acheteur_source", "") for r in rows))
    fp_src = dict(Counter(r.get("fonction_publique_source", "") for r in rows))

    unknowns_ta = [
        {"reference": r["reference"], "acheteur": r["acheteur"],
         "fp": r["fonction_publique"], "ta_source": r.get("type_acheteur_source", "")}
        for r in rows if r.get("type_acheteur") == "inconnu"
    ]
    unknowns_fp = [
        {"reference": r["reference"], "acheteur": r["acheteur"],
         "ta": r["type_acheteur"], "fp_source": r.get("fonction_publique_source", "")}
        for r in rows if r.get("fonction_publique") == "inconnue"
    ]

    # ── Matrice croisée ─────────────────────────────────────────────────
    cross: Dict[str, Dict[str, int]] = {}
    for r in rows:
        ta = r.get("type_acheteur", "")
        fp = r.get("fonction_publique", "")
        cross.setdefault(ta, Counter())[fp] += 1

    # ── Markdown ────────────────────────────────────────────────────────
    md = _build_markdown(
        now=now, csv_name=csv_path.name, n=n,
        bad_rows=bad_rows, bad_csv_name=(bad_csv_path.name if bad_csv_path else None),
        ta_dist=ta_dist, fp_dist=fp_dist,
        ta_src=ta_src, fp_src=fp_src,
        unknowns_ta=unknowns_ta, unknowns_fp=unknowns_fp,
        cross=cross,
    )

    if report_path:
        report_path = Path(report_path)
        report_path.write_text(md, encoding="utf-8")
        log.info("Rapport QA écrit dans %s", report_path)

    return ClassificationQAReport(
        total=n,
        bad_count=len(bad_rows),
        ta_dist=ta_dist,
        fp_dist=fp_dist,
        ta_source_dist=ta_src,
        fp_source_dist=fp_src,
        unknowns_ta=unknowns_ta,
        unknowns_fp=unknowns_fp,
        bad_rows=bad_rows,
        markdown=md,
    )


def _build_markdown(
    *, now, csv_name, n, bad_rows, bad_csv_name,
    ta_dist, fp_dist, ta_src, fp_src,
    unknowns_ta, unknowns_fp, cross,
) -> str:
    L = []
    L.append("# Rapport de contrôle qualité — Classification acheteurs\n")
    L.append(f"- **Date** : {now}")
    L.append(f"- **Fichier source** : `{csv_name}`")
    L.append(f"- **Lignes totales** : {n}\n")

    # Vocabulaire
    L.append("## 1. Validation du vocabulaire\n")
    if not bad_rows:
        L.append("✅ **Aucune violation** — toutes les valeurs appartiennent au vocabulaire autorisé.\n")
    else:
        L.append(f"⚠️ **{len(bad_rows)} ligne(s) hors vocabulaire**"
                 + (f" → `{bad_csv_name}`." if bad_csv_name else ".") + "\n")
        L.append("| reference | acheteur | violation |")
        L.append("|---|---|---|")
        for r in bad_rows:
            L.append(f"| {r['reference']} | {r['acheteur'][:50]} | {r['violation']} |")
    L.append("")

    # type_acheteur
    L.append("## 2. Distribution `type_acheteur`\n")
    L.append("| type_acheteur | count | % |")
    L.append("|---|---:|---:|")
    for k in sorted(ta_dist):
        L.append(f"| {k} | {ta_dist[k]} | {ta_dist[k]/n*100:.1f}% |")
    L.append("")

    # fonction_publique
    L.append("## 3. Distribution `fonction_publique`\n")
    L.append("| fonction_publique | count | % |")
    L.append("|---|---:|---:|")
    for k in sorted(fp_dist):
        L.append(f"| {k} | {fp_dist[k]} | {fp_dist[k]/n*100:.1f}% |")
    L.append("")

    # Sources
    L.append("## 4. Sources de classification\n")
    for label, dist in [("type_acheteur_source", ta_src), ("fonction_publique_source", fp_src)]:
        L.append(f"### `{label}`\n")
        L.append("| source | count | % |")
        L.append("|---|---:|---:|")
        for k in sorted(dist):
            L.append(f"| {k} | {dist[k]} | {dist[k]/n*100:.1f}% |")
        L.append("")

    # Cas à surveiller
    L.append("## 5. Cas à surveiller\n")
    L.append(f'### `type_acheteur = "inconnu"` ({len(unknowns_ta)} ligne(s))\n')
    if not unknowns_ta:
        L.append("Aucune.\n")
    else:
        L.append("| reference | acheteur | fp | ta_source |")
        L.append("|---|---|---|---|")
        for u in unknowns_ta:
            L.append(f"| {u['reference']} | {u['acheteur'][:60]} | {u['fp']} | {u['ta_source']} |")
    L.append("")

    L.append(f'### `fonction_publique = "inconnue"` ({len(unknowns_fp)} ligne(s))\n')
    if not unknowns_fp:
        L.append("Aucune.\n")
    else:
        L.append("| reference | acheteur | ta | fp_source |")
        L.append("|---|---|---|---|")
        for u in unknowns_fp:
            L.append(f"| {u['reference']} | {u['acheteur'][:60]} | {u['ta']} | {u['fp_source']} |")
    L.append("")

    # Matrice croisée
    L.append("## 6. Matrice croisée type_acheteur × fonction_publique\n")
    all_fp = sorted({fp for counts in cross.values() for fp in counts})
    header = "| type_acheteur | " + " | ".join(all_fp) + " | Total |"
    sep = "|---|" + "|".join(["---:" for _ in all_fp]) + "|---:|"
    L.append(header)
    L.append(sep)
    grand = Counter()
    for ta_val in sorted(cross):
        cells = [str(cross[ta_val].get(fp, 0)) for fp in all_fp]
        total = sum(cross[ta_val].values())
        L.append(f"| {ta_val} | " + " | ".join(cells) + f" | {total} |")
        for fp in all_fp:
            grand[fp] += cross[ta_val].get(fp, 0)
    totals = [str(grand[fp]) for fp in all_fp]
    L.append(f"| **Total** | " + " | ".join(totals) + f" | {sum(grand.values())} |")
    L.append("")

    return "\n".join(L)


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATION (pour appel depuis le pipeline)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class BuyerClassificationConfig:
    """Configuration de la phase CLASSIFY_BUYERS."""
    enabled: bool = False
    run_llm: bool = False
    acheteur_db: Optional[AcheteurDB] = None
    output_csv: Optional[Path] = None
    report_path: Optional[Path] = None
    bad_csv_path: Optional[Path] = None
    overwrite: bool = True


def run_buyer_classification(
    consolidated_csv: Path,
    config: BuyerClassificationConfig,
) -> Dict[str, Any]:
    """Orchestrateur : règles → (LLM optionnel) → rapport QA.

    Args:
        consolidated_csv: CSV issu de la phase CONSOLIDATE (ou export brut).
        config:           Configuration de la classification.

    Returns:
        Dictionnaire de statistiques combinées.

    Raises:
        ClassificationInputError: CSV absent ou schéma invalide.
        FileExistsError: fichier de sortie existant et overwrite=False.
    """
    # Garde-fou LLM — run_llm est interdit en mode déterministe
    if config.run_llm:
        raise LLMDisabledError(
            "APPEL LLM INTERDIT — run_buyer_classification() avec run_llm=True est interdit. "
            "Politique LLM OFF. Pour réactiver : voir ao_etl/llm/backend.py (LLMDisabledError)."
        )

    consolidated_csv = Path(consolidated_csv)
    log.info("run_buyer_classification: entrée=%s", consolidated_csv)

    # Valider l'entrée une seule fois au niveau orchestrateur
    _validate_input_csv(consolidated_csv)

    # Noms canoniques dérivés du stem du fichier d'entrée
    base = consolidated_csv.parent
    stem = consolidated_csv.stem  # ex: "final-v3-consolidated"

    rule_csv = _resolve_output_path(base, CANONICAL_RULE_CSV, stem)
    final_csv = config.output_csv or _resolve_output_path(base, CANONICAL_CLASSIFIED_CSV, stem)
    report_md = config.report_path or _resolve_output_path(base, CANONICAL_REPORT_MD, stem)
    bad_csv = config.bad_csv_path or _resolve_output_path(base, CANONICAL_BAD_CSV, stem)

    ow = config.overwrite

    # Phase 8a : règles
    rule_stats = classify_buyers_rule_based(consolidated_csv, rule_csv, overwrite=ow)

    # Phase 8b : LLM désactivé — le CSV rules est directement le CSV final
    llm_stats: Dict[str, Any] = {}
    final_csv = rule_csv

    # Phase 8c : rapport QA (lit le CSV avec colonnes internes)
    qa = report_buyer_classification_quality(final_csv, report_md, bad_csv, overwrite=ow)

    # Phase 8d : nettoyage — normaliser fonction_publique + supprimer colonnes internes
    with open(final_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_fieldnames = list(reader.fieldnames)
        final_rows = list(reader)
    _normalize_fp_for_export(final_rows)
    clean_fieldnames = _strip_internal_columns(final_rows, raw_fieldnames)
    with open(final_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=clean_fieldnames)
        writer.writeheader()
        writer.writerows(final_rows)
    log.info("Colonnes internes retirées du CSV final : %s", sorted(_COLUMNS_TO_STRIP))

    log.info(
        "run_buyer_classification: terminé — %d lignes, %d anomalies vocab, CSV=%s",
        qa.total, qa.bad_count, final_csv,
    )

    return {
        "rule_stats": rule_stats,
        "llm_stats": llm_stats,
        "qa": {
            "total": qa.total,
            "bad_count": qa.bad_count,
            "unknowns_ta": len(qa.unknowns_ta),
            "unknowns_fp": len(qa.unknowns_fp),
        },
        "output_csv": str(final_csv),
        "report_path": str(report_md),
        "bad_csv": str(bad_csv) if qa.bad_count > 0 else None,
    }


def print_classification_summary(stats: Dict[str, Any]) -> None:
    """Affiche un résumé de la classification sur stdout."""
    print("\n" + "=" * 70)
    print("PHASE 8 : CLASSIFICATION DES ACHETEURS")
    print("=" * 70)
    rs = stats.get("rule_stats", {})
    ls = stats.get("llm_stats", {})
    qa = stats.get("qa", {})
    print(f"  Lignes totales           : {rs.get('total', '?')}")
    print(f"  type_acheteur par règles : {rs.get('ta_changed', 0)}")
    print(f"  fonction_publique règles : {rs.get('fp_changed', 0)}")
    if ls:
        print(f"  type_acheteur par LLM    : {ls.get('ta_llm', 0)}")
        print(f"  fonction_publique LLM    : {ls.get('fp_llm', 0)}")
        print(f"  Encore inconnus          : {ls.get('still_unknown', '?')}")
    print(f"  Violations vocabulaire   : {qa.get('bad_count', 0)}")
    print(f"  CSV final                : {stats.get('output_csv', '?')}")
    print(f"  Rapport QA               : {stats.get('report_path', '?')}")
