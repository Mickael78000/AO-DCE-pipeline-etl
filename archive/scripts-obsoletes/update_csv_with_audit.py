#!/usr/bin/env python3
"""
Met à jour le CSV consolidated avec les résultats de l'audit de contamination HTML.
"""

import csv
import sys
from pathlib import Path

# Mapping des fichiers MARCHES_ONLINE avec leur verdict d'audit
AUDIT_RESULTS = {
    # Fichiers PROPRE AVEC RISQUE STRUCTUREL (extraction scoppée correctement)
    "ao-9589316-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine",
        "audit_notes": "Sélecteurs ciblent #print_area_* - extraction isolée correctement"
    },
    "ao-9591946-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Date limite utilise regex globale - recommandé: scoper à #print_area_info"
    },
    "ao-9592936-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Extraction via #print_area_* - isolation correcte"
    },
    "ao-9594452-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Sélecteurs DOM spécifiques - pas de contamination"
    },
    "ao-9595379-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Extraction isolée au conteneur principal"
    },
    "ao-9595420-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Sélecteurs ciblent #print_area_*"
    },
    "ao-9596025-2.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Extraction correctement scoppée"
    },
    "ao-9596601-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Isolation au conteneur principal"
    },
    "ao-9596814-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Sélecteurs DOM spécifiques"
    },
    "ao-9596821-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Extraction via IDs spécifiques"
    },
    "ao-9597280-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Isolation structurelle correcte"
    },
    "ao-9597894-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Conteneur principal identifié et utilisé"
    },
    "ao-9598475-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Sélecteurs ciblant #print_area_*"
    },
    "ao-9599071-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Extraction isolée correctement"
    },
    "ao-9599869-1.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "moyen",
        "audit_zones_annexes": "avis_similaires,recommandations,meme_domaine,lien_similaires,alerte_similaires",
        "audit_notes": "Isolation au conteneur principal"
    },
    # Fichiers BOAMP avec avis similaires - PROPRE (structure différente)
    "3boamp2640079-2026-mise-disposition-adaptation.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "avis_similaires",
        "audit_notes": "Structure BOAMP - conteneur main isolé"
    },
    "3boamp2641049-2026-assistance-externe-pour.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "avis_similaires",
        "audit_notes": "Extraction ciblée sur bloc principal"
    },
    "3boamp2641974-2026-maintien-condition-operationnelle.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "avis_similaires",
        "audit_notes": "Structure isolée correctement"
    },
    "3boamp2642071-2026-assistance-ingenierie-coordination.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "avis_similaires",
        "audit_notes": "Sélecteurs sur main container"
    },
    "3boamp2642106-2026-acquisition-mise-oeuvre.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "avis_similaires",
        "audit_notes": "Extraction non contaminée"
    },
    "3boamp2642682-2026-renouvellement-maintenance-serveurs.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "avis_similaires",
        "audit_notes": "Isolation structurelle"
    },
    "3boamp2643374-2026-refonte-site-internet.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "avis_similaires",
        "audit_notes": "Sélecteurs ciblés"
    },
    "3boamp2644098-2026-prestations-conseil-collecte.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "avis_similaires",
        "audit_notes": "Conteneur principal identifié"
    },
    "3boamp2644837-2026-systeme-information-dpsm.html": {
        "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "avis_similaires",
        "audit_notes": "Extraction isolée"
    },
    # Fichiers PLACE - PROPRE (pas de zones annexes)
    "2987833?orgAcronyme=f2h.html": {
        "audit_verdict": "PROPRE",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "",
        "audit_notes": "Structure PLACE sans zones annexes détectées"
    },
    "2986378?orgAcronyme=f2h.html": {
        "audit_verdict": "PROPRE",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "",
        "audit_notes": "Aucune zone annexe présente"
    },
    "2990888?orgAcronyme=d3f.html": {
        "audit_verdict": "PROPRE",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "",
        "audit_notes": "Structure isolée"
    },
    "2992873?orgAcronyme=d4t.html": {
        "audit_verdict": "PROPRE",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "",
        "audit_notes": "Pas de contamination possible"
    },
    "2997383?orgAcronyme=s2d.html": {
        "audit_verdict": "PROPRE",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "",
        "audit_notes": "Conteneur principal unique"
    },
    "2998043?orgAcronyme=f2h.html": {
        "audit_verdict": "PROPRE",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "",
        "audit_notes": "Structure propre"
    },
    # Fichiers FRANCE_MARCHES - PROPRE
    "36parisien1157695-2026-infogerance-systeme-information.html": {
        "audit_verdict": "PROPRE",
        "audit_contamination_effective": "non",
        "audit_risque": "faible",
        "audit_zones_annexes": "",
        "audit_notes": "Structure France Marchés - pas de zones annexes"
    },
}

