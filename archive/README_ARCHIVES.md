# Archives du Projet AO-DCE

Ce dossier contient les fichiers historiques et obsolètes du projet.

## 📁 Structure des Archives

### `/scripts-obsoletes/`
Scripts remplacés par le pipeline ETL moderne (`run_pipeline.py`).

| Script | Remplacé par | Raison |
|--------|--------------|--------|
| `apply_schema_contract.py` | Pipeline phase 7 | Consolidation intégrée |
| `audit_extraction_contamination.py` | `reports/audit/` | Outil d'analyse ponctuel |
| `classify_acheteur_llm.py` | `scripts/classify_with_llm.py` | Nouvelle version avec schéma RC |
| `cleanup_obsolete_files.py` | - | Outil de maintenance ponctuel |
| `compare_extractors.py` | Tests automatisés | Outil de comparaison legacy |
| `consolidate_procedure.py` | Pipeline phase 7 | Consolidation intégrée |
| `extract_fields_from_html.py` | `ao_etl/sources/` | Extracteurs modernisés |
| `recipe_report.py` | Pipeline reporting | Génération rapports legacy |
| `split_csv_metier_audit.py` | Pipeline | Split intégré |
| `update_csv_with_audit.py` | Pipeline | Mise à jour intégrée |
| `validate_classification.py` | `ao_etl/pipeline/validate.py` | Validation intégrée |

### `/logs/`
Logs historiques de traitement.

| Fichier | Date | Description |
|---------|------|-------------|
| `extraction_rc_new.log` | 2025-05-15 | Log extraction RC (nouveau format) |
| `extraction_rc_v2.log` | 2025-05-15 | Log extraction RC v2 |
| `reprocess_rc.log` | 2025-05-15 | Log retraitement RC |

### `/backups/`
Backups de configuration.

| Fichier | Date | Description |
|---------|------|-------------|
| `extraction_rc.json.backup` | 2025-05-15 | Backup schéma RC avant modifications |

### `/scripts/` (archive existante)
Scripts legacy déjà archivés précédemment.

| Script | Description |
|--------|-------------|
| `add_orphan_html.py` | Ajout HTML orphelins (legacy) |
| `test_pattern.py` | Tests patterns (legacy) |
| `update_csv_modern.py` | Mise à jour CSV (legacy) |

### `/docs/` (archive existante)
Documentation historique.

---

## 🔒 Politique d'Archivage

- **Conservation**: Archives conservées pour traçabilité et audit
- **Restauration**: Possible en cas de régression
- **Suppression**: Pas de suppression automatique (conservation historique)

## 📊 Statistiques

- Scripts archivés: 11
- Logs archivés: 3
- Backups: 1
- **Total**: ~350 KB

---
*Archivage effectué: Mai 2025*
