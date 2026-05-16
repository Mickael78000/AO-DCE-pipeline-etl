#!/usr/bin/env python3
"""Test du pipeline complet avec scraper et LLM."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
import json
import logging

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

from ao_etl.pipeline.run import run_pipeline
from ao_etl.pipeline.consolidate import ConsolidationConfig
from ao_etl.llm.backend import build_backend

def test_pipeline_complet():
    """Test le pipeline complet avec scraper + LLM."""
    
    print("=" * 70)
    print("TEST PIPELINE COMPLET - SCRAPER + LLM")
    print("=" * 70)
    print()
    
    # Configuration
    html_dir = Path("data/raw/html")
    input_csv = Path("data/input/AO-completed.csv")
    output_csv = Path("data/output/test-pipeline-complet.csv")
    
    print(f"HTML dir: {html_dir}")
    print(f"Input CSV: {input_csv}")
    print(f"Output CSV: {output_csv}")
    print()
    
    # Vérifier les prérequis
    print("Vérification des prérequis...")
    
    if not html_dir.exists():
        print(f"❌ HTML dir non trouvé: {html_dir}")
        return
    
    html_files = list(html_dir.glob("*.html"))
    print(f"✓ {len(html_files)} fichiers HTML trouvés")
    
    # Configuration consolidation avec LLM
    print()
    print("Configuration LLM...")
    try:
        backend = build_backend()
        print(f"✓ Backend LLM: {type(backend).__name__}")
        print(f"  Model: {backend.model}")
    except Exception as e:
        print(f"❌ Erreur backend LLM: {e}")
        return
    
    consolidation_config = ConsolidationConfig(
        enabled=True,
        llm_backend=backend,
        output_dir=Path("data/output/test-consolidation"),
        dry_run=False,  # Vrai LLM
        limit=3,  # Limiter à 3 marchés pour le test
    )
    
    print(f"✓ Consolidation: enabled=True, limit=3")
    print()
    
    # Lancer le pipeline
    print("=" * 70)
    print("LANCEMENT DU PIPELINE")
    print("=" * 70)
    print()
    
    try:
        result = run_pipeline(
            html_dir=html_dir,
            input_csv=input_csv,
            output_csv=output_csv,
            consolidation_config=consolidation_config,
            verbose=True,
        )
        
        print()
        print("=" * 70)
        print("RÉSULTATS DU PIPELINE")
        print("=" * 70)
        print()
        
        print(f"✓ Pipeline terminé avec succès: {result.success}")
        print(f"  Total lignes: {result.total_rows}")
        print(f"  Nouvelles lignes: {result.new_rows}")
        print(f"  Validation: {result.validation_passed}")
        
        if result.consolidation_stats:
            print()
            print("Statistiques consolidation:")
            for k, v in result.consolidation_stats.items():
                print(f"  {k}: {v}")
        
        # Vérifier le CSV de sortie
        if output_csv.exists():
            print()
            print(f"✓ CSV généré: {output_csv}")
            
            # Lire et analyser
            with open(output_csv) as f:
                import csv
                reader = csv.DictReader(f)
                rows = list(reader)
                
                print(f"  Lignes: {len(rows)}")
                
                # Compter les champs remplis
                champs = ["Localisation_auto", "Date_limite_auto", "Estimation_auto", "URL source HTTPS"]
                print()
                print("Taux de remplissage:")
                for champ in champs:
                    rempli = sum(1 for r in rows if r.get(champ) and r.get(champ) not in ("-", "", "None"))
                    pct = rempli / len(rows) * 100 if rows else 0
                    print(f"  {champ}: {rempli}/{len(rows)} ({pct:.1f}%)")
                
                # Exemples
                print()
                print("Exemples de lignes:")
                for i, row in enumerate(rows[:2], 1):
                    print(f"\n{i}. {row.get('Référence', 'N/A')}")
                    print(f"   Titre: {row.get('Intitulé synthétique', 'N/A')[:50]}...")
                    print(f"   Acheteur: {row.get('Acheteur_auto', 'N/A')[:40]}...")
                    print(f"   Estimation: {row.get('Estimation_auto', 'N/A')}")
                    print(f"   Date: {row.get('Date_limite_auto', 'N/A')}")
                    print(f"   URL: {row.get('URL source HTTPS', 'N/A')[:50]}...")
        
        # Vérifier les fichiers de consolidation
        consolidation_dir = Path("data/output/test-consolidation")
        if consolidation_dir.exists():
            json_files = list(consolidation_dir.glob("*.json"))
            print()
            print(f"✓ Fichiers de consolidation: {len(json_files)}")
            
            for jf in json_files[:2]:
                print(f"\n  {jf.name}:")
                try:
                    with open(jf) as f:
                        data = json.load(f)
                        # Afficher champs clés
                        for key in ['reference', 'estimation', 'date_limite', 'localisation']:
                            if key in data:
                                val = data[key]
                                if isinstance(val, dict):
                                    print(f"    {key}: {val.get('value', 'N/A')} ({val.get('status', 'N/A')})")
                                else:
                                    print(f"    {key}: {val}")
                except Exception as e:
                    print(f"    Erreur lecture: {e}")
        
    except Exception as e:
        print(f"❌ Erreur pipeline: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline_complet()
