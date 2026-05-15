#!/usr/bin/env python3
"""
Script de séparation CSV Métier / Audit.

Sépare le fichier consolidé en deux vues :
1. CSV Métier : vue compacte pour lecture/correction humaine
2. CSV Audit : vue complète avec toutes les preuves et calculs

Auteur: Pipeline AO-DCE
Version: 1.0 — 14 mai 2026
"""

import csv
import sys
from pathlib import Path
from typing import List, Dict, Set


# ============================================================================
# CONFIGURATION DES COLONNES
# ============================================================================

# Colonnes à conserver dans la vue MÉTIER (lecture/correction humaine)
COLONNES_METIER = [
    "reference",
    "titre",
    "acheteur",
    "type_acheteur",
    "type_marche",
    "procedure_source",
    "procedure_consolidee",
    "procedure_regime",
    "montant_estime",
    "date_limite_remise_offres",
    "url_marche",
    "fichier_source_html",
    "conflit_coherence",
    "motif_conflit",
]

# Colonnes spécifiques de consolidation à déplacer dans l'audit
COLONNES_CONSOLIDATION_AUDIT = [
    "source_procedure_evidence",
    "montant_estime_ht_parsed",
    "seuil_applicable_ht",
    "ratio_montant_sur_seuil",
    "priorite_juridique",
    "niveau_confiance",
    "procedure_verdict",
    "verdict_final",
    "notes_consolidation",
]

# Colonnes techniques du pipeline à déplacer dans l'audit
COLONNES_TECHNIQUES_AUDIT = [
    # Champs de classification juridique
    "famille_procedure_deduite",
    "typologie_marche_verifiee",
    "seuil_formalise_applicable",
    "ccag_type",
    "verification_requise",
    "raisons_verification",
    "notes_verification",
    "qualite_preuve_procedure",
    "conflit_detecte",
    "type_conflit",
    "preuve_regime",
    "preuve_typologie",
    "preuve_joue_detectee",
    "source_preuve_joue",
    "justification_juridique_courte",
    "code_couleur_procedure",
    "niveau_procedure_deduit",
    "url_provenance",
    
    # Champs d'audit HTML
    "audit_verdict",
    "audit_contamination_effective",
    "audit_risque",
    "audit_zones_annexes",
    "audit_notes",
    
    # Champs de contexte (optionnels dans métier)
    "fonction_publique",
    "categorie_regime",
    "duree",
    "renouvellements",
    "localisation",
    "cpv_principal",
    "cpv_secondaires",
]


def split_csv(input_path: Path, metier_path: Path, audit_path: Path) -> Dict:
    """
    Sépare le CSV source en deux fichiers : métier et audit.
    
    Retourne un rapport de transformation.
    """
    # Lire le CSV source
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        all_columns = reader.fieldnames.copy()
    
    if not rows:
        raise ValueError("Le fichier source est vide")
    
    total_rows = len(rows)
    
    # Identifier les colonnes métier présentes
    metier_columns_present = [col for col in COLONNES_METIER if col in all_columns]
    
    # Identifier les colonnes audit (toutes les autres)
    audit_columns = [
        col for col in all_columns 
        if col not in metier_columns_present
    ]
    
    # Catégoriser les colonnes audit pour le rapport
    consolidation_in_audit = [c for c in audit_columns if c in COLONNES_CONSOLIDATION_AUDIT]
    technique_in_audit = [c for c in audit_columns if c in COLONNES_TECHNIQUES_AUDIT]
    other_in_audit = [c for c in audit_columns if c not in COLONNES_CONSOLIDATION_AUDIT and c not in COLONNES_TECHNIQUES_AUDIT]
    
    # Ajouter la clé de liaison dans l'audit (reference)
    if "reference" not in audit_columns:
        audit_columns.insert(0, "reference")
    
    # Écrire le CSV Métier
    with open(metier_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=metier_columns_present)
        writer.writeheader()
        for row in rows:
            metier_row = {col: row.get(col, "") for col in metier_columns_present}
            writer.writerow(metier_row)
    
    # Écrire le CSV Audit
    with open(audit_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=audit_columns)
        writer.writeheader()
        for row in rows:
            audit_row = {col: row.get(col, "") for col in audit_columns}
            writer.writerow(audit_row)
    
    # Rapport
    rapport = {
        "total_rows": total_rows,
        "total_columns_source": len(all_columns),
        "columns_metier": len(metier_columns_present),
        "columns_audit": len(audit_columns),
        "metier_present": metier_columns_present,
        "audit_consolidation": consolidation_in_audit,
        "audit_technique": technique_in_audit,
        "audit_other": other_in_audit,
        "missing_metier": [c for c in COLONNES_METIER if c not in all_columns],
    }
    
    return rapport


