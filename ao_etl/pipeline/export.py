"""Phase EXPORT - Export des sorties et rapports.

Responsabilités :
- Exporter le CSV final
- Générer le rapport JSON avec toutes les statistiques
- Produire un rapport Markdown lisible
- Sauvegarder les métadonnées de l'exécution
"""

import csv
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
from datetime import datetime

from .discovery import DiscoveryResult
from .reconcile import ReconciliationResult
from .merge import MergeResult
from .validate import ValidationResult


@dataclass
class PipelineReport:
    """Rapport complet de l'exécution du pipeline."""
    timestamp: str
    version: str = "2.0.0"
    
    # Discovery
    files_discovered: int = 0
    files_by_category: Dict[str, int] = field(default_factory=dict)
    aliases_found: int = 0
    
    # Reconciliation
    files_matched: int = 0
    new_markets: int = 0
    orphans: int = 0
    collisions: int = 0
    aliases_ignored: int = 0
    
    # Merge
    rows_preserved: int = 0
    rows_updated: int = 0
    rows_added: int = 0
    total_rows: int = 0
    
    # Validation
    validation_passed: bool = True
    unique_references: int = 0
    duplicate_references: int = 0
    buyer_completion_rate: float = 0.0
    new_rows_with_issues: int = 0
    
    # Anomalies
    anomalies: List[Dict] = field(default_factory=list)
    
    # Chemins de sortie
    output_csv: str = ""
    output_report_json: str = ""
    
    def to_dict(self) -> Dict:
        """Convertit le rapport en dictionnaire."""
        return asdict(self)


def export_csv(rows: List[Dict], 
               fieldnames: List[str], 
               output_path: Path) -> None:
    """Exporte les lignes vers un fichier CSV.
    
    Args:
        rows: Lignes à exporter
        fieldnames: Noms des colonnes
        output_path: Chemin du fichier de sortie
    """
    # S'assurer que toutes les lignes ont toutes les colonnes
    for row in rows:
        for field in fieldnames:
            if field not in row:
                row[field] = '-'
    
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def export_json_report(report: PipelineReport, 
                       output_path: Path) -> None:
    """Exporte le rapport au format JSON.
    
    Args:
        report: Rapport à exporter
        output_path: Chemin du fichier JSON
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)


def generate_report(discovery: DiscoveryResult,
                   reconcile: ReconciliationResult,
                   merge: MergeResult,
                   validate: ValidationResult,
                   output_csv_path: Path,
                   output_report_path: Path) -> PipelineReport:
    """Génère le rapport complet du pipeline.
    
    Args:
        discovery: Résultat discovery
        reconcile: Résultat reconcile
        merge: Résultat merge
        validate: Résultat validate
        output_csv_path: Chemin CSV exporté
        output_report_path: Chemin rapport JSON
        
    Returns:
        PipelineReport complet
    """
    report = PipelineReport(
        timestamp=datetime.now().isoformat(),
        output_csv=str(output_csv_path),
        output_report_json=str(output_report_path)
    )
    
    # Discovery stats
    report.files_discovered = discovery.total_count
    report.files_by_category = {
        cat.value: len(files) 
        for cat, files in discovery.by_category.items()
    }
    report.aliases_found = len(discovery.aliases)
    
    # Reconciliation stats
    from .reconcile import ReconciliationStatus
    report.files_matched = len(reconcile.get_by_status(ReconciliationStatus.MATCHED))
    report.new_markets = len(reconcile.get_by_status(ReconciliationStatus.NEW_MARKET))
    report.orphans = len(reconcile.get_by_status(ReconciliationStatus.ORPHAN))
    report.collisions = len(reconcile.get_by_status(ReconciliationStatus.COLLISION))
    report.aliases_ignored = len(reconcile.get_by_status(ReconciliationStatus.ALIAS))
    
    # Merge stats
    report.rows_preserved = merge.preserved_count
    report.rows_updated = merge.updated_count
    report.rows_added = merge.new_count
    report.total_rows = len(merge.final_rows)
    
    # Validation stats
    report.validation_passed = validate.is_valid
    report.unique_references = validate.stats.unique_references
    report.duplicate_references = validate.stats.duplicate_references
    report.buyer_completion_rate = validate.stats.buyer_completion_rate
    report.new_rows_with_issues = len(validate.new_rows_with_issues)
    
    # Anomalies
    for issue in validate.issues:
        if issue.severity == 'error':
            report.anomalies.append({
                'type': 'error',
                'field': issue.field,
                'reference': issue.reference,
                'message': issue.message
            })
    
    return report


def print_export_summary(report: PipelineReport) -> None:
    """Affiche un résumé de l'export."""
    print(f"\n[EXPORT] Export terminé")
    print("=" * 60)
    
    print(f"\n  Fichiers générés:")
    print(f"    CSV:    {report.output_csv}")
    print(f"    Rapport: {report.output_report_json}")
    
    print(f"\n  Résumé pipeline:")
    print(f"    Fichiers découverts:    {report.files_discovered:>3}")
    print(f"    Nouveaux marchés:       {report.new_markets:>3}")
    print(f"    Lignes préservées:      {report.rows_preserved:>3}")
    print(f"    Lignes mises à jour:    {report.rows_updated:>3}")
    print(f"    Lignes ajoutées:        {report.rows_added:>3}")
    print(f"    Total lignes CSV:       {report.total_rows:>3}")
    
    print(f"\n  Qualité:")
    print(f"    Références uniques:     {report.unique_references:>3}")
    print(f"    Doublons:               {report.duplicate_references:>3}")
    print(f"    Taux acheteur:          {report.buyer_completion_rate:>5.1f}%")
    
    if report.anomalies:
        print(f"\n  ⚠ Anomalies: {len(report.anomalies)}")
    else:
        print(f"\n  ✓ Aucune anomalie bloquante")
    
    print("=" * 60)
