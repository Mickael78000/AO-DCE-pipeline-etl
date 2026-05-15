#!/usr/bin/env python3
"""
Analyse rapide des marchés rédondants - Version DOM-first avec BeautifulSoup
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict
from bs4 import BeautifulSoup

def extract_data(filepath):
    """Extrait les données clés d'un fichier HTML avec DOM-first + regex fallback"""
    try:
        filepath = Path(filepath)
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        soup = BeautifulSoup(content, 'html.parser')
        
        data = {
            'filename': filepath.name,
            'title': '',
            'reference': '',
            'buyer': '',
            'cpv': [],
            'source_type': '',
            'is_alias': False,
            'alias_of': ''
        }
        
        # Détection des alias (fichiers doublons sans description)
        if filepath.name == '13joue003085442026.html':
            # C'est un alias de 13joue003085442026-2026-fourniture-solutions-infrastructure.html
            data['is_alias'] = True
            data['alias_of'] = '13joue003085442026-2026-fourniture-solutions-infrastructure.html'
        
        # Détection du type de source
        if 'marchesonline.com' in content or filepath.name.startswith('ao-'):
            data['source_type'] = 'MARCHES_ONLINE'
            _extract_marches_online(soup, content, data, filepath)
        elif 'orgAcronyme' in filepath.name or 'consultation_depot' in content:
            data['source_type'] = 'PLACE_NUMERIC'
            _extract_place_numeric(soup, content, data, filepath)
        elif 'weboramaItemTag' in content and 'title_article' in content:
            data['source_type'] = 'FRANCE_MARCHES'
            _extract_france_marches(soup, content, data, filepath)
        elif filepath.name.startswith('26-') or 'boamp' in filepath.name.lower():
            data['source_type'] = 'BOAMP_XML'
            _extract_boamp_xml(soup, content, data)
        else:
            data['source_type'] = 'STANDARD'
            _extract_standard(soup, content, data)
        
        return data
    except Exception as e:
        return {'filename': Path(filepath).name, 'error': str(e), 'title': '', 'reference': '', 'buyer': '', 'cpv': [], 'source_type': 'ERROR'}

def _extract_marches_online(soup, content, data, filepath):
    """Extraction format Marchés Online (ao-*.html) - DOM-first"""
    # --- TITRE : DOM-first ---
    # 1. <title> tag
    if soup.title:
        title_match = re.search(r"Appel d'offres\s*:\s*(.*?)(?:,|</title>|$)", str(soup.title), re.IGNORECASE)
        if title_match:
            data['title'] = clean_text(title_match.group(1))
    
    # 2. <h1 class="...title-avis...">
    if not data['title']:
        h1_title = soup.find('h1', class_=lambda x: x and 'title-avis' in x)
        if h1_title:
            data['title'] = clean_text(h1_title.get_text())
    
    # 3. <meta name="description">
    if not data['title']:
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            desc_match = re.search(r"appel d'offre\s*:\s*(.*?)\.?\s*$", meta_desc.get('content'), re.IGNORECASE)
            if desc_match:
                data['title'] = clean_text(desc_match.group(1))
    
    # 4. Fallback regex: "Intitulé du marché :"
    if not data['title']:
        match = re.search(r'Intitulé du marché\s*:\s*(.*?)<', content, re.IGNORECASE)
        if match:
            data['title'] = clean_text(match.group(1))
    
    # --- RÉFÉRENCE : extraire depuis le nom de fichier (ID unique) ---
    # Format: ao-9594452-1.html → référence: MO-9594452 (Marchés Online)
    if not data['reference']:
        match = re.search(r'ao-(\d+)-', filepath.name)
        if match:
            data['reference'] = f"MO-{match.group(1)}"
    
    # Fallback (ancien - ne pas utiliser refContrat qui est identique pour tous)
    # match = re.search(r"'refContrat'\s*:\s*'(\d+)'", content)
    # if match:
    #     data['reference'] = match.group(1)
    
    # --- ACHETEUR : DOM + regex ---
    if not data['buyer']:
        # Chercher "Pouvoir adjudicateur" ou "Acheteur" dans le texte structuré
        buyer_section = soup.find(string=re.compile(r'Pouvoir adjudicateur|Acheteur', re.I))
        if buyer_section:
            parent = buyer_section.find_parent()
            if parent:
                next_span = parent.find_next('span', class_=re.compile(r'text', re.I))
                if next_span:
                    data['buyer'] = clean_text(next_span.get_text())
    
    # Fallback regex patterns existants
    if not data['buyer']:
        match = re.search(r'Organisme\s*:</label>.*?<span[^>]*>(.*?)</span>', content, re.DOTALL | re.IGNORECASE)
        if match:
            data['buyer'] = clean_text(match.group(1))
    
    # --- CPV : DOM + regex ---
    if not data['cpv']:
        # Recherche "Code CPV principal"
        cpv_match = re.search(r'Code CPV principal.*?:\s*(\d+)', content, re.IGNORECASE)
        if cpv_match:
            data['cpv'] = [cpv_match.group(1)]
    
    # Fallback sur les codes 8 chiffres
    if not data['cpv']:
        cpv_matches = re.findall(r'(\d{8})', content)
        if cpv_matches:
            data['cpv'] = list(set(cpv_matches))[:3]

