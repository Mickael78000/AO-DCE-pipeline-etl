"""
ao_etl/main.py — Orchestration ETL uniquement.
Séquence Extract → Transform → Load sans logique métier propre.
"""

import logging
from pathlib import Path

from ao_etl import config, detect, load, match, normalize, transform

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    log.info("=== Extraction AO ===")
    log.info("Repertoire  : %s", config.WORKDIR)
    log.info("Dossier HTML: %s", config.HTML_DIR)

    # ── LOAD (entrée) ─────────────────────────────────────────────────────────
    rows_in = load.read_csv(config.INPUT_CSV)
    log.info("CSV charge : %d lignes", len(rows_in))

    # ── EXTRACT ───────────────────────────────────────────────────────────────
    # Passe 1 : index rapide sur les noms de fichiers (sans internal_ref)
    file_index = match.build_file_index(config.HTML_DIR)
    log.info("Fichiers HTML indexes : %d", len(set(file_index.values())))

    html_cache: dict[Path, dict] = {}
    for html_file in sorted(config.HTML_DIR.glob("*.html")):
        try:
            html_cache[html_file] = detect.build_record(html_file)
            log.info("  Parsed: %s", html_file.name)
        except Exception as e:
            log.warning("  ERREUR parsing %s: %s", html_file.name, e)
            html_cache[html_file] = {}

    # Passe 2 : index enrichi avec les identifiants internes extraits du HTML
    file_index = match.build_file_index(config.HTML_DIR, html_cache)
    log.info("Index enrichi : %d cles", len(file_index))

    # ── TRANSFORM (lignes CSV existantes) ─────────────────────────────────────
    report_lines: list[str] = []
    out_rows:     list[dict] = []
    matched_files: set[Path] = set()

    for raw_row in rows_in:
        row = transform.remap_legacy_columns(raw_row)
        ref = row.get("Référence", "?")

        html_path = match.match_row_to_file(raw_row, file_index, html_cache, config.HTML_DIR)
        if html_path and html_path in html_cache:
            matched_files.add(html_path)
            row, changes = transform.merge_into_row(row, html_cache[html_path])
            transform.update_match_metadata(row, html_path, changes)
            
            # Appliquer la règle manual/auto pour recalculer les valeurs finales
            transform.apply_manual_overrides(row)
            
            # Recalculer les normalisations avec les valeurs finales
            row["Acheteur_clean"] = normalize.clean_acheteur(row.get("Acheteur", ""))
            row["Localisation_clean"] = normalize.clean_localisation(
                row.get("Localisation", ""), row.get("Acheteur", "")
            )
            if changes:
                report_lines.append(
                    f"- **{ref}** ({html_path.name}): {', '.join(changes)}"
                )
            else:
                report_lines.append(
                    f"- **{ref}** ({html_path.name}): trouve, rien a enrichir"
                )
        else:
            report_lines.append(f"- **{ref}**: aucun fichier HTML trouve")

        transform.annotate_issues(row)
        out_rows.append(row)

    # ── TRANSFORM (nouvelles lignes depuis HTML non matchés) ──────────────────
    new_from_html = 0
    for html_path in sorted(config.HTML_DIR.glob("*.html")):
        if html_path in matched_files:
            continue
        extracted = html_cache.get(html_path, {})
        new_row = transform.build_new_row(extracted, html_path)
        if new_row is None:
            continue
        out_rows.append(new_row)
        new_from_html += 1
        report_lines.append(
            f"- **{new_row['Référence']}** (NOUVEAU): {html_path.name}"
        )

    # ── LOAD (sortie) ─────────────────────────────────────────────────────────
    # Calculer les statistiques d'overrides manuels
    manual_overrides = {
        "Acheteur": sum(1 for r in out_rows if r.get("Acheteur_manual", "").strip()),
        "Localisation": sum(1 for r in out_rows if r.get("Localisation_manual", "").strip()),
        "Date_limite": sum(1 for r in out_rows if r.get("Date_limite_manual", "").strip()),
        "Estimation": sum(1 for r in out_rows if r.get("Estimation_manual", "").strip()),
    }
    
    load.export_csv(out_rows, config.OUTPUT_CSV)
    load.export_report(
        report_lines,
        {
            "html_parsed":            len(html_cache),
            "rows_in":                len(rows_in),
            "rows_out":               len(out_rows),
            "enriched":               sum(1 for r in out_rows if r.get("match_status") == "matched"),
            "unmatched":              sum(1 for r in out_rows if r.get("match_status") in ("unmatched", "")),
            "new_from_html":          new_from_html,
            "normalized_acheteur":    sum(1 for r in out_rows if r.get("Acheteur_clean")),
            "normalized_localisation":sum(1 for r in out_rows if r.get("Localisation_clean")),
            "manual_overrides":       manual_overrides,
        },
        config.REPORT_MD,
    )


if __name__ == "__main__":
    main()
