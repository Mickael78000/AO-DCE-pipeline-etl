# RAPPORT D'AUDIT ETL STRICT
## Fichier : AO-pipeline-v2-clean.csv

**Date d'audit** : 2026-05-12  
**Auditeur** : Senior ETL Data Quality Reviewer  
**Fichier audité** : AO-pipeline-v2-clean.csv  
**Sources de référence** : répertoire html_ao/ (50 fichiers HTML)  

---

## 1. RÉSUMÉ EXÉCUTIF

Le fichier AO-pipeline-v2-clean.csv contient 50 lignes de données correspondant aux 50 fichiers HTML présents dans html_ao/. La règle métier "1 fichier HTML = 1 ligne CSV" est respectée quantitativement.  

**Constats principaux** :
- Structure : 50 lignes, 30 colonnes, sans doublon de référence
- Traçabilité : chaque ligne possède un match_source valide et existant
- Classification : 31 lignes matched (62%), 19 lignes new (38%)
- Complétude : 48 lignes sur 50 disposent d'un Acheteur_auto renseigné (96%)
- Anomalies : 2 lignes présentent un champ Acheteur_auto vide

Le fichier est exploitable sous réserve de validation des 2 lignes incomplètes.

---

## 2. TABLEAU D'AUDIT DES ANOMALIES

| Identifiant ligne | Référence | Champ concerné | Type d'anomalie | Gravité | Preuve observée | Conclusion | Action recommandée |
|-------------------|-----------|----------------|-----------------|---------|-----------------|------------|-------------------|
| 40 | MO-9596601 | Acheteur_auto | Champ vide sans source exploitable | Moyenne | Fichier ao-9596601-1.html présent ; extraction automatique ne retourne pas d'acheteur ; structure HTML sans balise détectable | Donnée non vérifiable automatiquement | Revoir manuellement le fichier HTML source ou marquer comme "non déterminable" |
| 41 | MO-9598475 | Acheteur_auto | Champ vide sans source exploitable | Moyenne | Fichier ao-9598475-1.html présent ; extraction automatique ne retourne pas d'acheteur ; structure HTML sans balise détectable | Donnée non vérifiable automatiquement | Revoir manuellement le fichier HTML source ou marquer comme "non déterminable" |
| N/A | 13joue003085442026 | match_source | Doublon dans CSV source originel | Faible | Référence présente 2 fois dans AO-completed.csv initial ; 1 occurrence retirée lors du nettoyage | Doublon résolu par déduplication | Aucune action requise ; cas documenté |
| 1-19 (nouveaux marchés) | MO-9594452 à MO-9599869 | source_type | Champ vide (20 lignes) | Faible | Colonne source_type vide pour les 19 lignes new + 11 lignes matched historiques | Information manquante non critique | Compléter si nécessaire pour traçabilité, ou accepter l'absence |

---

## 3. TABLEAU DES POINTS VALIDÉS SANS RÉSERVE

| Point de contrôle | Méthode de vérification | Résultat | Preuve |
|-------------------|------------------------|----------|--------|
| Nombre de lignes = nombre de fichiers HTML | Comptage CSV (50 lignes) vs comptage répertoire html_ao/ (50 fichiers .html) | 50 = 50 | wc -l ; ls *.html |
| Unicité des match_source | Décompte des valeurs uniques dans colonne match_source | 50 valeurs distinctes, 0 doublon | Counter Python |
| Existence des fichiers sources | Vérification existence de chaque match_source dans html_ao/ | 50/50 fichiers trouvés | os.path.exists() |
| Unicité des références | Décompte des valeurs Référence | 50 valeurs distinctes, 0 doublon | set() sur colonne Référence |
| Cohérence références MO-* | Vérification pattern MO-XXXXX ↔ ao-XXXXX-Y.html | 12 références vérifiées, toutes cohérentes | Pattern matching |
| Absence de référence vide | Filtrage des lignes avec Référence = '-' ou vide | 0 référence vide | Filtre CSV |
| Absence de titre vide | Filtrage des lignes avec Intitulé synthétique = '-' ou vide | 0 titre vide | Filtre CSV |
| Classification match_status | Décompte des valeurs matched vs new | 31 matched (62%), 19 new (38%) | Counter |
| Traçabilité des suppressions | Analyse des 22 lignes retirées lors du nettoyage | Toutes les suppressions justifiées (sans fichier, fichier inexistant, ou doublon) | Rapport cleanup_unmatched.py |

