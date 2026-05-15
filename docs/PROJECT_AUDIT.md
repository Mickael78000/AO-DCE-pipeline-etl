# AUDIT DU PROJET ETL - AO-DCE

Date: 2026-05-11
Objectif: Restructuration en architecture propre, modulaire, testable

## 1. ÉTAT ACTUEL - ARBORESCENCE

```
/home/michka/Documents/0-AO-DCE/
├── ao_etl/                    # Package ETL déjà modulaire ✓
│   ├── __init__.py
│   ├── config.py              # Constantes, chemins, regex
│   ├── main.py                # Orchestration ETL
│   ├── extract.py             # Extraction HTML champ par champ
│   ├── detect.py              # Détection source + build_record
│   ├── normalize.py           # Normalisation acheteur/localisation
│   ├── transform.py           # Fusion CSV, overrides manual/auto
│   ├── match.py               # Matching fichiers HTML ↔ CSV
│   ├── load.py                # Export CSV et rapports
│   ├── utils.py               # Utilitaires transverses
│   └── clean_html.py          # Nettoyage HTML brut
│
├── html_ao/                   # 50 fichiers HTML sources
├── venv/                      # Environnement virtuel
│
├── Scripts standalone (redondants avec ao_etl):
│   ├── quick_analyze.py       (23K) - NOUVELLE extraction DOM-first
│   ├── analyze_redundancies.py (15K) - Ancienne analyse
│   ├── update_csv.py          (8K) - Mise à jour CSV
│   └── test_pattern.py        (1K) - Test regex ponctuel
│
├── Fichiers de données:
│   ├── AO-completed.csv       # CSV d'entrée
│   ├── AO-completed-updated.csv # CSV de sortie
│   ├── rapport_redondances.json # Rapport JSON
│   └── update_report.json     # Rapport de mise à jour
│
└── Documentation:
    ├── METHODOLOGY_SUMMARY.md
    ├── QA_CHECKLIST.md
    ├── QA_CHECKLIST_V1.md
    ├── README_WORKFLOW.md
    ├── REFACTORING_SUMMARY.md
    ├── rapport-extraction.md
    ├── rapport-final.md
    └── rapport-validation.md
```

## 2. ANALYSE DES MODULES ao_etl/

| Module | Lignes | Rôle | Qualité | Observations |
|--------|--------|------|---------|--------------|
| config.py | 117 | Configuration | ✓ Bon | Triplets _auto/_manual/_final bien documentés |
| main.py | 123 | Orchestration | ✓ Bon | Séquence ETL claire, logging présent |
| extract.py | 369 | Extraction HTML | ⚠ Moyen | Fonctions longues, mélange parsing/extraction |
| detect.py | 168 | Détection source | ✓ Bon | Découpage par source clair |
| normalize.py | 335 | Normalisation | ✓ Bon | Règles métier bien isolées |
| transform.py | 315 | Transformation | ⚠ Complexe | Logique _auto/_manual/_final correcte mais dense |
| match.py | 117 | Matching | ✓ Bon | Indexation et rapprochement |
| load.py | 114 | Export | ✓ Bon | CSV + rapports markdown |
| utils.py | 53 | Utilitaires | ✓ Bon | Minimal et utile |
| clean_html.py | 102 | Nettoyage HTML | ✓ Bon | Séparation des responsabilités |

**Total ao_etl**: ~1,570 lignes de code métier

## 3. ANALYSE DES SCRIPTS STANDALONE

### 3.1 quick_analyze.py (23,444 bytes, 559 lignes)

**Statut**: NOUVEAU - Contient la logique d'extraction DOM-first la plus récente

| Fonction | Lignes | Rôle | Destination proposée |
|----------|--------|------|---------------------|
| extract_data() | 40 | Router extraction | ao_etl/sources/router.py |
| _extract_marches_online() | 100 | Extraction Marchés Online | ao_etl/sources/marches_online.py |
| _extract_place_numeric() | 60 | Extraction PLACE | ao_etl/sources/place_numeric.py |
| _extract_france_marches() | 120 | Extraction France Marchés | ao_etl/sources/france_marches.py |
| _extract_boamp_xml() | 40 | Extraction BOAMP | ao_etl/sources/boamp_xml.py |
| _extract_standard() | 40 | Extraction fallback | ao_etl/sources/standard.py |
| clean_text() | 15 | Nettoyage texte | ao_etl/utils/text.py |
| find_duplicates() | 80 | Détection doublons | ao_etl/matching/deduplicator.py |

**Problème**: Redondance fonctionnelle avec ao_etl/extract.py et ao_etl/detect.py
**Solution**: Intégrer les améliorations de quick_analyze.py dans ao_etl/

### 3.2 analyze_redundancies.py (15,150 bytes, 351 lignes)

**Statut**: LEGACY - Ancienne analyse, code basé sur regex brut

