# AO-DCE ETL - Pipeline d'extraction d'appels d'offres

Pipeline ETL pour l'extraction, la normalisation et la fusion de données d'appels d'offres publics depuis des fichiers HTML.

## 🎯 Objectif

Transformer des fichiers HTML d'appels d'offres (sources diverses: Marchés Online, France Marchés, PLACE, BOAMP) en données structurées CSV, avec:
- Extraction DOM-first + regex fallback
- Normalisation automatique (acheteurs, localisations)
- Gestion des corrections manuelles (triplets _auto/_manual/_final)
- Détection de doublons et alias

## 📁 Structure du projet

```
data/
├── raw/html/             # Données source HTML (50 fichiers)
├── input/                # CSV d'entrée
├── output/               # CSV générés
└── intermediate/         # Fichiers temporaires

ao_etl/                   # Code source principal
├── pipeline/             # Pipeline ETL unifié
│   ├── run.py
│   ├── discovery.py
│   ├── reconcile.py
│   ├── merge.py
│   ├── validate.py
│   └── export.py
├── sources/              # Extracteurs par source
│   ├── router.py           # Routeur principal
│   ├── base.py             # Classes de base
│   ├── validation.py       # Validation et scoring
│   ├── boamp_xml.py        # Extracteur BOAMP
│   ├── joue.py             # Extracteur JOUE
│   ├── marches_online.py   # Extracteur Marchés Online
│   ├── place_numeric.py    # Extracteur PLACE
│   ├── france_marches.py   # Extracteur France Marchés
│   └── standard.py         # Extracteur standard
└── models/               # Modèles de données
    └── market_data.py

reports/                  # Rapports et audits
├── audit/
├── validation/
└── logs/

scripts/                  # Utilitaires
├── cleanup_unmatched.py
└── recipe_report.py

docs/                     # Documentation
archive/                  # Scripts obsolètes
```

## 🚀 Démarrage rapide

### Prérequis

```bash
# Environnement virtuel Python 3.10+
cd /home/michka/Documents/0-AO-DCE
python3 -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows
pip install -e .
```

### Exécution du pipeline principal

Le point d'entrée canonique du pipeline est **`./run_pipeline.py`** :

```bash
# Pipeline complet (recommandé)
python run_pipeline.py

# Avec chemins personnalisés
python run_pipeline.py --input data/input/AO-completed.csv --html-dir data/raw/html --output data/output/AO-pipeline.csv
```

