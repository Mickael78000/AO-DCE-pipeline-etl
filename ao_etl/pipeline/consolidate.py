"""Phase 7 du pipeline : Consolidation LLM des champs métier.

Séquence canonique complète :
  DISCOVERY → RECONCILE → EXTRACT → MERGE → VALIDATE → EXPORT → [CONSOLIDATE]

La consolidation est optionnelle et désactivée par défaut. Elle est pilotée
par un objet ConsolidationConfig passé à run_pipeline().

Règles clés :
- Ne réécrit pas les champs déjà extraits de manière déterministe et correcte.
- Enrichit les champs vides ou ambigus (procedure, ccag, buyer_type, fpublique, cpv…).
- En cas d'échec LLM : marque la ligne pour revue manuelle, ne bloque pas le pipeline.
- Produit une vue CSV métier lisible (une colonne métier par information principale).

Variables d'environnement (selon backend) :
    AO_LLM_BACKEND    = openai | anthropic | ollama
    OPENAI_API_KEY    = sk-...
    ANTHROPIC_API_KEY = sk-ant-...
    AO_LLM_BASE_URL   = http://localhost:11434  (Ollama)
    AO_LLM_MODEL      = nom du modèle (optionnel)
"""

from __future__ import annotations

import csv
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ao_etl.llm.backend import LLMBackend, LLMDisabledError, build_backend
from ao_etl.models.consolidated import (
    ConsolidatedField,
    ConsolidatedRecord,
    ConsolidationControl,
    SourceTrace,
)

log = logging.getLogger(__name__)

_RETRY_DELAY_S = 2
_MAX_RETRIES = 2


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ConsolidationConfig:
    """Configuration de la phase 7 - consolidation LLM.

    Passée à run_pipeline() pour activer et paramétrer la consolidation.

    Exemple minimal :
        config = ConsolidationConfig(enabled=True)

    Exemple complet :
        config = ConsolidationConfig(
            enabled=True,
            backend="openai",
            model="gpt-4o-mini",
            limit=5,
            dry_run=True,
        )
    """
    enabled: bool = False
    backend: str = ""
    model: str = ""
    api_key: str = ""
    limit: Optional[int] = None
    dry_run: bool = False
    delay_between_rows: float = 0.5
    json_dir: Optional[Path] = None
    output_csv: Optional[Path] = None

    def build_backend(self) -> LLMBackend:
        return build_backend(
            backend=self.backend or None,
            model=self.model or None,
            api_key=self.api_key or None,
        )


# =============================================================================
# Champs déterministes : ne pas écraser si déjà fiables
# =============================================================================

def _deterministic_value(row: dict, key: str) -> Optional[str]:
    """Retourne la valeur CSV si elle est non-vide et non-générique."""
    val = row.get(key, "")
    if not val or val in ("-", "None", "none", ""):
        return None
    return val.strip()


# Mapping pour le post-traitement Python pur :
# (clés CSV alternatives multiples, attribut record, justification source)
_DETERMINISTIC_PRESERVE = [
    # (liste de clés CSV à tester en ordre, attribut ConsolidatedRecord)
    (("Acheteur_auto", "Acheteur_clean", "Acheteur_manual"),          "buyer_final"),
    (("Localisation_auto", "Localisation_clean", "Localisation_manual", "Localisation"), "location_final"),
    (("Date_limite_auto", "Date_limite_manual", "Date limite de remise des offres"),      "deadline_final"),
    (("Estimation_auto", "Estimation_manual", "Estimation du marché"),                   "estimated_amount"),
    (("Intitulé synthétique",),                                                           "title"),
    (("Référence",),                                                                      "reference"),
    (("URL source HTTPS",),                                                               "source_url_field"),  # géré séparément
]


def _apply_deterministic_fields(
    row: dict,
    record: ConsolidatedRecord,
) -> None:
    """Préserve les champs CSV déjà fiables.

    Règle : si le champ LLM est 'missing' ou sans valeur, on injecte
    la valeur CSV avec status='found' et confidence='high'.
    On ne remplace JAMAIS un champ LLM déjà 'found'.
    """
    mappings = [
        (("Acheteur_auto", "Acheteur_clean", "Acheteur_manual"),           "buyer_final"),
        (("Localisation_auto", "Localisation_clean",
          "Localisation_manual", "Localisation"),                          "location_final"),
        (("Date_limite_auto", "Date_limite_manual",
          "Date limite de remise des offres"),                             "deadline_final"),
        (("Estimation_auto", "Estimation_manual", "Estimation du marché"), "estimated_amount"),
        (("Intitulé synthétique",),                                        "title"),
    ]
    for csv_keys, record_attr in mappings:
        csv_val: Optional[str] = None
        csv_key_used = ""
        for k in csv_keys:
            v = _deterministic_value(row, k)
            if v:
                csv_val = v
                csv_key_used = k
                break
        if csv_val is None:
            continue
        llm_field: ConsolidatedField = getattr(record, record_attr)
        if llm_field.status == "missing" or llm_field.value is None:
            setattr(record, record_attr, ConsolidatedField(
                value=csv_val,
                status="found",
                confidence="high",
                justification=f"Préservé depuis extraction déterministe ({csv_key_used})",
            ))