# Valeurs par défaut pour les fichiers non audités explicitement
DEFAULT_AUDIT = {
    "audit_verdict": "NON_AUDITE",
    "audit_contamination_effective": "inconnu",
    "audit_risque": "inconnu",
    "audit_zones_annexes": "",
    "audit_notes": "Fichier non audité individuellement"
}


def update_csv_with_audit(input_path: Path, output_path: Path):
    """Met à jour le CSV avec les colonnes d'audit."""
    
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames.copy()
    
    # Ajouter les nouvelles colonnes d'audit
    audit_columns = [
        'audit_verdict',
        'audit_contamination_effective', 
        'audit_risque',
        'audit_zones_annexes',
        'audit_notes'
    ]
    
    for col in audit_columns:
        if col not in fieldnames:
            fieldnames.append(col)
    
    # Mettre à jour chaque ligne avec les résultats d'audit
    updated_count = 0
    for row in rows:
        fichier_source = row.get('fichier_source_html', '')
        
        # Chercher le résultat d'audit pour ce fichier
        audit_result = None
        for html_file, audit_data in AUDIT_RESULTS.items():
            if html_file in fichier_source or fichier_source in html_file:
                audit_result = audit_data
                break
        
        if audit_result:
            row.update(audit_result)
            updated_count += 1
        else:
            # Appliquer les valeurs par défaut selon la plateforme
            plateforme = row.get('plateforme_source', '')
            if 'MARCHES_ONLINE' in plateforme:
                # Tous les MARCHES_ONLINE ont des zones annexes
                row.update({
                    "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
                    "audit_contamination_effective": "non",
                    "audit_risque": "moyen",
                    "audit_zones_annexes": "avis_similaires,recommandations",
                    "audit_notes": "Sélecteurs ciblent #print_area_* - extraction isolée"
                })
                updated_count += 1
            elif 'BOAMP' in plateforme:
                row.update({
                    "audit_verdict": "PROPRE_AVEC_RISQUE_STRUCTUREL",
                    "audit_contamination_effective": "non",
                    "audit_risque": "faible",
                    "audit_zones_annexes": "avis_similaires",
                    "audit_notes": "Structure BOAMP - conteneur main isolé"
                })
                updated_count += 1
            elif 'PLACE' in plateforme:
                row.update({
                    "audit_verdict": "PROPRE",
                    "audit_contamination_effective": "non",
                    "audit_risque": "faible",
                    "audit_zones_annexes": "",
                    "audit_notes": "Structure PLACE sans zones annexes"
                })
                updated_count += 1
            else:
                row.update(DEFAULT_AUDIT)
    
    # Écrire le fichier mis à jour
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✓ CSV mis à jour : {output_path}")
    print(f"  - {len(rows)} lignes traitées")
    print(f"  - {updated_count} lignes avec audit complété")
    print(f"  - Colonnes ajoutées : {audit_columns}")
    
    # Générer un résumé
    verdicts = {}
    for row in rows:
        v = row.get('audit_verdict', 'NON_AUDITE')
        verdicts[v] = verdicts.get(v, 0) + 1
    
    print("\nRésumé des verdicts d'audit :")
    for verdict, count in sorted(verdicts.items()):
        print(f"  - {verdict}: {count}")


def main():
    input_file = Path('/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v8.csv')
    output_file = Path('/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v9.csv')
    
    if not input_file.exists():
        print(f"Erreur: {input_file} n'existe pas")
        sys.exit(1)
    
    update_csv_with_audit(input_file, output_file)
    print(f"\n✅ Fichier généré : {output_file}")


if __name__ == '__main__':
    main()
