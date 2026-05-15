# Structure du Projet AO-DCE

## Architecture ETL pour Marchés Publics

Ce projet implémente un pipeline ETL spécialisé pour l'analyse des appels d'offres et marchés publics.

```
0-AO-DCE/
├── 📋 FICHIER DE CONFIGURATION
│   ├── .env                          # Variables d'environnement (LLM, API keys)
│   ├── extraction_rc.json            # 📊 Schéma canonique des données RC
│   └── pyproject.toml                # Dépendances Python
│
├── 🚀 POINTS D'ENTRÉE
│   ├── run_pipeline.py               # Pipeline ETL principal (phases 1-10)
│   └── run_full_pipeline.sh          # Script complet (pipeline + LLM)
│
├── 📦 MODULE ETL PRINCIPAL (ao_etl/)
│   ├── pipeline/                     # Orchestration des phases
│   │   ├── run.py                    # run_pipeline() principal
│   │   ├── consolidate.py            # Phase 7: Consolidation LLM
│   │   ├── classify.py               # Phase 8: Classification acheteurs
│   │   ├── enrich_juridique.py     # Phase 9: Enrichissement juridique
│   │   └── excel_export.py         # Phase 10: Export Excel
│   ├── classification/               # Moteur de classification
│   ├── llm/                          # Backend LLM (OpenAI/Anthropic/Ollama)
│   └── io/                           # Gestion entrées/sorties
│
├── 🛠️ SCRIPTS OPÉRATIONNELS (scripts/)
│   ├── classify_acheteur.py          # Classification déterministe (règles)
│   ├── classify_with_llm.py          # 🤖 Classification LLM (cas difficiles)
│   ├── cleanup_unmatched.py          # Nettoyage des non-matchés
│   ├── utils/                        # Utilitaires partagés
│   │   ├── __init__.py
│   │   ├── csv_utils.py
│   │   ├── paths.py
│   │   └── text.py
│   ├── legacy/                       # Scripts legacy (conservés)
│   └── rc/                           # Scripts spécifiques traitement RC
│
├── 📁 DONNÉES (data/)
│   ├── input/                        # CSV source (AO-completed.csv)
│   ├── raw/html/                   # Fichiers HTML source
│   ├── intermediate/pdf_extracts/    # Extracts PDF intermédiaires
│   └── output/                       # 🎯 RÉSULTATS FINaux
│       ├── AO-pipeline-v2.csv        # Export base (phases 1-6)
│       ├── final-v4-classified.csv   # Après classification règles
│       ├── final-v4-complete.csv     # ✅ Après classification LLM (93.4%)
│       └── final-v4-juridique.xlsx # Excel final formaté
│
├── 🧪 TESTS (tests/)
│   ├── unit/                         # Tests unitaires
│   ├── integration/                  # Tests intégration
│   └── fixtures/                     # Données de test
│
├── 📚 DOCUMENTATION (docs/)
│   ├── METHODOLOGY_SUMMARY.md
│   ├── PROJECT_AUDIT.md
│   ├── QA_CHECKLIST.md
│   └── CONSOLIDATION_RULE_PROCEDURE.md
│
├── 🗃️ ARCHIVES (archive/)            # Fichiers historiques
│   ├── scripts-obsoletes/            # Scripts remplacés par pipeline
│   ├── logs/                         # Logs historiques
│   ├── backups/                      # Backups JSON
│   └── docs/                         # Ancienne documentation
│
└── 📊 RAPPORTS (reports/)
    ├── audit/                        # Rapports d'audit ETL
    └── validation/                   # Résultats validation
```

## Workflow Recommandé

### 1. Pipeline Complet (Automatique)
```bash
./run_full_pipeline.sh
```
Exécute:
- Phases 1-6: Extraction et merge (rapide)
- Phase 7: **SKIPPÉE** (consolidation LLM trop lente sur CPU)
- Phases 8-10: Classification, enrichissement, Excel (rapide)
- Classification LLM: 19 cas difficiles via Ollama (~5 min)

### 2. Pipeline Manuel (Étape par Étape)
```bash
# Phases 1-6
venv/bin/python run_pipeline.py

# Phase 8 (classification règles)
venv/bin/python run_pipeline.py --classify-buyers

# Phase 9 (enrichissement juridique)
venv/bin/python run_pipeline.py --enrich-juridique

# Phase 10 (Excel)
venv/bin/python run_pipeline.py --excel

# Classification LLM résiduelle
venv/bin/python scripts/classify_with_llm.py \
    -i data/output/final-v4-classified.csv \
    -o data/output/final-v4-complete.csv
```

## Performance de Classification

| Méthode | Taux | Temps |
|---------|------|-------|
| Règles déterministes | 68.9% | < 1s |
| **+ LLM Ollama** | **93.4%** | ~5 min |
| Total | 93.4% | ~5 min |

## Fichiers Clés

| Fichier | Rôle |
|---------|------|
| `extraction_rc.json` | Schéma canonique (listes fermées, validation) |
| `run_full_pipeline.sh` | Workflow complet automatisé |
| `scripts/classify_with_llm.py` | Classification LLM avec validation schéma |
| `data/output/final-v4-complete.csv` | **Résultat final fiabilisé** |

## Suppressions Effectuées

- ❌ Logs temporaires (`*.log`)
- ❌ Backups (`*.backup`)
- ❌ Scripts obsolètes (remplacés par pipeline)
- ❌ CSV mal placés à la racine

---
*Dernière restructuration: Mai 2025*
