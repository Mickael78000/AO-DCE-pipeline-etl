# Méthodologie Triplets _auto / _manual / _final — Implémentation complète

## Date
2026-05-11

## Objectif
Séparer les valeurs automatiques (ETL) des corrections manuelles (Google Sheets) pour éviter que les re-runs n'écrasent les corrections utilisateur.

---

## Architecture implémentée

### Schéma de colonnes

Pour chaque champ sensible, un **triplet** :

```
<Champ>_auto    → Valeur calculée par l'ETL (écrasable)
<Champ>_manual  → Correction manuelle (PRÉSERVÉE)
<Champ>         → Valeur finale utilisée (= manual si non vide, sinon auto)
```

### Champs concernés

| Champ | Colonnes créées |
|-------|-----------------|
| Acheteur | `Acheteur_auto`, `Acheteur_manual`, `Acheteur` |
| Localisation | `Localisation_auto`, `Localisation_manual`, `Localisation` |
| Date limite | `Date_limite_auto`, `Date_limite_manual`, `Date limite de remise des offres` |
| Estimation | `Estimation_auto`, `Estimation_manual`, `Estimation du marché` |

### Ordre dans COLUMNS (config.py)

```python
# Pour chaque champ: _auto, _manual, _final
"Acheteur_auto", "Acheteur_manual", "Acheteur", "Acheteur_clean",
"Localisation_auto", "Localisation_manual", "Localisation", "Localisation_clean",
"Date_limite_auto", "Date_limite_manual", "Date limite de remise des offres",
"Estimation_auto", "Estimation_manual", "Estimation du marché",
```

---

## Modifications apportées

### 1. `config.py` — Nouveau schéma COLUMNS

- **Remplacement** de la liste `COLUMNS` avec les triplets
- **Organisation** : `_auto` → `_manual` → `_final` → `_clean`
- **Documentation** inline avec commentaires explicatifs

### 2. `transform.py` — Logique métier

#### Nouvelles fonctions :

**`TRIPLET_FIELDS`** — Mapping des champs triplets :
```python
TRIPLET_FIELDS = {
    "Acheteur": ("Acheteur_auto", "Acheteur_manual", "Acheteur"),
    "Localisation": ("Localisation_auto", "Localisation_manual", "Localisation"),
    "Date_limite": ("Date_limite_auto", "Date_limite_manual", "Date limite..."),
    "Estimation": ("Estimation_auto", "Estimation_manual", "Estimation du marché"),
}
```

**`apply_manual_overrides(row)`** — Règle de priorité :
```python
for auto_col, manual_col, final_col in TRIPLET_FIELDS.values():
    manual_val = row.get(manual_col, "").strip()
    auto_val = row.get(auto_col, "").strip()
    row[final_col] = manual_val if manual_val else auto_val
```

**`get_auto_column(field)`** — Helper pour mapper un champ vers sa colonne `_auto`.

#### Fonctions modifiées :

**`merge_into_row()`** — Écrit dans `_auto` au lieu de la colonne finale :
```python
target_field = get_auto_column(field) or field  # Redirige vers _auto si triplet
```

**`remap_legacy_columns()`** — Migration + préservation :
- Migre les anciennes colonnes vers `_auto` (si pas de `_manual`)
- Préserve les valeurs `_manual` existantes
- Appelle `apply_manual_overrides()` à la fin
- Normalise à partir des valeurs finales

**`build_new_row()`** — Pour nouvelles lignes HTML :
- Mapping explicite des champs extraits vers `_auto`
- Appel de `apply_manual_overrides()` (final = auto car manual vide)
- Normalisation des valeurs finales

### 3. `main.py` — Orchestration

#### Modification du pipeline principal :

```python
# Après merge_into_row()
row, changes = transform.merge_into_row(row, html_cache[html_path])

transform.apply_manual_overrides(row)  # ← AJOUTÉ

# Recalcul des normalisations avec valeurs finales
row["Acheteur_clean"] = normalize.clean_acheteur(row.get("Acheteur", ""))
row["Localisation_clean"] = normalize.clean_localisation(
    row.get("Localisation", ""), row.get("Acheteur", "")
)
```

#### Statistiques des overrides :

