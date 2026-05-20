# AO-DCE Pipeline ETL

Pipeline ETL **100% déterministe** pour appels d'offres publics français et européens.

Sources supportées : BOAMP, JOUE, PLACE, France Marchés, Marchés Online.
Entrée : fichiers HTML bruts. Sortie : CSV normalisé + rapport JSON.

> **Politique projet** : aucun appel LLM, aucune dépendance à une API externe.
> L'extraction repose uniquement sur du parsing HTML/regex documenté et testable.

---

## Architecture

```
ao_etl/
├── sources/            # Extracteurs par plateforme (1 fichier par source)
│   ├── router.py         # Détection + dispatch vers le bon extracteur
│   ├── base.py           # BaseExtractor + ExtractionContext + ExtractionResult
│   ├── validation.py     # Scoring + arbitrage candidats
│   ├── boamp_xml.py
│   ├── joue.py
│   ├── france_marches.py
│   ├── marches_online.py
│   ├── place_numeric.py
│   └── standard.py
├── pipeline/           # Orchestration ETL (10 phases linéaires)
│   ├── run.py            # Point d'entrée du pipeline
│   ├── discovery.py      # [1/10] Découverte des fichiers HTML
│   ├── reconcile.py      # [2/10] Réconciliation avec CSV existant
│   ├── merge.py          # [4/10] Merge des extractions
│   ├── validate.py       # [5/10] Validation et anomalies
│   ├── export.py         # [6/10] Export CSV
│   ├── normalize_final_phase.py   # [7] Normalisation finale
│   ├── enrich_juridique.py        # [9] Enrichissement juridique
│   ├── excel_export.py            # [10] Export Excel
│   └── url_builder.py    # Reconstruction d'URLs canoniques
├── models/
│   └── market.py         # MarketData, SourceType, ExtractionStatus
└── utils/                # Helpers transverses

data/
├── raw/html/           # 63 fichiers HTML source
├── input/              # CSV d'entrée (état précédent)
└── output/             # CSV produits

tests/
├── unit/               # Tests déterministes par module
└── integration/        # Tests end-to-end
```

---

## Démarrage

### Installation

```bash
git clone https://github.com/Mickael78000/AO-DCE-pipeline-etl.git
cd AO-DCE-pipeline-etl
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### Exécution du pipeline

```bash
# Pipeline complet (chemins par défaut)
python run_pipeline.py

# Avec chemins personnalisés
python run_pipeline.py \
  --input data/input/AO-completed.csv \
  --html-dir data/raw/html \
  --output data/output/AO-pipeline.csv \
  --report data/output/AO-pipeline.json
```

Le pipeline déroule 10 phases dans l'ordre :
`DISCOVERY → RECONCILE → EXTRACT → MERGE → VALIDATE → EXPORT → NORMALIZE → CLASSIFY_BUYERS → ENRICH_JURIDIQUE → EXCEL_EXPORT`.

---

## Extraction unitaire

```python
from pathlib import Path
from ao_etl.sources.router import extract_for_source

data = extract_for_source(Path("data/raw/html/ao-9594452-1.html"))
print(data.reference)   # "MO-9594452"
print(data.title)       # Titre normalisé
print(data.buyer)       # Acheteur extrait
print(data.source_type) # SourceType.MARCHES_ONLINE
```

---

## Triplet `_auto` / `_manual` / `_final` 

Pour les champs sensibles (`Acheteur`, `Localisation`, `Date_limite`, `Estimation`) :

| Suffixe        | Source                  | Priorité                 |
|----------------|-------------------------|--------------------------|
| `_auto`        | Calculé par l'ETL       | Basse                    |
| `_manual`      | Correction humaine      | Haute (écrase `_auto`)   |
| (sans suffixe) | Valeur finale retenue   | `_manual` sinon `_auto`  |

---

## Tests

```bash
# Tous les tests
venv/bin/python -m pytest -v

# Unitaires uniquement
venv/bin/python -m pytest tests/unit -v

# Intégration
venv/bin/python -m pytest tests/integration -v
```

---

## Invariant golden

Le pipeline produit un CSV stable. Le MD5 de référence sur le corpus actuel
(63 fichiers HTML, `data/input/AO-completed.csv`) est :

```
131cf73a8d7fa69d99e2eda9cb4c16bb
```

Toute modification doit préserver ce MD5, sauf changement explicite et documenté
du contrat d'extraction.

---

## Ajouter une source

1. Créer `ao_etl/sources/ma_source.py` héritant de `BaseExtractor`.
2. Enregistrer la classe et le pattern de détection dans `sources/router.py` 
   (fonction `detect_source_type` + dict `mapping`).
3. Ajouter des tests dans `tests/unit/test_sources/test_ma_source.py`.
4. Re-générer le golden et vérifier qu'aucune régression n'apparaît.

---

## Licence

MIT