# ---------------------------------------------------------------------------
# Post-traitement Python pur : inférence des champs sans LLM
# ---------------------------------------------------------------------------

_BUYER_TYPE_RULES: List[tuple] = [
    # (patterns titre/acheteur, buyer_type)
    (r"minist[eè]re|direction\s+g[eé]n[eé]rale|d[eé]l[eé]gation|pr[eé]fecture|"
     r"anssi|dinsic|dgfip|dnum|dsi|daf|secretariat\s+d['\'']etat|igf|igpde|"
     r"aife|chorus|sio|ssi|anssi", "etat"),
    (r"r[eé]gion|d[eé]partement|commune|m[eé]tropole|epci|agglom[eé]ration|"
     r"mairie|ville\s+de|conseil\s+(?:d[eé]partemental|r[eé]gional)|"
     r"syndicat\s+(?:mixte|intercommunal)|communaut[eé]\s+(?:de\s+communes|"
     r"agglom[eé]ration|urbaine)", "collectivite_territoriale"),
    (r"\bchu\b|\bchr\b|\bght\b|\bchru\b|\bchp\b|ehpad|ars\b|h.pital|hopital|"
     r"centre\s+hospitalier|groupement\s+hospitalier|ap.hp|ap.hm",
     "hopital"),
    (r"universit[eé]|rectorat|cnrs|inrae|inria|ifremer|inserm|cea\b|cirad|"
     r"\bepa\b|\bepic\b|\bopa\b|[eé]tablissement\s+public|agence\s+(?:nationale|"
     r"r[eé]gionale|de\s+(?:l|la)|du)", "etablissement_public"),
    (r"ugap|resah|caih|centrale\s+d['\'']achat|groupement\s+d['\'']achat|"
     r"centrale\s+d.achat", "groupement_achat"),
    (r"\bedf\b|\bsncf\b|\bratp\b|la\s+poste|franceagrimer|france\s+agri|"
     r"enedis|grdf|rte\b|bnf|ina\b|france\s+t[eé]l[eé]vision", "entreprise_publique"),
]

_PROCEDURE_RULES: List[tuple] = [
    (r"proc.dure.adapt.e|\bmapa\b", "mapa"),
    (r"appel.d.offres?.ouvert|\baoo\b|proc.dure.ouverte", "appel_offres_ouvert"),
    (r"appel.d.offres?.restreint|\baor\b|proc.dure.restreinte", "appel_offres_restreint"),
    (r"proc.dure.n.goci.e|march..n.goci.", "procedure_negociee"),
    (r"accord.cadre", "accord_cadre"),
    (r"march..subs.quent|bons?.de.commande", "marche_subsequent"),
    (r"dialogue.comp.titif", "dialogue_competitif"),
    (r"proc.dure.formalis.e", "appel_offres_ouvert"),
]

_NATURE_RULES: List[tuple] = [
    (r"\bsi\b|syst.me.information|infog.rance|h.bergement|cloud|"
     r"cyberse.curit.|maintenance.(?:applicative|logicielle|correctrice)|"
     r"d.veloppement.(?:logiciel|applicatif)|workplace|amoa|amoe|"
     r"conseil|formation|audit|assistance.+ma.trise",
     "services"),
    (r"serveurs?|mat.riels?|.quipements?|postes?.(?:de.travail|informatique)|"
     r"stockage|baie|r.seau|switch|routeur|licences?",
     "fournitures"),
    (r"travaux|construction|r.novation|btp|g.nie.civil|voirie|b.timent|r.habilitation",
     "travaux"),
]