def _extract_place_numeric(soup, content, data, filepath):
    """Extraction format PLACE numérique (2986*.html) - DOM-first"""
    # --- TITRE : DOM-first ---
    # 1. <h1> ou <h2> contenant "consultation" ou "intitulé"
    for heading in ['h1', 'h2']:
        if data['title']:
            break
        for tag in soup.find_all(heading):
            text = tag.get_text(strip=True).lower()
            if 'consultation' in text or 'intitul' in text:
                data['title'] = clean_text(tag.get_text())
                break
    
    # 2. Fallback: recherche label "intitulé" ou "objet"
    if not data['title']:
        for label in ['intitul', 'objet', 'titre']:
            pattern = re.compile(rf'{label}[éèe]?\s*[:\-]?\s*([^<\n]{{10,150}})', re.IGNORECASE)
            match = pattern.search(content)
            if match:
                data['title'] = clean_text(match.group(1))
                break
    
    # --- RÉFÉRENCE : nom de fichier ou contenu ---
    # Extraction ID depuis le nom de fichier (ex: 2986378?orgAcronyme=f2h.html)
    if not data['reference']:
        filename_match = re.search(r'(\d+)', filepath.name)
        if filename_match:
            data['reference'] = filename_match.group(1)
    
    # --- ACHETEUR : patterns spécifiques PLACE ---
    if not data['buyer']:
        # Recherche dans les métadonnées
        org_span = soup.find('span', string=re.compile(r'organisme|acheteur|client', re.I))
        if org_span:
            next_sibling = org_span.find_next_sibling()
            if next_sibling:
                data['buyer'] = clean_text(next_sibling.get_text())
    
    # Fallback patterns existants
    if not data['buyer']:
        for pattern in [
            r'Organisme\s*:</label>.*?<span[^>]*>(.*?)</span>',
            r'Nom officiel</span>\s*<span>:</span>\s*<span>(.*?)</span>',
        ]:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                data['buyer'] = clean_text(match.group(1))
                break
    
    # --- CPV ---
    if not data['cpv']:
        cpv_matches = re.findall(r'(\d{8})', content)
        if cpv_matches:
            data['cpv'] = list(set(cpv_matches))[:3]

def _extract_boamp_xml(soup, content, data):
    """Extraction format XML BOAMP (26-41049.html) - DOM-first"""
    # --- TITRE ---
    # Format: <span class="fr-text--bold">Titre</span>...<span>Texte du titre</span>
    titre_label = soup.find('span', class_='fr-text--bold', string=re.compile(r'Titre', re.I))
    if titre_label:
        parent = titre_label.find_parent()
        if parent:
            spans = parent.find_all('span')
            for span in spans:
                if span.get_text(strip=True) and span.get_text(strip=True) != 'Titre':
                    data['title'] = clean_text(span.get_text())
                    break
    
    # Fallback: <title> tag
    if not data['title'] and soup.title:
        title_match = re.search(r'Avis n°\s*(\d+-\d+).*?-\s*(.*?)$', soup.title.get_text())
        if title_match:
            data['title'] = clean_text(title_match.group(2))
    
    # --- RÉFÉRENCE ---
    # Format: Annonce n°<strong>26-41049</strong>
    if not data['reference']:
        annonce_match = re.search(r'Annonce n°\s*<strong>(\d+-\d+)</strong>', content, re.IGNORECASE)
        if annonce_match:
            data['reference'] = annonce_match.group(1)
    
    # Fallback: Identifiant interne
    if not data['reference']:
        identifiant_label = soup.find('span', class_='fr-text--bold', string=re.compile(r'Identifiant interne', re.I))
        if identifiant_label:
            parent = identifiant_label.find_parent()
            if parent:
                spans = parent.find_all('span')
                for span in spans:
                    text = span.get_text(strip=True)
                    if text and text not in ['Identifiant interne', ':']:
                        data['reference'] = clean_text(text)
                        break
    
    # --- ACHETEUR ---
    # Format: <span class="fr-text--bold">Nom officiel</span>...<span>Nom de l'acheteur</span>
    if not data['buyer']:
        nom_officiel = soup.find('span', class_='fr-text--bold', string=re.compile(r'Nom officiel', re.I))
        if nom_officiel:
            parent = nom_officiel.find_parent()
            if parent:
                spans = parent.find_all('span')
                for span in spans:
                    text = span.get_text(strip=True)
                    if text and text not in ['Nom officiel', ':']:
                        data['buyer'] = clean_text(text)
                        break
    
    # --- CPV ---
    if not data['cpv']:
        cpv_section = soup.find('span', string=re.compile(r'cpv', re.I))
        if cpv_section:
            cpv_matches = re.findall(r'(\d{8})', str(cpv_section.find_parent()))
            if cpv_matches:
                data['cpv'] = list(set(cpv_matches))[:3]

