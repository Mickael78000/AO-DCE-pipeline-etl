# Utilitaires partagés pour scripts AO-DCE

Ce dossier contient les utilitaires partagés utilisés par les scripts d'analyse.

## Modules disponibles

### `csv_utils.py` - Manipulation CSV

```python
from utils import read_csv, write_csv, update_csv_rows

# Lecture CSV
rows, fieldnames = read_csv(Path('data/output/fichier.csv'))

# Écriture CSV
write_csv(Path('sortie.csv'), rows, fieldnames)

# Mise à jour avec fonction de transformation
stats = update_csv_rows(
    input_path=Path('input.csv'),
    output_path=Path('output.csv'),
    transform_fn=ma_fonction_transformation,
    new_columns=['nouvelle_colonne']
)
```

### `paths.py` - Gestion des chemins

```python
from utils import get_output_path, get_html_dir, ProjectPaths

# Chemins standards
csv_path = get_output_path('fichier.csv')
html_dir = get_html_dir()

# Configuration personnalisée
paths = ProjectPaths()
input_csv = paths.get_input_csv('AO-completed.csv')
```

### `text.py` - Traitement de texte

```python
from utils import normalize, contains_any, starts_with_any, normalize_keywords

# Normalisation
norm = normalize("Ministère des Armées")  # -> "ministere des armees"

# Recherche de mots-clés
if contains_any(acheteur, ["Ministère", "Direction"]):
    # Match trouvé
    pass

# Recherche avec préfixes
if starts_with_any(acheteur, ["Ville de", "Commune de"]):
    # Match trouvé
    pass

# Normalisation en masse
keywords = normalize_keywords(["Ministère", "Hôpital"])
```

## Utilisation dans un script

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

# Ajouter le dossier parent au path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import read_csv, write_csv, normalize

# ... votre code
```

## Avantages

- **Code DRY** : Pas de duplication des fonctions CSV ou de normalisation
- **Chemins centralisés** : Modification des chemins en un seul endroit
- **Tests facilités** : Utilitaires réutilisables et testables
- **Maintenance** : Corrections à un seul endroit
