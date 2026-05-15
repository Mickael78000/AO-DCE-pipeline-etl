"""Phase VALIDATE - Validation qualité avant export.

Responsabilités :
- Vérifier les références non vides
- Vérifier l'unicité des références
- Vérifier les titres non vides
- Vérifier les source_type
- Calculer le taux de complétude Acheteur_auto
- Lister les lignes incomplètes
- Produire des statistiques exploitables
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set
from collections import Counter


@dataclass
class ValidationIssue:
    """Un problème de validation détecté."""
    row_index: int
    severity: str  # 'error', 'warning'
    field: str
    message: str
    reference: str = ""


@dataclass
class ValidationStats:
    """Statistiques de validation."""
    total_rows: int = 0
    unique_references: int = 0
    duplicate_references: int = 0
    empty_references: int = 0
    empty_titles: int = 0
    empty_source_type: int = 0
    buyer_filled: int = 0
    buyer_empty: int = 0
    buyer_completion_rate: float = 0.0


@dataclass
class ValidationResult:
    """Résultat de la phase validate."""
    is_valid: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    stats: ValidationStats = field(default_factory=ValidationStats)
    
    # Détail par catégorie
    new_rows_with_issues: List[Dict] = field(default_factory=list)
    
    def has_errors(self) -> bool:
        """Retourne True si des erreurs bloquantes existent."""
        return any(i.severity == 'error' for i in self.issues)
    
    def has_warnings(self) -> bool:
        """Retourne True si des warnings existent."""
        return any(i.severity == 'warning' for i in self.issues)


def validate_rows(rows: List[Dict], 
                  new_rows_only: bool = False) -> ValidationResult:
    """Valide les lignes CSV avant export.
    
    Args:
        rows: Lignes CSV à valider
        new_rows_only: Si True, ne valider que les lignes match_status='new'
        
    Returns:
        ValidationResult avec issues et stats
    """
    result = ValidationResult()
    
    # Filtrer si demandé
    if new_rows_only:
        rows_to_validate = [r for r in rows if r.get('match_status') == 'new']
    else:
        rows_to_validate = rows
    
    result.stats.total_rows = len(rows_to_validate)
    
    # 1. Vérifier les références
    refs = [r.get('Référence', '').strip() for r in rows_to_validate]
    ref_counts = Counter(refs)
    
    # Références vides
    empty_refs = [r for r in rows_to_validate if not r.get('Référence') or r['Référence'] == '-']
    result.stats.empty_references = len(empty_refs)
    for idx, row in enumerate(rows_to_validate):
        if not row.get('Référence') or row['Référence'] == '-':
            result.issues.append(ValidationIssue(
                row_index=idx,
                severity='error',
                field='Référence',
                message='Référence vide',
                reference='(vide)'
            ))
            result.is_valid = False
    
    # Références dupliquées
    dup_refs = [ref for ref, count in ref_counts.items() if count > 1 and ref and ref != '-']
    result.stats.duplicate_references = len(dup_refs)
    
    for ref in dup_refs:
        indices = [i for i, r in enumerate(rows_to_validate) if r.get('Référence') == ref]
        for idx in indices:
            result.issues.append(ValidationIssue(
                row_index=idx,
                severity='error',
                field='Référence',
                message=f'Référence dupliquée ({ref_counts[ref]} occurrences)',
                reference=ref
            ))
        result.is_valid = False
    
    result.stats.unique_references = len(set(refs)) - (1 if '' in refs or '-' in refs else 0)
    
    # 2. Vérifier les titres
    empty_titles = [r for r in rows_to_validate 
                   if not r.get('Intitulé synthétique') or r['Intitulé synthétique'] == '-']
    result.stats.empty_titles = len(empty_titles)
    
    for idx, row in enumerate(rows_to_validate):
        if not row.get('Intitulé synthétique') or row['Intitulé synthétique'] == '-':
            result.issues.append(ValidationIssue(
                row_index=idx,
                severity='warning',
                field='Intitulé synthétique',
                message='Titre vide',
                reference=row.get('Référence', '?')
            ))
    
    # 3. Vérifier les source_type
    empty_st = [r for r in rows_to_validate 
               if not r.get('source_type') or r['source_type'] == '-']
    result.stats.empty_source_type = len(empty_st)
    
    # 4. Statistiques Acheteur
    buyer_filled = [r for r in rows_to_validate 
                   if r.get('Acheteur_auto') and r['Acheteur_auto'] != '-']
    result.stats.buyer_filled = len(buyer_filled)
    result.stats.buyer_empty = len(rows_to_validate) - len(buyer_filled)
    
    if rows_to_validate:
        result.stats.buyer_completion_rate = len(buyer_filled) / len(rows_to_validate) * 100
    
    # Lister les nouvelles lignes avec problèmes
    for row in rows_to_validate:
        if row.get('match_status') == 'new':
            has_issue = (
                not row.get('Acheteur_auto') or row['Acheteur_auto'] == '-' or
                not row.get('Intitulé synthétique') or row['Intitulé synthétique'] == '-'
            )
            if has_issue:
                result.new_rows_with_issues.append(row)
    
    return result


def print_validation_summary(result: ValidationResult) -> None:
    """Affiche un résumé de la validation."""
    print(f"\n[VALIDATE] Validation qualité")
    print("-" * 60)
    
    stats = result.stats
    
    # Stats générales
    print(f"  Lignes validées:        {stats.total_rows:>3}")
    print(f"  Références uniques:     {stats.unique_references:>3}")
    
    # Problèmes critiques
    if stats.empty_references > 0:
        print(f"  ✗ Références vides:     {stats.empty_references:>3}")
    else:
        print(f"  ✓ Références vides:     {stats.empty_references:>3}")
    
    if stats.duplicate_references > 0:
        print(f"  ✗ Doublons référence:   {stats.duplicate_references:>3}")
    else:
        print(f"  ✓ Doublons référence:   {stats.duplicate_references:>3}")
    
    if stats.empty_titles > 0:
        print(f"  ⚠ Titres vides:         {stats.empty_titles:>3}")
    else:
        print(f"  ✓ Titres vides:         {stats.empty_titles:>3}")
    
    # Acheteur
    print(f"\n  Acheteur_auto:")
    print(f"    Renseigné:   {stats.buyer_filled:>3} ({stats.buyer_completion_rate:.1f}%)")
    print(f"    Vide:        {stats.buyer_empty:>3}")
    
    # Conclusion
    print(f"\n  Statut: {'✓ VALIDÉ' if result.is_valid else '✗ ERREURS BLOQUANTES'}")
    
    # Nouvelles lignes avec problèmes
    if result.new_rows_with_issues:
        print(f"\n  ⚠ {len(result.new_rows_with_issues)} nouvelles lignes avec problèmes:")
        for row in result.new_rows_with_issues[:5]:
            ref = row.get('Référence', '?')[:25]
            title = row.get('Intitulé synthétique', '?')[:20]
            buyer = row.get('Acheteur_auto', '?')[:15]
            print(f"    - {ref:<25} T:{title:<20} A:{buyer}")
        if len(result.new_rows_with_issues) > 5:
            print(f"    ... et {len(result.new_rows_with_issues) - 5} autres")
