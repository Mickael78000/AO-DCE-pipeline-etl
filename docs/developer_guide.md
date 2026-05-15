# Guide Développeur - AO-DCE ETL

## Vue d'ensemble

Ce projet implémente un pipeline ETL pour l'extraction et la normalisation
d'appels d'offres publics depuis des fichiers HTML.

## Architecture

### Structure du projet

```
ao_etl/
├── models/           # Modèles de données
├── sources/          # Extracteurs par source HTML
├── io/              # Entrée/Sortie (CSV, rapports)
├── parsing/         # Parsing HTML brut
├── matching/        # Matching et déduplication
├── transform/       # Transformation ETL
├── normalization/   # Normalisation métier
└── cli.py           # Interface en ligne de commande
```

### Flux de données

```
Fichier HTML → Détection source → Extraction → MarketData
                                    ↓
                              Normalisation
                                    ↓
                            Fusion CSV legacy
                                    ↓
                                Export
```

## Guide d'ajout d'une nouvelle source

### 1. Créer l'extracteur

Créer un fichier dans `ao_etl/sources/{nom_source}.py`:

```python
from ao_etl.sources.base import BaseExtractor
from ao_etl.models.market import MarketData, SourceType

class MaSourceExtractor(BaseExtractor):
    source_type = SourceType.MA_SOURCE
    
    def can_extract(self) -> bool:
        # Détection par heuristique
        return "pattern_identifiant" in self.content
    
    def extract(self) -> MarketData:
        self.data.source_type = self.source_type
        
        # Extraction champ par champ
        self._extract_title()
        self._extract_reference()
        self._extract_buyer()
        self._extract_cpv()
        
        return self.data
    
    def _extract_title(self) -> None:
        # Implémentation spécifique
        pass
```

### 2. Enregistrer dans le router

Modifier `ao_etl/sources/router.py`:

```python
from ao_etl.sources.ma_source import MaSourceExtractor

def detect_source(filepath: Path, content: str) -> SourceType:
    # Ajouter la détection
    if "pattern" in content:
        return SourceType.MA_SOURCE
    # ...

def get_extractor(...):
    extractors = {
        # ...
        SourceType.MA_SOURCE: MaSourceExtractor,
    }
```

### 3. Ajouter des tests

Créer `tests/unit/test_sources/test_ma_source.py`:

```python
class TestMaSourceExtractor:
    def test_detects_source(self):
        # Test de détection
        pass
    
    def test_extracts_title(self):
        # Test d'extraction
        pass
```

## Guide d'ajout d'un nouveau pattern d'extraction

### Pour un champ existant sur une nouvelle source

Modifier l'extracteur de la source concernée:

```python
def _extract_title(self) -> None:
    # Source 1: balise title
    if self.soup.title:
        self.data.title = self._clean_text(self.soup.title.string)
        return
    
    # Source 2: meta description (NOUVEAU)
    meta = self.soup.find('meta', attrs={'name': 'description'})
    if meta:
        self.data.title = self._clean_text(meta.get('content', ''))
        return
    
    # Source 3: regex fallback
    match = re.search(r'pattern', self.content)
    if match:
        self.data.title = match.group(1)
```

### Pour un nouveau champ

1. Ajouter le champ dans `MarketData` (models/market.py)
2. Créer une méthode d'extraction dans chaque extracteur
3. Ajouter des tests

## Gestion des corrections manuelles (_manual)

Le pipeline utilise une architecture "triplet" pour les champs sensibles:

```
Champ_auto     → Valeur calculée par l'ETL
Champ_manual   → Correction manuelle (Google Sheets)
Champ          → Valeur finale (= manual si non vide, sinon auto)
```

### Pour corriger une valeur:

1. Modifier le CSV avec suffixe `_manual`
2. Relancer le pipeline
3. La valeur `_manual` écrase la valeur `_auto`

### Exemple:

```csv
Acheteur_auto,Acheteur_manual,Acheteur
"Min Test",,"Min Test"           # Utilise auto
"Min Test","Ministère Défense","Ministère Défense"  # Utilise manual
```

## Commandes de développement

### Lancer les tests

```bash
# Tous les tests
venv/bin/python -m pytest tests/ -v

# Tests unitaires seuls
venv/bin/python -m pytest tests/unit/ -v

# Tests d'intégration
venv/bin/python -m pytest tests/integration/ -v

# Avec couverture
venv/bin/python -m pytest tests/ --cov=ao_etl --cov-report=html
```

### Exécuter le pipeline

```bash
# Extraction complète
venv/bin/python -m ao_etl.cli extract html_ao/ -o rapport.json

# Extraction d'un fichier spécifique
venv/bin/python -c "
from ao_etl.sources.router import extract_for_source
from pathlib import Path
data = extract_for_source(Path('html_ao/mon_fichier.html'))
print(data)
"
```

