#!/usr/bin/env python3
"""
Corrige les données mal extraites dans extraction_rc.json
Supprime les marchés avec identifiants incorrects et les remplace par les bonnes données.
"""

import json
import re

JSON_FILE = "/home/michka/Documents/0-AO-DCE/extraction_rc.json"

# Données manuelles extraites des PDFs
corrections = {
    # 2600006 - SPL IT Réseau Cloud Sécurité (marché à garder mais corriger)
    "2026A0239": {
        "titre": "Fourniture et supervision pour les Services Numériques Éducatifs, et pour les environnements de travail, Data Centers, LIB et CLC",
        "reference": "2026A0239",
        "acheteur": {
            "nom": "Ministère de l'Éducation Nationale - Direction du numérique pour l'éducation",
            "structure_juridique": "Direction du numérique pour l'éducation",
            "categorie_normee": "Etat"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-18T12:00:00+02:00",
            "valeur_brute": "18/06/2026 à 12:00",
            "fuseau_horaire": "Europe/Paris"
        }
    },
    
    # SPL Approv'Halles - 2600006
    "s de prestations similaires ré": {
        "new_ref": "2600006",
        "titre": "Prestation IT : Réseau / Cloud / Sécurité",
        "reference": "2600006",
        "acheteur": {
            "nom": "SPL APPROV'HALLES - Plateforme d'Approvisionnement de la Restauration Scolaire de l'Est Francilien",
            "structure_juridique": "Société Publique Locale",
            "categorie_normee": "etablissement_public"
        },
        "lieu": {
            "adresse": "ZAC du Provinois",
            "ville": "Provins",
            "code_postal": "77160",
            "pays": "France"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-24T12:00:00+02:00",
            "valeur_brute": "24/06/2026 à 12:00",
            "fuseau_horaire": "Europe/Paris"
        },
        "procedure": {
            "source": "Procédure adaptée",
            "consolidee": "procédure adaptée",
            "regime": "droit_commun"
        }
    },
    
    # GCS UniHA - 260424 - Prestations informatiques
    "48900000": {
        "new_ref": "260424",
        "titre": "Prestations de services informatiques pour le développement et la maintenance des outils informatiques du GCS UniHA",
        "reference": "260424",
        "acheteur": {
            "nom": "GCS UniHA",
            "structure_juridique": "Groupement de Coopération Sanitaire - Centrale d'achat",
            "categorie_normee": "etablissement_public"
        },
        "lieu": {
            "adresse": "83 Boulevard Marius Vivier Merle",
            "ville": "Lyon",
            "code_postal": "69003",
            "pays": "France"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-04T12:00:00+02:00",
            "valeur_brute": "04/06/2026",
            "fuseau_horaire": "Europe/Paris"
        },
        "procedure": {
            "source": "Appel d'offres ouvert",
            "consolidee": "appel d'offres ouvert",
            "regime": "droit_commun"
        },
        "type_marche": {
            "source": "Accord-cadre mono attributaire mixte",
            "consolide": "accord-cadre mono-attributaire mixte",
            "categorie_normee": "accord_cadre_mixte"
        }
    },
    
    # Euro-Métropole de Metz - 26910A
    "s fournitures et services List": {
        "new_ref": "26910A",
        "titre": "Accord-cadre de services : Achats, maintenances et évolution du système de sauvegarde",
        "reference": "26910A",
        "acheteur": {
            "nom": "Euro-Métropole de Metz",
            "structure_juridique": "Métropole",
            "categorie_normee": "collectivite_territoriale"
        },
        "lieu": {
            "adresse": "1 place du Parlement de Metz, CS30353",
            "ville": "Metz",
            "code_postal": "57011",
            "pays": "France"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-08T12:00:00+02:00",
            "valeur_brute": "08/06/2026 à 12:00",
            "fuseau_horaire": "Europe/Paris"
        },
        "procedure": {
            "source": "Appel d'offres ouvert",
            "consolidee": "appel d'offres ouvert",
            "regime": "droit_commun"
        },
        "type_marche": {
            "source": "Accord-cadre de services",
            "consolide": "accord-cadre",
            "categorie_normee": "accord_cadre_bc"
        }
    },
    
    # Conseil régional Auvergne-Rhône-Alpes - 26A0133001
    "s de prestations effectuées au": {
        "new_ref": "26A0133001",
        "titre": "Accompagnement à l'extension de l'ITSM de la DSI",
        "reference": "26A0133001",
        "acheteur": {
            "nom": "Conseil régional Auvergne-Rhône-Alpes",
            "structure_juridique": "Conseil régional",
            "categorie_normee": "collectivite_territoriale"
        },
        "lieu": {
            "adresse": "101 cours Charlemagne, CS 20033",
            "ville": "Lyon",
            "code_postal": "69269",
            "pays": "France"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-16T12:00:00+02:00",
            "valeur_brute": "16/06/2026 à 12:00",
            "fuseau_horaire": "Europe/Paris"
        },
        "procedure": {
            "source": "Appel d'offres ouvert",
            "consolidee": "appel d'offres ouvert",
            "regime": "droit_commun"
        }
    },
    
    # INPI - DAF_2026_000243
    "327838-2026. 1. Objet du march": {
        "new_ref": "DAF_2026_000243",
        "titre": "Portails HISI - Prestations de développement et maintenance applicative",
        "reference": "DAF_2026_000243",
        "acheteur": {
            "nom": "Institut National de la Propriété Industrielle (INPI)",
            "structure_juridique": "Établissement public à caractère administratif",
            "categorie_normee": "EPA"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-15T12:00:00+02:00",
            "valeur_brute": "15/06/2026 à 12:00",
            "fuseau_horaire": "Europe/Paris"
        },
        "procedure": {
            "source": "Procédure avec négociation",
            "consolidee": "procédure avec négociation",
            "regime": "droit_commun"
        }
    },
    
    # CEA-Liten - B26-01107-LS
    "s du responsable du marché, -": {
        "new_ref": "B26-01107-LS",
        "titre": "Prestations de Tierce Maintenance Applicative (TMA) des Logiciels Systèmes Energétiques du CEA-Liten",
        "reference": "B26-01107-LS",
        "acheteur": {
            "nom": "CEA - Commissariat à l'Énergie Atomique et aux Énergies Alternatives",
            "structure_juridique": "Établissement public à caractère industriel et commercial",
            "categorie_normee": "EPIC"
        },
        "lieu": {
            "adresse": "17 avenue des Martyrs",
            "ville": "Grenoble",
            "code_postal": "38054",
            "pays": "France"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-08-16T12:00:00+02:00",
            "valeur_brute": "16/08/2026 à 12:00",
            "fuseau_horaire": "Europe/Paris"
        },
        "procedure": {
            "source": "Appel d'offres ouvert",
            "consolidee": "appel d'offres ouvert",
            "regime": "droit_commun"
        }
    },
    
    # Missions d'infogérance - MS 26084
    "s au CCTP mentionnées dans le": {
        "new_ref": "MS26084",
        "titre": "Missions d'infogérance de systèmes d'information",
        "reference": "MS26084",
        "acheteur": {
            "nom": "Conseil départemental de la Haute-Savoie",
            "structure_juridique": "Conseil départemental",
            "categorie_normee": "collectivite_territoriale"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-11T12:00:00+02:00",
            "valeur_brute": "11/06/2026 à 12h00",
            "fuseau_horaire": "Europe/Paris"
        },
        "procedure": {
            "source": "Appel d'offres ouvert",
            "consolidee": "appel d'offres ouvert",
            "regime": "droit_commun"
        }
    },
    
    # 2026-04
    "2026-04": {
        "titre": "Prestations de services informatiques",
        "acheteur": {
            "nom": "Non précisé",
            "structure_juridique": "non précisé"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-17T12:00:00+02:00",
            "valeur_brute": "17/06/2026",
            "fuseau_horaire": "Europe/Paris"
        }
    },
    
    # Chatbot
    "s récentes (achevées depuis mo": {
        "new_ref": "2026-CHATBOT",
        "titre": "Développement et maintenance d'un chatbot",
        "reference": "2026-CHATBOT",
        "acheteur": {
            "nom": "Non précisé",
            "structure_juridique": "non précisé"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-02T12:00:00+02:00",
            "valeur_brute": "02/06/2026",
            "fuseau_horaire": "Europe/Paris"
        }
    },
    
    # 2018-347 / Département Vendée - 20260206_WEB
    "2018-347": {
        "new_ref": "2026-0206-WEB",
        "titre": "Maintenance, hébergement et développements des sites et applicatifs web du Département de la Vendée",
        "reference": "2026-0206-WEB",
        "acheteur": {
            "nom": "Département de la Vendée",
            "structure_juridique": "Conseil départemental",
            "categorie_normee": "collectivite_territoriale"
        },
        "date_limite_remise_offres": {
            "valeur_iso": "2026-06-12T12:00:00+02:00",
            "valeur_brute": "12/06/2026",
            "fuseau_horaire": "Europe/Paris"
        },
        "procedure": {
            "source": "Accord-cadre",
            "consolidee": "accord-cadre",
            "regime": "droit_commun"
        }
    }
}

