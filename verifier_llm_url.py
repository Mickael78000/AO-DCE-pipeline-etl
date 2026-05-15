#!/usr/bin/env python3
"""Vérifier si le LLM récupère les données depuis les URLs."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ao_etl.llm.backend import build_backend
from ao_etl.llm.prompt_builder import build_user_prompt, get_system_prompt
import json

# Test avec une URL réelle
TEST_URL = "https://www.francemarches.com/appel-offre/pp1e2-3001-6300-2026031-s-renouvellement-maintenance-des-solutions-dedrm"

def test_llm_avec_url():
    """Test si le LLM peut utiliser une URL pour compléter des données."""
    
    print("=" * 60)
    print("TEST: Le LLM récupère-t-il les données depuis l'URL ?")
    print("=" * 60)
    print()
    
    # Créer un cas de test avec données manquantes
    row = {
        "Référence": "PPP1E2-3001/6300/2026031-S",
        "Intitulé synthétique": "Renouvellement maintenance des solutions",
        "Acheteur_auto": "Conseil d'État",
        "Acheteur_manual": "",
        "Localisation_auto": "-",
        "Date_limite_auto": "-",
        "Estimation_auto": "-",
        "URL source HTTPS": TEST_URL,
        "extraction_notes": "Données partielles extraites",
        "source_type": "FRANCE_MARCHES",
        "match_source": "pp1e2-3001-6300-2026031-s-renouvellement-maintenance-des-solutions-dedrm.html",
    }
    
    print(f"Test avec URL: {TEST_URL}")
    print()
    print("Données fournies au LLM:")
    print(f"  - Référence: {row['Référence']}")
    print(f"  - Titre: {row['Intitulé synthétique']}")
    print(f"  - Acheteur: {row['Acheteur_auto']}")
    print(f"  - Localisation: {row['Localisation_auto']} (manquante)")
    print(f"  - Date: {row['Date_limite_auto']} (manquante)")
    print(f"  - Estimation: {row['Estimation_auto']} (manquante)")
    print(f"  - URL: {row['URL source HTTPS']}")
    print()
    
    # Construire les prompts
    system_prompt = get_system_prompt()
    user_prompt = build_user_prompt(row, html_content="", source_file=row["match_source"])
    
    print("=" * 60)
    print("Extrait du prompt système (priorité sources):")
    print("=" * 60)
    
    # Chercher la section sur les priorités
    if "PRIORITÉ DES SOURCES" in system_prompt:
        start = system_prompt.find("PRIORITÉ DES SOURCES")
        end = system_prompt.find("TAXONOMIES FERMÉES")
        if end == -1:
            end = start + 500
        print(system_prompt[start:end])
    
    print()
    print("=" * 60)
    print("Envoi au LLM (appel Ollama)...")
    print("=" * 60)
    print()
    
    try:
        # Construire le backend
        backend = build_backend()
        print(f"Backend: {type(backend).__name__}")
        print(f"Model: {backend.model}")
        print()
        
        # Appel LLM
        print("Appel en cours... (timeout 60s)")
        result = backend.call_json(system_prompt, user_prompt)
        
        print()
        print("=" * 60)
        print("RÉSULTAT LLM")
        print("=" * 60)
        print()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print()
        
        # Vérifier si l'URL a été utilisée
        print("=" * 60)
        print("ANALYSE")
        print("=" * 60)
        print()
        
        # Chercher les champs complétés
        champs_verifier = ['localisation', 'date_limite', 'estimation', 'duree']
        for champ in champs_verifier:
            if champ in result:
                val = result[champ]
                if isinstance(val, dict):
                    valeur = val.get('value', 'N/A')
                    status = val.get('status', 'N/A')
                    source = val.get('source', 'N/A')
                    print(f"{champ}: {valeur}")
                    print(f"  → status: {status}, source: {source}")
                    if status == 'found' and valeur not in ['', '-', 'N/A']:
                        print(f"  ✅ DONNÉE TROUVÉE!")
                else:
                    print(f"{champ}: {val}")
        
        # Vérifier si l'URL source est dans le résultat
        if 'source_trace' in result and isinstance(result['source_trace'], dict):
            source_url = result['source_trace'].get('source_url', '')
            if source_url:
                print()
                print(f"URL dans source_trace: {source_url}")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Vérifier Ollama
    import subprocess
    try:
        result = subprocess.run(['curl', '-s', 'http://localhost:11434/api/tags'], 
                              capture_output=True, text=True, timeout=5)
        if 'llama3.1' in result.stdout:
            print("✅ Ollama disponible avec llama3.1")
            print()
            test_llm_avec_url()
        else:
            print("❌ llama3.1 non disponible dans Ollama")
    except Exception as e:
        print(f"❌ Ollama non accessible: {e}")
