"""Phase DISCOVERY - Découverte des fichiers HTML source.

Responsabilités :
- Scanner le répertoire html_ao/
- Identifier tous les fichiers .html exploitables
- Classer les fichiers selon leur type (Marchés Online, France Marchés, etc.)
- Détecter les alias/fichiers techniques connus
- Produire une vue complète des sources disponibles
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Set, Optional
from enum import Enum


class FileCategory(Enum):
    """Catégorie d'un fichier HTML."""
    MARCHES_ONLINE = "marches_online"
    FRANCE_MARCHES = "france_marches"
    PLACE_NUMERIC = "place_numeric"
    BOAMP_XML = "boamp_xml"
    JOUE = "joue"
    STANDARD = "standard"
    ALIAS = "alias"
    TECHNICAL = "technical"


@dataclass
class DiscoveredFile:
    """Un fichier HTML découvert avec ses métadonnées."""
    path: Path
    filename: str
    category: FileCategory
    reference_derived: str  # Référence déduite du nom de fichier
    is_alias: bool = False
    alias_of: Optional[str] = None
    
    @property
    def is_orphan(self) -> bool:
        """Retourne True si ce fichier n'est pas encore lié à une entrée CSV."""
        return not hasattr(self, '_csv_row')


@dataclass
class DiscoveryResult:
    """Résultat de la phase discovery."""
    all_files: List[DiscoveredFile] = field(default_factory=list)
    by_category: dict = field(default_factory=dict)
    aliases: List[DiscoveredFile] = field(default_factory=list)
    potential_orphans: List[DiscoveredFile] = field(default_factory=list)
    total_count: int = 0
    
    def get_by_category(self, category: FileCategory) -> List[DiscoveredFile]:
        """Retourne les fichiers d'une catégorie donnée."""
        return self.by_category.get(category, [])


def derive_reference(filename: str) -> tuple[str, FileCategory]:
    """Dérive la référence et catégorie depuis le nom de fichier.
    
    Returns:
        (reference, category)
    """
    # Marchés Online: ao-XXXX-X.html → MO-XXXX
    if filename.startswith('ao-'):
        parts = filename.replace('ao-', '').replace('.html', '').split('-')
        ref = f"MO-{parts[0]}" if parts else filename
        return ref, FileCategory.MARCHES_ONLINE
    
    # JOUE: 13joueXXXXXXXX.html
    if filename.startswith('13joue'):
        ref = filename.replace('.html', '')
        return ref, FileCategory.JOUE
    
    # BOAMP: 3boampXXXXXXX.html
    if filename.startswith('3boamp'):
        ref = filename.replace('.html', '')
        return ref, FileCategory.BOAMP_XML
    
    # PLACE numeric: XXXXXX?orgAcronyme=XXX.html
    if '?orgAcronyme=' in filename:
        ref = filename.replace('.html', '')
        return ref, FileCategory.PLACE_NUMERIC
    
    # France Marchés: patterns connus
    if 'francemarches' in filename.lower() or filename.startswith(('37ao', '36parisien')):
        ref = filename.replace('.html', '')
        return ref, FileCategory.FRANCE_MARCHES
    
    # Standard
    return filename.replace('.html', ''), FileCategory.STANDARD


def is_likely_alias(filename: str) -> tuple[bool, Optional[str]]:
    """Détecte si un fichier est probablement un alias.
    
    Returns:
        (is_alias, alias_of_reference)
    """
    # Alias JOUE avec suffixe (1ère occurrence, 2ème occurrence)
    alias_patterns = [
        r'\(\s*1[èe]re?\s+occurrence\s*\)',
        r'\(\s*2[èe]me?\s+occurrence\s*\)',
        r'\(\s*doublon\s*\)',
    ]
    
    for pattern in alias_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            # Extraire la référence de base
            base_ref = re.sub(r'\s*\([^)]+\)\s*', '', filename)
            base_ref = base_ref.replace('.html', '')
            return True, base_ref
    
    return False, None


def discover_files(html_dir: Path) -> DiscoveryResult:
    """Découvre tous les fichiers HTML dans le répertoire.
    
    Args:
        html_dir: Répertoire contenant les fichiers HTML
        
    Returns:
        DiscoveryResult avec tous les fichiers classés
    """
    result = DiscoveryResult()
    
    if not html_dir.exists():
        raise FileNotFoundError(f"Répertoire HTML introuvable: {html_dir}")
    
    all_html_files = sorted(html_dir.glob('*.html'))
    
    for file_path in all_html_files:
        filename = file_path.name
        
        # Détecter les alias
        is_alias, alias_of = is_likely_alias(filename)
        
        # Dériver référence et catégorie
        ref, category = derive_reference(filename)
        
        # Créer l'objet DiscoveredFile
        discovered = DiscoveredFile(
            path=file_path,
            filename=filename,
            category=category,
            reference_derived=ref,
            is_alias=is_alias,
            alias_of=alias_of
        )
        
        result.all_files.append(discovered)
        
        # Classer par catégorie
        if category not in result.by_category:
            result.by_category[category] = []
        result.by_category[category].append(discovered)
        
        # Séparer les alias
        if is_alias:
            result.aliases.append(discovered)
    
    result.total_count = len(result.all_files)
    return result


def print_discovery_summary(result: DiscoveryResult) -> None:
    """Affiche un résumé de la découverte."""
    print(f"\n[DISCOVERY] Fichiers HTML découverts: {result.total_count}")
    print("-" * 60)
    
    for category, files in sorted(result.by_category.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {category.value:<20} {len(files):>3} fichier(s)")
    
    if result.aliases:
        print(f"\n  Alias détectés: {len(result.aliases)}")
        for alias in result.aliases[:5]:
            print(f"    - {alias.filename[:50]} (alias de {alias.alias_of})")
        if len(result.aliases) > 5:
            print(f"    ... et {len(result.aliases) - 5} autres")