```python
manual_overrides = {
    "Acheteur": sum(1 for r in out_rows if r.get("Acheteur_manual", "").strip()),
    "Localisation": sum(1 for r in out_rows if r.get("Localisation_manual", "").strip()),
    ...
}
```

### 4. `load.py` — Rapport enrichi

#### Documentation dans le rapport :

```markdown
## Documentation champs

### Architecture triplet (_auto / _manual / _final)

- **`*_auto`** : Valeur calculée automatiquement par l'ETL.
- **`*_manual`** : Correction manuelle saisie dans Google Sheets. **Jamais écrasée.**
- **`*_final`** (sans suffixe) : Valeur utilisée comme référence.

### Workflow recommandé

1. Lancer l'ETL pour remplir les colonnes `*_auto`.
2. Ouvrir le CSV dans Google Sheets.
3. Corriger directement dans les colonnes `*_manual`.
4. Relancer l'ETL : les valeurs `*_manual` sont préservées et prises en priorité.
```

---

## Test de validation

### Scénario testé

1. **Premier run ETL** : Extraction automatique
   - `Acheteur_auto = "RESA (opérateur d'énergie...)"`
   - `Acheteur_manual = ""`
   - `Acheteur = "RESA (opérateur d'énergie...)"` (= auto)

2. **Correction manuelle** dans Google Sheets (simulée) :
   - `Acheteur_manual = "RESA - Correction Test"`

3. **Second run ETL** :
   - `Acheteur_auto` recalculé avec nouvelle valeur HTML
   - `Acheteur_manual` **préservé** : `"RESA - Correction Test"`
   - `Acheteur` = `"RESA - Correction Test"` (= manual prioritaire)

### Résultat

```
✅ SUCCÈS: Acheteur_final = valeur manuelle
Total lignes avec Acheteur_manual: 1
```

Le rapport affiche :
```
## Corrections manuelles (Google Sheets)
- Acheteur_manual    : 1
- Localisation_manual: 1
- Date_limite_manual : 0
- Estimation_manual  : 0
```

---

## Workflow utilisateur (Google Sheets)

### Import
1. Ouvrir Google Sheets
2. Fichier → Importer → `AO-completed.csv`

### Correction
**✅ Faire** : Modifier uniquement les colonnes `*_manual`
- `Acheteur_manual`
- `Localisation_manual`
- `Date_limite_manual`
- `Estimation_manual`

**❌ Ne pas faire** : Modifier les colonnes finales (`Acheteur`, `Localisation`, etc.) ou `_auto`

### Export
1. Fichier → Télécharger → CSV
2. Remplacer `/home/michka/Documents/0-AO-DCE/AO-completed.csv`

### Relance
```bash
venv/bin/python -m ao_etl.main
```

---

## Fichiers créés/modifiés

| Fichier | Action | Description |
|---------|--------|---------------|
| `config.py` | Modifié | Nouveau schéma COLUMNS avec triplets |
| `transform.py` | Modifié | Logique `apply_manual_overrides`, `TRIPLET_FIELDS`, migration legacy |
| `main.py` | Modifié | Appel `apply_manual_overrides`, stats overrides |
| `load.py` | Modifié | Documentation architecture dans le rapport |
| `README_WORKFLOW.md` | **Créé** | Guide utilisateur complet |
| `METHODOLOGY_SUMMARY.md` | **Créé** | Ce document — résumé technique |

---

## Contraintes respectées

- [x] **Préservation** : `*_manual` jamais écrasé par l'ETL
- [x] **Migration** : Anciennes colonnes migrées vers `_auto`
- [x] **Règle** : `_final = _manual` si non vide, sinon `_auto`
- [x] **Traçabilité** : Rapport compte les overrides manuels
- [x] **Documentation** : Guide utilisateur + documentation inline
- [x] **Tests** : Scénario de correction manuelle validé

---

## Exemple de CSV généré (structure)

```csv
Référence,Acheteur_auto,Acheteur_manual,Acheteur,Acheteur_clean,Localisation_auto,Localisation_manual,Localisation,...
AO-123,"Valeur auto","","Valeur auto","Clean auto","Paris","","Paris",...
AO-456,"Valeur auto","Correction","Correction","Clean correct.","Paris","Lyon (69)","Lyon (69)",...
```

**Ligne 1** : Sans correction (final = auto)
**Ligne 2** : Avec correction (final = manual)