_CCAG_RULES: List[tuple] = [
    (r"\bsi\b|syst.me.information|infog.rance|h.bergement|cloud|"
     r"maintenance.applicative|workplace|\btic\b", "tic"),
    (r"amoa|amoe|assistance.+ma.trise|prestations?.intellectuelles|"
     r".tudes?|conseil|audit.(?:fonctionnel|organisationnel)", "prestations_intellectuelles"),
    (r"fournitures?.courantes?|mat.riels?|.quipements?|stockage",
     "fournitures_courantes_services"),
    (r"travaux|construction|r.novation|btp", "travaux"),
    (r"ma.trise.d..uvre|\bmoe\b", "moe"),
]


def _match_rules(text: str, rules: List[tuple]) -> Optional[str]:
    """Applique la première règle regex qui correspond au texte."""
    if not text:
        return None
    text_lower = text.lower()
    for pattern, value in rules:
        if re.search(pattern, text_lower):
            return value
    return None


def _infer_fields_from_hints(
    row: dict,
    record: ConsolidatedRecord,
    html_signals: Optional[dict] = None,
) -> None:
    """Post-traitement Python pur : infère les champs encore 'missing' depuis
    les indices CSV et HTML déjà disponibles, sans appel LLM.

    Appliqué APRÈS _apply_deterministic_fields et le LLM.
    Ne remplace jamais un champ déjà 'found' ou 'inferred'.
    """
    if html_signals is None:
        html_signals = {}

    # Texte combiné pour les inférences (titre + acheteur + HTML procedure/nature)
    title = record.title.value or _v(row, "Intitulé synthétique") or ""
    buyer = record.buyer_final.value or _v(row, "Acheteur_auto", "Acheteur_clean") or ""
    html_proc = html_signals.get("procedure", "")
    html_nat = html_signals.get("nature", "")
    html_ccag = html_signals.get("ccag", "")
    combined = " ".join([title, buyer, html_proc, html_nat]).strip()

    # ── buyer_type ──
    if record.buyer_type.status == "missing" and buyer:
        bt = _match_rules(buyer + " " + title, _BUYER_TYPE_RULES)
        if bt:
            record.buyer_type = ConsolidatedField(
                value=bt, status="inferred", confidence="medium",
                justification=f"Inféré depuis nom acheteur : {buyer[:60]}",
            )
        else:
            record.buyer_type = ConsolidatedField(
                value="inconnu", status="inferred", confidence="low",
                justification="Aucune règle ne correspond au nom de l'acheteur",
            )

    # ── fonction_publique : déduite de buyer_type ──
    if record.fonction_publique.status == "missing":
        fp_csv = _v(row, "Fonction publique")
        if fp_csv and fp_csv not in ("-", "None"):
            record.fonction_publique = ConsolidatedField(
                value=fp_csv, status="found", confidence="high",
                justification="Présent dans colonne 'Fonction publique' du CSV",
            )
        elif record.buyer_type.value:
            _fp_map = {
                "etat": "etat",
                "etablissement_public": "etat",
                "collectivite_territoriale": "territoriale",
                "hopital": "hospitaliere",
                "entreprise_publique": "etat",
                "groupement_achat": "etat",
                "organisme_prive_mission_publique": "inconnue",
                "autre": "inconnue",
                "inconnu": "inconnue",
            }
            fp = _fp_map.get(record.buyer_type.value, "inconnue")
            record.fonction_publique = ConsolidatedField(
                value=fp, status="inferred", confidence="medium",
                justification=f"Déduit depuis buyer_type={record.buyer_type.value}",
            )

    # ── procedure_family ──
    if record.procedure_family.status == "missing":
        proc_text = html_proc + " " + _v(row, "Type d'AO")
        pf = _match_rules(proc_text, _PROCEDURE_RULES)
        if pf:
            is_found = bool(html_proc)  # found si extrait du HTML, inferred si CSV
            record.procedure_family = ConsolidatedField(
                value=pf,
                status="found" if is_found else "inferred",
                confidence="high" if is_found else "medium",
                justification=f"Détecté dans signal HTML procédure : {html_proc[:80]}" if html_proc
                              else f"Inféré depuis csv_type_ao : {_v(row, 'Type d\'AO')}",
            )

    # ── formalisation_type : déduite de procedure_family ──
    if record.formalisation_type.status == "missing" and record.procedure_family.value:
        _formal_map = {
            "mapa": "adapte",
            "appel_offres_ouvert": "formalise",
            "appel_offres_restreint": "formalise",
            "procedure_negociee": "formalise",
            "dialogue_competitif": "formalise",
            "accord_cadre": "formalise",
            "marche_subsequent": "formalise",
            "concours": "formalise",
            "sans_objet": "inconnu",
            "inconnue": "inconnu",
        }
        ft = _formal_map.get(record.procedure_family.value, "inconnu")
        src = "procédure formalisée détectée dans HTML" if "formalis" in html_proc.lower() \
              else f"déduit depuis procedure_family={record.procedure_family.value}"
        record.formalisation_type = ConsolidatedField(
            value=ft, status="inferred", confidence="medium",
            justification=src,
        )

    # ── contract_nature ──
    if record.contract_nature.status == "missing":
        nat_text = title + " " + html_nat + " " + combined
        cn = _match_rules(nat_text, _NATURE_RULES)
        if cn:
            is_html = bool(html_nat)
            record.contract_nature = ConsolidatedField(
                value=cn,
                status="found" if is_html else "inferred",
                confidence="high" if is_html else "medium",
                justification=f"Extrait de html_nature : {html_nat[:60]}" if is_html
                              else f"Inféré depuis titre : {title[:60]}",
            )

    # ── ccag_type ──
    if record.ccag_type.status == "missing":
        ccag_text = html_ccag + " " + title + " " + html_nat
        ct = _match_rules(ccag_text, _CCAG_RULES)
        if ct:
            record.ccag_type = ConsolidatedField(
                value=ct,
                status="found" if html_ccag else "inferred",
                confidence="high" if html_ccag else "medium",
                justification=f"Extrait de html_ccag : {html_ccag[:60]}" if html_ccag
                              else f"Inféré depuis titre/nature : {title[:60]}",
            )

    # ── CPV depuis HTML si encore missing ──
    if record.cpv_main.status == "missing":
        cpv_codes_str = html_signals.get("cpv_codes", "")
        if cpv_codes_str:
            codes = [c.strip() for c in cpv_codes_str.split(",") if c.strip()]
            if codes:
                record.cpv_main = ConsolidatedField(
                    value=codes[0], status="found", confidence="high",
                    justification=f"Code CPV extrait du HTML source",
                )
                record.cpv_list = ConsolidatedField(
                    value=codes, status="found", confidence="high",
                    justification=f"{len(codes)} CPV extraits du HTML",
                )

    # ── Recalcul manual_review_required ──
    flags = record.control.quality_flags[:]
    reasons = record.control.review_reasons[:]
    needs_review = record.control.manual_review_required
    if record.buyer_final.status == "missing":
        needs_review = True
        if "missing_buyer" not in flags:
            flags.append("missing_buyer")
            reasons.append("Acheteur non déterminable")
    if record.deadline_final.status == "missing":
        if "missing_deadline" not in flags:
            flags.append("missing_deadline")
    if record.procedure_family.status == "missing" or record.procedure_family.value == "inconnue":
        if "missing_procedure" not in flags:
            flags.append("missing_procedure")
    record.control = ConsolidationControl(
        manual_review_required=needs_review,
        review_reasons=reasons,
        quality_flags=flags,
    )


