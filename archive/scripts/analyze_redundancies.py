#!/usr/bin/env python3
"""
Analyse des marchés rédondants dans les fichiers HTML
"""

import os
import re
import json
from pathlib import Path
from html.parser import HTMLParser
from difflib import SequenceMatcher
from collections import defaultdict

# Liste des fichiers à analyser
HTML_DIR = Path("/home/michka/Documents/0-AO-DCE/html_ao")

class MarketDataExtractor:
    """Extracteur de données de marché à partir de fichiers HTML"""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.content = Path(filepath).read_text(encoding='utf-8', errors='ignore')
        self.data = {
            'filename': Path(filepath).name,
            'filepath': str(filepath),
            'title': '',
            'reference': '',
            'object': '',
            'buyer': '',
            'cpv_codes': [],
            'procedure_id': '',
            'internal_id': '',
            'date_cloture': ''
        }
    
    def extract_place_format(self):
        """Extraction format PLACE (marches-publics.gouv.fr)"""
        # Titre/Intitulé
        title_match = re.search(r'<label[^>]*>Intitulé\s*:</label>.*?<div[^>]*>.*?<span[^>]*>(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if title_match:
            self.data['title'] = self.clean_text(title_match.group(1))
        
        # Référence
        ref_match = re.search(r'<label[^>]*>Référence\s*:</label>.*?<span[^>]*>(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if ref_match:
            self.data['reference'] = self.clean_text(ref_match.group(1))
        
        # Objet
        obj_match = re.search(r'<label[^>]*>Objet\s*:</label>.*?<div[^>]*>.*?<span[^>]*>(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if obj_match:
            self.data['object'] = self.clean_text(obj_match.group(1))
        
        # Organisme/Acheteur
        org_match = re.search(r'<label[^>]*>Organisme\s*:</label>.*?<span[^>]*>(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if org_match:
            self.data['buyer'] = self.clean_text(org_match.group(1))
        
        # Codes CPV
        cpv_matches = re.findall(r'data-code-cpv="(\d+)"', self.content)
        self.data['cpv_codes'] = list(set(cpv_matches))
        
        # Date de clôture
        date_match = re.search(r'Date.*?(?:limite|cloture).*?</label>.*?<span[^>]*>.*?<span[^>]*>(\d{2}/\d{2}/\d{4})', self.content, re.DOTALL | re.IGNORECASE)
        if date_match:
            self.data['date_cloture'] = date_match.group(1)
        
        return bool(self.data['title'])
    
    def extract_boamp_format(self):
        """Extraction format BOAMP"""
        # Titre dans titrePrincipal
        title_match = re.search(r'<span[^>]*titrePrincipal[^>]*>(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if title_match:
            self.data['title'] = self.clean_text(title_match.group(1))
        
        # Titre alternatif
        if not self.data['title']:
            title_match = re.search(r'<span[^>]*class="fr-text--bold"[^>]*>Titre</span>\s*<span>:</span>\s*<span>(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
            if title_match:
                self.data['title'] = self.clean_text(title_match.group(1))
        
        # Description/Objet
        desc_match = re.search(r'<span[^>]*class="fr-text--bold"[^>]*>Description</span>\s*<span>:</span>\s*<span>(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if desc_match:
            self.data['object'] = self.clean_text(desc_match.group(1))
        
        # Acheteur
        buyer_match = re.search(r'<span[^>]*class="fr-text--bold"[^>]*>Nom officiel</span>\s*<span>:</span>\s*<span>(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if buyer_match:
            self.data['buyer'] = self.clean_text(buyer_match.group(1))
        
        # Identifiant de procédure
        proc_match = re.search(r'<span[^>]*class="fr-text--bold"[^>]*>Identifiant de la procédure</span>\s*<span>:</span>\s*<span>(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if proc_match:
            self.data['procedure_id'] = self.clean_text(proc_match.group(1))
        
        # Identifiant interne
        int_match = re.search(r'<span[^>]*class="fr-text--bold"[^>]*>Identifiant interne</span>\s*<span>:</span>\s*<span>(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if int_match:
            self.data['internal_id'] = self.clean_text(int_match.group(1))
            if not self.data['reference']:
                self.data['reference'] = self.data['internal_id']
        
        # Référence numéro d'annonce BOAMP
        annonce_match = re.search(r'Annonce n°\s*<strong>(\d+-\d+)</strong>', self.content)
        if annonce_match:
            self.data['reference'] = annonce_match.group(1)
        
        # Codes CPV
        cpv_matches = re.findall(r'data>\d+</span>\s*<span[^>]*data[^>]*>.*?Services? [^<]*</span>', self.content)
        # Extraction plus simple
        cpv_matches = re.findall(r'(\d{8})', self.content)
        self.data['cpv_codes'] = [c for c in cpv_matches if c.startswith(('72', '48', '79'))]
        
        # Date de clôture
        date_match = re.search(r'Date.*?(?:limite|cloture|clôture).*?<span[^>]*>(\d{2}/\d{2}/\d{4})', self.content, re.DOTALL | re.IGNORECASE)
        if date_match:
            self.data['date_cloture'] = date_match.group(1)
        
        return bool(self.data['title'])
    
    def extract_joue_format(self):
        """Extraction format JOUE"""
        # Titre dans bt-21-procedure ou titrePrincipal
        title_match = re.search(r'data-labels-key="field\|name\|BT-21-Procedure".*?</span><span>: </span><span class="data">(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if title_match:
            self.data['title'] = self.clean_text(title_match.group(1))
        
        if not self.data['title']:
            title_match = re.search(r'<span[^>]*titrePrincipal[^>]*>(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
            if title_match:
                self.data['title'] = self.clean_text(title_match.group(1))
        
        # Description/Objet
        desc_match = re.search(r'data-labels-key="field\|name\|BT-24-Procedure".*?</span><span>: </span><span class="data">(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if desc_match:
            self.data['object'] = self.clean_text(desc_match.group(1))
        
        # Acheteur
        buyer_match = re.search(r'data-labels-key="field\|name\|BT-500-Organization-Company".*?</span><span>: </span><span class="data">(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if buyer_match:
            self.data['buyer'] = self.clean_text(buyer_match.group(1))
        
        # Identifiant procédure
        proc_match = re.search(r'data-labels-key="field\|name\|BT-04-notice".*?</span><span>: </span><span class="data">(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if proc_match:
            self.data['procedure_id'] = self.clean_text(proc_match.group(1))
        
        # Identifiant interne
        int_match = re.search(r'data-labels-key="field\|name\|BT-22-Procedure".*?</span><span>: </span><span class="data">(.*?)</span>', self.content, re.DOTALL | re.IGNORECASE)
        if int_match:
            self.data['internal_id'] = self.clean_text(int_match.group(1))
            if not self.data['reference']:
                self.data['reference'] = self.data['internal_id']
        
        # Codes CPV
        cpv_matches = re.findall(r'data">(\d{8})</span>', self.content)
        self.data['cpv_codes'] = list(set(cpv_matches))
        
        # Date de clôture
        date_match = re.search(r'business-term\|name\|BT-131".*?</span><span>: </span><span class="data">(\d{2}/\d{2}/\d{4})', self.content, re.DOTALL | re.IGNORECASE)
        if date_match:
            self.data['date_cloture'] = date_match.group(1)
        
        return bool(self.data['title'])
    
    def clean_text(self, text):
        """Nettoie le texte HTML"""
        if not text:
            return ''
        # Supprimer les balises HTML
        text = re.sub(r'<[^>]+>', '', text)
        # Nettoyer les espaces
        text = ' '.join(text.split())
        # Décoder les entités HTML
        text = text.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&#039;', "'").replace('&#039;', "'")
        return text.strip()
    
    def extract(self):
        """Extrait les données selon le format détecté"""
        # Détecter le format
        filename = Path(self.filepath).name
        
        if 'orgAcronyme' in filename:
            self.extract_place_format()
        elif 'boamp' in filename.lower():
            self.extract_boamp_format()
        elif 'joue' in filename.lower():
            self.extract_joue_format()
        else:
            # Essayer tous les formats
            if not self.extract_place_format():
                if not self.extract_boamp_format():
                    self.extract_joue_format()
        
        return self.data

def find_similarity(str1, str2):
    """Calcule la similarité entre deux chaînes"""
    if not str1 or not str2:
        return 0.0
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def find_redundancies(markets_data, similarity_threshold=0.75):
    """Trouve les marchés rédondants"""
    redundancies = []
    
    # Grouper par acheteur
    by_buyer = defaultdict(list)
    for data in markets_data:
        if data['buyer']:
            by_buyer[data['buyer']].append(data)
        else:
            by_buyer['INCONNU'].append(data)
    
    # Comparer dans chaque groupe
    for buyer, markets in by_buyer.items():
        for i, m1 in enumerate(markets):
            for m2 in markets[i+1:]:
                # Comparer titres
                title_sim = find_similarity(m1['title'], m2['title'])
                # Comparer objets
                obj_sim = find_similarity(m1['object'], m2['object'])
                # Comparer références
                ref_match = m1['reference'] and m2['reference'] and m1['reference'] == m2['reference']
                # Comparer CPV
                cpv_match = bool(set(m1['cpv_codes']) & set(m2['cpv_codes']))
                
                # Critères de redondance
                score = 0
                reasons = []
                
                if ref_match:
                    score += 3
                    reasons.append("Même référence")
                
                if title_sim > similarity_threshold:
                    score += 2
                    reasons.append(f"Titres similaires ({title_sim:.0%})")
                
                if obj_sim > similarity_threshold:
                    score += 2
                    reasons.append(f"Objets similaires ({obj_sim:.0%})")
                
                if cpv_match and m1['cpv_codes']:
                    score += 1
                    reasons.append("Codes CPV communs")
                
                # Si score suffisant, c'est un doublon potentiel
                if score >= 3:
                    redundancies.append({
                        'file1': m1['filename'],
                        'file2': m2['filename'],
                        'buyer': buyer,
                        'score': score,
                        'reasons': reasons,
                        'title1': m1['title'][:100] + '...' if len(m1['title']) > 100 else m1['title'],
                        'title2': m2['title'][:100] + '...' if len(m2['title']) > 100 else m2['title'],
                        'reference1': m1['reference'],
                        'reference2': m2['reference'],
                        'date1': m1['date_cloture'],
                        'date2': m2['date_cloture']
                    })
    
    return sorted(redundancies, key=lambda x: x['score'], reverse=True)

def main():
    """Fonction principale"""
    print("=" * 80)
    print("ANALYSE DES MARCHÉS RÉDONDANTS")
    print("=" * 80)
    
    # Récupérer tous les fichiers HTML
    html_files = sorted(HTML_DIR.glob("*.html"))
    print(f"\n{len(html_files)} fichiers HTML trouvés\n")
    
    # Extraire les données
    markets_data = []
    for filepath in html_files:
        try:
            extractor = MarketDataExtractor(filepath)
            data = extractor.extract()
            if data['title'] or data['reference']:
                markets_data.append(data)
                print(f"✓ {filepath.name[:50]:<50} | {data['title'][:40]:<40} | {data['buyer'][:30]}")
            else:
                print(f"✗ {filepath.name[:50]:<50} | [PAS DE DONNÉES EXTRAITES]")
        except Exception as e:
            print(f"✗ {filepath.name[:50]:<50} | [ERREUR: {e}]")
    
    print(f"\n{len(markets_data)} marchés analysés avec succès")
    
    # Recherche des redondances
    print("\n" + "=" * 80)
    print("RECHERCHE DES RÉDONDANCES")
    print("=" * 80)
    
    redundancies = find_redundancies(markets_data)
    
    if not redundancies:
        print("\nAucune redondance détectée (seuil: 75% de similarité)")
    else:
        print(f"\n{len(redundancies)} redondances potentielles détectées:\n")
        
        for i, red in enumerate(redundancies, 1):
            print(f"\n{'─' * 80}")
            print(f"RÉDONDANCE #{i} (Score: {red['score']}/8)")
            print(f"{'─' * 80}")
            print(f"  Acheteur : {red['buyer']}")
            print(f"  Raisons  : {', '.join(red['reasons'])}")
            print()
            print(f"  Fichier 1: {red['file1']}")
            print(f"  Référence: {red['reference1']}")
            print(f"  Date     : {red['date1']}")
            print(f"  Titre    : {red['title1']}")
            print()
            print(f"  Fichier 2: {red['file2']}")
            print(f"  Référence: {red['reference2']}")
            print(f"  Date     : {red['date2']}")
            print(f"  Titre    : {red['title2']}")
    
    # Sauvegarder les résultats
    output_file = Path("/home/michka/Documents/0-AO-DCE/redundancies_report.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_files': len(html_files),
            'parsed_files': len(markets_data),
            'redundancies': redundancies,
            'markets': markets_data
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n\nRapport sauvegardé dans: {output_file}")
    
    # Résumé par acheteur
    print("\n" + "=" * 80)
    print("RÉSUMÉ PAR ACHETEUR")
    print("=" * 80)
    by_buyer = defaultdict(list)
    for data in markets_data:
        buyer = data['buyer'] if data['buyer'] else 'INCONNU'
        by_buyer[buyer].append(data)
    
    for buyer, markets in sorted(by_buyer.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n{buyer[:60]:<60} ({len(markets)} marchés)")
        for m in markets:
            print(f"  - {m['filename'][:40]:<40} | {m['title'][:50]:<50}")

if __name__ == "__main__":
    main()