def _extract_france_marches(soup, content, data, filepath):
    """Extraction format France Marchés (weboramaItemTag JSON) - regex sur JavaScript"""
    # --- TITRE : regex sur weboramaItemTag JSON ---
    # Format: var weboramaItemTag = JSON.parse("..."title_article\\u0022":"..."")
    if not data['title']:
        # Pattern pour extraire title_article du JSON (avec échappements \u0022 pour ")
        match = re.search(r'title_article\\u0022\s*:\\u0022([^\\u0022]+)', content, re.IGNORECASE)
        if match:
            # Décode les séquences Unicode échappées (\u0022 -> ", \u0020 -> espace, etc.)
            title = match.group(1)
            title = title.replace('\\u0020', ' ').replace('\\u0027', "'").replace('\\u0022', '"')
            title = title.replace('\\u00E9', 'é').replace('\\u00E8', 'è').replace('\\u00EA', 'ê')
            title = title.replace('\\u00E0', 'à').replace('\\u00E2', 'â').replace('\\u00E7', 'ç')
            title = title.replace('\\u00F4', 'ô').replace('\\u00FB', 'û').replace('\\u00F9', 'ù')
            title = title.replace('\\u00EB', 'ë').replace('\\u00EF', 'ï').replace('\\u00FC', 'ü')
            title = title.replace('\\u002D', '-').replace('\\u2019', "'")
            data['title'] = clean_text(title)
    
    # Fallback DOM: chercher dans <title> ou <meta name="description">
    if not data['title']:
        # Extraire depuis <title> après "Appel d'offre :"
        if soup.title:
            title_match = re.search(r"Appel d'offre\s*:\s*([^<\-]+)", str(soup.title), re.IGNORECASE)
            if title_match:
                data['title'] = clean_text(title_match.group(1))
        
        # Fallback: <meta name="description">
        if not data['title']:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                desc_match = re.search(r"Appel d'offre\s+n°[^:]+:\s*([^\.]+)", meta_desc.get('content'), re.IGNORECASE)
                if desc_match:
                    data['title'] = clean_text(desc_match.group(1))
        
        # Dernier fallback: <h1>
        if not data['title']:
            h1 = soup.find('h1')
            if h1:
                data['title'] = clean_text(h1.get_text())
    
    # --- RÉFÉRENCE : extraire du nom de fichier ou du contenu ---
    if not data['reference']:
        # Pattern 1: 3boamp2643374 -> 3/boamp/2643374
        match = re.search(r'(\dboamp\d+)', filepath.name, re.IGNORECASE)
        if match:
            ref = match.group(1)
            # Formater comme 3/boamp/2643374
            data['reference'] = f"{ref[0]}/boamp/{ref[6:]}"
        else:
            # Pattern 2: 37ao26181581260520263294
            match = re.search(r'(\d{2}ao\d+)', filepath.name, re.IGNORECASE)
            if match:
                data['reference'] = match.group(1).upper()
            else:
                # Pattern 3: 36parisien1157695
                match = re.search(r'parisien(\d+)', filepath.name, re.IGNORECASE)
                if match:
                    data['reference'] = match.group(1)
    
    # Fallback: chercher "Appel d'offre n°X" dans <title> ou <meta>
    if not data['reference']:
        # Dans <title> ou <meta description>: "Appel d'offre n°13/joue/002946822026"
        # ou "Appel d'offre n°3/boamp/2643374"
        # Note: l'apostrophe peut être échappée comme &#039; ou &amp;#039;
        ref_patterns = [
            r"Appel d&#039;offre\s+n°([^\s\-]+)",  # Format avec &#039;
            r"Appel d'offre\s+n°([^\s\-]+)",       # Format standard
            r"Appel d&#039;offre\s+:\s*[^<\-]+\s*-\s*([^<\-]+)\s*-\s*2026",  # Format <title> avec &#039;
            r"Appel d'offre\s+:\s*[^<\-]+\s*-\s*([^<\-]+)\s*-\s*2026",       # Format <title> standard
        ]
        for pattern in ref_patterns:
            ref_match = re.search(pattern, content, re.IGNORECASE)
            if ref_match:
                data['reference'] = ref_match.group(1).strip()
                break
        
        # Chercher "Avis n°"
        if not data['reference']:
            match = re.search(r'Avis\s+n[°o]\s*(\d+[-/\d]*)', content, re.IGNORECASE)
            if match:
                data['reference'] = match.group(1)
    
    # --- ACHETEUR : chercher dans le contenu textuel ---
    if not data['buyer']:
        # Cherche "Acheteur" ou "Organisme" dans le contenu
        buyer_patterns = [
            r'Acheteur\s*:\s*([^<\n]{5,100})',
            r'Organisme\s*:\s*([^<\n]{5,100})',
            r'Nom\s+officiel\s*:\s*([^<\n]{5,100})',
        ]
        for pattern in buyer_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                data['buyer'] = clean_text(match.group(1))
                break
    
    # Fallback: chercher dans les balises structurées
    if not data['buyer']:
        buyer_label = soup.find(string=re.compile(r'Acheteur|Organisme', re.I))
        if buyer_label:
            parent = buyer_label.find_parent()
            if parent:
                next_elem = parent.find_next_sibling()
                if next_elem:
                    data['buyer'] = clean_text(next_elem.get_text())
    
    # --- CPV : extraction des codes 8 chiffres ---
    if not data['cpv']:
        cpv_matches = re.findall(r'(\d{8})', content)
        if cpv_matches:
            data['cpv'] = list(set(cpv_matches))[:3]