| Classe/Fonction | Usage actuel | Destination |
|-----------------|--------------|-------------|
| MarketDataExtractor | Obsolète | archive/ |
| find_duplicates() | Partiellement redondant | archive/ |

**Problème**: Approche regex-only, remplacée par DOM-first dans quick_analyze.py
**Solution**: Archiver comme référence historique

### 3.3 update_csv.py (8,431 bytes)

**Statut**: FONCTIONNEL - Script de mise à jour CSV basé sur quick_analyze.py

| Fonction | Rôle | Destination |
|----------|------|-------------|
| update_csv() | Met à jour CSV avec rapports | ao_etl/cli/commands.py |

**Solution**: Intégrer comme commande CLI

### 3.4 test_pattern.py (979 bytes)

**Statut**: JETABLE - Test ponctuel
**Solution**: Supprimer (remplacé par vraie suite de tests)

## 4. DIAGNOSTIC - POINTS DE DOULEUR

### 4.1 Redondance extraction
- `ao_etl/extract.py` et `ao_etl/detect.py` contiennent une logique d'extraction
- `quick_analyze.py` contient une NOUVELLE logique d'extraction DOM-first plus robuste
- **Impact**: Maintenance dans 2 endroits, risque de divergence

### 4.2 Détection de source dispersée
- `detect.py` a une logique de détection
- `quick_analyze.py` a une AUTRE logique de détection (ligne 37-52)
- **Impact**: Inconsistance dans la classification des sources

### 4.3 Pas de tests automatisés
- Aucun test unitaire présent
- Seul `test_pattern.py` existe (test ponctuel jetable)
- **Impact**: Impossible de valider les non-régressions automatiquement

### 4.4 Scripts standalone non intégrés
- `quick_analyze.py`, `update_csv.py` fonctionnent en dehors du package ao_etl
- **Impact**: Double point d'entrée, confusion sur le "vrai" pipeline

## 5. PROPOSITION - TABLEAU DE CLASSEMENT

### 5.1 Fichiers à CONSERVER (racine)

| Chemin | Justification |
|--------|---------------|
| AO-completed.csv | Donnée d'entrée du pipeline |
| AO-completed-updated.csv | Donnée de sortie du pipeline |
| README_WORKFLOW.md | Documentation utilisateur |
| METHODOLOGY_SUMMARY.md | Documentation méthodologique |
| QA_CHECKLIST.md | Procédures de validation |

### 5.2 Fichiers à ARCHIVER (archive/)