> **Note** : Le pipeline intègre toutes les phases (discovery → reconcile → extract → merge → validate → export). Pour une extraction unitaire sans réconciliation, voir [Utilitaires](#utilitaires).

### Tests

```bash
# Tous les tests
venv/bin/python -m pytest tests/ -v

# Tests unitaires
venv/bin/python -m pytest tests/unit/ -v

# Tests d'intégration
venv/bin/python -m pytest tests/integration/ -v
```

## 🔧 Architecture

### Flux de données

```
HTML → Détection source → Extraction → MarketData → Normalisation → CSV
```

### Système de sources (nouveau)

Chaque source HTML a son extracteur dédié:

```python
from ao_etl.sources.router import extract_for_source
from pathlib import Path

data = extract_for_source(Path('html_ao/ao-9594452-1.html'))
print(data.reference)  # "MO-9594452"
print(data.title)      # Titre extrait
print(data.buyer)      # Acheteur extrait
```

### Triplet _auto/_manual/_final

Pour les champs sensibles (acheteur, localisation, date, estimation):

| Suffixe | Description | Priorité |
|---------|-------------|----------|
| `_auto` | Valeur calculée par l'ETL | Basse |
| `_manual` | Correction manuelle | Haute (écrase _auto) |
| (sans suffixe) | Valeur finale | = _manual sinon _auto |

## 🐛 Bugs critiques corrigés

### Bug 1838554 - Références Marchés Online

**Problème:** La référence `1838554` était extraite depuis `refContrat` JavaScript,
identique pour tous les marchés d'un même compte client → 12 faux doublons.

**Solution:** Extraction depuis le nom de fichier: `ao-9594452-1.html` → `MO-9594452`

**Validation:** 15 références uniques au lieu de 15× la même référence.

### Bug Unicode - Titres France Marchés

**Problème:** Le JSON `weboramaItemTag` encode les caractères avec `\u0022`,
produisant des titres illisibles.

**Solution:** Décodeur Unicode intégré dans `FranceMarchesExtractor._decode_unicode_escapes()`

## 📊 Résultats de validation

| Métrique | Valeur |
|----------|--------|
| Fichiers analysés | 50/50 (100%) |
| Extraction complète | 50/50 (100%) |
| Références uniques | 50/50 (100%) |
| Tests passants | 8/8 unitaires + 6/6 intégration |

**Sources détectées:**
- FRANCE_MARCHES: 27 fichiers
- MARCHES_ONLINE: 15 fichiers (MO-XXXX uniques)
- PLACE_NUMERIC: 7 fichiers
- BOAMP_XML: 1 fichier

## 📚 Documentation

- [Guide développeur](docs/developer_guide.md) - Architecture, ajout de sources/patterns
- [Méthodologie](METHODOLOGY_SUMMARY.md) - Décisions métier et normalisation
- [Workflow](README_WORKFLOW.md) - Guide d'utilisation Google Sheets
- [Audit projet](PROJECT_AUDIT.md) - Analyse initiale et architecture cible

## 🔍 Exemples

### Extraction unitaire

```python
from ao_etl.sources.router import extract_for_source
from pathlib import Path

data = extract_for_source(Path('html_ao/mon_fichier.html'))
print(f"Source: {data.source_type.value}")
print(f"Réf: {data.reference}")
print(f"Titre: {data.title}")
print(f"Complet: {data.is_complete()}")
```

## 🧪 Développement

### Ajouter une source

1. Créer `ao_etl/sources/ma_source.py` héritant de `BaseExtractor`
2. Enregistrer dans `router.py`
3. Ajouter des tests dans `tests/unit/test_sources/`

### Ajouter un pattern

Modifier l'extracteur concerné avec la logique DOM-first + fallback:

```python
def _extract_title(self) -> None:
    # 1. DOM-first
    if self.soup.title:
        self.data.title = self._clean_text(self.soup.title.string)
        return
    
    # 2. Fallback regex
    match = re.search(r'pattern', self.content)
    if match:
        self.data.title = match.group(1)
```

## 📦 Livraison

Fichiers générés:
- `AO-completed-updated.csv` - Données enrichies
- `rapport-extraction.md` - Rapport de synthèse
- `rapport_redondances.json` - Analyse des doublons

## 📝 Changelog

### 2026-05-11 - Restructuration majeure

- ✅ Architecture modulaire `sources/` créée
- ✅ Bug 1838554 corrigé (références Marchés Online uniques)
- ✅ Bug Unicode décodé (titres France Marchés)
- ✅ 8 tests unitaires + 6 tests d'intégration
- ✅ Pipeline ETL unifié (v2 devenue canonique)
- ✅ CLI moderne

## 🔧 Utilitaires

### Extraction unitaire (sans réconciliation)

Pour une extraction simple d'un fichier HTML sans passer par le pipeline complet :

```bash
# Extraction avec le CLI utilitaire
python -m ao_etl.cli extract data/raw/html/ao-12345.html -o rapport.json
```

> **Note** : Cet utilitaire ne fait que l'extraction. Il ne réconcilie pas avec un CSV existant et ne produit pas de CSV final. Utiliser `./run_pipeline.py` pour le pipeline complet.

### Nettoyage de CSV

```bash
# Retirer les lignes sans fichier HTML associé
python scripts/cleanup_unmatched.py data/output/AO-pipeline.csv
```

---

## 🗃️ Archives

Les scripts obsolètes sont conservés dans `archive/` pour référence historique.

---

## ⚖️ Licence

MIT

## 🤝 Contribution

1. Créer une branche feature/
2. Ajouter des tests
3. Documenter dans developer_guide.md
4. Soumettre PR avec rapport de validation

---

**Statut:** ✅ Production-ready | 50/50 fichiers extraits | 100% références uniques
