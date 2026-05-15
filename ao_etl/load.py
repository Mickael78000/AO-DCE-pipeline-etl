"""
ao_etl/load.py — Lecture CSV en entrée, export CSV et rapport Markdown.
Aucune logique métier. Importe config uniquement.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path

from ao_etl.config import COLUMNS

log = logging.getLogger(__name__)


def read_csv(path: Path) -> list[dict]:
    """Charge le CSV d'entrée. Retourne une liste vide si le fichier n'existe pas."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def export_csv(rows: list[dict], path: Path) -> None:
    """Écrit le CSV de sortie avec le schéma COLUMNS."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info("CSV exporte : %s (%d lignes)", path, len(rows))


def export_report(lines: list[str], stats: dict, path: Path) -> None:
    """Génère le rapport Markdown d'extraction."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Section sur les overrides manuels
    manual_stats = stats.get('manual_overrides', {})
    manual_section = ""
    if manual_stats:
        manual_section = (
            f"\n## Corrections manuelles (Google Sheets)\n\n"
            f"Nombre de champs finalisés manuellement :\n"
            f"- Acheteur_manual    : {manual_stats.get('Acheteur', 0)}\n"
            f"- Localisation_manual: {manual_stats.get('Localisation', 0)}\n"
            f"- Date_limite_manual : {manual_stats.get('Date_limite', 0)}\n"
            f"- Estimation_manual  : {manual_stats.get('Estimation', 0)}\n\n"
            f"Règle : `_final = _manual` si non vide, sinon `_auto`.\n\n"
        )
    
    content = (
        f"# Rapport d'extraction AO — {now}\n\n"
        f"## Statistiques\n\n"
        f"- Fichiers HTML analyses   : {stats['html_parsed']}\n"
        f"- Lignes CSV en entree     : {stats['rows_in']}\n"
        f"- Lignes CSV en sortie     : {stats['rows_out']}\n"
        f"- Lignes enrichies         : {stats['enriched']}\n"
        f"- Lignes restant unmatched : {stats['unmatched']}\n"
        f"- Nouvelles lignes HTML    : {stats['new_from_html']}\n"
        f"- Acheteur_clean non vide  : {stats.get('normalized_acheteur', 'n/a')}\n"
        f"- Localisation_clean non vide : {stats.get('normalized_localisation', 'n/a')}\n"
        f"{manual_section}"
        f"## Documentation champs\n\n"
        f"### Architecture triplet (_auto / _manual / _final)\n\n"
        f"Pour les champs sensibles (Acheteur, Localisation, Date limite, Estimation), "
        f"le CSV utilise un système de triplets :\n\n"
        f"- **`*_auto`** : Valeur calculée automatiquement par l'ETL.\n"
        f"- **`*_manual`** : Correction manuelle saisie dans Google Sheets. **Jamais écrasée.**\n"
        f"- **`*_final`** (sans suffixe) : Valeur utilisée comme référence. "
        f"Égale à `*_manual` si non vide, sinon `*_auto`.\n\n"
        f"### Workflow recommandé\n\n"
        f"1. Lancer l'ETL pour remplir les colonnes `*_auto`.\n"
        f"2. Ouvrir le CSV dans Google Sheets.\n"
        f"3. Corriger directement dans les colonnes `*_manual` (pas dans les colonnes finales).\n"
        f"4. Relancer l'ETL : les valeurs `*_manual` sont préservées et prises en priorité.\n\n"
        f"## Detail des enrichissements\n\n"
        + "\n".join(lines)
        + "\n\n## Colonnes\n\n"
        + ", ".join(f"`{c}`" for c in COLUMNS)
        + "\n"
    )
    path.write_text(content, encoding="utf-8")
    log.info("Rapport exporte : %s", path)
