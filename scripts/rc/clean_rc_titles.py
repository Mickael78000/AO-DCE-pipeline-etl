#!/usr/bin/env python3
"""
Script de nettoyage automatique des titres RC pour extraction_rc.json

Usage:
    python clean_rc_titles.py --json extraction_rc.json [--dry-run]
    python clean_rc_titles.py --extract-only --pdf "public/rc/RC candidature -2026-04.pdf"
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional


# Mapping des références aux noms de fichiers PDF correspondants
PDF_MAPPING = {
    "2026-04": "RC candidature -2026-04.pdf",
    "2600006": "2600006 - SPL -  IT Réseau Cloud Sécurité - RC .pdf",
    "260424": "260424 - RC PRESTATIONS INFORMATIQUES .pdf",
    "26910A": "26910A RC.pdf",
    "26A0133001": "26A0133001_ RC.pdf",
    "2026-CHATBOT": "RC chatbot.pdf",
    "2026-0206-WEB": "RC_20260206_WEB.pdf",
}


# Titres corrigés manuellement (backup si extraction auto échoue)
MANUAL_TITLES = {
    "2026-04": "Assistance et infogérance du Système d'Information de la HAS",
    "2600006": "Prestation IT : Réseau / Cloud / Sécurité",
    "260424": "Prestations de services informatiques pour le développement et la maintenance des outils informatiques du GCS UniHA",
    "26910A": "Accord-cadre de services : Achats, maintenances et évolution du système de sauvegarde",
    "26A0133001": "Accompagnement à l'extension de l'ITSM de la DSI",
    "2026-CHATBOT": "Assistance à la maîtrise d'œuvre et développement d'un chatbot pour la documentation interne",
    "2026-0206-WEB": "Maintenance, hébergement et développements des sites et applicatifs web du Département de la Vendée",
}


class TitleCleaner:
    """Nettoyeur de titres OCR/extraction."""
    
    def __init__(self):
        self.patterns = [
            # Pattern 1: "Objet du marché : [titre]" ou "Objet : [titre]"
            (r'[Oo]bjet(?:\s+du\s+march[ée])?\s*:\s*([^\n.]{20,150})(?:\n|\.|\s{3,})', 'objet_marche'),
            # Pattern 2: "Prestations..." après "Marché N°X" sur page de garde
            (r'[Mm]arch[ée]\s+N°?\s*\S+\s+([A-Z][^\n]{20,150}?)(?:\s{2,}|\n|\.|REGLEMENT|Mode\s+de)', 'apres_marche_num'),
            # Pattern 3: Ligne tout en majuscules ou avec mots clés techniques
            (r'\b(PRESTATIONS?\s+(?:DE\s+)?(?:SUPPORT|MAINTENANCE|SERVICES?|INFORMATIQUES?|R[ÉE]SEAU|CLOUD|ASSISTANCE)[^\n.]{10,100})', 'mot_cle_technique'),
            # Pattern 4: Après "du marché :"
            (r'du\s+march[ée]\s*:\s*([^\n.]{20,150})(?:\n|\.\.\.)', 'titre_direct'),
            # Pattern 5: Après "Consultation n° X - [titre]"
            (r'[Cc]onsultation\s+n°?\s*\S+\s*[-–—]\s*([^\n.]{20,150})(?:\n|\.)', 'consultation_titre'),
        ]
    
    def clean_ocr_noise(self, text: str) -> str:
        """Nettoie le bruit OCR du texte."""
        # Supprimer les lignes de points (................)
        text = re.sub(r'\.{10,}', ' ', text)
        # Supprimer les numéros de page isolés
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        # Supprimer les puces graphiques
        text = re.sub(r'[■◆▲●○□▪]', ' ', text)
        # Supprimer les table des matières
        text = re.sub(r'[^\n]{5,100}\.{5,}\s*\d+', '', text, flags=re.MULTILINE)
        # Supprimer les numéros de section type "3.2 Allotissement"
        text = re.sub(r'^\s*\d+(\.\d+)*\s+[A-Z][a-z]+[^\n]*$', '', text, flags=re.MULTILINE)
        # Normaliser les espaces
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def extract_title(self, text: str, reference: str) -> Optional[str]:
        """Extrait le titre du texte avec patterns améliorés."""
        # D'abord nettoyer le texte
        clean_text = self.clean_ocr_noise(text)
        
        for pattern, pattern_name in self.patterns:
            match = re.search(pattern, clean_text, re.IGNORECASE | re.MULTILINE)
            if match:
                title = match.group(1).strip()
                # Post-traitement du titre
                title = self._post_process_title(title)
                if self._is_valid_title(title):
                    return title
        
        # Fallback: chercher la première phrase longue avec majuscules après la référence
        return self._extract_fallback(clean_text, reference)
    
    def _post_process_title(self, title: str) -> str:
        """Post-traitement du titre extrait."""
        # Supprimer les points de suspension résiduels
        title = re.sub(r'\.{2,}', '', title)
        # Supprimer les espaces multiples
        title = re.sub(r'\s+', ' ', title)
        # Supprimer les artefacts de fin de ligne
        title = re.sub(r'\s*ARTICLE\s+\d+.*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*Proc[ée]dure.*$', '', title, flags=re.IGNORECASE)
        # Capitaliser première lettre
        title = title[0].upper() + title[1:] if title else title
        # Limiter la longueur
        if len(title) > 200:
            # Couper au dernier mot complet avant 200 caractères
            title = title[:200].rsplit(' ', 1)[0]
        return title.strip()
    
    def _is_valid_title(self, title: str) -> bool:
        """Vérifie si le titre extrait est valide."""
        if not title or len(title) < 20:  # Réduit à 20 car certains titres courts sont valides
            return False
        # Rejeter les titres qui sont juste "DU MARCHE" + points
        if re.match(r'^[Dd][Uu]\s+[Mm]arch[ée]\s*\.\.*\s*\d*$', title):
            return False
        # Rejeter les titres avec trop de caractères spéciaux (>40%, tolérance pour majuscules)
        special_ratio = len(re.findall(r'[^\w\s\-\'\"]', title)) / len(title) if title else 0
        if special_ratio > 0.4:
            return False
        # Rejeter les titres qui sont juste des numéros de section
        if re.match(r'^\d+(\.\d+)*\s+[A-Z][a-z]', title):
            return False
        return True
    
    def _extract_fallback(self, text: str, reference: str) -> Optional[str]:
        """Extraction de secours si les patterns principaux échouent."""
        # Chercher la référence dans le texte et prendre les mots suivants
        ref_pattern = re.escape(reference)
        match = re.search(rf'{ref_pattern}.*?([A-Z][^\n]{{30,150}})(?:\n|\.|\s{{3,}})', text, re.IGNORECASE)
        if match:
            return self._post_process_title(match.group(1))
        return None


class RCTitleUpdater:
    """Met à jour les titres dans extraction_rc.json."""
    
    def __init__(self, json_path: Path, rc_dir: Path):
        self.json_path = json_path
        self.rc_dir = rc_dir
        self.cleaner = TitleCleaner()
        self.results = []
    
    def extract_text_from_pdf(self, pdf_name: str) -> Optional[str]:
        """Extrait le texte d'un PDF avec pdftotext."""
        pdf_path = self.rc_dir / pdf_name
        if not pdf_path.exists():
            return None
        
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), "-"],
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.stdout
        except Exception as e:
            print(f"Erreur extraction {pdf_name}: {e}")
            return None
    
    def process_market(self, market: Dict, dry_run: bool = False) -> Tuple[bool, str, str]:
        """Traite un marché et retourne (modifié, ancien_titre, nouveau_titre)."""
        reference = market.get("reference", "")
        
        if reference not in PDF_MAPPING:
            return False, market.get("titre", ""), ""
        
        old_title = market.get("titre", "")
        pdf_name = PDF_MAPPING[reference]
        
        # Vérifier si le titre actuel est mauvais (à corriger)
        needs_fix = self._needs_correction(old_title)
        
        if not needs_fix:
            return False, old_title, old_title
        
        # Extraire et nettoyer
        text = self.extract_text_from_pdf(pdf_name)
        if text:
            new_title = self.cleaner.extract_title(text, reference)
        else:
            new_title = None
        
        # Fallback sur titre manuel si extraction auto échoue
        if not new_title:
            new_title = MANUAL_TITLES.get(reference, old_title)
            source = "manual"
        else:
            source = "auto"
        
        if not dry_run and new_title != old_title:
            market["titre"] = new_title
            # Mettre à jour le contrôle
            if "controle" in market:
                market["controle"]["qualite_extraction"] = "bonne"
                market["controle"]["commentaire"] = f"Titre corrigé automatiquement ({source})"
        
        return new_title != old_title, old_title, new_title
    
    def _needs_correction(self, title: str) -> bool:
        """Détermine si un titre nécessite une correction."""
        if not title:
            return True
        # Signes de mauvaise extraction
        bad_patterns = [
            r'\.{5,}',  # Points de suspension (>5)
            r'^DU\s+MARCH[ÉE]',  # Commence par "DU MARCHE"
            r'ARTICLE\s+\d+',  # Contient "ARTICLE X"
            r'3\.\d+\s+[A-Z]',  # Numéros de section
            r'^[A-Z]\s+\d{1,2}\s+[A-Z]',  # Format "A 12 Juin"
        ]
        for pattern in bad_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                return True
        # Titre trop court
        if len(title) < 40:
            return True
        return False
    
    def run(self, dry_run: bool = False) -> Dict:
        """Lance le nettoyage sur tous les marchés."""
        with open(self.json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        marches = data.get("marches", [])
        modified_count = 0
        results = []
        
        print(f"\n{'='*70}")
        print(f"NETTOYAGE AUTOMATIQUE DES TITRES RC")
        print(f"{'='*70}")
        print(f"Mode: {'DRY-RUN (simulation)' if dry_run else 'APPLY'}")
        print(f"Fichier: {self.json_path}")
        print(f"{'='*70}\n")
        
        for market in marches:
            ref = market.get("reference", "N/A")
            if ref not in PDF_MAPPING:
                continue
            
            modified, old, new = self.process_market(market, dry_run)
            
            if modified or self._needs_correction(old):
                status = "✓ MODIFIÉ" if modified else "⚠ PAS MODIFIÉ"
                print(f"\n{status} [{ref}]")
                print(f"  AVANT: {old[:80]}...")
                print(f"  APRÈS: {new[:80]}...")
                modified_count += 1 if modified else 0
                
                results.append({
                    "reference": ref,
                    "modified": modified,
                    "old": old,
                    "new": new
                })
        
        # Sauvegarder si pas dry-run
        if not dry_run and modified_count > 0:
            backup_path = self.json_path.with_suffix('.json.backup')
            # Créer backup
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Sauvegarder modifié
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"\n{'='*70}")
            print(f"✓ Sauvegarde créée: {backup_path}")
            print(f"✓ Fichier mis à jour: {self.json_path}")
        
        print(f"\n{'='*70}")
        print(f"RÉSULTAT: {modified_count} titres modifiés sur {len(PDF_MAPPING)} cibles")
        print(f"{'='*70}\n")
        
        return {
            "modified_count": modified_count,
            "total_target": len(PDF_MAPPING),
            "results": results,
            "dry_run": dry_run
        }


