"""
Phase 7d: Reconstruction des URLs depuis match_source.

Cette phase tente de reconstruire l'URL source HTTPS à partir du nom de fichier
(match_source) selon des règles par type de source.

Patterns supportés:
- 13joue* -> https://www.boamp.fr/avis/... (France Marchés / BOAMP)
- ao-* -> https://www.marchesonline.com/... (Marchés Online)
- 3boamp* -> https://www.boamp.fr/... (BOAMP XML)
- *parisien* -> https://marches.megalis.bzh/... (autres plateformes)
"""

import logging
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class EnrichUrlResult:
    """Résultat de la phase de reconstruction des URLs."""
    total_rows: int
    urls_reconstructed: int = 0
    urls_already_present: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class EnrichUrlConfig:
    """Configuration pour la phase de reconstruction des URLs."""
    enabled: bool = True
    output_csv: Optional[Path] = None


def resolve_url(match_source: str, source_type: str, reference: str) -> Optional[str]:
    """
    Tente de résoudre l'URL depuis match_source selon des patterns.
    
    Args:
        match_source: Nom du fichier HTML source
        source_type: Type de source (FRANCE_MARCHES, MARCHES_ONLINE, etc.)
        reference: Référence de l'AO
        
    Returns:
        URL reconstruite ou None
    """
    if not match_source or match_source == '-':
        return None
    
    # Nettoyer le nom de fichier
    filename = match_source.replace('.html', '').replace('.txt', '')
    
    # Pattern 1: France Marchés / BOAMP (13joue*, 13place*)
    # Ex: 13joue002671162026-2026-mise-disposition-gestion
    joue_match = re.search(r'13joue(\d+)', filename, re.IGNORECASE)
    if joue_match:
        id_num = joue_match.group(1)
        # France Marchés / JOUe
        return f"https://www.boamp.fr/avis/detail/{id_num}"
    
    # Pattern 2: BOAMP XML (3boamp*)
    # Ex: 3boamp2647639-2026-mise-place-outil
    boamp_match = re.search(r'3boamp(\d+)', filename, re.IGNORECASE)
    if boamp_match:
        annonce_num = boamp_match.group(1)
        return f"https://www.boamp.fr/avis/detail/{annonce_num}"
    
    # Pattern 3: Marchés Online (ao-*-N.html ou MO-*)
    # Ex: ao-9594452-1, MO-9597280
    mo_match = re.search(r'[ao|MO]-(\d+)', filename, re.IGNORECASE)
    if mo_match:
        mo_num = mo_match.group(1)
        # Marchés Online
        return f"https://www.marchesonline.com/appel-offre/afficher/{mo_num}"
    
    # Pattern 4: Références avec structure connue
    # Ex: 2026-022-BL, 2026_07, 26-011
    if re.match(r'\d{4}-\d+', filename):
        # Format type référence interne - pas d'URL standard
        return None
    
    # Pattern 5: Place (PLACE_NUMERIC)
    # Ex: 2956468?orgAcronyme=g7h
    place_match = re.search(r'^(\d+)\?orgAcronyme=(\w+)', filename, re.IGNORECASE)
    if place_match:
        org_id = place_match.group(1)
        org_acr = place_match.group(2)
        return f"https://www.place-ici.fr/avis/{org_id}?org={org_acr}"
    
    # Pattern 6: ID numérique simple
    # Ex: 2987833, 2990888
    simple_id = re.match(r'^\d+$', filename)
    if simple_id:
        # Tenter de deviner selon source_type
        if source_type == 'FRANCE_MARCHES' or source_type == 'BOAMP_XML':
            return f"https://www.boamp.fr/avis/detail/{filename}"
        elif source_type == 'MARCHES_ONLINE':
            return f"https://www.marchesonline.com/appel-offre/afficher/{filename}"
    
    return None


def run_enrich_url_phase(
    input_csv: Path,
    output_csv: Path,
) -> Dict[str, Any]:
    """
    Exécute la phase de reconstruction des URLs.
    
    Args:
        input_csv: Fichier CSV d'entrée
        output_csv: Fichier CSV de sortie
        
    Returns:
        Statistiques de la reconstruction
    """
    log.info(f"Phase de reconstruction des URLs: {input_csv} -> {output_csv}")
    
    # Lire le CSV d'entrée
    rows = []
    fieldnames = []
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    
    log.info(f"{len(rows)} lignes à traiter pour les URLs")
    
    result = EnrichUrlResult(total_rows=len(rows))
    
    # Traiter chaque ligne
    for i, row in enumerate(rows):
        try:
            url_current = row.get('URL source HTTPS', '')
            
            # Si URL déjà présente et valide, passer
            if url_current and url_current != '-' and url_current.startswith('http'):
                result.urls_already_present += 1
                continue
            
            # Récupérer les données nécessaires
            match_source = row.get('match_source', '')
            source_type = row.get('source_type', '')
            reference = row.get('Référence', '')
            
            # Tenter de résoudre l'URL
            url = resolve_url(match_source, source_type, reference)
            
            if url:
                row['URL source HTTPS'] = url
                result.urls_reconstructed += 1
                log.debug(f"URL reconstruite pour {reference}: {url}")
            else:
                log.debug(f"Impossible de reconstruire l'URL pour {reference} (source: {match_source})")
                    
        except Exception as e:
            error_msg = f"Erreur URL ligne {i}: {e}"
            log.error(error_msg)
            result.errors.append(error_msg)
    
    # S'assurer que toutes les lignes ont les mêmes clés
    all_new_keys = set()
    for row in rows:
        all_new_keys.update(row.keys())
    
    final_fieldnames = list(fieldnames)
    for key in all_new_keys:
        if key not in final_fieldnames:
            final_fieldnames.append(key)
    
    # Écrire le CSV avec URLs
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=final_fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    log.info(f"CSV avec URLs écrit: {output_csv}")
    log.info(f"URLs déjà présentes: {result.urls_already_present}")
    log.info(f"URLs reconstruites: {result.urls_reconstructed}")
    log.info(f"URLs manquantes: {result.total_rows - result.urls_already_present - result.urls_reconstructed}")
    
    return {
        'total_rows': result.total_rows,
        'urls_reconstructed': result.urls_reconstructed,
        'urls_already_present': result.urls_already_present,
        'errors': result.errors,
        'output_csv': str(output_csv),
    }


def print_enrich_url_summary(stats: Dict[str, Any]) -> None:
    """Affiche le résumé de la phase de reconstruction des URLs."""
    print()
    print("=" * 70)
    print("RECONSTRUCTION DES URLS - Résumé")
    print("=" * 70)
    print(f"Lignes traitées:          {stats.get('total_rows', 0)}")
    print(f"URLs déjà présentes:      {stats.get('urls_already_present', 0)}")
    print(f"URLs reconstruites:       {stats.get('urls_reconstructed', 0)}")
    urls_missing = stats.get('total_rows', 0) - stats.get('urls_already_present', 0) - stats.get('urls_reconstructed', 0)
    print(f"URLs manquantes:          {urls_missing}")
    if stats.get('errors'):
        print(f"Erreurs:                  {len(stats['errors'])}")
    print(f"Fichier sortie:           {stats.get('output_csv', 'N/A')}")
    print("=" * 70)
