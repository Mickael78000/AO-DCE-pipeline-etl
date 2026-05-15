# Rapport final de clôture — 2026-05-08 02:32

## Résumé

| Indicateur | Valeur |
|---|---|
| Lignes CSV totales | 61 |
| Lignes matchées avec HTML | 42 |
| Lignes sans HTML (unmatched) | 17 |
| Nouvelles lignes créées depuis HTML | 2 |

## Contrôle qualité — lignes matchées

| Indicateur | Résultat | Statut |
|---|---|---|
| URL source HTTPS manquante | 1 | Tracée dans `extraction_notes` (structurel) |
| Date limite manquante | 0 | ✓ |
| Fonction publique manquante | 2 | Non classifiable — tracée dans `extraction_notes` |
| Type d'AO manquant | 0 | ✓ |
| Acheteur manquant | 0 | ✓ |
| Localisation manquante | 0 | ✓ |
| Estimation manquante | 13 | Absent du HTML source — non inventé |
| Notes obsolètes | 0 | ✓ |
| Estimations format Euro/EUR | 0 | ✓ |

## Exceptions tracées

### 1. URL source HTTPS manquante — 1 cas structurel

**`DGFIP-DRS-2500077`** (`26-41049.html`)  
Fichier XML BOAMP brut sans balise `canonical`, `og:url` ni lien `<a>` HTTPS vers un domaine d'avis connu.  
URL non récupérable par parsing.  
Note : *"URL source absente : fichier 26-41049.html est un XML BOAMP sans lien HTTPS exploitable"*

### 2. Fonction publique non classifiable — 2 cas

**`3boamp2642106`** et **`13joue002889082026`** — Acheteur : Association ASF Vacances (loi 1901)  
Catégorisée "Loisirs, culture et culte" par le BOAMP. Non classifiable parmi Etat / Territoriale / Hospitalière.  
Champ laissé vide. Note dans `extraction_notes`.

### 3. Estimation absente du HTML — 13 cas

Aucune valeur estimée dans le HTML source. Aucune valeur inventée.

- `13joue002671162026` — `13joue002671162026-2026-mise-disposition-gestion.html`
- `3boamp2641974` — `3boamp2641974-2026-maintien-condition-operationnelle.html`
- `36parisien1157695` — `36parisien1157695-2026-infogerance-systeme-information.html`
- `13joue002695002026` — `13joue002695002026-2026-prestations-intermediation-expertises.html`
- `13joue002708922026` — `13joue002708922026-2026-fourniture-prestation-service.html`
- `13joue002946202026` — `13joue002946202026-2026-continuite-exploitation-hebergement?q=h%C3%A9bergement web.html`
- `13joue002850982026` — `13joue002850982026-2026-accord-cadre-bons.html`
- `13joue002925532026` — `13joue002925532026-2026-marche-public-relatif.html`
- `3boamp2645067` — `3boamp2645067-2026-maintien-condition-operationnelle.html`
- `3boamp2644837` — `3boamp2644837-2026-systeme-information-dpsm.html`
- `13joue003107212026` — `13joue003107212026-2026-maintien-condition-operationnelle.html`
- `3boamp2643374` — `3boamp2643374-2026-refonte-site-internet.html`
- `ao-9589316-1` — `ao-9589316-1.html`

### 4. Lignes unmatched — 17 cas

Aucun fichier HTML correspondant dans le dossier courant. Aucune modification apportée.

