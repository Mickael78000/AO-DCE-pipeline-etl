#!/usr/bin/env python3
import re

# Lire un fichier France Marchés
with open('html_ao/37ao26181581260520263294-2026-prestations-assistance-expertise.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Chercher la position de title_article
idx = content.find('title_article')
if idx != -1:
    print('Extrait autour de title_article:')
    print(repr(content[idx:idx+150]))
    print()

# Test du pattern pour title_article
# Le format dans le fichier est avec des échappements Unicode
patterns = [
    (r'title_article\\u0022:\\u0022([^\\u0022]+)', 'Pattern 1: unicode échappé'),
    (r'title_article\u0022:\u0022([^"]+)', 'Pattern 2: unicode brut'),
    (r'title_article"\s*:\s*"([^"]+)', 'Pattern 3: guillemets simples'),
]

for pattern, desc in patterns:
    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        print(f'{desc}: OK')
        print(f'  Titre: {match.group(1)[:80]}...')
    else:
        print(f'{desc}: NO MATCH')
    print()