# =============================================================================
# Parsing réponse LLM
# =============================================================================

def _parse_llm_response(data: dict, source_file: str) -> ConsolidatedRecord:
    """Convertit le dict JSON retourné par le LLM en ConsolidatedRecord."""

    def _field(raw: dict) -> ConsolidatedField:
        if not isinstance(raw, dict):
            return ConsolidatedField.missing("Champ absent ou malformé dans la réponse LLM")
        return ConsolidatedField(
            value=raw.get("value"),
            status=raw.get("status", "missing"),
            confidence=raw.get("confidence", "low"),
            justification=raw.get("justification", ""),
        )

    trace_raw = data.get("source_trace", {})
    trace = SourceTrace(
        source_file=trace_raw.get("source_file") or source_file,
        source_platform=trace_raw.get("source_platform", "UNKNOWN"),
        source_url=trace_raw.get("source_url"),
        input_reference=trace_raw.get("input_reference"),
    )

    ctrl_raw = data.get("control", {})
    control = ConsolidationControl(
        manual_review_required=bool(ctrl_raw.get("manual_review_required", False)),
        review_reasons=list(ctrl_raw.get("review_reasons", [])),
        quality_flags=list(ctrl_raw.get("quality_flags", [])),
    )

    ff = data.get("final_fields", {})
    return ConsolidatedRecord(
        record_id=data.get("record_id", ""),
        source_trace=trace,
        reference=_field(ff.get("reference", {})),
        title=_field(ff.get("title", {})),
        buyer_final=_field(ff.get("buyer_final", {})),
        buyer_type=_field(ff.get("buyer_type", {})),
        fonction_publique=_field(ff.get("fonction_publique", {})),
        fonction_publique_detail=_field(ff.get("fonction_publique_detail", {})),
        procedure_label=_field(ff.get("procedure_label", {})),
        procedure_family=_field(ff.get("procedure_family", {})),
        formalisation_type=_field(ff.get("formalisation_type", {})),
        contract_nature=_field(ff.get("contract_nature", {})),
        ccag_type=_field(ff.get("ccag_type", {})),
        cpv_main=_field(ff.get("cpv_main", {})),
        cpv_list=_field(ff.get("cpv_list", {})),
        location_final=_field(ff.get("location_final", {})),
        deadline_final=_field(ff.get("deadline_final", {})),
        duration_initial=_field(ff.get("duration_initial", {})),
        renewals=_field(ff.get("renewals", {})),
        estimated_amount=_field(ff.get("estimated_amount", {})),
        control=control,
    )


