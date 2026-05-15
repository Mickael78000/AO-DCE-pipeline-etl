"""
ao_etl/config.py — Constantes, chemins et regex globales.
Importé par tous les modules ; n'importe rien d'interne au package.
"""

import re
from pathlib import Path

# ── Chemins ───────────────────────────────────────────────────────────────────

WORKDIR    = Path("/home/michka/Documents/0-AO-DCE")

# Chemins legacy (conservés pour compatibilité transitoire)
HTML_DIR_LEGACY   = WORKDIR / "html_ao"
INPUT_CSV_LEGACY  = WORKDIR / "AO-completed.csv"
OUTPUT_CSV_LEGACY = WORKDIR / "AO-completed.csv"

# Chemins cible (nouvelle structure)
HTML_DIR_TARGET   = WORKDIR / "data" / "raw" / "html"
INPUT_CSV_TARGET  = WORKDIR / "data" / "input" / "AO-completed.csv"
OUTPUT_CSV_TARGET = WORKDIR / "data" / "output" / "AO-pipeline-v2.csv"
REPORTS_DIR       = WORKDIR / "reports"

# Chemins actifs (auto-détection avec fallback legacy)
def _get_path(target: Path, legacy: Path) -> Path:
    """Retourne le chemin cible s'il existe, sinon le legacy."""
    return target if target.exists() else legacy

HTML_DIR   = _get_path(HTML_DIR_TARGET, HTML_DIR_LEGACY)
INPUT_CSV  = _get_path(INPUT_CSV_TARGET, INPUT_CSV_LEGACY)
OUTPUT_CSV = _get_path(OUTPUT_CSV_TARGET, OUTPUT_CSV_LEGACY)

# Rapport d'extraction
REPORT_MD  = WORKDIR / "rapport-extraction.md"

# ── Schéma CSV ────────────────────────────────────────────────────────────────
# Architecture: triplets _auto / _manual / _final pour les champs sensibles
# Règle: _final = _manual si non vide, sinon _auto

COLUMNS = [
    # ── Identifiants et classification ─────────────────────────────────────────
    "Référence",
    "Intitulé synthétique",
    "Type d'AO",
    "Type",
    "Fonction publique",

    # ── Acheteur (triplet) ───────────────────────────────────────────────────
    "Acheteur_auto",       # Valeur calculée par l'ETL
    "Acheteur_manual",     # Correction manuelle (Google Sheets) - PRÉSERVÉE
    "Acheteur",            # Valeur finale utilisée (= manual sinon auto)
    "Acheteur_clean",      # Normalisation automatique de la valeur finale

    # ── Localisation (triplet) ───────────────────────────────────────────────
    "Localisation_auto",   # Valeur calculée par l'ETL
    "Localisation_manual", # Correction manuelle (Google Sheets) - PRÉSERVÉE
    "Localisation",        # Valeur finale utilisée (= manual sinon auto)
    "Localisation_clean",  # Normalisation automatique de la valeur finale

    # ── Date limite (triplet) ─────────────────────────────────────────────────
    "Date_limite_auto",    # Valeur calculée par l'ETL
    "Date_limite_manual",  # Correction manuelle (Google Sheets) - PRÉSERVÉE
    "Date limite de remise des offres",  # Valeur finale utilisée

    # ── Durée et Reconduction (non-triplet: faible volatilité) ────────────────
    "Durée initiale du marché",
    "Reconduction(s)",

    # ── Estimation (triplet) ─────────────────────────────────────────────────
    "Estimation_auto",     # Valeur calculée par l'ETL
    "Estimation_manual",   # Correction manuelle (Google Sheets) - PRÉSERVÉE
    "Estimation du marché", # Valeur finale utilisée (= manual sinon auto)

    # ── Métadonnées et traçabilité ────────────────────────────────────────────
    "URL source HTTPS",
    "Plateforme",
    "match_status",
    "match_source",
    "review_needed",
    "extraction_notes",
]

# ── Regex partagées ───────────────────────────────────────────────────────────

# Valeurs existantes considérées comme ambiguës → autorisent remplacement
AMBIGUOUS_RE = re.compile(
    r"non\s+(pr[eé]cis[eé]|identifi[eé]|d[eé]terminé|applicable|explicit)"
    r"|^Non$|^Inconnu$|^-$",
    re.IGNORECASE,
)

# Artefact MarchesOnline : 'VILLE M (NN)' → à nettoyer
_MARCHESONLINE_M_RE = re.compile(r"^([A-Z][A-Z\s\-\']+?)\s+M\s+(\(\d{2}\))$")

# Domaines d'avis publics connus (fallback URL source)
AVIS_DOMAINS = (
    "boamp.fr", "francemarches.com", "marches-publics.info",
    "marchesonline.com", "ted.europa.eu", "place.gouv.fr",
    "marches-publics.gouv.fr", "achatpublic.com", "achatpublic.info",
    "aws.achatpublic.com",
)

# ── Regex de nettoyage des valeurs héritées ───────────────────────────────────

# Estimations héritées clairement erronées (année ou < 1000 €)
_BAD_ESTIM_RE = re.compile(
    r"^(2\s*0[2-9]\d|[0-9]{1,3})\s*(Euro|EUR|€)\s*$",
    re.IGNORECASE,
)

# Durées héritées aberrantes
_BAD_DUREE_RE = re.compile(r"^(\d+)\s*(an|mois)", re.IGNORECASE)

# Reconductions héritées clairement invalides
_BAD_RECON_RE = re.compile(
    r"^[a-z0-9\-]+$"
    r"|^[a-z]{1,5}$"
    r"|^(comprises?|du march[eé])$"
    r"|^(est\s+fix[eé]\s+[àa]\s*\d*)$"
    r"|^Nombre\s+max(?:imal)?\s+de\s+renouvellements?\s*$"
    r"|^Nombre\s+maximum\s+de\s+reconductions?\s*$"
    r"|^,\s+",
    re.IGNORECASE,
)

# Valeurs de reconduction non exploitables (utilisé dans extract.py)
RECON_REJECT_RE = re.compile(
    r"^(Nombre\s+max(?:imal)?\s+de\s+renouvellements?\s*$"
    r"|Nombre\s+maximum\s+de\s+reconductions?\s*$"
    r"|[a-z0-9\-]+$"
    r"|[a-z]{1,5}$"
    r"|comprises?$|du\s+[Mm]arch[eé]$"
    r"|est\s+fix[eé]\s+[àa]\s*$)",
    re.IGNORECASE,
)