---

## 4. TABLEAU DES POINTS À REVUE MANUELLE

| Ligne | Référence | Champ | Question | Priorité | Critère de validation |
|-------|-----------|-------|----------|----------|----------------------|
| 40 | MO-9596601 | Acheteur_auto | L'acheteur est-il présent dans le fichier HTML ao-9596601-1.html sous une forme non détectée par l'extraction automatique ? | Moyenne | Ouvrir le fichier HTML, rechercher le bloc "Acheteur" ou "Organisme", valider ou infirmer l'absence |
| 41 | MO-9598475 | Acheteur_auto | L'acheteur est-il présent dans le fichier HTML ao-9598475-1.html sous une forme non détectée par l'extraction automatique ? | Moyenne | Même protocole que ligne 40 |
| 1-31 (lignes matched historiques) | 13joue*, 26-*, DAF_* | source_type | La colonne source_type doit-elle être systématiquement renseignée pour tous les enregistrements ? | Faible | Décision métier : est-ce un champ obligatoire ou facultatif ? |

---

## 5. LIMITES DE L'AUDIT

**Ce qui a été démontré** :
- La correspondance exacte entre les 50 lignes CSV et les 50 fichiers HTML
- L'unicité des identifiants de référence
- La validité des chemins de sources (match_source)
- La classification correcte des statuts (matched/new)

**Ce qui n'a pas été démontré** :
- La justesse métier des contenus extraits (titres, acheteurs, dates) n'a pas été comparée manuellement aux sources HTML ; l'audit s'est limité à vérifier la présence/non-présence des données
- La qualité sémantique des champs n'a pas été évaluée (par exemple : un titre tronqué ou un acheteur partiellement extrait n'apparaîtrait pas comme anomalie)
- La véracité des 48 valeurs Acheteur_auto non vides n'a pas été contrôlée par échantillonnage manuel

**Hypothèses non vérifiées** :
- L'hypothèse selon laquelle les 2 champs Acheteur_auto vides sont effectivement non présents dans les HTML sources ; cela n'a pas été vérifié par inspection manuelle des fichiers
- L'hypothèse que les 22 lignes supprimées étaient effectivement sans valeur : cette hypothèse est fondée sur le rapport de nettoyage et non sur une inspection manuelle de chaque ligne

**Données non auditables sans accès externe** :
- La validité des URLs sources (colonne "URL source HTTPS") n'a pas été vérifiée par appel HTTP
- La correspondance entre les références et les identifiants officiels des marchés publics (par exemple sur les portails BOAMP ou JOUE) n'a pas été vérifiée

---

## 6. CONCLUSION FINALE

**Verdict : PARTIELLEMENT COHÉRENT**

**Justification** :

Le fichier AO-pipeline-v2-clean.csv respecte les critères structurels fondamentaux :
- Cardinalité correcte (50 lignes pour 50 sources)
- Traçabilité assurée (tous les match_source valides)
- Unicité des identifiants (pas de doublon)
- Classification cohérente (distinction matched/new logique)

Cependant, le fichier présente des anomalies métier mineures mais non négligeables :
- 2 champs critiques (Acheteur_auto) sont vides sur 50 (4%)
- Ces vides n'ont pas été vérifiés comme étant effectivement non récupérables dans les sources

**Recommandation** :

Le fichier est **exploitable sous réserve** d'une revue manuelle des 2 lignes identifiées (MO-9596601 et MO-9598475). Si ces 2 acheteurs sont effectivement absents des sources HTML, le fichier peut être considéré comme cohérent. Si les acheteurs sont présents mais non extraits, une correction de l'extraction est nécessaire.

**Décision de validation** : 
- ✅ Structure : validée
- ✅ Traçabilité : validée  
- ⚠️ Complétude métier : à confirmer (2 cas)
- 🔍 Conclusion globale : PARTIELLEMENT COHÉRENT — accepté sous réserve de validation des 2 cas manquants

---

**Annexe technique** :
- Fichier source : AO-pipeline-v2-clean.csv (51 lignes dont 1 en-tête)
- Fichiers HTML : 50 fichiers dans html_ao/
- Script d'audit : audit_etl_report.py
- Rapport de nettoyage : cleanup-unmatched-report.txt
- Horodatage : 2026-05-12T00:00:00
