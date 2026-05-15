#!/usr/bin/env python3
"""Transforme extraction_rc.json en CSV comparatif."""

import json
import csv
import sys

def safe_get(obj, key, default="non_precise"):
    """Récupère une valeur de manière sécurisée."""
    if obj is None:
        return default
    return obj.get(key, default) if obj.get(key) is not None else default

def format_criteres(criteres):
    """Formate les critères de sélection."""
    if not criteres:
        return "non_precise"
    parts = []
    for c in criteres:
        crit = c.get("critere", "")
        pond = c.get("ponderation", "")
        if crit and pond:
            parts.append(f"{crit} {pond}")
    return " | ".join(parts) if parts else "non_precise"

def format_pieces(pieces):
    """Formate les pièces DCE."""
    if not pieces:
        return "non_precise"
    return " ; ".join([p.get("nom", "") for p in pieces if p.get("nom")])

def format_conflits(conflits):
    """Formate les conflits."""
    if not conflits:
        return "non"
    return "oui"

def format_motif_conflit(conflits):
    """Formate le motif de conflit."""
    if not conflits:
        return ""
    parts = []
    for c in conflits:
        champ = c.get("champ", "")
        motif = c.get("motif_conflit", "")
        if champ and motif:
            parts.append(f"[{champ}] {motif}")
    return " | ".join(parts) if parts else ""

