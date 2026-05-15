# Checklist QA — ETL AO (Appels d'Offres)

**Version** : 2.0  
**Date** : 2026-05-11  
**Contexte** : ETL `ao_etl` avec schéma triplets `_auto/_manual/_final`  
**Jeu de référence** : 61 lignes CSV + 38 fichiers HTML

---

## Guide rapide : Quand exécuter quoi ?

| Niveau | Quand l'exécuter | Durée estimée | Section |
|--------|------------------|---------------|---------|
| 🔥 **Smoke** | À chaque run ETL ou import de lot | 2 min | [1. Smoke Tests](#1-smoke-tests--à-chaque-run) |
| 🎯 **Régression** | Quand tu modifies parsing, extract, normalize | 10 min | [2. Tests de Régression](#2-tests-de-régression--si-modif-parsing) |
| 🔬 **Complet** | Avant livraison, refactor majeur, nouveau type de source | 30 min | [3. Tests Complets](#3-tests-complets--avant-livraison) |
| 📊 **Validation** | À la fin de chaque session de test | 5 min | [4. Tableaux de Bord](#4-tableaux-de-bord--validation-finale) |

---

## 1. Smoke Tests — À chaque run

> **Objectif** : Vérifier en 2 minutes que l'ETL tourne et produit un résultat cohérent.

### 1.1 Exécution et sortie

| # | Test | Commande/Résultat | Critère |
|---|------|-------------------|---------|
| 1.1 | Exit code 0 | `venv/bin/python -m ao_etl.main; echo $?` | Affiche `0` |
| 1.2 | Pas d'exception Python | Dernier log = `INFO Rapport exporté` | Pas de traceback |
| 1.3 | CSV généré | `test -f AO-completed.csv && echo "OK"` | `OK` |
| 1.4 | Rapport généré | `test -f rapport-extraction.md && echo "OK"` | `OK` |

### 1.2 Intégrité structurelle

| # | Test | Commande | Résultat attendu |
|---|------|----------|------------------|
| 1.5 | Nombre de lignes | `wc -l < AO-completed.csv` | `62` (header + 61) |
| 1.6 | Colonnes triplets présentes | `head -1 AO-completed.csv | tr ',' '\n' | grep -E "_(auto|manual)$" | wc -l` | `8` |
| 1.7 | Pas de colonnes dupliquées | `head -1 AO-completed.csv | tr ',' '\n' | sort | uniq -d` | Vide |
| 1.8 | Encodage UTF-8 | `file -i AO-completed.csv` | `charset=utf-8` |

### 1.3 Cohérence métier (rapide)

| # | Test | Commande | Seuil |
|---|------|----------|-------|
| 1.9 | Matched cohérent | `grep -c ',matched,' AO-completed.csv` | Entre 42 et 46 |
| 1.10 | Unmatched cohérent | `grep -c ',unmatched,\|,$' AO-completed.csv | head -60` | Entre 15 et 19 |
| 1.11 | Pas de régression localisation | `csvcut -c Localisation_clean AO-completed.csv | tail -n +2 | grep -v '^$' | wc -l` | ≥ 45 |
| 1.12 | Pas de faux positif évident | `grep -c "Date de clotûre" AO-completed.csv` | `0` |

---

## 2. Tests de Régression — Si modif parsing

> **Objectif** : Vérifier que les changements dans `extract.py`, `normalize.py`, `clean_html.py` ou `detect.py` n'ont pas cassé l'existant.

### 2.1 Alignement champs dérivés

> **⚠️ IMPORTANT** : `Acheteur_clean` et `Localisation_clean` sont dérivés des valeurs **finales** (`Acheteur`, `Localisation`), pas des valeurs `_auto`. Si une correction manuelle est active, la normalisation doit s'appliquer à la valeur manuelle.

| # | Test | Vérification | Commande de contrôle |
|---|------|--------------|---------------------|
| 2.1 | `Acheteur_clean` dépend de `Acheteur` (final) | Lire code : `normalize.clean_acheteur(row.get("Acheteur"))` | `grep -n "clean_acheteur" ao_etl/main.py ao_etl/transform.py` |
| 2.2 | `Localisation_clean` dépend de `Localisation` (final) | Lire code : `normalize.clean_localisation(row.get("Localisation"), ...)` | `grep -n "clean_localisation" ao_etl/main.py ao_etl/transform.py` |
| 2.3 | Pas de normalisation sur `_auto` directement | Vérifier absence de `clean_*(*_auto)` dans le code | `grep -rn "clean_.*_auto" ao_etl/` → doit être vide |

### 2.2 Stabilité extraction champs critiques

**Prérequis** : Avoir une version de référence du CSV avant modification.

| # | Champ | Test | Tolérance |
|---|-------|------|-------------|
| 2.4 | `Référence` | Comparer liste des refs avant/après | 0 référence perdue, 0 nouvelle référence dupliquée |
| 2.5 | `Acheteur_auto` | Comparer valeurs `_auto` avant/après | Variations expliquées par changement de code ou HTML |
| 2.6 | `Localisation_auto` | Idem | ⚠️ Attention aux faux positifs qui doivent disparaître |
| 2.7 | `Date_limite_auto` | Idem | Format stable JJ/MM/AAAA |
| 2.8 | `Estimation_auto` | Idem | Notation stable (€, espaces) |

### 2.3 Gestion des faux positifs (ciblée)

| # | Anti-régression | Test | Résultat attendu |
|---|---------------|------|------------------|
| 2.9 | Pas de "Date de clotûre" | `grep "Date de clotûre" AO-completed.csv` | Vide |
| 2.10 | Pas de "géographique, nature" | `grep "géographique, nature" AO-completed.csv` | Vide |
| 2.11 | Pas de "La consultation comporte" | `grep "La consultation comporte" AO-completed.csv` | Vide |
| 2.12 | Pas d'artefact "M (NN)" | `grep -E "M\s*\(\d{2}\)" AO-completed.csv` | Vide |

### 2.4 Parsing spécifique (si modifié)

| Module modifié | Tests à ajouter | Validation |
|----------------|-----------------|------------|
| `clean_html.py` | Vérifier `len(text)` avant/après sur 3 fichiers | Réduction > 20% sans perte d'info métier |
| `extract.py` | Tester regex modifiée sur cas positifs et négatifs | Cas positifs : extraits / Cas négatifs : rejetés |
| `normalize.py` | Tester `clean_localisation()` avec valeurs manuelles | Normalisation appliquée à valeur finale, pas source |
| `detect.py` | Vérifier `site_type` détecté sur tous les fichiers | 100% détection correcte |

---

## 3. Tests Complets — Avant livraison

> **Objectif** : Validation exhaustive avant mise en production ou refactor majeur.

### 3.1 Extraction HTML — Profondeur

| Famille | Test | Critère de succès | Priorité |
|---------|------|-------------------|----------|
| Nettoyage | Scripts supprimés | `soup.find('script')` = `None` sur 10 fichiers aléatoires | P1 |
| Nettoyage | Styles supprimés | `soup.find('style')` = `None` | P1 |
| Nettoyage | JSON-LD supprimé | Pas de `application/ld+json` dans texte extrait | P2 |
| Parsing | Pas d'exception | 0 exception sur les 38 fichiers | P0 |
| Parsing | Fallback body | Si pas de `<main>` ni `<article>`, fallback `<body>` fonctionne | P1 |

### 3.2 Champs métiers — Cas limites

| Champ | Cas testé | Comportement attendu |
|-------|-----------|----------------------|
| `Référence` | Doublon détecté | Les deux lignes conservées, `match_status` différent si applicable |
| `Référence` | Fichier sans référence extractible | Fallback sur nom de fichier, note dans `extraction_notes` |
| `Acheteur` | Association non classifiable | `Fonction publique` vide, note "non classifiable" |
| `Acheteur` | Multi-entités | Valeur conservée telle quelle, pas de troncature |
| `Localisation` | "France entière" | `Localisation_clean` = "France entière" |
| `Localisation` | International (Bruxelles, Genève) | Accepté tel quel, pas de normalisation forcée France |
| `Date limite` | Format ISO "2026-05-29" | Converti en "29/05/2026" |
| `Date limite` | Absence de date | Vide, `review_needed = oui`, note "Date non extraite" |
| `Durée` | Label seul "Durée du marché" | Rejeté, champ vide |
| `Estimation` | Valeur aberrante textuelle | Rejetée par `_BAD_ESTIM_RE` |
| `Estimation` | Fourchette | Extraite avec contexte ou première valeur |

### 3.3 Triplets auto/manual/final — Scénarios complets

| Scénario | Procédure | Vérifications |
|----------|-----------|---------------|
| **Premier run** | Effacer `*_manual`, lancer ETL | `*_auto` rempli, `*_manual` vide, `*` = `*_auto` |
| **Correction manuelle** | Remplir `Acheteur_manual` dans CSV, relancer | `Acheteur` = valeur manuelle, `Acheteur_auto` inchangé |
| **HTML mis à jour** | Modifier HTML source, relancer ETL | `Acheteur_auto` = nouvelle valeur, `Acheteur` reste = manuelle |
| **Suppression correction** | Effacer `Acheteur_manual`, relancer | `Acheteur` = `Acheteur_auto` (fallback) |
| **Correction partielle** | Remplir seulement `Localisation_manual` | `Localisation` = manuel, `Acheteur` = auto |
| **Migration legacy** | Tester avec CSV ancien schéma (sans `_auto`) | Migration automatique vers `_auto`, préservation valeurs |
| **Espaces uniquement** | `Acheteur_manual = "   "` | Considéré vide, `Acheteur` = `Acheteur_auto` |

### 3.4 Google Sheets — Cycle complet

| Étape | Test | Validation |
|-------|------|------------|
| Import | UTF-8 conservé | Éditer cellule avec "Électricité — €", vérifier affichage |
| Import | Colonnes triplets visibles | `Acheteur_auto`, `Acheteur_manual`, `Acheteur` présentes |
| Correction | Modification `_manual` uniquement | Éditer `Acheteur_manual`, ne pas toucher autres colonnes |
| Export | Séparateur virgule | Ouvrir CSV exporté, vérifier `,` comme séparateur |
| Export | Caractères spéciaux | Vérifier `"Électricité — €"` bien encodé |
| Re-import | Persistences corrections | Réimporter, vérifier `Acheteur_manual` toujours présent |
| Second run ETL | Priorité manuelle | `Acheteur` = valeur manuelle malgré `Acheteur_auto` recalculé |

---

## 4. Tableaux de Bord — Validation finale

> **Objectif** : Indicateurs chiffrés stricts pour valider la qualité de la sortie.

### 4.1 Dashboard Run ETL

| Métrique | Cible | Alerte Rouge | Commande |
|----------|-------|--------------|----------|
| Lignes CSV | 61 | ≠ 61 | `tail -n +2 AO-completed.csv | wc -l` |
| Matched | 44 | < 40 ou > 50 | `grep -c ',matched,' AO-completed.csv` |
| Unmatched | 17 | > 25 | `grep -c ',unmatched,\|,$' AO-completed.csv` |
| Nouvelles lignes | 0 | > 2 | `grep -c ',new,' AO-completed.csv` |
| HTML parsés | 38 | ≠ 38 | `ls html_ao/*.html | wc -l` |

### 4.2 Dashboard Qualité Extraction

| Métrique | Cible | Alerte Rouge | Commande |
|----------|-------|--------------|----------|
| Acheteur_clean non vide | 57 | < 52 | `csvcut -c Acheteur_clean AO-completed.csv | tail -n +2 | grep -v '^$' | wc -l` |
| Localisation_clean non vide | 48 | < 42 | `csvcut -c Localisation_clean AO-completed.csv | tail -n +2 | grep -v '^$' | wc -l` |
| Faux positifs localisation | 0 | > 0 | `grep -c "Date de clotûre\|géographique, nature\|consultation comporte" AO-completed.csv` |
| Review needed | ~17 | > 22 | `grep -c 'review_needed.*oui' AO-completed.csv` |
| Exceptions documentées | 3 | > 3 | `grep -E "DGFIP-DRS-2500077|3boamp2642106|13joue002889082026" AO-completed.csv | wc -l` |

### 4.3 Dashboard Overrides Manuels

| Métrique | Source | Commande |
|----------|--------|----------|
| Acheteur_manual non vide | CSV | `csvcut -c Acheteur_manual AO-completed.csv | tail -n +2 | grep -v '^$' | wc -l` |
| Localisation_manual non vide | CSV | `csvcut -c Localisation_manual AO-completed.csv | tail -n +2 | grep -v '^$' | wc -l` |
| Date_limite_manual non vide | CSV | `csvcut -c Date_limite_manual AO-completed.csv | tail -n +2 | grep -v '^$' | wc -l` |
| Estimation_manual non vide | CSV | `csvcut -c Estimation_manual AO-completed.csv | tail -n +2 | grep -v '^$' | wc -l` |
| **Total overrides** | Rapport | `grep "Acheteur_manual.*:" rapport-extraction.md` |

### 4.4 Dashboard Cohérence Triplets

> Vérifier que la règle `final = manual si non vide sinon auto` est respectée.

```bash
# Script de validation rapide
python3 << 'EOF'
import csv
from pathlib import Path

csv_path = Path('AO-completed.csv')
errors = []

with open(csv_path, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        ref = row.get('Référence', '?')
        
        # Vérifier chaque triplet
        triplets = [
            ('Acheteur_auto', 'Acheteur_manual', 'Acheteur'),
            ('Localisation_auto', 'Localisation_manual', 'Localisation'),
            ('Date_limite_auto', 'Date_limite_manual', 'Date limite de remise des offres'),
            ('Estimation_auto', 'Estimation_manual', 'Estimation du marché'),
        ]
        
        for auto, manual, final in triplets:
            auto_val = row.get(auto, '').strip()
            manual_val = row.get(manual, '').strip()
            final_val = row.get(final, '').strip()
            
            expected = manual_val if manual_val else auto_val
            if final_val != expected:
                errors.append(f"{ref}: {final}={final_val!r}, attendu={expected!r} (manual={manual_val!r}, auto={auto_val!r})")

if errors:
    print(f"❌ {len(errors)} erreurs de cohérence triplet:")
    for e in errors[:5]:
        print(f"  - {e}")
else:
    print("✅ Tous les triplets sont cohérents")
EOF
```

---

## 5. Ordre d'Exécution Recommandé

### 5.1 Workflow "Run quotidien" (2 min)

```bash
# 1. Exécution
venv/bin/python -m ao_etl.main

# 2. Smoke tests (section 1)
# Vérifier visuellement les 4 points de la section 1.1

# 3. Dashboard rapide (section 4.1)
# Vérifier : 61 lignes, ~44 matched, ~17 unmatched
```

### 5.2 Workflow "Après modif parsing" (15 min)

```bash
# 1. Sauvegarder version de référence
cp AO-completed.csv AO-completed-ref.csv

# 2. Appliquer modifications code
# ...

# 3. Exécuter ETL
venv/bin/python -m ao_etl.main

# 4. Tests de régression (section 2)
# - Alignement champs dérivés (2.1-2.3)
# - Stabilité champs critiques (2.4-2.8)
# - Faux positifs (2.9-2.12)

# 5. Dashboard qualité (section 4.2)
# - Acheteur_clean ≥ 52
# - Localisation_clean ≥ 42
# - Faux positifs = 0

# 6. Si OK : remplacer référence
# Si KO : git checkout + investiguer
```

### 5.3 Workflow "Livraison / Refactor majeur" (45 min)

```bash
# 1. Tests complets section 3
# 3.1 : Extraction HTML profondeur
# 3.2 : Champs métiers cas limites
# 3.3 : Triplets scénarios complets
# 3.4 : Google Sheets cycle complet

# 2. Tous les dashboards section 4
# 4.1 : Run ETL
# 4.2 : Qualité extraction
# 4.3 : Overrides manuels
# 4.4 : Cohérence triplets (script Python)

# 3. Validation finale
# Tous les indicateurs dans les seuils verts
```

---

## Annexes

### A. Cas documentés non corrigibles (référence)

| Référence | Problème | Statut attendu | Vérification |
|-----------|----------|----------------|--------------|
| DGFIP-DRS-2500077 | URL vide (XML BOAMP sans lien HTTPS) | `URL source HTTPS` = vide | `grep "DGFIP-DRS-2500077" AO-completed.csv | cut -d',' -f21` = vide |
| 3boamp2642106 | FP vide (Association) | `Fonction publique` = vide | `grep "3boamp2642106" AO-completed.csv | cut -d',' -f6` = vide |
| 13joue002889082026 | FP vide (Association) | `Fonction publique` = vide | `grep "13joue002889082026" AO-completed.csv | cut -d',' -f6` = vide |

### B. Commandes utilitaires

```bash
# Extraction rapide d'une valeur
ref="3boamp2639793-2026"
csvcut -c Acheteur,Acheteur_manual,Acheteur_auto AO-completed.csv | csvgrep -c Acheteur -m "$ref"

# Diff entre deux runs
diff <(csvcut -c Référence,Localisation_auto AO-completed-ref.csv | sort) \
     <(csvcut -c Référence,Localisation_auto AO-completed.csv | sort)

# Liste des overrides actifs
csvcut -c Référence,Acheteur_manual,Localisation_manual AO-completed.csv | csvgrep -c Acheteur_manual -m "." | head -10
```

### C. Matrice de décision "Quel test lancer ?"

| Situation | Tests obligatoires | Tests recommandés |
|-----------|-------------------|-------------------|
| Run quotidien sans modif | Smoke (§1) | Dashboard §4.1 |
| Modif `config.py` (chemins) | Smoke (§1) | Dashboard §4.1, §4.3 |
| Modif `clean_html.py` | Smoke (§1) + Régression §2.4 (nettoyage) | Complet §3.1 |
| Modif `extract.py` | Régression §2.4 (parsing) + §2.2 | Complet §3.2 |
| Modif `normalize.py` | Régression §2.1 (alignement) + §2.3 | Complet §3.2 (localisation) |
| Modif `transform.py` | Régression §2.1 + Dashboard §4.4 | Complet §3.3 (triplets) |
| Modif `main.py` | Smoke (§1) + Dashboard §4.1, §4.2 | Régression complète |
| Nouveau lot HTML | Smoke (§1) + Dashboard §4.1 | Régression §2.2 |
| Import Google Sheets | Smoke (§1) + Dashboard §4.3 | Régression §2.1 + Complet §3.4 |
| Livraison client | **Tous les tests** §1-§4 | Validation manuelle échantillon |

---

**Checklist validée** : Cette structure en 4 niveaux (Smoke → Régression → Complet → Dashboard) permet de choisir rapidement la profondeur de test adaptée au contexte.
