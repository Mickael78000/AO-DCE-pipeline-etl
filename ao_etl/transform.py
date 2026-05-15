"""
ao_etl/transform.py — Fusion, remapping legacy, nettoyage, annotations.
Applique les règles métier sur les données après extraction et matching.
N'a pas connaissance des fichiers HTML. Importe config et utils uniquement.
"""

import logging
import re
from pathlib import Path

from ao_etl.config import (
    AMBIGUOUS_RE, COLUMNS,
    _MARCHESONLINE_M_RE, _BAD_ESTIM_RE, _BAD_DUREE_RE, _BAD_RECON_RE,
)
from ao_etl.utils import normaliser_texte
from ao_etl import normalize

log = logging.getLogger(__name__)


# ── Gestion des triplets _auto / _manual / _final ────────────────────────────

# Mapping: nom base -> (colonne_auto, colonne_manual, colonne_finale)
TRIPLET_FIELDS = {
    "Acheteur": ("Acheteur_auto", "Acheteur_manual", "Acheteur"),
    "Localisation": ("Localisation_auto", "Localisation_manual", "Localisation"),
    "Date_limite": ("Date_limite_auto", "Date_limite_manual", "Date limite de remise des offres"),
    "Estimation": ("Estimation_auto", "Estimation_manual", "Estimation du marché"),
}


def apply_manual_overrides(row: dict) -> None:
    """
    Applique la règle: _final = _manual si non vide, sinon _auto.
    Met à jour les colonnes finales pour tous les triplets définis.
    """
    for auto_col, manual_col, final_col in TRIPLET_FIELDS.values():
        manual_val = row.get(manual_col, "").strip()
        auto_val = row.get(auto_col, "").strip()
        
        if manual_val:
            row[final_col] = manual_val
        elif auto_val:
            row[final_col] = auto_val
        else:
            row[final_col] = ""


def get_auto_column(field: str) -> str | None:
    """Retourne le nom de la colonne _auto correspondant à un champ, ou None."""
    for base, (auto, _, final) in TRIPLET_FIELDS.items():
        if field == final or field == base:
            return auto
    return None


def merge_into_row(row: dict, extracted: dict) -> tuple[dict, list[str]]:
    """
    Enrichit row avec les champs extraits.
    Écrit dans les colonnes *_auto pour les champs en triplet.
    Ne remplace une valeur existante que si elle est vide ou ambiguë.
    Ignore les champs internes (préfixe _).
    """
    changes = []
    for field, new_val in extracted.items():
        if field.startswith("_") or not new_val:
            continue
        
        # Déterminer la colonne cible (triplet _auto si applicable, sinon champ direct)
        target_field = get_auto_column(field) or field
        
        existing = row.get(target_field, "").strip()
        if not existing or AMBIGUOUS_RE.search(existing):
            if existing != new_val:
                row[target_field] = new_val
                changes.append(f"{target_field}={new_val[:50]}")
    return row, changes


def _nettoyer_localisation_existante(val: str) -> str:
    """Supprime l'artefact 'M (NN)' produit par l'ancienne extraction MarchesOnline."""
    val = normaliser_texte(val)
    m = _MARCHESONLINE_M_RE.match(val)
    if m:
        return f"{m.group(1).strip()} {m.group(2)}"
    return val