def cmd_clean(args):
    """Commande principale de nettoyage."""
    json_path = Path(args.json)
    rc_dir = Path(args.rc_dir) if args.rc_dir else Path("public/rc")
    
    if not json_path.exists():
        print(f"✗ Fichier JSON non trouvé: {json_path}")
        return 1
    
    updater = RCTitleUpdater(json_path, rc_dir)
    result = updater.run(dry_run=args.dry_run)
    
    return 0


def cmd_extract_single(args):
    """Extrait et affiche le titre d'un seul PDF."""
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"✗ PDF non trouvé: {pdf_path}")
        return 1
    
    # Extraire texte
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=60
        )
        text = result.stdout
    except Exception as e:
        print(f"Erreur extraction: {e}")
        return 1
    
    # Nettoyer et extraire
    cleaner = TitleCleaner()
    
    print(f"\n{'='*70}")
    print(f"EXTRACTION TITRE: {pdf_path.name}")
    print(f"{'='*70}\n")
    
    print("Texte brut (premiers 500 caractères):")
    print(text[:500].replace('\n', ' | '))
    print(f"\n{'='*70}\n")
    
    print("Texte nettoyé:")
    clean = cleaner.clean_ocr_noise(text[:1000])
    print(clean[:300])
    print(f"\n{'='*70}\n")
    
    title = cleaner.extract_title(text, "UNKNOWN")
    if title:
        print(f"✓ Titre extrait: {title}")
    else:
        print("✗ Aucun titre trouvé")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Nettoyage automatique des titres RC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Nettoyer tous les titres problématiques (simulation)
  python clean_rc_titles.py clean --json extraction_rc.json --dry-run
  
  # Appliquer les corrections
  python clean_rc_titles.py clean --json extraction_rc.json
  
  # Tester sur un seul PDF
  python clean_rc_titles.py extract --pdf "public/rc/RC candidature -2026-04.pdf"
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commandes")
    
    # Commande clean
    clean_parser = subparsers.add_parser("clean", help="Nettoyer les titres dans extraction_rc.json")
    clean_parser.add_argument("--json", "-j", required=True, help="Fichier extraction_rc.json")
    clean_parser.add_argument("--rc-dir", "-r", help="Répertoire des PDFs (défaut: public/rc)")
    clean_parser.add_argument("--dry-run", "-d", action="store_true", help="Simulation sans modification")
    
    # Commande extract
    extract_parser = subparsers.add_parser("extract", help="Extraire titre d'un seul PDF")
    extract_parser.add_argument("--pdf", "-p", required=True, help="Chemin du PDF")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == "clean":
        return cmd_clean(args)
    elif args.command == "extract":
        return cmd_extract_single(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
