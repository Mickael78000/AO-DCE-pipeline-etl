"""Module de matching robuste entre références CSV et fichiers HTML."""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Optional, Set
from dataclasses import dataclass, asdict

log = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Résultat d'un matching."""
    reference: str
    html_path: Optional[Path]
    match_method: str  # 'index', 'content', 'pattern', 'none'
    confidence: float  # 0.0 - 1.0


class HTMLMatcher:
    """Matcher robuste avec cache persistant."""
    
    def __init__(self, html_dir: Path, cache_path: Optional[Path] = None):
        self.html_dir = Path(html_dir)
        self.cache_path = cache_path or (html_dir / '.matcher_cache.json')
        self.index: Dict[str, Path] = {}
        self.indexed_identifiers: Set[str] = set()
        self._load_cache()
        self._build_index()
    
    def _load_cache(self) -> None:
        """Charge le cache depuis le disque."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.index = {k: Path(v) for k, v in cache_data.get('index', {}).items()}
                    self.indexed_identifiers = set(cache_data.get('indexed', []))
                    log.info(f"Cache chargé: {len(self.index)} entrées")
            except Exception as e:
                log.warning(f"Échec chargement cache: {e}")
                self.index = {}
                self.indexed_identifiers = set()
    
    def _save_cache(self) -> None:
        """Sauvegarde le cache sur le disque."""
        try:
            cache_data = {
                'index': {k: str(v) for k, v in self.index.items()},
                'indexed': list(self.indexed_identifiers)
            }
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            log.warning(f"Échec sauvegarde cache: {e}")
    
    def _build_index(self) -> None:
        """Construit l'index des fichiers HTML."""
        new_files = []
        
        for html_path in self.html_dir.glob('*.html'):
            if html_path.stem in self.indexed_identifiers:
                continue  # Déjà indexé
            
            try:
                with open(html_path, 'r', encoding='utf-8') as f:
                    content = f.read(100000)
                
                # Index par identifiant interne
                match = re.search(r'Identifiant interne\s*[:\s]+([^\s<\n]+)', content, re.IGNORECASE)
                if match:
                    identifiant = match.group(1).strip()
                    self.index[identifiant] = html_path
                    self.indexed_identifiers.add(html_path.stem)
                    new_files.append(identifiant)
                
                # Index par référence dans le contenu
                for ref_pattern in [
                    r'Annonce n°\s*[:\s]+([^\s<\n]+)',
                    r'Référence\s*[:\s]+([^\s<\n]+)',
                ]:
                    match = re.search(ref_pattern, content, re.IGNORECASE)
                    if match:
                        ref = match.group(1).strip()
                        if ref not in self.index:
                            self.index[ref] = html_path
                
            except Exception as e:
                log.debug(f"Erreur indexation {html_path}: {e}")
        
        if new_files:
            log.info(f"Index construit: {len(new_files)} nouveaux fichiers")
            self._save_cache()
    
    def find_html(self, reference: str) -> MatchResult:
        """Trouve le fichier HTML correspondant à une référence."""
        
        # 1. Recherche exacte dans l'index
        if reference in self.index:
            return MatchResult(
                reference=reference,
                html_path=self.index[reference],
                match_method='index',
                confidence=1.0
            )
        
        # 2. Recherche par nom de fichier normalisé
        ref_clean = reference.replace('/', '').replace('-', '').replace('_', '').lower()
        for html_path in self.html_dir.glob('*.html'):
            html_name = html_path.stem.lower().replace('-', '').replace('_', '').replace('.', '')
            if ref_clean in html_name or html_name in ref_clean:
                # Ajouter au cache
                self.index[reference] = html_path
                return MatchResult(
                    reference=reference,
                    html_path=html_path,
                    match_method='pattern',
                    confidence=0.8
                )
        
        # 3. Recherche dans le contenu (fallback lent)
        for html_path in self.html_dir.glob('*.html'):
            try:
                with open(html_path, 'r', encoding='utf-8') as f:
                    content = f.read(80000)
                if reference in content:
                    self.index[reference] = html_path
                    self._save_cache()
                    return MatchResult(
                        reference=reference,
                        html_path=html_path,
                        match_method='content',
                        confidence=0.9
                    )
            except Exception:
                continue
        
        return MatchResult(
            reference=reference,
            html_path=None,
            match_method='none',
            confidence=0.0
        )
    
    def get_stats(self) -> dict:
        """Retourne les statistiques du matcher."""
        return {
            'total_indexed': len(self.index),
            'files_indexed': len(self.indexed_identifiers),
            'cache_path': str(self.cache_path),
        }