| Chemin | Justification | Action |
|--------|---------------|--------|
| analyze_redundancies.py | Ancienne analyse regex-only | Déplacer vers archive/scripts/ |
| QA_CHECKLIST_V1.md | Version obsolète checklist | Déplacer vers archive/docs/ |
| test_pattern.py | Test ponctuel jetable | SUPPRIMER (pas d'archive nécessaire) |
| rapport_redondances.json | Vieux rapport d'analyse | Déplacer vers archive/reports/ |
| update_report.json | Vieux rapport | Déplacer vers archive/reports/ |

### 5.3 Fichiers à INTÉGRER dans ao_etl/

| Chemin | Destination | Justification |
|--------|-------------|---------------|
| quick_analyze.py | Split dans ao_etl/sources/*.py | Nouvelle extraction DOM-first |
| update_csv.py | ao_etl/cli/commands.py | Commande de mise à jour |

### 5.4 Modules ao_etl/ à REFACTORER

| Module | Action | Justification |
|--------|--------|---------------|
| extract.py | Refactorer + splitter | Fonctions trop longues, mélange parsing/extraction |
| detect.py | Fusionner avec quick_analyze.py | Unifier la logique de détection |
| transform.py | Simplifier | Complexité des triplets _auto/_manual/_final |

## 6. ARCHITECTURE CIBLE PROPOSÉE

```
/home/michka/Documents/0-AO-DCE/
├── ao_etl/                          # Package principal
│   ├── __init__.py
│   ├── cli.py                       # Point d'entrée CLI unique
│   ├── config.py                    # Configuration (inchangé)
│   ├── models/                      # Modèles de données
│   │   ├── __init__.py
│   │   ├── market.py               # Dataclass Market/Tender
│   │   └── enums.py                # Enums SourceType, Status
│   │
│   ├── io/                          # Entrée/Sortie (refactor load.py)
│   │   ├── __init__.py
│   │   ├── csv_loader.py           # Lecture/écriture CSV
│   │   ├── html_loader.py          # Lecture HTML
│   │   └── reporters.py            # Rapports markdown/JSON
│   │
│   ├── parsing/                     # Parsing HTML brut
│   │   ├── __init__.py
│   │   ├── cleaner.py              # Nettoyage HTML (from clean_html.py)
│   │   └── soup_utils.py           # Utilitaires BeautifulSoup
│   │
│   ├── sources/                     # Extraction par source (NEW from quick_analyze.py)
│   │   ├── __init__.py
│   │   ├── base.py                 # Classe abstraite Extractor
│   │   ├── router.py               # Routing detection source
│   │   ├── france_marches.py       # Extraction France Marchés
│   │   ├── marches_online.py       # Extraction Marchés Online
│   │   ├── place_numeric.py        # Extraction PLACE
│   │   ├── boamp_xml.py            # Extraction BOAMP
│   │   └── standard.py             # Extraction fallback
│   │
│   ├── extraction/                  # Extraction métier par champ
│   │   ├── __init__.py
│   │   ├── reference.py            # Extraction référence
│   │   ├── title.py                # Extraction titre
│   │   ├── buyer.py                # Extraction acheteur
│   │   ├── cpv.py                  # Extraction CPV
│   │   ├── dates.py                # Extraction dates
│   │   ├── location.py             # Extraction localisation
│   │   └── estimation.py           # Extraction estimation
│   │
│   ├── normalization/               # Normalisation (refactor normalize.py)
│   │   ├── __init__.py
│   │   ├── text.py                 # Nettoyage texte
│   │   ├── buyer.py                # Normalisation acheteur
│   │   ├── location.py             # Normalisation localisation
│   │   └── dates.py                # Normalisation dates
│   │
│   ├── matching/                    # Matching et déduplication
│   │   ├── __init__.py
│   │   ├── indexer.py              # Indexation fichiers (from match.py)
│   │   ├── deduplicator.py         # Détection doublons (from quick_analyze.py)
│   │   └── merger.py               # Fusion CSV/HTML
│   │
│   ├── transform/                   # Transformation ETL
│   │   ├── __init__.py
│   │   ├── overrides.py            # Gestion _auto/_manual/_final
│   │   ├── enricher.py             # Enrichissement données
│   │   └── validator.py            # Validation lignes
│   │
│   └── pipeline.py                  # Orchestration (refactor main.py)
│
├── tests/                           # Tests
│   ├── unit/                        # Tests unitaires
│   │   ├── __init__.py
│   │   ├── test_sources/            # Tests par source
│   │   ├── test_extraction/         # Tests extraction champ
│   │   ├── test_normalization/      # Tests normalisation
│   │   └── test_matching/           # Tests matching
│   ├── integration/                 # Tests d'intégration
│   │   ├── __init__.py
│   │   └── test_pipeline.py         # Test pipeline complet
│   └── fixtures/                    # Données de test
│       ├── html/                    # Extraits HTML de test
│       └── csv/                     # CSV de test
│
├── scripts/                         # Scripts utilitaires
│   └── archive_and_cleanup.py       # Script de nettoyage (one-time)
│
├── archive/                         # Archive historique
│   ├── scripts/                     # Anciens scripts
│   ├── docs/                        # Ancienne documentation
│   └── reports/                     # Anciens rapports
│
├── docs/                            # Documentation technique (NEW)
│   ├── architecture.md              # Architecture détaillée
│   ├── developer_guide.md           # Guide développeur
│   └── adding_source.md             # Guide ajout nouvelle source
│
├── html_ao/                         # Données source HTML
├── AO-completed.csv                 # Donnée d'entrée
├── AO-completed-updated.csv         # Donnée de sortie
├── pyproject.toml                   # Configuration projet
└── README.md                        # Documentation principale
```

## 7. PLAN DE MIGRATION INCRÉMENTAL

### Phase 1: Préparation (sans modification métier)
1. Créer structure `archive/`, `tests/`, `docs/`
2. Déplacer fichiers obsolètes vers `archive/`
3. Créer `pyproject.toml`
4. Ajouter tests de caractérisation (capturer comportement actuel)

### Phase 2: Intégration quick_analyze.py
1. Créer `ao_etl/sources/` avec modules par source
2. Migrer fonctions d'extraction de quick_analyze.py
3. Ajouter tests unitaires pour chaque source
4. Router temporairement: utiliser quick_analyze si présent, sinon ancien

### Phase 3: Refactor extraction métier
1. Split `ao_etl/extract.py` en modules par champ
2. Unifier avec logique quick_analyze.py
3. Ajouter tests pour chaque champ
4. Valider non-régression avec tests d'intégration

### Phase 4: Nettoyage final
1. Supprimer anciens scripts (maintenant dans sources/)
2. Mettre à jour imports et CLI
3. Générer documentation finale
4. Valider pipeline complet

## 8. MÉTRIQUES DE SUCCÈS

| Critère | Cible | Mesure |
|---------|-------|--------|
| Couverture tests | >70% | pytest --cov |
| Fichiers modules | <200 lignes/module | wc -l |
| Duplication code | <5% | flake8 + review |
| Complexité cyclomatique | <10/fonction | radon cc |
| Tests passent | 100% | pytest |
| Non-régression | 0 régression | Comparaison CSV |

---

**Prochaine étape**: Validation de cette analyse et approbation de l'architecture cible avant début de la restructuration.
