#!/usr/bin/env python3
"""Test de consolidation LLM avec utilisation de l'URL source."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from ao_etl.pipeline.consolidate import run_consolidation, ConsolidationConfig
from ao_etl.llm.backend import build_backend

def test_consolidation():
    """Test la consolidation sur quelques marchés avec données manquantes."""
    
    input_csv = Path("data/output/AO-pipeline-v2.csv")
    html_dir = Path("data/raw/html")
    output_dir = Path("data/output/test_consolidation")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Configuration avec dry-run d'abord pour voir les hints
    config_dry = ConsolidationConfig(
        enabled=True,
        llm_backend=build_backend(),
        output_dir=output_dir,
        dry_run=True,  # Dry-run pour voir les hints
        limit=3,  # Seulement 3 marchés pour le test
    )
    
    print("=" * 60)
    print("TEST CONSOLIDATION LLM - DRY RUN")
    print("=" * 60)
    print()
    
    print(f"Input CSV: {input_csv}")
    print(f"HTML dir: {html_dir}")
    print(f"Output dir: {output_dir}")
    print()
    
    # Lancer consolidation en dry-run
    stats = run_consolidation(
        input_csv=input_csv,
        html_dir=html_dir,
        config=config_dry,
    )
    
    print()
    print("=" * 60)
    print("RÉSULTATS DRY-RUN")
    print("=" * 60)
    print()
    
    # Afficher les fichiers JSON générés
    json_files = list(output_dir.glob("*.json"))
    print(f"Fichiers JSON générés: {len(json_files)}")
    
    for json_file in json_files[:2]:
        print(f"\n--- {json_file.name} ---")
        import json
        with open(json_file) as f:
            data = json.load(f)
            # Afficher les champs clés
            for key in ['reference', 'source_url', 'date_limite', 'estimation', 'localisation']:
                if key in data:
                    val = data[key]
                    if isinstance(val, dict):
                        val_str = val.get('value', 'N/A')
                        status = val.get('status', 'N/A')
                        print(f"  {key}: {val_str} ({status})")
                    else:
                        print(f"  {key}: {val}")
    
    print()
    print("=" * 60)
    print("TEST CONSOLIDATION LLM - AVEC LLM")
    print("=" * 60)
    print()
    
    # Maintenant avec le vrai LLM
    config_llm = ConsolidationConfig(
        enabled=True,
        llm_backend=build_backend(),
        output_dir=output_dir,
        dry_run=False,  # Vrai LLM
        limit=1,  # Juste 1 pour tester
    )
    
    print("Lancement consolidation avec LLM (peut prendre 30-60s)...")
    print()
    
    stats = run_consolidation(
        input_csv=input_csv,
        html_dir=html_dir,
        config=config_llm,
    )
    
    print()
    print("=" * 60)
    print("RÉSULTATS AVEC LLM")
    print("=" * 60)
    print()
    print(f"Traité: {stats.get('processed', 0)}")
    print(f"Succès: {stats.get('success', 0)}")
    print(f"Erreurs: {stats.get('errors', 0)}")
    print(f"Dry-run: {stats.get('dry_run', False)}")
    
    # Vérifier le résultat
    consolidated_files = list(output_dir.glob("*-consolidated.json"))
    if consolidated_files:
        print(f"\nFichiers consolidés: {len(consolidated_files)}")
        for cf in consolidated_files[:1]:
            print(f"\n--- {cf.name} ---")
            import json
            with open(cf) as f:
                data = json.load(f)
                for key in ['reference', 'source_url', 'date_limite', 'estimation', 'localisation']:
                    if key in data:
                        val = data[key]
                        if isinstance(val, dict):
                            val_str = val.get('value', 'N/A')
                            status = val.get('status', 'N/A')
                            print(f"  {key}: {val_str} ({status})")
                        else:
                            print(f"  {key}: {val}")

if __name__ == "__main__":
    test_consolidation()
