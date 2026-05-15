#!/usr/bin/env python3
"""
Script de nettoyage des fichiers obsolètes du projet AO-DCE.
Supprime les fichiers CSV, JSON, MD et LOG identifiés comme obsolètes.

Auteur: Pipeline AO-DCE
Version: 1.0 — 15 mai 2026
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple
from datetime import datetime


# ============================================================================
# LISTE DES FICHIERS À SUPPRIMER
# ============================================================================

FILES_TO_DELETE = {
    "csv": [
        # Anciennes versions legacy et v2
        "/home/michka/Documents/0-AO-DCE/data/output/final-legacy.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v2.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v2-stabilise.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/AO-pipeline-v2.csv",
        
        # Fichiers de test
        "/home/michka/Documents/0-AO-DCE/data/output/test-legacy.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/test-v2.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/test-v2-patched.csv",
        
        # Anciennes méthodes de classification
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-llm.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-rule.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified.csv",
        
        # Versions intermédiaires v2 à v8
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v2.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v3.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v4.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v5.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v6.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v7.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v8.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v8b.csv",
        
        # Version non classifiée
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated.csv",
        
        # Fichiers redondants (versions contract)
        "/home/michka/Documents/0-AO-DCE/data/output/AO-metier-consolide-v10-contract.csv",
        "/home/michka/Documents/0-AO-DCE/data/output/AO-audit-complet-v10-contract.csv",
    ],
    
    "json": [
        # Anciennes versions
        "/home/michka/Documents/0-AO-DCE/data/output/final-legacy.json",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v2.json",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v2-stabilise.json",
        "/home/michka/Documents/0-AO-DCE/data/output/AO-pipeline-v2.json",
        "/home/michka/Documents/0-AO-DCE/data/output/extraction-champs-html.json",
        
        # Rapports d'archive
        "/home/michka/Documents/0-AO-DCE/archive/reports/rapport_redondances.json",
        "/home/michka/Documents/0-AO-DCE/archive/reports/update_report.json",
    ],
    
    "md": [
        # Rapports et résumés obsolètes (racine)
        "/home/michka/Documents/0-AO-DCE/EXTRACTION_FIX_REPORT.md",
        "/home/michka/Documents/0-AO-DCE/EXTRACTION_IMPROVEMENTS_SUMMARY.md",
        "/home/michka/Documents/0-AO-DCE/EXTRACTION_V2_SUMMARY.md",
        "/home/michka/Documents/0-AO-DCE/POINT_OF_ENTRY_CLARIFICATION.md",
        "/home/michka/Documents/0-AO-DCE/QA_VERIFICATION_REPORT.md",
        "/home/michka/Documents/0-AO-DCE/README_WORKFLOW.md",
        "/home/michka/Documents/0-AO-DCE/RECETTE_FINALE_QA.md",
        "/home/michka/Documents/0-AO-DCE/RESTRUCTURING_EXECUTION_REPORT.md",
        "/home/michka/Documents/0-AO-DCE/RESTRUCTURING_PLAN.md",
        "/home/michka/Documents/0-AO-DCE/STABILISATION_REPORT.md",
        
        # Archive
        "/home/michka/Documents/0-AO-DCE/archive/docs/QA_CHECKLIST_V1.md",
        "/home/michka/Documents/0-AO-DCE/archive/reports/rapport-extraction.md",
        "/home/michka/Documents/0-AO-DCE/archive/reports/rapport-validation.md",
        
        # Output data
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classification-quality.md",
        "/home/michka/Documents/0-AO-DCE/data/output/report-buyer-classification-quality.md",
        
        # Docs obsolètes
        "/home/michka/Documents/0-AO-DCE/docs/REFACTORING_SUMMARY.md",
        "/home/michka/Documents/0-AO-DCE/docs/RESTRUCTURING_SUMMARY.md",
        "/home/michka/Documents/0-AO-DCE/docs/extraction_v2_migration.md",
    ],
    
    "log": [
        "/home/michka/Documents/0-AO-DCE/recette_execution.log",
        "/home/michka/Documents/0-AO-DCE/reports/logs/pipeline-v2-execution.log",
    ],
    
    "xlsx": [
        # Exports Excel obsolètes du pipeline (versions intermédiaires)
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v2.xlsx",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v3.xlsx",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v4.xlsx",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v5.xlsx",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v6.xlsx",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v7.xlsx",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v8.xlsx",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique-v8b.xlsx",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-juridique.xlsx",
        "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated-classified-readable.xlsx",
    ]
}

# Dossiers à nettoyer (fichiers JSON individuels)
JSON_INDIVIDUAL_DIR = "/home/michka/Documents/0-AO-DCE/data/output/final-v3-consolidated"


def get_individual_json_files() -> List[str]:
    """Récupère la liste des fichiers JSON individuels dans le dossier final-v3-consolidated."""
    json_files = []
    dir_path = Path(JSON_INDIVIDUAL_DIR)
    
    if dir_path.exists():
        for file in dir_path.iterdir():
            if file.is_file() and file.suffix == '.json':
                json_files.append(str(file))
    
    return sorted(json_files)


def check_files_existence(files: List[str]) -> Tuple[List[str], List[str]]:
    """Vérifie quels fichiers existent et lesquels sont déjà absents."""
    existing = []
    missing = []
    
    for file in files:
        if Path(file).exists():
            existing.append(file)
        else:
            missing.append(file)
    
    return existing, missing


def delete_files(files: List[str]) -> Tuple[int, List[str]]:
    """Supprime les fichiers et retourne le nombre de succès + liste des erreurs."""
    deleted_count = 0
    errors = []
    
    for file in files:
        try:
            Path(file).unlink()
            deleted_count += 1
        except Exception as e:
            errors.append(f"{file}: {e}")
    
    return deleted_count, errors


def format_size(bytes_size: int) -> str:
    """Formate la taille en bytes en format lisible."""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    else:
        return f"{bytes_size / (1024 * 1024):.1f} MB"


def calculate_total_size(files: List[str]) -> int:
    """Calcule la taille totale des fichiers existants."""
    total = 0
    for file in files:
        path = Path(file)
        if path.exists():
            total += path.stat().st_size
    return total


def main():
    """Point d'entrée principal."""
    print("=" * 80)
    print("NETTOYAGE DES FICHIERS OBSOLÈTES — AO-DCE")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Récupérer les JSON individuels
    individual_json = get_individual_json_files()
    
    # Statistiques par catégorie
    stats = {
        "csv": {"planned": 0, "existing": 0, "deleted": 0, "size": 0},
        "json": {"planned": 0, "existing": 0, "deleted": 0, "size": 0},
        "md": {"planned": 0, "existing": 0, "deleted": 0, "size": 0},
        "log": {"planned": 0, "existing": 0, "deleted": 0, "size": 0},
        "xlsx": {"planned": 0, "existing": 0, "deleted": 0, "size": 0},
        "json_individual": {"planned": 0, "existing": 0, "deleted": 0, "size": 0},
    }
    
    all_errors = []
    
    # Traiter chaque catégorie
    for category, files in FILES_TO_DELETE.items():
        print(f"\n📁 Catégorie: {category.upper()}")
        print("-" * 40)
        
        existing, missing = check_files_existence(files)
        stats[category]["planned"] = len(files)
        stats[category]["existing"] = len(existing)
        stats[category]["size"] = calculate_total_size(existing)
        
        print(f"  Fichiers planifiés: {len(files)}")
        print(f"  Fichiers existants: {len(existing)}")
        print(f"  Déjà absents: {len(missing)}")
        print(f"  Taille totale: {format_size(stats[category]['size'])}")
        
        if existing:
            print(f"  → Suppression en cours...")
            deleted, errors = delete_files(existing)
            stats[category]["deleted"] = deleted
            all_errors.extend(errors)
            print(f"  ✅ Supprimés: {deleted}/{len(existing)}")
        else:
            print(f"  ℹ️ Aucun fichier à supprimer")
    
    # Traiter les JSON individuels
    print(f"\n📁 Catégorie: JSON INDIVIDUELS (final-v3-consolidated/)")
    print("-" * 40)
    
    stats["json_individual"]["planned"] = len(individual_json)
    existing_json, missing_json = check_files_existence(individual_json)
    stats["json_individual"]["existing"] = len(existing_json)
    stats["json_individual"]["size"] = calculate_total_size(existing_json)
    
    print(f"  Fichiers planifiés: {len(individual_json)}")
    print(f"  Fichiers existants: {len(existing_json)}")
    print(f"  Taille totale: {format_size(stats['json_individual']['size'])}")
    
    if existing_json:
        print(f"  → Suppression en cours...")
        deleted, errors = delete_files(existing_json)
        stats["json_individual"]["deleted"] = deleted
        all_errors.extend(errors)
        print(f"  ✅ Supprimés: {deleted}/{len(existing_json)}")
    else:
        print(f"  ℹ️ Aucun fichier à supprimer")
    
    # Supprimer le dossier final-v3-consolidated s'il est vide
    json_dir = Path(JSON_INDIVIDUAL_DIR)
    if json_dir.exists():
        try:
            # Vérifier s'il reste des fichiers
            remaining = list(json_dir.iterdir())
            if not remaining:
                json_dir.rmdir()
                print(f"  📂 Dossier supprimé: {JSON_INDIVIDUAL_DIR}")
            else:
                print(f"  ⚠️ Dossier non vide ({len(remaining)} éléments restants): {JSON_INDIVIDUAL_DIR}")
        except Exception as e:
            print(f"  ⚠️ Impossible de supprimer le dossier: {e}")
    
    # Bilan final
    print("\n" + "=" * 80)
    print("BILAN FINAL")
    print("=" * 80)
    
    total_planned = sum(s["planned"] for s in stats.values())
    total_deleted = sum(s["deleted"] for s in stats.values())
    total_size = sum(s["size"] for s in stats.values())
    
    print(f"\n{'Catégorie':<25} {'Planifiés':>10} {'Supprimés':>10} {'Taille':>12}")
    print("-" * 60)
    for category, stat in stats.items():
        if stat["planned"] > 0:
            print(f"{category:<25} {stat['planned']:>10} {stat['deleted']:>10} {format_size(stat['size']):>12}")
    
    print("-" * 60)
    print(f"{'TOTAL':<25} {total_planned:>10} {total_deleted:>10} {format_size(total_size):>12}")
    
    if all_errors:
        print(f"\n⚠️ Erreurs rencontrées ({len(all_errors)}):")
        for error in all_errors[:10]:
            print(f"  - {error}")
        if len(all_errors) > 10:
            print(f"  ... et {len(all_errors) - 10} autres erreurs")
    else:
        print(f"\n✅ Aucune erreur rencontrée")
    
    print(f"\n🎉 Nettoyage terminé!")
    print(f"   {total_deleted} fichiers supprimés")
    print(f"   {format_size(total_size)} libérés")
    
    return len(all_errors) == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