def print_rapport(rapport: Dict, metier_path: Path, audit_path: Path):
    """Affiche le rapport de transformation."""
    print()
    print("=" * 70)
    print("RAPPORT DE SÉPARATION CSV MÉTIER / AUDIT")
    print("=" * 70)
    print()
    print(f"📊 Statistiques:")
    print(f"   Lignes traitées:           {rapport['total_rows']}")
    print(f"   Colonnes source:           {rapport['total_columns_source']}")
    print(f"   → Colonnes CSV Métier:     {rapport['columns_metier']}")
    print(f"   → Colonnes CSV Audit:      {rapport['columns_audit']}")
    print()
    
    print("=" * 70)
    print("COLONNES CONSERVÉES DANS CSV MÉTIER")
    print("=" * 70)
    for i, col in enumerate(rapport['metier_present'], 1):
        print(f"  {i:2d}. {col}")
    print()
    
    if rapport['missing_metier']:
        print("⚠️  Colonnes métier manquantes dans la source:")
        for col in rapport['missing_metier']:
            print(f"     - {col}")
        print()
    
    print("=" * 70)
    print("COLONNES DÉPLACÉES DANS CSV AUDIT")
    print("=" * 70)
    
    if rapport['audit_consolidation']:
        print()
        print("  📋 Consolidation de procédure:")
        for col in rapport['audit_consolidation']:
            print(f"     - {col}")
    
    if rapport['audit_technique']:
        print()
        print("  ⚙️  Données techniques pipeline:")
        for col in rapport['audit_technique'][:10]:  # Limiter l'affichage
            print(f"     - {col}")
        if len(rapport['audit_technique']) > 10:
            print(f"     ... et {len(rapport['audit_technique']) - 10} autres colonnes")
    
    if rapport['audit_other']:
        print()
        print("  📁 Autres colonnes:")
        for col in rapport['audit_other']:
            print(f"     - {col}")
    
    print()
    print("=" * 70)
    print("FICHIERS GÉNÉRÉS")
    print("=" * 70)
    print(f"  📄 CSV Métier:  {metier_path}")
    print(f"  📄 CSV Audit:   {audit_path}")
    print()
    print("✅ Transformation terminée avec succès!")
    print()
    print("📌 Utilisation recommandée:")
    print("   - CSV Métier: Ouvrir dans Google Sheets pour relecture/correction")
    print("   - CSV Audit:  Conserver comme référence de traçabilité complète")


def main():
    """Point d'entrée principal."""
    input_file = Path('/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v10.csv')
    metier_file = Path('/home/michka/Documents/0-AO-DCE/data/output/AO-metier-consolide-v10.csv')
    audit_file = Path('/home/michka/Documents/0-AO-DCE/data/output/AO-audit-complet-v10.csv')
    
    if not input_file.exists():
        print(f"❌ Erreur: {input_file} n'existe pas")
        sys.exit(1)
    
    print("=" * 70)
    print("SÉPARATION CSV MÉTIER / AUDIT")
    print("=" * 70)
    print()
    print(f"📁 Fichier source: {input_file}")
    print()
    
    try:
        rapport = split_csv(input_file, metier_file, audit_file)
        print_rapport(rapport, metier_file, audit_file)
    except Exception as e:
        print(f"❌ Erreur lors du traitement: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
