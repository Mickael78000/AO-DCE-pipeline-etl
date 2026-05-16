"""
Phase d'enrichissement des descriptifs du pipeline.
Utilise extract_descriptif.py pour enrichir le CSV avec les données structurées.
"""

import logging
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ao_etl.enrich_descriptif import enrich_from_descriptif, enrich_csv_row

log = logging.getLogger(__name__)


@dataclass
class EnrichDescriptifConfig:
    """Configuration pour la phase d'enrichissement des descriptifs."""
    enabled: bool = False
    output_csv: Optional[Path] = None


@dataclass
class EnrichDescriptifResult:
    """Résultat de la phase d'enrichissement."""
    total_rows: int
    enriched_rows: int
    errors: List[str] = field(default_factory=list)
    new_columns: List[str] = field(default_factory=list)
    lots_found: int = 0
    cpv_found: int = 0
    montants_enriched: int = 0


def run_enrich_descriptif_phase(
    input_csv: Path,
    html_dir: Path,
    output_csv: Path,
) -> Dict[str, Any]:
    """
    Exécute la phase d'enrichissement des descriptifs.
    
    Args:
        input_csv: Fichier CSV d'entrée
        html_dir: Répertoire contenant les fichiers HTML sources
        output_csv: Fichier CSV de sortie enrichi
        
    Returns:
        Statistiques de l'enrichissement
    """
    log.info(f"Enrichissement des descriptifs depuis {html_dir}")
    
    # Lire le CSV d'entrée
    rows = []
    fieldnames = []
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    
    log.info(f"{len(rows)} lignes à enrichir")
    
    # Nouvelles colonnes à ajouter
    new_columns = [
        'cpv_principal',
        'cpv_supplementaires',
        'nombre_lots',
        'lots_detail',
        'criteres_attribution',
        'duree_reelle',
        'options_reconduction',
        'departements_publication',
        'annonce_numero',
        'conflits_detectes',
    ]
    
    # Ajouter les nouvelles colonnes
    for col in new_columns:
        if col not in fieldnames:
            fieldnames.append(col)
    
    result = EnrichDescriptifResult(
        total_rows=len(rows),
        enriched_rows=0,
        new_columns=new_columns,
    )
    
    # Pré-indexer tous les fichiers HTML par leur contenu pour accélérer la recherche
    log.info("Indexation des fichiers HTML...")
    html_index = {}  # reference -> html_path
    
    for html_path in html_dir.glob("*.html"):
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read(150000)  # Lire 150KB pour avoir tout le descriptif
            
            # Extraire l'identifiant interne du contenu
            match = re.search(r'Identifiant interne\s*[:\s]+([^\s<\n]+)', content, re.IGNORECASE)
            if match:
                identifiant = match.group(1).strip()
                html_index[identifiant] = html_path
                
            # Aussi indexer par référence si présente dans le contenu
            for ref in [row.get('Référence', '') for row in rows]:
                if ref in content[:100000]:
                    html_index[ref] = html_path
                    
        except Exception as e:
            log.debug(f"Erreur indexation {html_path}: {e}")
            continue
    
    log.info(f"{len(html_index)} entrées dans l'index")
    
    # Enrichir chaque ligne
    for i, row in enumerate(rows):
        try:
            # Chercher le fichier HTML correspondant
            reference = row.get('Référence', '')
            if not reference:
                continue
            
            html_file = None
            
            # Stratégie 1: Chercher dans l'index par référence exacte
            if reference in html_index:
                html_file = html_index[reference]
            
            # Stratégie 2: Match par nom de fichier normalisé
            if not html_file:
                ref_clean = reference.replace('/', '').replace('-', '').replace('_', '').lower()
                for html_path in html_dir.glob("*.html"):
                    html_name = html_path.stem.lower().replace('-', '').replace('_', '').replace('.', '')
                    if ref_clean in html_name or html_name in ref_clean:
                        html_file = html_path
                        break
            
            # Stratégie 3: Match par patterns spécifiques (BOAMP, MO, etc.)
            if not html_file:
                # BOAMP: 3/boamp/2647639 → 3boamp2647639
                boamp_match = re.search(r'(\d+)[/\\]boamp[/\\](\d+)', reference, re.IGNORECASE)
                if boamp_match:
                    pattern = f"{boamp_match.group(1)}boamp{boamp_match.group(2)}"
                    for identifiant, path in html_index.items():
                        if pattern in identifiant.lower() or pattern in path.stem.lower():
                            html_file = path
                            break
                
                # MO-XXXX → chercher dans l'index ou fichiers
                if not html_file:
                    mo_match = re.search(r'MO-?(\d+)', reference, re.IGNORECASE)
                    if mo_match:
                        mo_num = mo_match.group(1)
                        # Chercher dans l'index
                        for identifiant, path in html_index.items():
                            if mo_num in identifiant or mo_num in path.stem:
                                html_file = path
                                break
            
            # Stratégie 4: Recherche dans le contenu de tous les fichiers (fallback)
            if not html_file:
                for html_path in html_dir.glob("*.html"):
                    try:
                        with open(html_path, 'r', encoding='utf-8') as f:
                            content = f.read(80000)
                        if reference in content:
                            html_file = html_path
                            # Ajouter à l'index pour les prochaines fois
                            html_index[reference] = html_file
                            break
                    except Exception:
                        continue
            
            # Si pas trouvé par référence, chercher par identifiant interne dans le descriptif
            if not html_file:
                # Essayer avec les fichiers déjà extraits (.txt)
                txt_file = html_dir / f"{reference}_descriptif.txt"
                if txt_file.exists():
                    # Lire directement le fichier texte
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        text = f.read()
                    # Parsing manuel du texte
                    from ao_etl.enrich_descriptif import parse_cpv, parse_lots, parse_montant
                    
                    # Extraire les données
                    cpv_principal, cpv_supp = parse_cpv(text)
                    lots = parse_lots(text)
                    
                    # Montants
                    montant_estime = None
                    match = re.search(r'Valeur estimée hors TVA\s*[:\s]+([\d\s,\.]+)', text)
                    if match:
                        montant_estime = parse_montant(match.group(1))
                    
                    # Mise à jour de la ligne
                    if cpv_principal:
                        row['cpv_principal'] = cpv_principal
                        result.cpv_found += 1
                    
                    if lots:
                        row['nombre_lots'] = len(lots)
                        row['lots_detail'] = "; ".join([
                            f"Lot {l.numero}: {l.titre[:50]}" for l in lots
                        ])
                        result.lots_found += len(lots)
                    
                    if montant_estime and not row.get('Estimation du marché'):
                        row['Estimation du marché'] = montant_estime
                        result.montants_enriched += 1
                    
                    result.enriched_rows += 1
                    continue
            
            if html_file:
                # Enrichir depuis le HTML
                enrichi = enrich_from_descriptif(html_file)
                if enrichi:
                    row = enrich_csv_row(row, enrichi)
                    result.enriched_rows += 1
                    
                    if enrichi.lots:
                        result.lots_found += len(enrichi.lots)
                    if enrichi.cpv_principal:
                        result.cpv_found += 1
                    if enrichi.montant_estime:
                        result.montants_enriched += 1
            else:
                log.warning(f"Fichier HTML non trouvé pour {reference}")
                
        except Exception as e:
            error_msg = f"Erreur ligne {i} ({reference}): {e}"
            log.error(error_msg)
            result.errors.append(error_msg)
    
    # S'assurer que toutes les lignes ont les mêmes clés
    all_keys = set(fieldnames)
    for row in rows:
        all_keys.update(row.keys())
    
    # Écrire le CSV enrichi avec toutes les colonnes
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
        writer.writeheader()
        writer.writerows(rows)
    
    log.info(f"CSV enrichi écrit: {output_csv}")
    log.info(f"Lignes enrichies: {result.enriched_rows}/{result.total_rows}")
    log.info(f"Lots trouvés: {result.lots_found}, CPV trouvés: {result.cpv_found}")
    
    return {
        'total_rows': result.total_rows,
        'enriched_rows': result.enriched_rows,
        'lots_found': result.lots_found,
        'cpv_found': result.cpv_found,
        'montants_enriched': result.montants_enriched,
        'new_columns': result.new_columns,
        'errors': result.errors,
        'output_csv': str(output_csv),
    }


def print_enrich_descriptif_summary(stats: Dict[str, Any]) -> None:
    """Affiche le résumé de la phase d'enrichissement."""
    print()
    print("=" * 70)
    print("ENRICHISSEMENT DESCRIPTIF - Résumé")
    print("=" * 70)
    print(f"Lignes traitées:    {stats.get('total_rows', 0)}")
    print(f"Lignes enrichies:   {stats.get('enriched_rows', 0)}")
    print(f"Lots trouvés:       {stats.get('lots_found', 0)}")
    print(f"CPV identifiés:     {stats.get('cpv_found', 0)}")
    print(f"Montants complétés: {stats.get('montants_enriched', 0)}")
    print(f"Nouvelles colonnes: {len(stats.get('new_columns', []))}")
    if stats.get('errors'):
        print(f"Erreurs:            {len(stats['errors'])}")
    print(f"Fichier sortie:     {stats.get('output_csv', 'N/A')}")
    print("=" * 70)