# Identifiants de marchés à supprimer (incorrects)
BAD_REFS = [
    "s de prestations similaires ré",
    "48900000",
    "s fournitures et services List",
    "s de prestations effectuées au",
    "327838-2026. 1. Objet du march",
    "s du responsable du marché, -",
    "s au CCTP mentionnées dans le",
    "s récentes (achevées depuis mo",
    "2018-347"
]


def fix_json():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    marches = data.get("marches", [])
    print(f"Nombre de marchés avant nettoyage: {len(marches)}")
    
    # Filtrer les marchés incorrects
    cleaned_marches = []
    removed_count = 0
    
    for market in marches:
        ref = market.get("reference_consolidee", "")
        if ref in BAD_REFS:
            print(f"Suppression: {ref}")
            removed_count += 1
            continue
        
        # Corriger 2026A0239 si présent
        if ref == "2026A0239":
            if ref in corrections:
                print(f"Correction: {ref}")
                market["titre"] = corrections[ref].get("titre", market.get("titre"))
                if "acheteur" in corrections[ref]:
                    market["acheteur"].update(corrections[ref]["acheteur"])
                if "date_limite_remise_offres" in corrections[ref]:
                    market["date_limite_remise_offres"].update(corrections[ref]["date_limite_remise_offres"])
        
        cleaned_marches.append(market)
    
    print(f"Marchés supprimés: {removed_count}")
    
    # Créer les nouveaux marchés corrigés
    new_markets = []
    
    for bad_ref, fix_data in corrections.items():
        if bad_ref == "2026A0239":
            continue  # Déjà corrigé ci-dessus
        
        if "new_ref" in fix_data:
            new_market = {
                "reference": fix_data["new_ref"],
                "reference_source": fix_data["new_ref"],
                "reference_consolidee": fix_data["new_ref"],
                "identification_confiance": "moyen",
                "titre": fix_data.get("titre", "non précisé"),
                "acheteur": fix_data.get("acheteur", {"nom": "non précisé", "structure_juridique": "non précisé", "categorie_normee": "non_precise"}),
                "lieu": fix_data.get("lieu", {"adresse": None, "code_postal": None, "ville": None, "pays": "France", "source_brute": "non précisé"}),
                "date_limite_remise_offres": fix_data.get("date_limite_remise_offres", {"valeur_iso": None, "valeur_brute": "non précisé", "fuseau_horaire": "Europe/Paris", "source_brute": "non précisé"}),
                "plateforme_remise_offres": {"nom": "non précisé", "url": None, "source_brute": "non précisé"},
                "type_marche": fix_data.get("type_marche", {"source": "non précisé", "consolide": "services", "categorie_normee": "services"}),
                "procedure": fix_data.get("procedure", {"source": "non précisé", "consolidee": "non précisé", "regime": "droit_commun", "niveau_preuve": "deduit"}),
                "duree": {"valeur": None, "unite": "mois", "structure": "non précisé", "source_brute": "non précisé"},
                "montants": {
                    "global": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
                    "estime": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
                    "maximum": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
                    "minimum": {"valeur": None, "devise": "EUR", "precision": "non précisé", "source_brute": "non précisé", "nature": "non_precise"},
                    "nature_marche": "services"
                },
                "allotissement": {"statut": "non_alloti", "nombre_lots": 0, "source_brute": "non précisé"},
                "ccag": {"mentionne": False, "source_brute": "non précisé", "principal": None, "categorie_normee": "non_precise", "mode_determination": "non_precise", "niveau_preuve": "absent", "hypothese": None},
                "lots": [],
                "criteres_selection": [],
                "dce": {"pieces_constitutives": []},
                "conflits": [],
                "controle": {"statut_verification": "partiellement_verifie", "niveau_confiance": "moyen", "qualite_extraction": "moyenne", "commentaire": "Données corrigées manuellement"},
                "source_extrait": {"fichier": "public/rc", "page": 1, "section": "Page de garde", "citation_brute": fix_data.get("titre", "non précisé")}
            }
            new_markets.append(new_market)
            print(f"Ajouté: {fix_data['new_ref']}")
    
    # Ajouter les nouveaux marchés
    cleaned_marches.extend(new_markets)
    
    print(f"Nombre de marchés après nettoyage: {len(cleaned_marches)}")
    print(f"Nouveaux marchés ajoutés: {len(new_markets)}")
    
    # Sauvegarder
    data["marches"] = cleaned_marches
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\nFichier sauvegardé: {JSON_FILE}")


if __name__ == "__main__":
    fix_json()
