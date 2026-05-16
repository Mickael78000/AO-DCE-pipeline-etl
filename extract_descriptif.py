#!/usr/bin/env python3
"""
Script d'extraction du descriptif d'un appel d'offres à partir d'un fichier HTML.
Cible le bloc div.limit-descript-height.descript-line avec multiples fallbacks.
"""

from bs4 import BeautifulSoup, Comment
import re
import sys


def _fix_split_class_attributes(html: str) -> str:
    """
    Corrige les attributs class splités sur plusieurs lignes.
    Gère les variations d'espaces et de quotes.
    """
    # Pattern pour attraper class="..." suivi de class="..." sur ligne suivante
    # avec espaces/tabs/newlines entre les deux
    pattern = r'class=["\']([^"\']+)["\']\s+class=["\']([^"\']+)["\']'
    
    def replacer(match):
        classes1 = match.group(1)
        classes2 = match.group(2)
        merged = f'{classes1} {classes2}'.strip()
        return f'class="{merged}"'
    
    return re.sub(pattern, replacer, html, flags=re.MULTILINE)


def _clean_extracted_text(text: str, aggressive: bool = False) -> str:
    """
    Nettoie le texte extrait.
    
    Args:
        text: Texte à nettoyer
        aggressive: Si True, applique un nettoyage plus agressif (pour body entier)
    """
    if not text:
        return ""
    
    # Suppression des lignes vides multiples
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Normalisation des espaces
    text = re.sub(r"[ \t]+", " ", text)
    
    if aggressive:
        # Supprimer les lignes trop courtes (probablement du bruit)
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Garder les lignes qui ont du sens ou contiennent des mots-clés
            if len(stripped) > 10 or any(kw in stripped.lower() for kw in [
                'acheteur', 'marché', 'procédure', 'lot', 'cpv', 'valeur',
                'offre', 'soumission', 'avis', 'appel', 'contrat', 'minist',
                'région', 'département', 'prestation', 'service'
            ]):
                cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines)
        
        # Recleanup après filtrage
        text = re.sub(r"\n{3,}", "\n\n", text)
    
    return text.strip()


def extract_descriptif(html_path: str) -> str | None:
    """
    Extrait le texte du bloc descriptif à partir d'un fichier HTML.
    Utilise une cascade de stratégies pour maximiser le taux de succès.
    
    Args:
        html_path: Chemin vers le fichier HTML
        
    Returns:
        Le texte extrait nettoyé, ou None si aucun contenu pertinent trouvé
    """
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        print(f"Erreur lecture {html_path}: {e}", file=sys.stderr)
        return None

    # Étape 1: Correction des attributs class splités
    html = _fix_split_class_attributes(html)

    soup = BeautifulSoup(html, "html.parser")
    
    # Stratégie 1: Sélecteur principal marchesonline.com (plusieurs variantes)
    selectors_primary = [
        "div.limit-descript-height.descript-line",
        "div[class*='limit-descript-height']",
        "div[class*='descript-line']",
    ]
    
    bloc = None
    for selector in selectors_primary:
        bloc = soup.select_one(selector)
        if bloc:
            break
    
    # Stratégie 2: francemarches.com et autres plateformes similaires
    if not bloc:
        selectors_secondary = [
            "div.contentContenu",
            "div#contentContenu",
            "div.contenu",
            "div.annonce-detail",
            "div.avis-detail",
            "div.marche-content",
            "article",
            "main",
        ]
        for selector in selectors_secondary:
            bloc = soup.select_one(selector)
            if bloc:
                break
    
    # Stratégie 3: Fallback - extraction du body avec nettoyage agressif
    if not bloc:
        body = soup.find("body")
        if body:
            # Supprimer scripts, styles, nav, footer, header
            for tag in body.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            # Supprimer les commentaires
            for comment in body.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            text = body.get_text("\n", strip=True)
            text = _clean_extracted_text(text, aggressive=True)
            
            # Ne retourner que si on a trouvé du contenu substantiel
            if len(text) > 500:
                return text
    
    # Stratégie 4: Extraction depuis les métadonnées (dernier recours)
    if not bloc:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            content = meta_desc.get("content")
            # Essayer aussi le titre
            title = soup.find("title")
            title_text = title.get_text(strip=True) if title else ""
            
            combined = f"{title_text}\n\n{content}" if title_text else content
            if len(combined) > 100:
                return _clean_extracted_text(combined)
        return None

    # Extraction du texte avec retours à la ligne
    texte = bloc.get_text("\n", strip=True)
    texte = _clean_extracted_text(texte)
    
    return texte if texte else None


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