def main():
    with open("/home/michka/Documents/0-AO-DCE/extraction_rc.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    marches = data.get("marches", [])

    headers = [
        "reference",
        "reference_source",
        "reference_consolidee",
        "titre",
        "acheteur_nom",
        "acheteur_structure_juridique",
        "acheteur_categorie_normee",
        "acheteur_service_interne",
        "lieu_ville",
        "lieu_code_postal",
        "lieu_pays",
        "date_limite_remise_offres_iso",
        "date_limite_remise_offres_brute",
        "plateforme_nom",
        "plateforme_url",
        "type_marche_source",
        "type_marche_consolide",
        "type_marche_norme",
        "procedure_source",
        "procedure_consolidee",
        "procedure_regime",
        "allotissement_statut",
        "nombre_lots",
        "lot_numero",
        "lot_titre",
        "lot_objet",
        "lot_description_technique_succincte",
        "montant_global_valeur",
        "montant_global_devise",
        "montant_estime_valeur",
        "montant_estime_devise",
        "montant_maximum_valeur",
        "montant_maximum_devise",
        "montant_minimum_valeur",
        "montant_minimum_devise",
        "nature_marche",
        "ccag_mentionne",
        "ccag_principal",
        "ccag_hypothese",
        "ccag_mode_determination",
        "niveau_preuve_ccag",
        "criteres_selection",
        "pieces_dce",
        "conflits",
        "motif_conflit",
        "statut_verification",
        "niveau_confiance",
        "qualite_extraction",
        "commentaire_controle"
    ]

    rows = []

    for marche in marches:
        base_row = {
            "reference": safe_get(marche, "reference"),
            "reference_source": safe_get(marche, "reference_source"),
            "reference_consolidee": safe_get(marche, "reference_consolidee"),
            "titre": safe_get(marche, "titre"),
            "acheteur_nom": safe_get(marche.get("acheteur"), "nom"),
            "acheteur_structure_juridique": safe_get(marche.get("acheteur"), "structure_juridique"),
            "acheteur_categorie_normee": safe_get(marche.get("acheteur"), "categorie_normee"),
            "acheteur_service_interne": safe_get(marche.get("acheteur"), "service_interne"),
            "lieu_ville": safe_get(marche.get("lieu"), "ville"),
            "lieu_code_postal": safe_get(marche.get("lieu"), "code_postal"),
            "lieu_pays": safe_get(marche.get("lieu"), "pays"),
            "date_limite_remise_offres_iso": safe_get(marche.get("date_limite_remise_offres"), "valeur_iso"),
            "date_limite_remise_offres_brute": safe_get(marche.get("date_limite_remise_offres"), "valeur_brute"),
            "plateforme_nom": safe_get(marche.get("plateforme_remise_offres"), "nom"),
            "plateforme_url": safe_get(marche.get("plateforme_remise_offres"), "url"),
            "type_marche_source": safe_get(marche.get("type_marche"), "source"),
            "type_marche_consolide": safe_get(marche.get("type_marche"), "consolide"),
            "type_marche_norme": safe_get(marche.get("type_marche"), "categorie_normee"),
            "procedure_source": safe_get(marche.get("procedure"), "source"),
            "procedure_consolidee": safe_get(marche.get("procedure"), "consolidee"),
            "procedure_regime": safe_get(marche.get("procedure"), "regime"),
            "allotissement_statut": safe_get(marche.get("allotissement"), "statut"),
            "nombre_lots": str(safe_get(marche.get("allotissement"), "nombre_lots", "0")),
            "nature_marche": safe_get(marche.get("montants"), "nature_marche"),
            "ccag_mentionne": str(safe_get(marche.get("ccag"), "mentionne", "non_precise")).lower(),
            "ccag_principal": safe_get(marche.get("ccag"), "principal", ""),
            "ccag_hypothese": safe_get(marche.get("ccag"), "hypothese", ""),
            "ccag_mode_determination": safe_get(marche.get("ccag"), "mode_determination"),
            "niveau_preuve_ccag": safe_get(marche.get("ccag"), "niveau_preuve"),
            "statut_verification": safe_get(marche.get("controle"), "statut_verification"),
            "niveau_confiance": safe_get(marche.get("controle"), "niveau_confiance"),
            "qualite_extraction": safe_get(marche.get("controle"), "qualite_extraction"),
            "commentaire_controle": safe_get(marche.get("controle"), "commentaire"),
        }

        # Traitement des montants
        montants = marche.get("montants", {})
        base_row["montant_global_valeur"] = str(safe_get(montants.get("global"), "valeur", "")).replace("None", "")
        base_row["montant_global_devise"] = safe_get(montants.get("global"), "devise", "")
        base_row["montant_estime_valeur"] = str(safe_get(montants.get("estime"), "valeur", "")).replace("None", "")
        base_row["montant_estime_devise"] = safe_get(montants.get("estime"), "devise", "")
        base_row["montant_maximum_valeur"] = str(safe_get(montants.get("maximum"), "valeur", "")).replace("None", "")
        base_row["montant_maximum_devise"] = safe_get(montants.get("maximum"), "devise", "")
        base_row["montant_minimum_valeur"] = str(safe_get(montants.get("minimum"), "valeur", "")).replace("None", "")
        base_row["montant_minimum_devise"] = safe_get(montants.get("minimum"), "devise", "")

        # Pièces DCE
        dce = marche.get("dce", {})
        pieces = dce.get("pieces_constitutives", [])
        base_row["pieces_dce"] = format_pieces(pieces)

        # Conflits
        conflits = marche.get("conflits", [])
        base_row["conflits"] = format_conflits(conflits)
        base_row["motif_conflit"] = format_motif_conflit(conflits)

        lots = marche.get("lots", [])
        allotissement_statut = base_row["allotissement_statut"]

        if allotissement_statut == "alloti" and lots:
            # Une ligne par lot
            for lot in lots:
                lot_row = base_row.copy()
                lot_row["lot_numero"] = safe_get(lot, "lot_numero", "")
                lot_row["lot_titre"] = safe_get(lot, "lot_titre", "")
                lot_row["lot_objet"] = safe_get(lot, "lot_objet", "")
                lot_row["lot_description_technique_succincte"] = safe_get(lot, "description_technique_succincte", "")

                # Montants du lot
                lot_montants = lot.get("montants", {})
                lot_row["montant_global_valeur"] = str(safe_get(lot_montants.get("global"), "valeur", "")).replace("None", "")
                lot_row["montant_global_devise"] = safe_get(lot_montants.get("global"), "devise", "")
                lot_row["montant_estime_valeur"] = str(safe_get(lot_montants.get("estime"), "valeur", "")).replace("None", "")
                lot_row["montant_estime_devise"] = safe_get(lot_montants.get("estime"), "devise", "")
                lot_row["montant_maximum_valeur"] = str(safe_get(lot_montants.get("maximum"), "valeur", "")).replace("None", "")
                lot_row["montant_maximum_devise"] = safe_get(lot_montants.get("maximum"), "devise", "")
                lot_row["montant_minimum_valeur"] = str(safe_get(lot_montants.get("minimum"), "valeur", "")).replace("None", "")
                lot_row["montant_minimum_devise"] = safe_get(lot_montants.get("minimum"), "devise", "")

                # Critères du lot
                criteres = lot.get("criteres_selection", [])
                lot_row["criteres_selection"] = format_criteres(criteres)

                rows.append(lot_row)
        else:
            # Marché non alloti ou sans lots détaillés
            base_row["lot_numero"] = ""
            base_row["lot_titre"] = ""
            base_row["lot_objet"] = ""
            base_row["lot_description_technique_succincte"] = ""
            base_row["criteres_selection"] = "non_precise"
            rows.append(base_row)

    # Écriture CSV
    with open("/home/michka/Documents/0-AO-DCE/comparatif_marches.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"CSV généré: comparatif_marches.csv ({len(rows)} lignes)")

if __name__ == "__main__":
    main()