def _extract_standard(soup, content, data):
    """Extraction format standard (PLACE, BOAMP, JOUE classiques)"""
    # Extraction titre - multi-format
    # Format PLACE: Intitulé :</label>...<span>...
    if not data['title']:
        match = re.search(r'Intitulé\s*:</label>.*?<span[^>]*>(.*?)</span>', content, re.DOTALL | re.IGNORECASE)
        if match:
            data['title'] = clean_text(match.group(1))
    
    # Format BOAMP/JOUE: titrePrincipal
    if not data['title']:
        match = re.search(r'titrePrincipal[^>]*>(.*?)</span>', content, re.DOTALL | re.IGNORECASE)
        if match:
            data['title'] = clean_text(match.group(1))
    
    # Format BT-21-Procedure
    if not data['title']:
        match = re.search(r'BT-21-Procedure.*?</span><span>: </span><span[^>]*>(.*?)</span>', content, re.DOTALL | re.IGNORECASE)
        if match:
            data['title'] = clean_text(match.group(1))
    
    # Extraction référence
    if not data['reference']:
        match = re.search(r'Référence\s*:</label>.*?<span[^>]*>(.*?)</span>', content, re.DOTALL | re.IGNORECASE)
        if match:
            data['reference'] = clean_text(match.group(1))
    
    if not data['reference']:
        match = re.search(r'Annonce n°\s*<strong>(\d+-\d+)</strong>', content)
        if match:
            data['reference'] = match.group(1)
    
    if not data['reference']:
        match = re.search(r'Identifiant interne.*?</span><span>: </span><span[^>]*>(.*?)</span>', content, re.DOTALL)
        if match:
            data['reference'] = clean_text(match.group(1))
    
    # Extraction acheteur
    if not data['buyer']:
        match = re.search(r'Organisme\s*:</label>.*?<span[^>]*>(.*?)</span>', content, re.DOTALL | re.IGNORECASE)
        if match:
            data['buyer'] = clean_text(match.group(1))
    
    if not data['buyer']:
        match = re.search(r'Nom officiel</span>\s*<span>:</span>\s*<span>(.*?)</span>', content, re.DOTALL)
        if match:
            data['buyer'] = clean_text(match.group(1))
    
    if not data['buyer']:
        match = re.search(r'BT-500-Organization-Company.*?</span><span>: </span><span[^>]*>(.*?)</span>', content, re.DOTALL)
        if match:
            data['buyer'] = clean_text(match.group(1))
    
    # Extraction CPV
    if not data['cpv']:
        cpv_matches = re.findall(r'data-code-cpv="(\d+)"', content)
        if cpv_matches:
            data['cpv'] = list(set(cpv_matches))[:3]
        else:
            cpv_matches = re.findall(r'(\d{8})', content)
            if cpv_matches:
                data['cpv'] = list(set(cpv_matches))[:3]