| Référence | Acheteur | Intitulé |
|---|---|---|
| `AO-2617-2505` | INSEAMM / ESADMM, Marseille (1 | Infogérance du système d’information de  |
| `AO-2618-2579` | Gaz Électricité de Grenoble, G | SOC managé et protection des identités |
| `AO-2619-0506` | EPPGHV (Établissement public d | Maintenance, assistance et infogérance d |
| `370726260520267275` | Acheteur non clairement identi | Prestations d’assistance technique, d’ex |
| `37202609080720267293` | Haute Autorité de Santé (HAS), | Avis de préinformation – mise à disposit |
| `372600004150520267277` | “Ville de …” – la ville n’est  | Conception ergonomique, graphique, techn |
| `3boamp2639725` | CNAF – Caisse Nationale d’Allo | Prestations d’assistance technique, d’ex |
| `13joue002723472026` | Gaz Électricité de Grenoble, G | Fourniture, mise en œuvre d’un SOC manag |
| `2026-02` | Ministère de la Culture – ENSM | “2026‑02 REFONTE DU SITE INTERNET DE LA  |
| `2026-180` | Ministère de la Culture – EPMO | AMO pour le renouvellement du marché d’i |
| `24HA0007` | Acheteur non identifié dans l’ | Prestations d’aide à la passation de mar |
| `2026-0733` | Organisme non identifié dans l | Prestations de codage Pharo / SDL3 / Blo |
| `2026-667` | Acheteur non identifié dans l’ | Développement, mise en œuvre et maintien |
| `3boamp2645992` | — | Assistance maîtrise d'ouvrage refonte éc |
| `13joue003133982026` | — | Développement maintenance application ge |
| `13joue003094352026` | — | TMA TME Système d'Information DPSM BRGM |
| `37af202602030620267275` | — | Refonte site internet Académie Française |

## Validation des matchs via identifiant interne

| Référence CSV | Fichier HTML | Statut |
|---|---|---|
| `DAF_2025_001001` | `37ao26181581260520263294-*.html` | ✓ confirmé |
| `26_AIFE_PEPPOL` | `ao-9560835-1.html` | ✓ confirmé |
| `26-010` | `13joue002929142026-*.html` | ✓ confirmé |
| `26_TMA_CASIER` | `37ao26154015290520267275-*.html` | ✓ confirmé |
| `DGFIP-DRS-2500077` | `26-41049.html` | ✓ confirmé |
| `2026-22` | `3boamp2644226-*.html` | ✓ confirmé |

## État du pipeline — `extract_ao.py` figé

Aucune modification du script lors de cette passe. Pipeline stable.

| Fonction modifiée | Correction |
|---|---|
| `extraire_url_source` | Fallback `<a href>` vers 8 domaines d'avis connus |
| `extraire_date_limite` | Aplatissement multi-lignes JOUE + 7 patterns ordonnés |
| `extraire_duree` | Reconductions : patterns stricts + `_RECON_REJECT` |
| `build_file_index` | 2e passe indexant les `_internal_ref` extraits du HTML |
| `match_row_to_file` | Fuzzy strict : longueur ≥ 10, ratio de couverture ≥ 0.8 |
| `_BAD_RECON_RE` | Labels seuls sans valeur numérique détectés et effacés |
| `remap_legacy_columns` | Nettoyage estimations/durées/reconductions héritées |

## Tableau des 42 lignes matchées

| Référence | Acheteur | Fonction publique | Type AO | Date limite | Estimation | URL |
|---|---|---|---|---|---|---|
| `13joue002671162026` | RESA (opérateur d’énergie | Territoriale | AOO | 19/05/2026 | — | ✓ |
| `3boamp2642071 (1ʳᵉ occurr` | Région Nouvelle‑Aquitaine | Territoriale | AOO | 29/05/2026 | 1.12 M€ HT | ✓ |
| `3boamp2641974` | Ville de Paris et Centre  | Territoriale | AOO | 09/06/2026 | — | ✓ |
| `3boamp2639793` | Ministère des Armées – Co | Etat | AOO | 07/05/2026 | 18.02 M€ HT | ✓ |
| `3boamp2642106` | Association ASF Vacances | — | AOO | 05/06/2026 | 800 000 € HT | ✓ |
| `36parisien1157695` | Ville de Croissy‑sur‑Sein | Territoriale | MAPA | 20/05/2026 | — | ✓ |
| `37ao26181552260520267275` | CNAF Établissement public | Etat | MAPA | 26/05/2026 | 8.7 M€ HT | ✓ |
| `3boamp2641049` | Direction Générale des Fi | Etat | AOO | 04/06/2026 | 400 000 € HT | ✓ |
| `37ao26181581260520263294` | Ministère des Armées – Ce | Etat | MAPA | 26/05/2026 | 18.02 M€ HT | ✓ |
| `13joue002695002026` | EDF SA et filiales bénéfi | Territoriale | AOO | 13/05/2026 | — | ✓ |
| `13joue002708922026` | UNICANCER ACHATS | Etat | AOO | 18/05/2026 | — | ✓ |
| `3boamp2642071 (2ᵉ occurre` | Identique à la ligne 5 | Territoriale | AOO | 29/05/2026 | 1.12 M€ HT | ✓ |
| `DAF_2025_001001` | Ministère des Armées – DN | Etat | Procédure négociée | 26/05/2026 | 18.02 M€ HT | ✓ |
| `26_AIFE_PEPPOL` | MEFSIN / AIFE (Agence pou | Etat | AOO | 08/04/2026 | 315 000 € HT | ✓ |
| `26-010` | Conservatoire national de | Etat | Procédure négociée | 28/05/2026 | 400 000 € HT | ✓ |
| `26_TMA_CASIER` | Ministère de la Justice – | Etat | AOO | 29/05/2026 | 16 M€ HT | ✓ |
| `DGFIP-DRS-2500077` | Direction Générale des Fi | Etat | AOO | 04/06/2026 | 400 000 € HT | ∅ |
| `2026-22` | INSTITUT FRANCAIS DUCHEVA | Etat | AOO | 04/06/2026 | 2 M€ HT | ✓ |
| `13joue002946202026` | Institut géographique nat | Etat | AOO | 15/06/2026 | — | ✓ |
| `13joue003036002026` | Compagnie Nationale du Rh | Etat | AOO | 10/06/2026 | 5 M€ HT | ✓ |
| `13joue002850982026` | VILLE de PARIS - DFA - SD | Territoriale | AOO | 09/06/2026 | — | ✓ |
| `13joue002925532026` | Parlement Wallon | Territoriale | AOO | 08/06/2026 | — | ✓ |
| `13joue002939872026` | Institut Français | Etat | AOO | 08/06/2026 | 400 000 € HT | ✓ |
| `13joue002889082026` | Association ASF Vacances | — | AOO | 05/06/2026 | 800 000 € HT | ✓ |
| `3boamp2645067` | Centre Hospitalier de l'A | Hospitalière | AOO | 05/06/2026 | — | ✓ |
| `3boamp2644837` | Bureau de Recherche en Gé | Etat | AOO | 05/06/2026 | — | ✓ |
| `13joue003107212026` | Centre Hospitalier de l'A | Hospitalière | AOO | 05/06/2026 | — | ✓ |
| `3boamp2642682` | SICIO | Territoriale | AOO | 04/06/2026 | 1.02 M€ HT | ✓ |
| `3boamp2643609` | UNIHA-GCS | Hospitalière | AOO | 04/06/2026 | 400 000 € HT | ✓ |
| `3boamp2644226` | I.F.C.E. | Etat | AOO | 04/06/2026 | 2 M€ HT | ✓ |
| `13joue003011922026` | GCS-UNIHA | Hospitalière | AOO | 04/06/2026 | 400 000 € HT | ✓ |
| `13joue002946822026` | SICIO | Territoriale | AOO | 04/06/2026 | 1.02 M€ HT | ✓ |
| `3boamp2643374` | ACADEMIE FRANCAISE | Etat | AOO | 03/06/2026 | — | ✓ |
| `3boamp2644098` | Etablissement d'enseignem | Etat | AOO | 03/06/2026 | 750 000 € HT | ✓ |
| `13joue003085442026` | Union des Groupements d'A | Territoriale | AOO | 29/06/2026 | 600 M€ HT | ✓ |
| `13joue003085442026` | Union des Groupements d'A | Territoriale | AOO | 29/06/2026 | 600 M€ HT | ✓ |
| `13joue002929142026` | Conservatoire national de | Etat | AOO | 28/05/2026 | 400 000 € HT | ✓ |
| `37ao26154015290520267275` | Ministère de la Justice | Etat | MAPA | 29/05/2026 | 16 M€ HT | ✓ |
| `3boamp2640079` | HAUTE AUTORITE DE SANTE | Etat | MAPA | 08/07/2026 | 500 000 € HT | ✓ |
| `13joue002845752026` | EPPGHV | Territoriale | AOO | 01/06/2026 | 620 000 € HT | ✓ |
| `ao-9560835-1` | Agence pour l'informatiqu | Etat | AOO | 08/04/2026 | 315 000 € HT | ✓ |
| `ao-9589316-1` | ESADMM | Territoriale | AOO | 29/05/2026 | — | ✓ |
