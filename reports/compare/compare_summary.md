# Comparaison Legacy vs V2

- Fichiers comparés : **63**
- Date : 2026-05-20T15:01:24

## Vue d'ensemble par champ

| Champ | match | both_empty | only_legacy | only_v2 | diff | Δ (v2 utile) |
|---|---:|---:|---:|---:|---:|---:|
| `source_type` | 26 | 0 | 0 | 0 | 37 | +0 |
| `status` | 13 | 0 | 0 | 0 | 50 | +0 |
| `reference` | 23 | 0 | 17 | 13 | 10 | -4 |
| `title` | 25 | 0 | 14 | 0 | 24 | -14 |
| `buyer` | 22 | 0 | 27 | 0 | 14 | -27 |
| `cpv` | 0 | 39 | 24 | 0 | 0 | -24 |
| `url_source` | 0 | 18 | 0 | 45 | 0 | +45 |
| `location` | 8 | 6 | 2 | 33 | 14 | +31 |
| `procedure_type` | 16 | 0 | 0 | 47 | 0 | +47 |
| `contract_nature` | 13 | 0 | 0 | 50 | 0 | +50 |
| `date_limite` | 23 | 17 | 1 | 22 | 0 | +21 |
| `duree_mois` | 0 | 53 | 10 | 0 | 0 | -10 |
| `estimation_eur` | 0 | 20 | 8 | 35 | 0 | +27 |

> `only_v2` = v2 remplit un champ vide en legacy. `only_legacy` = v2 a perdu une valeur. `diff` = les deux ont une valeur, mais différente.

## Changements de source_type

| Fichier | Legacy | V2 |
|---|---|---|
| 13joue002671162026-2026-mise-disposition-gestion.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue002708922026-2026-fourniture-prestation-service.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue002845752026-2026-marche-prestations-maintenance.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue002850982026-2026-accord-cadre-bons.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue002925532026-2026-marche-public-relatif.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue002929142026-2026-accompagnement-convergence-systemes.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue002939872026-2026-marche-pour-maintenance.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue002946202026-2026-continuite-exploitation-hebergement?q=h%C3%A9bergement web.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue002946822026-2026-renouvellement-maintenance-serveurs.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue003036002026-2026-accord-cadre-infrastructure.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue003085442026-2026-fourniture-solutions-infrastructure.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue003107212026-2026-maintien-condition-operationnelle.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue003228322026-2026-continuite-exploitation-hebergement?q=72200000.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue003237302026-2026-prestations-tierce-maintenance?q=72200000.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue003241312026-2026-prestations-support-maintenance?q=72200000.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue003272002026-2026-accompagnement-extension-itsm?q=72200000.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue003278382026-2026-hisi-hebergement-infogerance?q=72200000.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue003293162026-2026-maintenance-hebergement-developpements?q=72200000.html | FRANCE_MARCHES | BOAMP_XML |
| 13joue003304802026-2026-groupement-commandes-pour?q=72200000.html | FRANCE_MARCHES | BOAMP_XML |
| 37ao26154015290520267275-2026-cadrage-conception-developpement.html | FRANCE_MARCHES | BOAMP_XML |
| 37ao26181552260520267275-2026-prestations-assistance-technique.html | FRANCE_MARCHES | BOAMP_XML |
| 37ao26181581260520263294-2026-prestations-assistance-expertise.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2640079-2026-mise-disposition-adaptation.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2641049-2026-assistance-externe-pour.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2641974-2026-maintien-condition-operationnelle.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2642071-2026-assistance-ingenierie-coordination.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2642106-2026-acquisition-mise-oeuvre.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2642682-2026-renouvellement-maintenance-serveurs.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2643374-2026-refonte-site-internet.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2643609-2026-prestations-services-informatiques.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2644098-2026-prestations-conseil-collecte.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2644226-2026-assistance-maitrise-oeuvre.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2644837-2026-systeme-information-dpsm.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2646966-2026-present-marche-pour?q=72200000.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2647530-2026-missions-infogerance-systemes?q=72200000.html | FRANCE_MARCHES | BOAMP_XML |
| 3boamp2647639-2026-mise-place-outil?q=72200000.html | FRANCE_MARCHES | BOAMP_XML |
| M_3530.html | FRANCE_MARCHES | BOAMP_XML |

## Erreurs d'extraction

Aucune.

## Top fichiers divergents

| Fichier | Nb champs divergents |
|---|---:|
| 3boamp2640079-2026-mise-disposition-adaptation.html | 11 |
| 3boamp2641974-2026-maintien-condition-operationnelle.html | 11 |
| 3boamp2642071-2026-assistance-ingenierie-coordination.html | 11 |
| 13joue002708922026-2026-fourniture-prestation-service.html | 10 |
| 13joue002845752026-2026-marche-prestations-maintenance.html | 10 |
| 13joue002925532026-2026-marche-public-relatif.html | 10 |
| 13joue002946202026-2026-continuite-exploitation-hebergement?q=h%C3%A9bergement web.html | 10 |
| 13joue003107212026-2026-maintien-condition-operationnelle.html | 10 |
| 13joue003228322026-2026-continuite-exploitation-hebergement?q=72200000.html | 10 |
| 26-41049.html | 10 |
| 3boamp2642106-2026-acquisition-mise-oeuvre.html | 10 |
| 3boamp2642682-2026-renouvellement-maintenance-serveurs.html | 10 |
| 3boamp2644098-2026-prestations-conseil-collecte.html | 10 |
| 3boamp2644837-2026-systeme-information-dpsm.html | 10 |
| 3boamp2647530-2026-missions-infogerance-systemes?q=72200000.html | 10 |