def clean_text(text):
    """Nettoie le texte"""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = ' '.join(text.split())
    text = text.replace('&quot;', '"').replace('&amp;', '&').replace('&#039;', "'")
    return text.strip()[:200]  # Limiter la longueur

def find_duplicates(all_data):
    """Trouve les doublons"""
    duplicates = []
    
    # Grouper par acheteur
    by_buyer = defaultdict(list)
    for d in all_data:
        buyer = d['buyer'] if d['buyer'] else 'INCONNU'
        by_buyer[buyer].append(d)
    
    # Comparer dans chaque groupe
    for buyer, items in by_buyer.items():
        for i, item1 in enumerate(items):
            for item2 in items[i+1:]:
                score = 0
                reasons = []
                
                # Même référence
                if item1['reference'] and item2['reference'] and item1['reference'] == item2['reference']:
                    score += 4
                    reasons.append("MÊME RÉFÉRENCE")
                
                # Titres similaires
                if item1['title'] and item2['title']:
                    t1 = item1['title'].lower()
                    t2 = item2['title'].lower()
                    
                    # Similarité exacte
                    if t1 == t2:
                        score += 3
                        reasons.append("TITRES IDENTIQUES")
                    # Mots clés communs
                    else:
                        words1 = set(t1.split())
                        words2 = set(t2.split())
                        common = words1 & words2
                        if len(common) >= 5:
                            score += 2
                            reasons.append(f"{len(common)} mots communs")
                        
                        # Contient des termes clés
                        keywords = ['maintenance', 'infogérance', 'système information', 'informatique', 
                                   'télécom', 'réseau', 'serveur', 'logiciel', 'prestation', 'assistance']
                        k1 = [k for k in keywords if k in t1]
                        k2 = [k for k in keywords if k in t2]
                        if k1 and k2 and set(k1) == set(k2):
                            score += 1
                
                # Codes CPV communs
                if item1['cpv'] and item2['cpv']:
                    common_cpv = set(item1['cpv']) & set(item2['cpv'])
                    if common_cpv:
                        score += 1
                        reasons.append(f"CPV: {','.join(list(common_cpv)[:2])}")
                
                if score >= 3:
                    duplicates.append({
                        'score': score,
                        'file1': item1['filename'],
                        'file2': item2['filename'],
                        'buyer': buyer,
                        'reasons': reasons,
                        'ref1': item1['reference'],
                        'ref2': item2['reference'],
                        'title1': item1['title'][:80],
                        'title2': item2['title'][:80]
                    })
    
    return sorted(duplicates, key=lambda x: x['score'], reverse=True)

def main():
    html_dir = Path("/home/michka/Documents/0-AO-DCE/html_ao")
    files = list(html_dir.glob("*.html"))
    
    print(f"ANALYSE DE {len(files)} FICHIERS HTML")
    print("=" * 80)
    
    # Extraction
    all_data = []
    for f in files:
        data = extract_data(f)
        if data.get('title') or data.get('reference'):
            all_data.append(data)
            status = "✓"
        else:
            status = "✗"
        print(f"{status} {data['filename'][:50]:<50} | {data.get('title', '')[:40]:<40}")
    
    print(f"\n{len(all_data)} fichiers avec données exploitables")
    
    # Recherche doublons
    print("\n" + "=" * 80)
    print("REDONDANCES DÉTECTÉES")
    print("=" * 80)
    
    dups = find_duplicates(all_data)
    
    if not dups:
        print("\nAucune redondance significative détectée.")
    else:
        print(f"\n{len(dups)} redondances trouvées:\n")
        
        for i, d in enumerate(dups[:20], 1):  # Limiter à 20
            print(f"\n--- RÉDONDANCE #{i} (Score: {d['score']}) ---")
            print(f"Acheteur: {d['buyer']}")
            print(f"Raisons: {', '.join(d['reasons'])}")
            print(f"Fichier 1: {d['file1']}")
            print(f"  Réf: {d['ref1']}")
            print(f"  Titre: {d['title1']}")
            print(f"Fichier 2: {d['file2']}")
            print(f"  Réf: {d['ref2']}")
            print(f"  Titre: {d['title2']}")
    
    # Sauvegarde
    output = {
        'total': len(files),
        'parsed': len(all_data),
        'duplicates': dups,
        'data': all_data
    }
    
    out_file = Path("/home/michka/Documents/0-AO-DCE/rapport_redondances.json")
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n\nRapport complet sauvegardé: {out_file}")

if __name__ == "__main__":
    main()
