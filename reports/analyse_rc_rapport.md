# Analyse Comparative RC / Rapports - Marchés Publics TIC 2026

## Document de travail - Extraction des métadonnées

---

## 1. EXTRACTION DES RAPPORTS PDF

### Rapport v1 (rapport_marches_publics_2026)
**Date:** Mai 2026
**Auteur:** BlockHack.io / Perplexity Computer
**Nombre de marchés:** 6 (M1 à M6)

| Marché | Référence | Acheteur | Type | Montant | Date limite | CCAG |
|--------|-----------|----------|------|---------|-------------|------|
| M1 EPPGHV | 2026MDAF0063 (PLACE), 13/joue/002845752026 | Établissement Public du Parc et de la Grande Halle de la Villette | Infogérance parc info & telecom | ~660 k€ HT (max AC: 160 k€) | 01/06/2026 14h00 | TIC |
| M2/M3 DGFiP | DGFIP-DRS-2500077 (PLACE), BOAMP 26-41049 | Direction Générale des Finances Publiques | Assistance AMO-TIC | 400 k€ HT | 04/06/2026 17h00 | PI |
| M4 BRGM | HADPSM260413, BOAMP 26-44837, TED 309435-2026 | Bureau de Recherche en Géologie Minière | TMA-TME SI DPSM | Non publiée | 05/06/2026 12h00 | TIC probable |
| M5 Institut Français | 13/joue/002939872026 | Institut Français | Maintenance Culturethèque + hébergement | Non publiée | 08/06/2026 12h00 | TIC |
| M6 HAS | BOAMP 26-40079, TED 273519-2026 | Haute Autorité de Santé | SIF financier (PRÉ-INFO) | 500 k€ HT | 08/07/2026 12h00 (manifestation intérêt) | Non précisé |

**Doublons identifiés v1:** M2=M3 (même marché DGFiP, deux références de publication)

---

### Rapport v2 (rapport_marches_publics_2026_v2)
**Date:** Mai 2026
**Auteur:** BlockHack.io / Perplexity Computer
**Nombre de marchés:** 11 (M1 à M11)

**Marchés initiaux (M1-M6):** Identiques au rapport v1

