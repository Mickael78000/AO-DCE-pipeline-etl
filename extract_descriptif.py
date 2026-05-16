#!/usr/bin/env python3
"""
Script d'extraction du descriptif d'un appel d'offres à partir d'un fichier HTML.
Cible le bloc div.limit-descript-height.descript-line
"""

from bs4 import BeautifulSoup
import re
import sys


def extract_descriptif(html_path: str) -> str | None:
    """
    Extrait le texte du bloc descriptif à partir d'un fichier HTML.
    
    Args:
        html_path: Chemin vers le fichier HTML
        
    Returns:
        Le texte extrait nettoyé, ou None si le bloc n'est pas trouvé
    """
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Correction : le HTML a deux attributs class séparés, on les fusionne
    html = html.replace(
        'class="limit-descript-height descript-line" class="overflow-auto mt-4 p-4"',
        'class="limit-descript-height descript-line overflow-auto mt-4 p-4"'
    )

    soup = BeautifulSoup(html, "html.parser")
    
    # Essayer d'abord la structure marchesonline.com
    bloc = soup.select_one("div.limit-descript-height.descript-line")
    
    # Sinon essayer la structure francemarches.com
    if not bloc:
        bloc = soup.select_one("div.contentContenu")
    
    if not bloc:
        return None

    # Extraction du texte avec retours à la ligne
    texte = bloc.get_text("\n", strip=True)
    
    # Nettoyage : suppression des retours à la ligne excessifs (3+ → 2)
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    
    # Normalisation des espaces multiples
    texte = re.sub(r"[ \t]+", " ", texte)
    
    return texte


def main():
    # Chemin par défaut ou argument en ligne de commande
    if len(sys.argv) > 1:
        html_path = sys.argv[1]
    else:
        html_path = "data/raw/html/test.html"

    # Définir le chemin de sortie
    output_path = html_path.replace(".html", "_descriptif.txt")

    print(f"Extraction depuis : {html_path}\n")
    
    texte = extract_descriptif(html_path)
    
    if texte:
        # Sauvegarder dans un fichier
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(texte)
        
        print("=" * 80)
        print(texte)
        print("=" * 80)
        print(f"\nExtraction réussie : {len(texte)} caractères")
        print(f"Résultat sauvegardé dans : {output_path}")
    else:
        print("ERREUR : Bloc 'div.limit-descript-height.descript-line' introuvable")
        sys.exit(1)


if __name__ == "__main__":
    main()