def remap_legacy_columns(row: dict) -> dict:
    """
    Adapte les anciens noms de colonnes au schéma cible et nettoie les valeurs héritées.
    Gère la migration vers le schéma triplet (_auto/_manual/_final).
    """
    new_row = {col: "" for col in COLUMNS}
    
    # Copier les colonnes existantes du nouveau schéma
    for col in COLUMNS:
        if col in row:
            new_row[col] = row[col]
    
    # Gestion du champ legacy "Source"
    if "Source" in row and not new_row.get("match_source"):
        new_row["match_source"] = row["Source"]

    # ── Migration vers schéma triplet ─────────────────────────────────────────
    # Si des colonnes _auto n'existent pas mais les colonnes finales existent (ancien schéma),
    # migrer les valeurs vers _auto (sauf si _manual existe déjà)
    
    # Acheteur: legacy "Acheteur" -> "Acheteur_auto"
    if not new_row.get("Acheteur_auto") and row.get("Acheteur"):
        if not new_row.get("Acheteur_manual"):  # Ne pas écraser si correction manuelle existe
            new_row["Acheteur_auto"] = row["Acheteur"]
    
    # Localisation: legacy "Localisation" -> "Localisation_auto"
    if not new_row.get("Localisation_auto") and row.get("Localisation"):
        if not new_row.get("Localisation_manual"):
            new_row["Localisation_auto"] = row["Localisation"]
    
    # Date limite: legacy "Date limite..." -> "Date_limite_auto"
    legacy_date = row.get("Date limite de remise des offres", "")
    if not new_row.get("Date_limite_auto") and legacy_date:
        if not new_row.get("Date_limite_manual"):
            new_row["Date_limite_auto"] = legacy_date
    
    # Estimation: legacy "Estimation du marché" -> "Estimation_auto"
    if not new_row.get("Estimation_auto") and row.get("Estimation du marché"):
        if not new_row.get("Estimation_manual"):
            new_row["Estimation_auto"] = row["Estimation du marché"]

    # Nettoyer les localisations avec artefact 'M (NN)'
    if new_row.get("Localisation"):
        new_row["Localisation"] = _nettoyer_localisation_existante(new_row["Localisation"])

    # Effacer les estimations héritées clairement erronées
    estim = new_row.get("Estimation du marché", "")
    if estim and _BAD_ESTIM_RE.match(estim.strip()):
        log.debug("Estimation héritée effacée : %r", estim)
        new_row["Estimation du marché"] = ""

    # Effacer les durées héritées aberrantes
    duree = new_row.get("Durée initiale du marché", "")
    if duree:
        md = _BAD_DUREE_RE.match(duree.strip())
        if md:
            v, unit = int(md.group(1)), md.group(2).lower()
            if (unit == "mois" and v > 120) or (unit == "an" and v > 15):
                log.debug("Durée héritée effacée : %r", duree)
                new_row["Durée initiale du marché"] = ""

    # Effacer les reconductions héritées invalides
    recon = new_row.get("Reconduction(s)", "")
    if recon:
        recon_s = recon.strip()
        if _BAD_RECON_RE.match(recon_s) or _BAD_RECON_RE.search(recon_s):
            log.debug("Reconduction héritée effacée : %r", recon)
            new_row["Reconduction(s)"] = ""
        elif re.match(
            r"^Nombre\s+max(?:imal)?\s+de\s+renouvellements?\s*$"
            r"|^Nombre\s+maximum\s+de\s+reconductions?\s*$",
            recon_s, re.IGNORECASE
        ):
            log.debug("Reconduction label seul effacé : %r", recon)
            new_row["Reconduction(s)"] = ""

    # Corriger les classifications Fonction publique erronées dans le CSV source
    acheteur_src = new_row.get("Acheteur", "")
    fp_src       = new_row.get("Fonction publique", "")
    if fp_src:
        if re.search(r"\bGCS\b|\bUNIHA\b|\bUniHA\b|\bGCS-UNIHA\b|\bUNIHA-GCS\b",
                     acheteur_src, re.IGNORECASE):
            new_row["Fonction publique"] = "Hospitalière"
        elif re.search(r"\bI\.?F\.?C\.?E\.?\b|\bInstitut [Ff]ran[cç]ais du [Cc]heval\b",
                       acheteur_src, re.IGNORECASE):
            new_row["Fonction publique"] = "Etat"
        elif re.search(r"\bCNAF\b|\bCNAM\b|\bCNAV\b", acheteur_src, re.IGNORECASE):
            new_row["Fonction publique"] = "Etat"

    duree_prev = row.get("Durée prévisionnelle", "")
    if duree_prev and not new_row.get("Durée initiale du marché"):
        m = re.search(r"(reconduct|renouvellement)", duree_prev, re.IGNORECASE)
        if m:
            new_row["Durée initiale du marché"] = normaliser_texte(duree_prev[:m.start()])
            new_row["Reconduction(s)"]           = normaliser_texte(duree_prev[m.start():])
        else:
            new_row["Durée initiale du marché"] = normaliser_texte(duree_prev)

    # ── Application de la règle manual/auto pour les valeurs finales ───────────
    apply_manual_overrides(new_row)

    # Normalisation Acheteur / Localisation
    # Utilise la valeur finale (après application de manual/auto)
    loc_source = new_row.get("Localisation", "")
    new_row["Acheteur_clean"]     = normalize.clean_acheteur(new_row.get("Acheteur", ""))
    new_row["Localisation_clean"] = normalize.clean_localisation(
        loc_source,
        new_row.get("Acheteur", ""),
    )

    return new_row


def update_match_metadata(row: dict, html_path: Path, changes: list[str]) -> None:
    """Met à jour match_status et match_source après un match réussi."""
    if changes:
        if row.get("match_status") in ("unmatched", "new", ""):
            row["match_status"] = "matched"
        row["match_source"] = html_path.name


def annotate_issues(row: dict) -> None:
    """Ajoute les notes d'extraction manquantes et positionne review_needed."""
    issues = []
    if not row.get("Type d'AO"):
        issues.append("Type d'AO non determine")
    if not row.get("Fonction publique"):
        issues.append("Fonction publique non determinee")
    if not row.get("Date limite de remise des offres"):
        issues.append("Date non extraite")
    notes = row.get("extraction_notes", "")
    for issue in issues:
        if issue not in notes:
            notes = (notes + "; " + issue).lstrip("; ")
    row["extraction_notes"] = notes
    row["review_needed"]    = "oui" if issues else ""


def build_new_row(extracted: dict, html_path: Path) -> "dict | None":
    """
    Construit une nouvelle ligne CSV depuis un fichier HTML non matché.
    Initialise les colonnes _auto avec les valeurs extraites.
    Retourne None si le record ne contient pas d'intitulé (non exploitable).
    """
    if not extracted.get("Intitulé synthétique"):
        return None
    new_row = {col: "" for col in COLUMNS}
    new_row["Référence"]        = extracted.get("Référence", "")
    new_row["match_source"]     = html_path.name
    new_row["match_status"]     = "new"
    
    # Mapping des champs extraits vers les colonnes _auto
    field_to_auto = {
        "Acheteur": "Acheteur_auto",
        "Localisation": "Localisation_auto",
        "Date limite de remise des offres": "Date_limite_auto",
        "Estimation du marché": "Estimation_auto",
    }
    
    for field, value in extracted.items():
        if field.startswith("_"):
            continue
        # Écrire dans la colonne _auto si c'est un champ triplet
        target = field_to_auto.get(field, field)
        if value:
            new_row[target] = value
    
    # Calculer les valeurs finales (manual vide pour nouvelle ligne -> final = auto)
    apply_manual_overrides(new_row)
    
    # Normalisations
    new_row["Acheteur_clean"] = normalize.clean_acheteur(new_row.get("Acheteur", ""))
    new_row["Localisation_clean"] = normalize.clean_localisation(
        new_row.get("Localisation", ""), new_row.get("Acheteur", "")
    )
    
    annotate_issues(new_row)
    return new_row