## Debugging

### Activer les logs détaillés

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Tester un extracteur isolé

```python
from ao_etl.sources.france_marches import FranceMarchesExtractor
from pathlib import Path
from bs4 import BeautifulSoup

filepath = Path('html_ao/mon_fichier.html')
content = filepath.read_text()
soup = BeautifulSoup(content, 'html.parser')

extractor = FranceMarchesExtractor(filepath, soup, content)
data = extractor.extract()

# Inspection
print(f"Titre: {data.title}")
print(f"Notes: {data.extraction_notes}")
```

## Bonnes pratiques

### Extraction

1. **DOM-first**: Privilégier BeautifulSoup avant regex
2. **Fallbacks**: Toujours avoir 2-3 sources de données
3. **Nettoyage**: Utiliser `_clean_text()` systématiquement
4. **Validation**: Rejeter les valeurs suspectes

### Tests

1. **Un test = une assertion**: Un seul cas testé par test
2. **Fixtures**: Utiliser des données réelles ou très proches
3. **Isolation**: Ne pas dépendre d'autres tests
4. **Nommage**: `test_<action>_<condition>_<resultat>`

### Documentation

1. **Docstrings**: Toutes les fonctions publiques
2. **Types**: Annoter avec Python 3.10+
3. **Commentaires**: Expliquer le "pourquoi", pas le "quoi"

## Résolution de problèmes courants

### Référence dupliquée

**Symptôme:** Plusieurs fichiers avec même référence

**Diagnostic:**
```python
# Vérifier si c'est le bug 1838554
if reference == "1838554":
    print("Bug refContrat! Utiliser ID fichier")
```

**Solution:** Utiliser `MarchesOnlineExtractor` qui extrait depuis le nom de fichier

### Titre avec caractères étranges

**Symptôme:** `\u0020` ou `\u00E9` dans les titres

**Diagnostic:**
```python
if "\\u00" in title:
    print("Séquences Unicode non décodées")
```

**Solution:** Utiliser `_decode_unicode_escapes()` dans l'extracteur

### Extraction partielle

**Symptôme:** Champs manquants

**Diagnostic:**
```python
data = extract_for_source(filepath)
if not data.is_complete():
    print(f"Incomplet: {data.completeness_score()}")
    print(f"Notes: {data.extraction_notes}")
```

## Pipeline ETL Unifié v2.0

### Séquence canonique

Le nouveau pipeline principal suit une séquence stricte :

```
DISCOVERY → RECONCILE → EXTRACT → MERGE → VALIDATE → EXPORT
```

### Modules du pipeline

#### `ao_etl/pipeline/discovery.py`
Détection de tous les fichiers HTML source.

- Scanne `html_ao/`
- Classe les fichiers par source (Marchés Online, France Marchés, etc.)
- Détecte les alias et fichiers techniques

#### `ao_etl/pipeline/reconcile.py`
Réconciliation avec le CSV existant.

- Charge le CSV existant
- Associe les fichiers aux entrées existantes
- Identifie nouveaux marchés, orphelins, collisions

#### `ao_etl/pipeline/merge.py`
Fusion et mise à jour.

- Crée les nouvelles lignes CSV
- Met à jour les lignes existantes si nécessaire
- Applique la règle : `final = manual si non vide, sinon auto`

#### `ao_etl/pipeline/validate.py`
Validation qualité.

- Vérifie références uniques
- Vérifie champs critiques
- Calcule taux de complétion

#### `ao_etl/pipeline/export.py`
Export des sorties.

- Génère CSV final
- Génère rapport JSON

### Utilisation

```python
from ao_etl.pipeline import run_pipeline

result = run_pipeline(
    html_dir=Path('html_ao'),
    input_csv=Path('AO.csv'),
    output_csv=Path('AO-final.csv')
)
```

### CLI

```bash
python run_pipeline.py --html-dir html_ao --input AO.csv --output AO-final.csv
```

### Règles métier préservées

- **Marchés Online** : références `MO-XXXX` extraites du nom de fichier (jamais `refContrat`)
- **JOUE** : gestion des alias et doublons
- **France Marchés** : décodage Unicode des champs
- **PLACE/BOAMP** : extraction DOM-first avec fallback regex
- **Triplets** : `_auto / _manual / final` avec priorité manual

### Scripts obsolètes

Les scripts suivants sont remplacés par le pipeline unifié :

- `add_orphans_simple.py` → pipeline intégré
- `fix_orphan_buyers.py` → pipeline intégré
- Scripts ad-hoc d'extraction → extracteurs `ao_etl/sources/`

## Ressources

- Documentation BeautifulSoup: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- pytest: https://docs.pytest.org/
- Architecture ETL: Voir PROJECT_AUDIT.md