def _make_error_record(row: dict, source_file: str, error: Exception) -> ConsolidatedRecord:
    """Crée un enregistrement d'erreur sans valeur inventée."""
    ref = row.get("Référence", source_file)
    return ConsolidatedRecord(
        record_id=ref,
        source_trace=SourceTrace(
            source_file=source_file,
            source_platform=row.get("source_type", "UNKNOWN"),
            source_url=_deterministic_value(row, "URL source HTTPS"),
            input_reference=ref,
        ),
        control=ConsolidationControl(
            manual_review_required=True,
            review_reasons=[f"Erreur LLM: {error}"],
            quality_flags=["llm_error"],
        ),
    )


# =============================================================================
# Appel LLM par ligne
# =============================================================================

def _load_html(source_file: str, html_dir: Path) -> Optional[str]:
    path = html_dir / source_file
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    candidates = list(html_dir.glob(f"*{Path(source_file).stem}*"))
    if candidates:
        return candidates[0].read_text(encoding="utf-8", errors="ignore")
    return None


# =============================================================================
# Construction d'URL de marché
# =============================================================================

_PLACE_NUMERIC_RE = re.compile(r'^(\d+\?orgAcronyme=[a-z0-9]+)\.html$', re.IGNORECASE)
_PLACE_NUMERIC_ALT_RE = re.compile(r'^(\d+)-orgAcronyme-([a-z0-9]+)\.html$', re.IGNORECASE)
_CANONICAL_RE = re.compile(r'<link[^>]+rel=\s*["\']canonical["\'][^>]+href=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def _extract_canonical_url(html_content: Optional[str]) -> Optional[str]:
    """Extrait l'URL canonique depuis la balise <link rel="canonical"> du HTML."""
    if not html_content:
        return None
    m = _CANONICAL_RE.search(html_content)
    if m:
        url = m.group(1).strip()
        # Vérifier que c'est une URL absolue valide
        if url.startswith("http://") or url.startswith("https://"):
            return url
    return None


def _is_reliable_url(url: Optional[str]) -> bool:
    """Vérifie si une URL est complète et fiable."""
    if not url:
        return False
    if url in ("-", "None", "none", ""):
        return False
    return url.startswith("http://") or url.startswith("https://")


def build_market_url(
    source_file: str,
    source_platform: str,
    source_url: Optional[str] = None,
    html_content: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """Construit l'URL publique canonique du marché de façon déterministe.

    Returns:
        Tuple (url, source_type) où source_type indique la provenance :
        - 'source_url' : URL fiable fournie en entrée
        - 'canonical' : URL extraite de la balise <link rel="canonical">
        - 'fallback_francemarches' : URL reconstruite pour France Marchés
        - 'fallback_place' : URL reconstruite pour PLACE
        - '' : URL non déterminée

    Priorité générale :
    1. Si source_url existe et est une URL complète fiable → l'utiliser
    2. Sinon, si le HTML source est disponible → chercher <link rel="canonical" href="...">
    3. Sinon, appliquer un fallback déterministe spécifique à la plateforme
    4. Sinon, retourner (None, '') (le caller ajoutera missing_market_url à quality_flags)

    Règles par plateforme :

    FRANCE_MARCHES:
    - Chercher d'abord la balise canonical dans le HTML
    - Si absente, fallback sûr : retirer .html du source_file, préfixer avec
      https://www.francemarches.com/appel-offre/

    MARCHES_ONLINE:
    - Ne jamais reconstruire l'URL à partir du seul nom de fichier ao-XXXXXXX-1.html
    - Si source_url existe et est fiable → l'utiliser
    - Sinon, si le HTML contient une balise canonical → utiliser cette valeur
    - Sinon retourner (None, '')

    PLACE_NUMERIC:
    - Si source_url existe et est fiable → l'utiliser
    - Sinon, si le HTML contient une canonical → l'utiliser
    - Sinon fallback par pattern sur source_file :
      * 2956468-orgAcronyme-g7h.html ou 2956468?orgAcronyme=g7h.html
      * devient https://www.marches-publics.gouv.fr/app.php/entreprise/consultation/2956468?orgAcronyme=g7h

    BOAMP_XML:
    - Si source_url existe et est fiable → l'utiliser
    - Sinon, si le HTML contient une canonical ou une URL publique explicite → l'utiliser
    - Sinon retourner (None, '')
    """
    sf = (source_file or "").strip()
    platform = (source_platform or "").upper()
    existing = (source_url or "").strip()

    # Normalise les valeurs vides/génériques héritées du CSV
    if existing in ("-", "None", "none"):
        existing = ""

    # Extraction canonique du HTML (si disponible)
    canonical_url = _extract_canonical_url(html_content)

    # ── FRANCE_MARCHES ──
    if platform == "FRANCE_MARCHES":
        # 1. source_url fiable ?
        if _is_reliable_url(existing):
            return existing, "source_url"
        # 2. canonical dans HTML ?
        if canonical_url:
            return canonical_url, "canonical"
        # 3. Fallback sûr : retirer .html et préfixer
        if sf.endswith(".html"):
            slug = sf[:-5]
            return f"https://www.francemarches.com/appel-offre/{slug}", "fallback_francemarches"
        return None, ""

    # ── MARCHES_ONLINE ──
    if platform == "MARCHES_ONLINE":
        # 1. source_url fiable ?
        if _is_reliable_url(existing):
            return existing, "source_url"
        # 2. canonical dans HTML ? (ex: ao-9597894-1.html contient le slug titre)
        if canonical_url:
            return canonical_url, "canonical"
        # 3. Ne jamais reconstruire à partir du nom de fichier seul
        return None, ""

    # ── PLACE_NUMERIC ──
    if platform == "PLACE_NUMERIC":
        # 1. source_url fiable ?
        if _is_reliable_url(existing):
            return existing, "source_url"
        # 2. canonical dans HTML ?
        if canonical_url:
            return canonical_url, "canonical"
        # 3. Fallback par pattern sur source_file
        # Pattern 1: 2956468?orgAcronyme=g7h.html
        m = _PLACE_NUMERIC_RE.match(sf)
        if m:
            query_part = m.group(1)
            return (
                f"https://www.marches-publics.gouv.fr/"
                f"app.php/entreprise/consultation/{query_part}"
            ), "fallback_place"
        # Pattern 2: 2956468-orgAcronyme-g7h.html
        m = _PLACE_NUMERIC_ALT_RE.match(sf)
        if m:
            id_part = m.group(1)
            org_part = m.group(2)
            return (
                f"https://www.marches-publics.gouv.fr/"
                f"app.php/entreprise/consultation/{id_part}?orgAcronyme={org_part}"
            ), "fallback_place"
        return None, ""

    # ── BOAMP_XML ──
    if platform == "BOAMP_XML":
        # 1. source_url fiable ?
        if _is_reliable_url(existing):
            return existing, "source_url"
        # 2. canonical dans HTML ou URL publique explicite ?
        if canonical_url:
            return canonical_url, "canonical"
        # 3. Fallback BOAMP: construire depuis le nom de fichier si pattern boamp
        if "boamp" in sf.lower():
            # Extraire l'ID du nom de fichier
            import re
            m = re.search(r'(\d+)', sf)
            if m:
                boamp_id = m.group(1)
                return f"https://www.boamp.fr/avis/detail/{boamp_id}", "fallback_boamp"
        return None, ""
    
    # ── JOUE ──
    if platform == "JOUE":
        # 1. source_url fiable ?
        if _is_reliable_url(existing):
            return existing, "source_url"
        # 2. canonical dans HTML ?
        if canonical_url:
            return canonical_url, "canonical"
        # 3. Fallback JOUE/TED: construire depuis le nom de fichier
        # Pattern: 13joueXXXXXXXX-YYYY-...
        import re
        m = re.match(r"13joue(\d{8,12})", sf, re.I)
        if m:
            numero = m.group(1)
            # Format TED: 2026/S 123-456789
            if len(numero) >= 10:
                annee = numero[:2] if numero.startswith('20') else numero[2:4]
                return f"https://ted.europa.eu/udl?uri=TED:NOTICE:{numero}-20{annee}:TEXT:FR", "fallback_joue"
        return None, ""

    # ── Plateformes non reconnues : source_url si fiable, sinon None ──
    if _is_reliable_url(existing):
        return existing, "source_url"
    return None, ""


def _consolidate_row(
    row: dict,
    html_dir: Path,
    backend: LLMBackend,
    system_prompt: str = "",
    dry_run: bool = False,
) -> ConsolidatedRecord:
    """Consolide une ligne CSV via le LLM + post-traitement Python.

    Séquence :
    1. Chargement HTML
    2. Si dry_run → record vide avec champs déterministes + inférence Python
    3. Sinon → LLM → parse → _apply_deterministic_fields → _infer_fields_from_hints
    4. Sur erreur LLM → record d'erreur + _apply_deterministic_fields + _infer_fields_from_hints
    """
    source_file = row.get("match_source", "") or row.get("Référence", "unknown")
    html_content = _load_html(source_file, html_dir)

    if not html_content:
        log.warning("HTML non trouvé pour %s", source_file)

    html_signals = extract_html_signals(html_content)

    platform = row.get("source_type", "") or ""
    existing_url = _deterministic_value(row, "URL source HTTPS")
    market_url, url_source_type = build_market_url(
        source_file, platform, source_url=existing_url, html_content=html_content
    )

    # Mettre à jour la row avec l'URL calculée pour que build_resolved_hints l'utilise
    if market_url and (not existing_url or existing_url == "-"):
        row["URL source HTTPS"] = market_url
        existing_url = market_url
    
    # Scraper l'URL pour enrichir les données si nécessaire (données manquantes)
    try:
        from ao_etl.scraper.url_scraper import enrich_row_with_url_content
        row = enrich_row_with_url_content(row)
        if row.get("_url_scraped_content"):
            log.info("Row enrichie avec contenu URL scrappé: %s", source_file)
    except Exception as e:
        log.debug("Scraping URL non disponible: %s", e)

    def _attach_market_url(rec: ConsolidatedRecord, url_src: str = "") -> None:
        """Injecte market_url dans source_trace et trace sa provenance.

        Args:
            url_src: Type de source de l'URL pour traçabilité
                     ('source_url', 'canonical', 'fallback_francemarches', 'fallback_place', '')
        """
        rec.source_trace.source_url = market_url or rec.source_trace.source_url
        flags = rec.control.quality_flags

        if not rec.source_trace.source_url:
            if "missing_market_url" not in flags:
                flags.append("missing_market_url")
        else:
            # Tracer la provenance de l'URL si elle a été construite
            if url_src == "source_url" and "url_from_source" not in flags:
                flags.append("url_from_source")
            elif url_src == "canonical" and "url_from_canonical" not in flags:
                flags.append("url_from_canonical")
            elif url_src == "fallback_francemarches" and "url_fallback_francemarches" not in flags:
                flags.append("url_fallback_francemarches")
            elif url_src == "fallback_place" and "url_fallback_place" not in flags:
                flags.append("url_fallback_place")

    if dry_run:
        ref = row.get("Référence", source_file)
        log.info("DRY-RUN: simulation consolidation pour %s", ref)
        record = ConsolidatedRecord(
            record_id=ref,
            source_trace=SourceTrace(
                source_file=source_file,
                source_platform=platform or "UNKNOWN",
                source_url=market_url,
                input_reference=ref,
            ),
            control=ConsolidationControl(
                manual_review_required=False,
                review_reasons=[],
                quality_flags=["dry_run"],
            ),
        )
        _apply_deterministic_fields(row, record)
        _infer_fields_from_hints(row, record, html_signals)
        _attach_market_url(record, url_source_type)
        return record

    # GARDE-FOU LLM — aucun appel modèle autorisé
    raise LLMDisabledError(
        "APPEL LLM INTERDIT — _consolidate_row() ne peut pas appeler le backend. "
        "Pipeline en mode déterministe. Pour réactiver : voir ao_etl/llm/backend.py."
    )


# =============================================================================
# Orchestration principale
# =============================================================================

def run_consolidation(
    input_csv: Path,
    html_dir: Path,
    output_csv: Path,
    config: ConsolidationConfig,
    json_dir: Optional[Path] = None,
) -> Dict:
    """Lance la consolidation LLM (phase 7) sur toutes les lignes du CSV stabilisé.

    Args:
        input_csv:  Chemin vers final-v2-stabilise.csv (sortie phase 6).
        html_dir:   Répertoire des fichiers HTML source.
        output_csv: Chemin de sortie du CSV consolidé métier (v3).
        config:     ConsolidationConfig avec paramètres backend et options.
        json_dir:   Répertoire de sortie des JSONs individuels (optionnel).

    Returns:
        Dictionnaire de statistiques {total, ok, error, review, skipped}.
    """
    if not config.enabled:
        log.info("Phase 7 désactivée (config.enabled=False)")
        return {"total": 0, "ok": 0, "error": 0, "review": 0, "skipped": 0}

    if not config.dry_run:
        raise LLMDisabledError(
            "APPEL LLM INTERDIT — run_consolidation() nécessite un backend LLM. "
            "Pipeline en mode déterministe. Utilisez dry_run=True ou désactivez "
            "la phase 7 (config.enabled=False). "
            "Pour réactiver : voir ao_etl/llm/backend.py (LLMDisabledError)."
        )
    backend = None  # non utilisé en dry_run
    system_prompt = ""  # non utilisé en mode déterministe

    with open(input_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if config.limit:
        rows = rows[:config.limit]
        log.info("Consolidation limitée aux %d premières lignes", config.limit)

    if json_dir:
        json_dir.mkdir(parents=True, exist_ok=True)

    records: List[ConsolidatedRecord] = []
    stats: Dict = {"total": len(rows), "ok": 0, "error": 0, "review": 0, "skipped": 0}

    for i, row in enumerate(rows, 1):
        ref = row.get("Référence", f"row_{i}")
        log.info("[%d/%d] Consolidation: %s", i, len(rows), ref)

        record = _consolidate_row(
            row=row,
            html_dir=html_dir,
            backend=backend,
            system_prompt=system_prompt,
            dry_run=config.dry_run,
        )
        records.append(record)

        if "llm_error" in record.control.quality_flags:
            stats["error"] += 1
        elif "dry_run" in record.control.quality_flags:
            stats["skipped"] += 1
        else:
            stats["ok"] += 1

        if record.control.manual_review_required:
            stats["review"] += 1

        if json_dir:
            safe_ref = ref.replace("/", "_").replace(" ", "_")
            json_path = json_dir / f"{safe_ref}.json"
            json_path.write_text(
                json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        if i < len(rows) and not config.dry_run:
            time.sleep(config.delay_between_rows)

    _write_consolidated_csv(records, output_csv)

    log.info(
        "Phase 7 terminée: %d OK, %d dry-run, %d erreurs, %d à revoir",
        stats["ok"], stats["skipped"], stats["error"], stats["review"],
    )
    return stats


def print_consolidation_summary(stats: dict) -> None:
    sep = "-" * 60
    print(f"\n[CONSOLIDATE] Phase 7 - Consolidation LLM")
    print(sep)
    print(f"  Total lignes        : {stats['total']}")
    if stats.get('skipped'):
        print(f"  Dry-run (simulés)   : {stats['skipped']}")
    else:
        print(f"  OK                  : {stats['ok']}")
    print(f"  Erreurs LLM         : {stats['error']}")
    print(f"  Revue manuelle req. : {stats['review']}")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Phase 7 - Consolidation LLM (usage autonome)"
    )
    parser.add_argument("--input", required=True, help="CSV stabilisé v2")
    parser.add_argument("--html-dir", required=True, help="Répertoire HTML source")
    parser.add_argument("--output", required=True, help="CSV consolidé v3 (métier)")
    parser.add_argument("--json-dir", default=None, help="Répertoire JSONs individuels")
    parser.add_argument("--backend", default="", help="LLM backend: openai|anthropic|ollama")
    parser.add_argument("--model", default="", help="Nom du modèle LLM")
    parser.add_argument("--limit", type=int, default=None, help="Limiter à N lignes")
    parser.add_argument("--delay", type=float, default=0.5, help="Délai entre appels (s)")
    parser.add_argument("--dry-run", action="store_true", help="Simulation sans appel LLM")
    args = parser.parse_args()

    cfg = ConsolidationConfig(
        enabled=True,
        backend=args.backend,
        model=args.model,
        limit=args.limit,
        dry_run=args.dry_run,
        delay_between_rows=args.delay,
    )

    stats = run_consolidation(
        input_csv=Path(args.input),
        html_dir=Path(args.html_dir),
        output_csv=Path(args.output),
        config=cfg,
        json_dir=Path(args.json_dir) if args.json_dir else None,
    )
    print_consolidation_summary(stats)
