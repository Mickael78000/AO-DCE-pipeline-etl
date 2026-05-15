"""Phase RECONCILE - Réconciliation avec le CSV existant.

Responsabilités :
- Charger le CSV existant
- Associer les fichiers découverts aux entrées CSV existantes
- Identifier les nouveaux marchés
- Détecter les collisions et doublons
- Classer chaque fichier selon son statut de réconciliation
"""

import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum, auto

from .discovery import DiscoveredFile, FileCategory


class ReconciliationStatus(Enum):
    """Statut de réconciliation d'un fichier avec le CSV."""
    MATCHED = auto()           # Fichier lié à une entrée existante
    NEW_MARKET = auto()        # Nouveau marché, pas dans le CSV
    ORPHAN = auto()            # Fichier sans correspondance CSV
    ALIAS = auto()             # Alias d'un marché existant
    COLLISION = auto()         # Conflit de référence
    IGNORED = auto()           # Fichier ignoré (technique, etc.)


@dataclass
class ReconciledItem:
    """Un fichier réconcilié avec son statut et données associées."""
    discovered: DiscoveredFile
    status: ReconciliationStatus
    csv_row: Optional[Dict] = None  # Ligne CSV existante si applicable
    csv_row_index: Optional[int] = None
    extracted_data: Optional[Dict] = None  # Données extraites
    
    @property
    def reference(self) -> str:
        """Retourne la référence (extraite ou CSV)."""
        if self.csv_row and self.csv_row.get('Référence'):
            return self.csv_row['Référence']
        return self.discovered.reference_derived
    
    @property
    def needs_extraction(self) -> bool:
        """Retourne True si on doit extraire les données de ce fichier."""
        return self.status in (ReconciliationStatus.NEW_MARKET, 
                               ReconciliationStatus.ORPHAN,
                               ReconciliationStatus.MATCHED)


@dataclass
class ReconciliationResult:
    """Résultat de la phase reconcile."""
    items: List[ReconciledItem] = field(default_factory=list)
    by_status: Dict[ReconciliationStatus, List[ReconciledItem]] = field(default_factory=dict)
    csv_rows: List[Dict] = field(default_factory=list)
    csv_fieldnames: List[str] = field(default_factory=list)
    reference_to_items: Dict[str, List[ReconciledItem]] = field(default_factory=dict)
    
    def get_by_status(self, status: ReconciliationStatus) -> List[ReconciledItem]:
        """Retourne les items d'un statut donné."""
        return self.by_status.get(status, [])
    
    @property
    def new_markets(self) -> List[ReconciledItem]:
        """Retourne les nouveaux marchés à ajouter."""
        return self.get_by_status(ReconciliationStatus.NEW_MARKET)
    
    @property
    def orphans(self) -> List[ReconciledItem]:
        """Retourne les orphelins."""
        return self.get_by_status(ReconciliationStatus.ORPHAN)
    
    @property
    def collisions(self) -> List[ReconciledItem]:
        """Retourne les collisions."""
        return self.get_by_status(ReconciliationStatus.COLLISION)


def load_csv(csv_path: Path) -> tuple[List[Dict], List[str]]:
    """Charge le CSV existant."""
    if not csv_path.exists():
        return [], []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        rows = [dict(row) for row in reader]
    
    return rows, fieldnames


def find_csv_row_by_reference(rows: List[Dict], reference: str) -> tuple[Optional[Dict], Optional[int]]:
    """Trouve une ligne CSV par référence.
    
    Returns:
        (row, index) ou (None, None)
    """
    for idx, row in enumerate(rows):
        csv_ref = row.get('Référence', '').strip()
        match_source = row.get('match_source', '').strip()
        
        # Match par référence exacte
        if csv_ref == reference:
            return row, idx
        
        # Match par nom de fichier
        if match_source and match_source.replace('.html', '') == reference.replace('.html', ''):
            return row, idx
        
        # Match pour Marchés Online (MO-XXXX ↔ ao-XXXX)
        if reference.startswith('MO-') and match_source.startswith('ao-'):
            mo_id = reference[3:]
            if f'ao-{mo_id}' in match_source:
                return row, idx
    
    return None, None


