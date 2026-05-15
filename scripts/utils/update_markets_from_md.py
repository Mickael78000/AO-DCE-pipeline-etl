#!/usr/bin/env python3
"""
Met à jour les marchés dans extraction_rc.json avec les données détaillées des fichiers .md
"""

import json
from datetime import datetime

JSON_FILE = "/home/michka/Documents/0-AO-DCE/extraction_rc.json"

# Données enrichies extraites des fichiers .md
market_updates = {
    # MS26084 - SYANE (RC-PHASE-CANDIDATURES.md)
    "MS26084": {
        "titre": "Missions d'infogérance de systèmes d'information des collectivités adhérentes au Conseil numérique du SYANE",
        "acheteur": {
            "nom": "SYANE - Syndicat des énergies et de l'aménagement numérique de la Haute-Savoie",
            "structure_juridique": "Syndicat mixte",
            "categorie_normee": "etablissement_public"
        },
        "lieu": {
            "adresse": "Non précisé",
            "ville": "Haute-Savoie",
            "code_postal": None,
            "pays": "France",
            "source_brute": "Haute-Savoie - territoire du syndicat"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-11T12:00:00+02:00",
            "valeur_brute": "11/06/2026 à 12h00",
            "fuseau_horaire": "Europe/Paris",
            "source_brute": "Jeudi 11 juin 2026 à 12h00"
        },
        "plateforme_remise_offres": {
            "nom": "marches-publics.info",
            "url": "https://www.marches-publics.info",
            "source_brute": "www.marches-publics.info"
        },
        "procedure": {
            "source": "Procédure avec négociation en deux phases",
            "consolidee": "procédure avec négociation",
            "regime": "droit_commun",
            "niveau_preuve": "verifie"
        },
        "type_marche": {
            "source": "Accord-cadre à bons de commande mono-attributaire",
            "consolide": "accord-cadre à bons de commande",
            "categorie_normee": "accord_cadre_bc"
        },
        "duree": {
            "valeur": 12,
            "unite": "mois",
            "structure": "1 an reconductible 3 fois (4 ans maximum)",
            "source_brute": "un an reconductible trois fois"
        },
        "montants": {
            "global": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
            "estime": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
            "maximum": {"valeur": 5000000, "devise": "EUR", "precision": "Plafond maximum 5 000 000 € HT", "source_brute": "montant maximum de 5 000 000 € HT", "nature": "plafond"},
            "minimum": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
            "nature_marche": "services"
        },
        "allotissement": {
            "statut": "non_alloti",
            "nombre_lots": 0,
            "source_brute": "Marché non alloti"
        },
        "criteres_selection": [
            {
                "critere": "Valeur technique",
                "ponderation": "60%",
                "commentaire": "Qualité technique de l'offre",
                "source_brute": "jugement des offres sur valeur technique 60%"
            },
            {
                "critere": "Prix",
                "ponderation": "40%",
                "commentaire": "Critère prix",
                "source_brute": "prix 40%"
            }
        ],
        "dce": {
            "pieces_constitutives": [
                {"nom": "RC", "type_piece": "reglement", "obligatoire": True, "source_brute": "Règlement de consultation"},
                {"nom": "CCTP", "type_piece": "cahier_clauses", "obligatoire": True, "source_brute": "Cahier des Clauses Techniques"},
                {"nom": "CCAP", "type_piece": "cahier_clauses", "obligatoire": True, "source_brute": "Cahier des Clauses Administratives"},
                {"nom": "DC1", "type_piece": "formulaire", "obligatoire": True, "source_brute": "DC1"},
                {"nom": "DC2", "type_piece": "formulaire", "obligatoire": True, "source_brute": "DC2"},
                {"nom": "Mémoire technique", "type_piece": "technique", "obligatoire": True, "source_brute": "Mémoire technique (max 35 pages)"}
            ]
        },
        "controle": {
            "statut_verification": "verifie",
            "niveau_confiance": "eleve",
            "qualite_extraction": "bonne",
            "commentaire": "Données enrichies depuis RC-PHASE-CANDIDATURES.md"
        }
    },
    
    # B26-01107-LS - CEA-Liten (B26-01107-LS_RC.md)
    "B26-01107-LS": {
        "titre": "Tierce Maintenance Applicative (TMA) des Logiciels Systèmes Énergétiques du CEA-Liten",
        "acheteur": {
            "nom": "CEA - Commissariat à l'Énergie Atomique et aux Énergies Alternatives - Liten",
            "structure_juridique": "Établissement public à caractère industriel et commercial (EPIC)",
            "categorie_normee": "EPIC"
        },
        "lieu": {
            "adresse": "17 avenue des Martyrs",
            "ville": "Grenoble",
            "code_postal": "38054",
            "pays": "France",
            "source_brute": "CEA Centre de Grenoble, 17 avenue des Martyrs, 38054 GRENOBLE Cedex 9"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-10T16:00:00+02:00",
            "valeur_brute": "10/06/2026 à 16h00",
            "fuseau_horaire": "Europe/Paris",
            "source_brute": "10 juin 2026 avant 16 heures"
        },
        "plateforme_remise_offres": {
            "nom": "PLACE",
            "url": "https://www.marches-publics.gouv.fr",
            "source_brute": "PLACE"
        },
        "procedure": {
            "source": "Appel d'offres ouvert formalisé",
            "consolidee": "appel d'offres ouvert",
            "regime": "droit_commun",
            "niveau_preuve": "verifie"
        },
        "type_marche": {
            "source": "Marché à tranches",
            "consolide": "marché à tranches",
            "categorie_normee": "services"
        },
        "duree": {
            "valeur": 24,
            "unite": "mois",
            "structure": "Tranche ferme 2 ans (16/08/2026 - 16/08/2028) + 3 tranches optionnelles jusqu'au 16/08/2030",
            "source_brute": "Tranche ferme 2 ans + tranches optionnelles"
        },
        "criteres_selection": [
            {
                "critere": "Prix",
                "ponderation": "50%",
                "commentaire": "Critère prix",
                "source_brute": "Prix : 50%"
            },
            {
                "critere": "Méthodologie d'exécution",
                "ponderation": "30%",
                "commentaire": "Méthodologie d'exécution des prestations",
                "source_brute": "Méthodologie d'exécution des prestations : 30%"
            },
            {
                "critere": "Organisation et moyens humains",
                "ponderation": "20%",
                "commentaire": "Organisation et moyens humains proposés",
                "source_brute": "Organisation et moyens humains proposés : 20%"
            }
        ],
        "dce": {
            "pieces_constitutives": [
                {"nom": "RC", "type_piece": "reglement", "obligatoire": True, "source_brute": "Règlement de consultation"},
                {"nom": "DC1", "type_piece": "formulaire", "obligatoire": True, "source_brute": "DC1"},
                {"nom": "DC2/DUME", "type_piece": "formulaire", "obligatoire": True, "source_brute": "DC2 ou DUME"},
                {"nom": "Offre technique", "type_piece": "technique", "obligatoire": True, "source_brute": "Offre technique (organisation, méthodes, réversibilité)"},
                {"nom": "Offre commerciale", "type_piece": "financiere", "obligatoire": True, "source_brute": "Annexe financière (Excel + PDF)"}
            ]
        },
        "controle": {
            "statut_verification": "verifie",
            "niveau_confiance": "eleve",
            "qualite_extraction": "bonne",
            "commentaire": "Données enrichies depuis B26-01107-LS_RC.md"
        },
        "variantes": {
            "acceptees": True,
            "commentaire": "Variantes de durée autorisées"
        }
    },
    
    # DAF_2026_000243 - Banque de France (AE20260004_PORTAILS_HISI-V2_RC_V1.0.md)
    "DAF_2026_000243": {
        "titre": "Portails HISI V2 - Développement, maintenance applicative et infogérance",
        "acheteur": {
            "nom": "Banque de France",
            "structure_juridique": "Établissement public national - Institution nationale indépendante",
            "categorie_normee": "etablissement_public"
        },
        "lieu": {
            "adresse": "08-1196 Service des Achats Informatiques",
            "ville": "Paris",
            "code_postal": "75049",
            "pays": "France",
            "source_brute": "Banque de France, 75049 PARIS Cedex 01"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-15T12:00:00+02:00",
            "valeur_brute": "15/06/2026 à 12H00",
            "fuseau_horaire": "Europe/Paris",
            "source_brute": "15/06/2026 à 12H00, heure de Paris"
        },
        "plateforme_remise_offres": {
            "nom": "Safetender - Profil acheteur Banque de France",
            "url": "https://achats-banquedefrance.safetender.com",
            "source_brute": "https://achats-banquedefrance.safetender.com"
        },
        "procedure": {
            "source": "Procédure avec négociation (2 phases : candidature puis offre)",
            "consolidee": "procédure avec négociation",
            "regime": "droit_commun",
            "niveau_preuve": "verifie"
        },
        "type_marche": {
            "source": "Accord-cadre à bons de commande avec un seul opérateur",
            "consolide": "accord-cadre à bons de commande mono-attributaire",
            "categorie_normee": "accord_cadre_bc"
        },
        "duree": {
            "valeur": 48,
            "unite": "mois",
            "structure": "48 mois ferme + 4 reconductions expresses d'1 an = 8 ans maximum",
            "source_brute": "Durée ferme 48 mois, 4 reconductions d'un an, durée max 8 ans"
        },
        "montants": {
            "global": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
            "estime": {"valeur": 16670000, "devise": "EUR", "precision": "Montant estimé sur durée totale", "source_brute": "16 670 000 € HT", "nature": "estimation"},
            "maximum": {"valeur": 51000000, "devise": "EUR", "precision": "Plafond maximum du marché", "source_brute": "51 000 000 € HT", "nature": "plafond"},
            "minimum": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
            "nature_marche": "services"
        },
        "allotissement": {
            "statut": "non_alloti",
            "nombre_lots": 0,
            "source_brute": "Le marché n'est pas alloti"
        },
        "criteres_selection": [
            {
                "critere": "Références et capacités techniques",
                "ponderation": "à définir",
                "commentaire": "Capacité technique, certifications ISO 27001",
                "source_brute": "Références, capacités techniques, certification ISO 27001"
            },
            {
                "critere": "Engagements RSE",
                "ponderation": "à définir",
                "commentaire": "Engagements environnementaux et sociaux",
                "source_brute": "Engagements RSE"
            },
            {
                "critere": "Prix",
                "ponderation": "à définir",
                "commentaire": "Modalités de calcul de la note financière",
                "source_brute": "Modalités de calcul de la note financière"
            }
        ],
        "dce": {
            "pieces_constitutives": [
                {"nom": "RC", "type_piece": "reglement", "obligatoire": True, "source_brute": "Règles de la consultation"},
                {"nom": "CCA", "type_piece": "cahier_clauses", "obligatoire": True, "source_brute": "Conditions Générales d'Achat"},
                {"nom": "CCPDP", "type_piece": "cahier_clauses", "obligatoire": True, "source_brute": "Cahier des Clauses Particulières de Déontologie et de Propriété"},
                {"nom": "CCT", "type_piece": "cahier_clauses", "obligatoire": True, "source_brute": "Cahier des Clauses Techniques"},
                {"nom": "DC1", "type_piece": "formulaire", "obligatoire": True, "source_brute": "DC1"},
                {"nom": "DC2", "type_piece": "formulaire", "obligatoire": True, "source_brute": "DC2"},
                {"nom": "Bordereau offre financière", "type_piece": "financiere", "obligatoire": True, "source_brute": "Bordereau d'offre financière"}
            ]
        },
        "controle": {
            "statut_verification": "verifie",
            "niveau_confiance": "eleve",
            "qualite_extraction": "excellente",
            "commentaire": "Données enrichies depuis AE20260004_PORTAILS_HISI-V2_RC_V1.0.md"
        },
        "publication": {
            "joue_reference": "327838-2026",
            "joue_date": "13/05/2026",
            "profil_acheteur_url": "https://achats-banquedefrance.safetender.com"
        }
    }
}


def update_markets():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    marches = data.get("marches", [])
    updated_count = 0
    
    for market in marches:
        ref = market.get("reference_consolidee", "")
        
        if ref in market_updates:
            print(f"Mise à jour: {ref}")
            update = market_updates[ref]
            
            # Mettre à jour les champs
            for key, value in update.items():
                if key in ["acheteur", "lieu", "date_limite_remise_offres", "plateforme_remise_offres", 
                          "procedure", "type_marche", "duree", "montants", "allotissement", 
                          "criteres_selection", "dce", "controle", "variantes", "publication"]:
                    if isinstance(value, dict) and isinstance(market.get(key), dict):
                        market[key].update(value)
                    else:
                        market[key] = value
                else:
                    market[key] = value
            
            updated_count += 1
    
    print(f"\nTotal marchés mis à jour: {updated_count}")
    
    # Sauvegarder
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Fichier sauvegardé: {JSON_FILE}")


if __name__ == "__main__":
    update_markets()
