#!/usr/bin/env python3
"""Script pour extraire tous les descriptifs des fichiers HTML."""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour importer ao_etl
sys.path.insert(0, str(Path(__file__).parent))

from ao_etl.parsing.extract_descriptif import extract_descriptif

def main():
    # Chemin depuis la racine du projet (remonter 1 niveau depuis scripts/)
    base_dir = Path(__file__).parent.parent
    html_dir = base_dir / 'data' / 'raw' / 'html'
    html_files = list(html_dir.glob('*.html'))
    
    print(f"Extraction de {len(html_files)} fichiers HTML...")
    
    for i, html_file in enumerate(html_files, 1):
        txt_file = html_file.with_suffix('').with_name(html_file.stem + '_descriptif.txt')
        
        try:
            # Extraire le descriptif
            text = extract_descriptif(str(html_file))
            
            # Vérifier si l'extraction a réussi
            if text is None:
                print(f"[{i:3d}/{len(html_files)}] ✗ {html_file.name}: pas de descriptif trouvé")
                continue
            
            # Sauvegarder dans le fichier .txt
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(text)
            
            print(f"[{i:3d}/{len(html_files)}] ✓ {html_file.name} -> {txt_file.name}")
            
        except Exception as e:
            print(f"[{i:3d}/{len(html_files)}] ✗ {html_file.name}: {e}")
    
    print(f"\nExtraction terminée!")

if __name__ == '__main__':
    main()