def find_csv_row_by_match_source(rows: List[Dict], filename: str) -> tuple[Optional[Dict], Optional[int]]:
    """Trouve une ligne CSV par match_source (nom de fichier)."""
    for idx, row in enumerate(rows):
        if row.get('match_source', '').strip() == filename:
            return row, idx
    return None, None


def reconcile(discovered_files: List[DiscoveredFile], 
              csv_rows: List[Dict],
              csv_fieldnames: List[str]) -> ReconciliationResult:
    """Réconcilie les fichiers découverts avec le CSV existant.
    
    Args:
        discovered_files: Liste des fichiers découverts
        csv_rows: Lignes du CSV existant
        csv_fieldnames: Noms des colonnes CSV
        
    Returns:
        ReconciliationResult avec tous les items classés
    """
    result = ReconciliationResult(
        csv_rows=csv_rows,
        csv_fieldnames=csv_fieldnames
    )
    
    # Indexer les références CSV pour détecter les doublons
    csv_refs: Dict[str, List[int]] = {}
    for idx, row in enumerate(csv_rows):
        ref = row.get('Référence', '').strip()
        if ref:
            if ref not in csv_refs:
                csv_refs[ref] = []
            csv_refs[ref].append(idx)
    
    # Réconcilier chaque fichier découvert
    for discovered in discovered_files:
        # 1. Chercher par match_source exact
        csv_row, csv_idx = find_csv_row_by_match_source(csv_rows, discovered.filename)
        
        # 2. Si pas trouvé, chercher par référence dérivée
        if not csv_row:
            csv_row, csv_idx = find_csv_row_by_reference(csv_rows, discovered.reference_derived)
        
        # 3. Déterminer le statut
        if discovered.is_alias:
            status = ReconciliationStatus.ALIAS
        elif csv_row:
            status = ReconciliationStatus.MATCHED
        else:
            # Vérifier si c'est vraiment un nouveau marché ou un orphelin
            # Un nouveau marché a une référence qui n'existe pas dans le CSV du tout
            ref_exists = discovered.reference_derived in csv_refs
            if ref_exists:
                status = ReconciliationStatus.COLLISION
            else:
                status = ReconciliationStatus.NEW_MARKET
        
        # Créer l'item réconcilié
        item = ReconciledItem(
            discovered=discovered,
            status=status,
            csv_row=csv_row,
            csv_row_index=csv_idx
        )
        
        result.items.append(item)
        
        # Classer par statut
        if status not in result.by_status:
            result.by_status[status] = []
        result.by_status[status].append(item)
        
        # Indexer par référence
        ref = item.reference
        if ref not in result.reference_to_items:
            result.reference_to_items[ref] = []
        result.reference_to_items[ref].append(item)
    
    # Détecter les CSV entries sans fichier (unmatched CSV rows)
    matched_csv_indices = set()
    for item in result.items:
        if item.csv_row_index is not None:
            matched_csv_indices.add(item.csv_row_index)
    
    unmatched_csv = [idx for idx in range(len(csv_rows)) if idx not in matched_csv_indices]
    # Ces lignes sont préservées dans csv_rows mais marquées comme unmatched
    
    return result


def print_reconciliation_summary(result: ReconciliationResult) -> None:
    """Affiche un résumé de la réconciliation."""
    print(f"\n[RECONCILE] Réconciliation effectuée")
    print("-" * 60)
    
    total = len(result.items)
    
    for status in ReconciliationStatus:
        items = result.get_by_status(status)
        if items:
            pct = len(items) / total * 100 if total else 0
            print(f"  {status.name:<15} {len(items):>3} ({pct:>5.1f}%)")
    
    print(f"\n  Total fichiers: {total}")
    print(f"  Lignes CSV existantes: {len(result.csv_rows)}")
    
    # Alertes
    collisions = result.collisions
    if collisions:
        print(f"\n  ⚠ COLLISIONS détectées: {len(collisions)}")
        for item in collisions[:3]:
            print(f"    - {item.discovered.filename[:40]} → référence {item.reference}")
    
    new_markets = result.new_markets
    if new_markets:
        print(f"\n  ✓ Nouveaux marchés à ajouter: {len(new_markets)}")
