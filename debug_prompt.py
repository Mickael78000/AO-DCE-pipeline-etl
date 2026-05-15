#!/usr/bin/env python3
"""Debug: voir ce qui est envoyé au LLM."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ao_etl.llm.prompt_builder import build_user_prompt, get_system_prompt, build_resolved_hints, extract_html_signals

# Cas de test avec URL
row = {
    "Référence": "TEST-001",
    "Intitulé synthétique": "Test marché",
    "Acheteur_auto": "Test Acheteur",
    "Localisation_auto": "-",  # Manquant
    "Date_limite_auto": "-",   # Manquant
    "Estimation_auto": "-",    # Manquant
    "URL source HTTPS": "https://www.francemarches.com/appel-offre/test-marche",
    "extraction_notes": "Notes d'extraction",
    "source_type": "FRANCE_MARCHES",
}

html_content = """
<html>
<body>
<h1>Test marché</h1>
<p>Localisation: Paris</p>
<p>Date limite: 31/12/2026</p>
<p>Budget: 50000 EUR</p>
</body>
</html>
"""

print("=" * 60)
print("HINTS ENVOYÉS AU LLM")
print("=" * 60)
print()

html_signals = extract_html_signals(html_content)
hints = build_resolved_hints(row, html_signals, "test.html")

import json
print(json.dumps(hints, indent=2, ensure_ascii=False))

print()
print("=" * 60)
print("EXTRAIT DU PROMPT SYSTÈME (priorité P4)")
print("=" * 60)
print()

system = get_system_prompt()
# Chercher la section P4
if "P4 — source_url" in system:
    start = system.find("P4 — source_url")
    end = system.find("P5 —")
    print(system[start:end])

print()
print("=" * 60)
print("⚠️  IMPORTANT")
print("=" * 60)
print()
print("Le LLM reçoit bien l'URL dans 'source_url', mais:")
print("❌ Il NE PEUT PAS ouvrir la page web (pas d'accès internet)")
print("✅ Il peut utiliser l'URL comme contexte métier")
print("✅ Il peut extraire des données si elles sont dans le HTML fourni")
print()
print("Pour vraiment utiliser l'URL, il faudrait:")
print("1. Scraper la page et inclure son contenu dans le prompt")
print("2. Utiliser un LLM avec outils web (GPT-4 + browsing)")