| Marché | Référence | Acheteur | Type | Montant | Date limite | CCAG |
|--------|-----------|----------|------|---------|-------------|------|
| M7 IFCE | BOAMP 26-44226, 2026-22 | Institut Français du Cheval et de l'Equitation | AMO & TMA (6 lots) | 2 000 k€ HT (AC 6 lots) | 04/06/2026 12h00 | PI probable |
| M8 Institut Français | 13/joue/002939872026 | Institut Français | Culturethèque (identique M5) | Non publiée | 08/06/2026 12h00 | TIC |
| M9 IGN Belgique | TED 294620-2026, PM BROKER 26-15 | Institut Géographique National BELGE (NGI) | Plateforme eTOD aviation | Non publiée | 15/06/2026 14h00 | Droit belge |
| M10 MJL-DNUM | 26_AMOE_AST, consultation 2990888, orgAcronyme=d3f | Ministère de la Justice DNUM | AMO socle transverse (5 lots) | 32,5 M€ HT est. (65 M€ max) | 17/06/2026 14h00 | PI probable |
| M11 UGAP | 25U018, JOUE 003085442026 | UGAP (centrale d'achat) | Fournitures infrastructure informatique (8 lots) | 600 M€ HT max | 29/06/2026 14h00 | FCS probable |

**Doublons identifiés v2:** M2=M3, M5=M8 (doublons de soumission)
**Alertes v2:** M9 = marché belge (hors périmètre), M11 = seuils CA incompatibles PME

---

### Rapport v3 (rapport_marches_publics_2026_v3)
**Date:** Mai 2026
**Auteur:** BlockHack.io / Perplexity Computer
**Nombre de marchés:** 18 (M1 à M18)

**Marchés v1/v2 (M1-M11):** Identiques aux versions précédentes

| Marché | Référence | Acheteur | Type | Montant | Date limite | CCAG |
|--------|-----------|----------|------|---------|-------------|------|
| M12 RESA Belgique | JOUE 13/joue/002671162026 | RESA Innovation / RESA SA (Belgique) | Workplace IT | Inconnu | 19/05/2026 16h00 | Droit belge |
| M13 Parlement Wallon | JOUE 13/joue/002925532026 | Parlement Wallon (Belgique) | ERP intégré RH+Finance | Inconnu | 08/06/2026 11h00 | Droit belge |
| M14 GCS UNIHA | M_3530, PLACE consultation 2979848 | GCS UniHA (hospitalier) | Développement et maintenance outils (2 lots) | 900 k€ HT (Lot2: 500k) | 02/06/2026 00h00 (heure à vérifier) | PI probable |
| M15 Centre Morbihan | 26CMC13, Megalis consultation 231914 | Centre Morbihan Communauté | Infrastructure IT MCO | 450 k€ HT | 02/06/2026 12h00 | TIC probable |
| M16 SICIO | SIRET 25940011700034 | SICIO (syndicat intercommunal) | Serveurs de sauvegarde (2 lots) | 1 025 k€ HT | 04/06/2026 12h00 | FCS probable |
| M17 CNR | DDA 26-022 | Compagnie Nationale du Rhône | Infrastructure HCI + VDI | 5 000 k€ HT | 10/06/2026 19h00 | CPA/CGA |
| M18 Région Grand Est | 2026A0239, IDM 1815620 | Région Grand Est | Support et infogérance (4 lots, 234 lycées) | 14 875 k€ HT | 18/06/2026 12h00 | Non précisé |

**Alertes v3:**
- M9, M12, M13 = marchés belges (hors périmètre France)
- M11, M16, M17, M18, M15 = incompatibles structure PME
- M14 UNIHA lot 2 = GO prioritaire (PHP/Symfony/Python/IA/Blockchain)

---

## 2. EXTRACTION DES RC (6 fichiers)

### RC 1: DGFIP_DRS_2500077_RC.txt
| Métadonnée | Valeur extraite |
|------------|-----------------|
| **Référence RC** | DGFiP-DRS-2500077 (version du 09/04/2026) |
| **Acheteur** | Direction Générale des Finances Publiques - Service des Systèmes d'Information, Département des Ressources et du Support |
| **Adresse** | 10, rue Auguste Blanqui, 93186 MONTREUIL Cedex |
| **Type de marché** | Prestations intellectuelles |
| **Objet** | Assistance externe pour la conduite de consultations organisées dans le cadre des dispositions du code de la commande publique pour les marchés de techniques de l'information et de la communication |
| **CPV principal** | 72220000 – Services de conseil en systèmes informatiques et conseils techniques |
| **Allotissement** | Non (lot unique) |
| **Forme** | Accord-cadre à bons de commande |
| **Durée** | 24 mois ferme + 2 reconductions de 12 mois = 48 mois max |
| **Montant max** | 1 200 000 € HT (soit 1 440 000 € TTC) |
| **Montant estimé** | 480 000 € TTC sur durée totale |
| **Date limite** | [À extraire du RC complet] |
| **Plateforme** | PLACE (marches-publics.gouv.fr) |
| **Contact** | Emilie FAGES (01 41 63 50 88), Anthony HENRION |
| **CCAG** | CCAG Prestations Intellectuelles (probable, vu type "Prestations intellectuelles") |
| **Variantes** | Interdites |

---

### RC 2: 260424 - RC PRESTATIONS INFORMATIQUES .txt (GCS UniHA)
| Métadonnée | Valeur extraite |
|------------|-----------------|
| **Référence RC** | M_3530 |
| **Acheteur** | GCS UniHA (Groupement de Coopération Sanitaire) – 83 Boulevard Marius Vivier Merle, 69003 LYON |
| **Référent technique** | Stéphane BUISSON (stephane.buisson@uniha.org) |
| **Référente administrative** | Shaïnez BOUGHANMI (shainez.boughanmi@uniha.org) |
| **Type de marché** | Prestations de services informatiques pour le développement et la maintenance des outils informatiques du GCS UniHA |
| **Allotissement** | 2 lots |
| **Lot 1** | Webdev, WinDev, technologies PCSOFT – 400 000 € HT max |
| **Lot 2** | PHP/Symfony/Python + IA et Blockchain – 500 000 € HT max |
| **Forme** | Accord-cadre mono-attributaire pour partie à bons de commande et pour partie à marchés subséquents |
| **Durée** | 4 ans maximum |
| **CPV principal** | 72200000 – Services de programmation et de conseil en logiciels |
| **CPV secondaires** | 72261000 (assistance logiciels) + 72262000 (développement logiciels) |
| **Date limite** | 02/06/2026 à 12H00 |
| **Plateforme** | PLACE (marches-publics.gouv.fr) |
| **Procédure** | Appel d'offres ouvert |
| **CCAG** | Non mentionné – [HYPOTHÈSE] CCAG Prestations Intellectuelles |

---

### RC 3: AWS-MPI-1816545-RC.txt (BRGM-DPSM)
| Métadonnée | Valeur extraite |
|------------|-----------------|
| **Référence RC** | HADPSM260413 |
| **Acheteur** | BRGM (Bureau de Recherche en Géologie Minière) – 3 Avenue Claude Guillemin, Orléans 45060 |
| **Représentant** | Madame la Présidente Directrice Générale |
| **Type de marché** | Accord-cadre de services TMA – TME |
| **Objet** | Tierce maintenance applicative et évolutive, maintenance corrective et préventive pour des applications gérées au sein de la DPSM (Département Prévention et Sécurité Minière) |
| **CPV** | 72500000-0 (Services informatiques), 72250000-2 (Maintenance systèmes), 72600000-6 (Assistance/conseils), 72610000-9 (Assistance informatique) |
| **Allotissement** | Non (lot unique) |
| **Forme** | Accord-cadre à bons de commande sans minimum et avec maximum mono-attributaire |
| **Durée** | 48 mois – 1 an ferme + 1 an x3 (reconductions tacites) |
| **Date limite** | 05/06/2026 à 12h00 |
| **Plateforme** | marches-publics.info |
| **Procédure** | Appel d'offres ouvert (Article R2124-2 1° - CCP) |
| **CCAG** | Non mentionné dans l'extrait |
| **Variantes** | Non autorisées |
| **Délai validité offre** | 150 jours |

---

### RC 4: RC N° 2026-22.txt (IFCE)
| Métadonnée | Valeur extraite |
|------------|-----------------|
| **Référence RC** | 2026-22 |
| **Acheteur** | Institut Français du Cheval et de l'Equitation (IFCE) – Route de Troche – BP 6, 19231 Arnac-Pompadour Cedex |
| **Adresse siège** | 170 Avenue du Cadre Noir, 49400 Saumur |
| **Représentant** | Monsieur Ludovic PACAUD, Directeur général |
| **Type de marché** | Assistance à maîtrise d'œuvre : prestations d'expertise, de développements informatiques et d'assistance technique |
| **Objet** | Assistance aux services informatiques de l'IFCE pour la maintenance corrective et évolutive de ses applications |
| **CPV principal** | 72500000-0 Services informatiques |
| **Allotissement** | 6 lots |
| **Lot 1** | Expertise, développement et support technique en architecture logicielle et sécurité |
| **Lot 2** | TMA des applications sous technologies Java |
| **Lot 3** | TMA des applications mobiles Unity |
| **Lot 4** | TMA des applications sous technologies PHP/Symfony |
| **Lot 5** | TMA des applications mobiles React Native |
| **Lot 6** | TMA des modèles d'édition réalisés avec Hamonie Communication Suite (SEFAS) |
| **Forme** | Accord-cadre mono/multi-attributaire à marchés subséquents sans minimum et avec maximum de 2 000 000,00 € HT |
| **Durée** | 2 ans initiale + 2 reconductions d'1 an = 4 ans max |
| **Date limite** | Jeudi 4 juin 2026 à 12 heures |
| **Plateforme** | PLACE (marches-publics.gouv.fr) |
| **Procédure** | Appel d'offres ouvert (procédure européenne) |
| **Variantes** | Non autorisées |
| **Délai validité offre** | 6 mois |

---

### RC 5: RC_Assistance et infogerance.txt (EPPGHV)
| Métadonnée | Valeur extraite |
|------------|-----------------|
| **Référence RC** | 2026MDAF0063 |
| **Acheteur** | Établissement Public du Parc et de la Grande Halle de la Villette – 211 avenue Jean-Jaurès, 75935 Paris cedex 19 |
| **SIRET** | 39140695600014 |
| **Type de marché** | Marché public de services – Prestations de maintenance d'assistance et d'infogérance du parc informatique, réseau et telecom de l'EPPGHV |
| **CPV** | 72500000-0 (Services informatiques), 72610000 (Assistance informatique), 72611000 (Assistance technique), 72600000 (Assistance/conseils) |
| **Allotissement** | Non (lot unique) |
| **Forme** | Marché composite : prix global forfaitaire + accord-cadre à bons de commande mono-attributaire |
| **Partie AC** | Sans montant minimum, max 160 000 € HT pour toute durée |
| **Durée offre base** | 1 an ferme + 3 reconductions tacites d'1 an = 4 ans max |
| **Variante exigée** | 48 mois ferme |
| **Date limite** | 01/06/2026 à 14h00 |
| **Plateforme** | PLACE (marches-publics.gouv.fr) |
| **Procédure** | Appel d'offres ouvert (L2124-2 CCP) |
| **Délai validité offre** | 180 jours |
| **Variantes** | Non autorisées (sauf variante exigée sur durée) |
| **Sous-traitance** | Totale interdite, partielle autorisée |
| **CCAG** | [À extraire du CCAP] |

---

### RC 6: Règlement de consultation.txt (Institut Français)
| Métadonnée | Valeur extraite |
|------------|-----------------|
| **Référence RC** | 2026 / DARC/ N°03 |
| **Acheteur** | Institut Français – 40 rue de la Folie-Régnault, 75011 Paris |
| **Contact** | marches.publics@institutfrancais.com, contact@institutfrancais.com |
| **Type de marché** | Maintenance applicative, corrective et évolutive du site internet Culturethèque (et toutes ses fonctionnalités) et hébergement |
| **CPV** | 72000000-5 (Services TI conseil/développement), 72415000-2 (Hébergement WWW), 72400000-4 (Services Internet), 50324100-3 (Maintenance système) |
| **Allotissement** | Non (conformément L2113-10 CCP) |
| **Forme** | [À extraire] |
| **Durée** | [À extraire du CCAP] |
| **Date limite** | Lundi 8 juin 2026 à 12:00:00 |
| **Plateforme** | e-marchespublics.com |
| **Procédure** | Appel d'offres ouvert (L2124-2, R2124-1 CCP) |
| **Variantes** | Non autorisées |
| **Délai validité offre** | 120 jours |
| **CCAG** | [À extraire du CCAP] |

---

## 3. TABLEAU DE CORRESPONDANCE RC / RAPPORTS

| RC Fichier | Référence RC | Marché Rapport | Correspondance | Confiance |
|------------|--------------|----------------|----------------|-----------|
| DGFIP_DRS_2500077_RC.txt | DGFiP-DRS-2500077 | M2/M3 DGFiP | **CERTAINE** | Référence interne identique, acheteur DGFiP confirmé |
| 260424 - RC PRESTATIONS INFORMATIQUES .txt | M_3530 | M14 GCS UNIHA | **CERTAINE** | Référence M_3530 mentionnée dans rapport v3, acheteur GCS UniHA |
| AWS-MPI-1816545-RC.txt | HADPSM260413 | M4 BRGM-DPSM | **CERTAINE** | Référence HADPSM260413 identique, acheteur BRGM, objet TMA/TME |
| RC N° 2026-22.txt | 2026-22 | M7 IFCE | **CERTAINE** | Référence 2026-22 identique, acheteur IFCE, 6 lots |
| RC_Assistance et infogerance.txt | 2026MDAF0063 | M1 EPPGHV | **CERTAINE** | Référence 2026MDAF0063 identique, acheteur EPPGHV, infogérance |
| Règlement de consultation.txt | 2026/DARC/N°03 | M5/M8 Institut Français | **CERTAINE** | Objet Culturethèque, date limite 08/06/2026, acheteur Institut Français |

**Conclusion identification:** Les 6 RC correspondent chacun à un marché distinct analysé dans les rapports. Aucun RC n'est orphelin, aucun marché du rapport v1 n'est sans RC.

---

## 4. ÉCARTS À ANALYSER (points de vigilance)

### Écart 1: DGFiP - Montant
- **RC:** Montant max 1 200 000 € HT / Montant estimé 480 000 € TTC
- **Rapport v1/v2/v3:** 400 000 € HT (valeur max AC)
- **Nature:** Incohérence significative
- **Explication possible:** Le rapport mentionne "400 k€ HT" comme valeur estimée, le RC indique "montant max 1 200 000 € HT" et "montant estimé 480 000 € TTC"

### Écart 2: EPPGHV - Montant
- **RC:** Montant max AC 160 000 € HT
- **Rapport v1:** ~660 k€ HT (max AC 160 k€)
- **Nature:** Cohérent - le rapport cite les deux valeurs

### Écart 3: BRGM - Montant
- **RC:** Non précisé dans l'extrait
- **Rapport:** Non publié
- **Nature:** Cohérent

### Écart 4: Institut Français - Montant
- **RC:** Non précisé dans l'extrait
- **Rapport:** Non publié
- **Nature:** Cohérent

### Écart 5: IFCE - Montant
- **RC:** Maximum 2 000 000,00 € HT
- **Rapport v2/v3:** 2 000 000 € HT (AC 6 lots)
- **Nature:** Cohérent

### Écart 6: GCS UniHA - Référence JOUE
- **RC:** Aucune référence JOUE/TED dans l'extrait
- **Rapport v3:** Mentionné comme M14
- **Nature:** Le RC est un document interne, la référence JOUE serait dans l'avis de marché

---

*Document généré le 15 mai 2026 - Phase 1: Extraction et identification*
