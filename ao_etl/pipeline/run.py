"""Pipeline principal ETL unifié - Orchestration complète.

Séquence canonique :
  DISCOVERY → RECONCILE → EXTRACT → MERGE → VALIDATE → EXPORT
  → [CONSOLIDATE] → [CLASSIFY_BUYERS]

Les phases 7 (CONSOLIDATE) et 8 (CLASSIFY_BUYERS) sont optionnelles
et désactivées par défaut.

Usage:
    from ao_etl.pipeline import run_pipeline, PipelineResult
    from ao_etl.pipeline.consolidate import ConsolidationConfig
    from ao_etl.classification import BuyerClassificationConfig

    result = run_pipeline(
        html_dir=Path('html_ao'),
        input_csv=Path('AO.csv'),
        output_csv=Path('AO-final.csv'),
        report_path=Path('report.json'),
        consolidation_config=ConsolidationConfig(enabled=True, backend='openai'),
        buyer_classification_config=BuyerClassificationConfig(enabled=True),
    )
"""

import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime

# Imports du nouveau pipeline
from .discovery import discover_files, print_discovery_summary
from .reconcile import reconcile, load_csv, print_reconciliation_summary
from .merge import merge, print_merge_summary
from .validate import validate_rows, print_validation_summary
from .export import (
    export_csv, export_json_report, generate_report, print_export_summary
)
from .consolidate import (
    ConsolidationConfig, run_consolidation, print_consolidation_summary
)
from ao_etl.classification import (
    BuyerClassificationConfig, run_buyer_classification, print_classification_summary
)
from .enrich_descriptif_phase import (
    EnrichDescriptifConfig, run_enrich_descriptif_phase, print_enrich_descriptif_summary
)
from .enrich_txt_phase import (
    EnrichTxtConfig, run_enrich_txt_phase, print_enrich_txt_summary
)
from .enrich_llm_phase import (
    EnrichLLMConfig, run_enrich_llm_phase, print_enrich_llm_summary
)
from ao_etl.llm.backend import LLMDisabledError
from .normalize_final_phase import (
    NormalizeConfig, run_normalize_phase, print_normalize_summary
)
from .enrich_url_phase import (
    EnrichUrlConfig, run_enrich_url_phase, print_enrich_url_summary
)
from .enrich_juridique import (
    EnrichJuridiqueConfig, run_enrich_juridique, print_enrich_summary
)
from .excel_export import (
    ExcelExportConfig, run_excel_export, print_excel_summary
)

# Imports des extracteurs
from ao_etl.sources.router import extract_for_source
from ao_etl.models.market import MarketData

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Résultat complet de l'exécution du pipeline."""
    success: bool
    output_csv: Path
    output_report: Path
    total_rows: int
    new_rows: int
    validation_passed: bool
    consolidated_csv: Optional[Path] = None
    consolidation_stats: Optional[Dict] = None
    classification_csv: Optional[Path] = None
    classification_stats: Optional[Dict] = None
    enrich_descriptif_csv: Optional[Path] = None
    enrich_descriptif_stats: Optional[Dict] = None
    enrich_txt_csv: Optional[Path] = None
    enrich_txt_stats: Optional[Dict] = None
    enrich_llm_csv: Optional[Path] = None
    enrich_llm_stats: Optional[Dict] = None
    normalize_csv: Optional[Path] = None
    normalize_stats: Optional[Dict] = None
    url_csv: Optional[Path] = None
    url_stats: Optional[Dict] = None
    juridique_csv: Optional[Path] = None
    juridique_stats: Optional[Dict] = None
    excel_output: Optional[Path] = None
    excel_stats: Optional[Dict] = None


def run_pipeline(
    html_dir: Path,
    input_csv: Path,
    output_csv: Path,
    report_path: Optional[Path] = None,
    verbose: bool = True,
    consolidation_config: Optional[ConsolidationConfig] = None,
    buyer_classification_config: Optional[BuyerClassificationConfig] = None,
    enrich_descriptif_config: Optional[EnrichDescriptifConfig] = None,
    enrich_txt_config: Optional[EnrichTxtConfig] = None,
    enrich_llm_config: Optional[EnrichLLMConfig] = None,
    normalize_config: Optional[NormalizeConfig] = None,
    url_config: Optional[EnrichUrlConfig] = None,
    enrich_juridique_config: Optional[EnrichJuridiqueConfig] = None,
    excel_export_config: Optional[ExcelExportConfig] = None,
) -> PipelineResult:
    """Exécute le pipeline ETL complet.
    
    Args:
        html_dir: Répertoire contenant les fichiers HTML
        input_csv: Fichier CSV d'entrée (peut ne pas exister)
        output_csv: Fichier CSV de sortie
        report_path: Fichier de rapport JSON (optionnel)
        verbose: Afficher les logs détaillés
        
    Returns:
        PipelineResult avec le statut de l'exécution
    """
    print("=" * 70)
    print("PIPELINE ETL AO-DCE - Exécution unifiée")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"HTML dir: {html_dir}")
    print(f"Input CSV: {input_csv}")
    print(f"Output CSV: {output_csv}")
    
    # =====================================================================
    # PHASE 1: DISCOVERY
    # =====================================================================
    log.info("[1/6] DISCOVERY - Découverte des fichiers HTML")
    
    try:
        discovery_result = discover_files(html_dir)
        if verbose:
            print_discovery_summary(discovery_result)
    except FileNotFoundError as e:
        log.error(f"Échec discovery: {e}")
        return PipelineResult(
            success=False,
            output_csv=output_csv,
            output_report=report_path or Path(""),
            total_rows=0,
            new_rows=0,
            validation_passed=False
        )
    
    if discovery_result.total_count == 0:
        log.warning("Aucun fichier HTML trouvé")
        return PipelineResult(
            success=False,
            output_csv=output_csv,
            output_report=report_path or Path(""),
            total_rows=0,
            new_rows=0,
            validation_passed=False
        )
    
    # =====================================================================
    # PHASE 2: RECONCILE
    # =====================================================================
    log.info("[2/6] RECONCILE - Réconciliation avec CSV existant")
    
    # Charger le CSV existant (ou créer une structure vide)
    csv_rows, fieldnames = load_csv(input_csv)
    
    reconcile_result = reconcile(
        discovered_files=discovery_result.all_files,
        csv_rows=csv_rows,
        csv_fieldnames=fieldnames
    )
    
    if verbose:
        print_reconciliation_summary(reconcile_result)
    
    # =====================================================================
    # PHASE 3: EXTRACT (pour les nouveaux marchés et mises à jour)
    # =====================================================================
    log.info("[3/6] EXTRACT - Extraction des données")
    
    extracted_data_map: Dict = {}
    extraction_errors = []
    
    # Extraire les données pour les items qui en ont besoin
    items_to_extract = [
        item for item in reconcile_result.items
        if item.needs_extraction
    ]
    
    log.info(f"Extraction de {len(items_to_extract)} fichiers...")
    
    for idx, item in enumerate(items_to_extract, 1):
        try:
            data = extract_for_source(item.discovered.path)
            extracted_data_map[item.discovered.filename] = data  # Utiliser filename comme clé
            
            if verbose and idx <= 5:  # Logguer les 5 premiers
                log.info(f"  [{idx}/{len(items_to_extract)}] {item.discovered.filename[:40]:<40} → {data.buyer[:30] if data.buyer else '(pas acheteur)'}")
                
        except Exception as e:
            extraction_errors.append({
                'file': item.discovered.filename,
                'error': str(e)
            })
            log.warning(f"  [{idx}/{len(items_to_extract)}] {item.discovered.filename[:40]:<40} → ERREUR: {e}")
    
    if extraction_errors:
        log.warning(f"{len(extraction_errors)} erreurs d'extraction")
    
    # =====================================================================
    # PHASE 4: MERGE
    # =====================================================================
    log.info("[4/6] MERGE - Fusion et mise à jour")
    
    merge_result = merge(
        result=reconcile_result,
        extracted_data_map=extracted_data_map
    )
    
    if verbose:
        print_merge_summary(merge_result)
    
    # =====================================================================
    # PHASE 5: VALIDATE
    # =====================================================================
    log.info("[5/6] VALIDATE - Validation qualité")
    
    # Valider toutes les lignes
    validation_result = validate_rows(merge_result.final_rows, new_rows_only=False)
    
    if verbose:
        print_validation_summary(validation_result)
    
    # Bloquer si erreurs critiques ?
    if not validation_result.is_valid:
        log.error("Validation échouée - erreurs bloquantes détectées")
        # On continue quand même pour générer le rapport
    
    # =====================================================================
    # PHASE 6: EXPORT
    # =====================================================================
    log.info("[6/6] EXPORT - Export des fichiers")
    
    # Export CSV
    export_csv(
        rows=merge_result.final_rows,
        fieldnames=merge_result.fieldnames,
        output_path=output_csv
    )
    
    # Générer rapport
    report = generate_report(
        discovery=discovery_result,
        reconcile=reconcile_result,
        merge=merge_result,
        validate=validation_result,
        output_csv_path=output_csv,
        output_report_path=report_path or output_csv.with_suffix('.json')
    )
    
    # Export rapport JSON
    if report_path:
        export_json_report(report, report_path)
    else:
        export_json_report(report, output_csv.with_suffix('.json'))
    
    if verbose:
        print_export_summary(report)
    
    # =====================================================================
    # PHASE 7 (optionnelle): ENRICH_TXT - Enrichissement depuis fichiers .txt
    # =====================================================================
    enrich_txt_csv: Optional[Path] = None
    enrich_txt_stats: Optional[Dict] = None
    
    if enrich_txt_config and enrich_txt_config.enabled:
        log.info("[7] ENRICH_TXT - Enrichissement depuis les fichiers .txt")
        try:
            _enrich_txt_output = (
                enrich_txt_config.output_csv
                or output_csv.parent / "final-v4-complete-enriched.csv"
            )
            
            enrich_txt_stats = run_enrich_txt_phase(
                input_csv=output_csv,
                html_dir=html_dir,
                output_csv=_enrich_txt_output,
            )
            enrich_txt_csv = _enrich_txt_output
            
            if verbose:
                print_enrich_txt_summary(enrich_txt_stats)
                
        except Exception as e:
            log.error("Phase 7 (enrich txt) échouée (pipeline non bloqué): %s", e)
    
    # Déterminer le CSV d'entrée pour les phases suivantes
    _next_input_csv = enrich_txt_csv or output_csv
    
    # =====================================================================
    # PHASE 7b (optionnelle): ENRICH_LLM - Complément via LLM
    # =====================================================================
    enrich_llm_csv: Optional[Path] = None
    enrich_llm_stats: Optional[Dict] = None
    
    if enrich_llm_config and enrich_llm_config.enabled:
        log.info("[7b] ENRICH_LLM - Complément des informations manquantes via LLM")
        try:
            _enrich_llm_output = (
                enrich_llm_config.output_csv
                or output_csv.parent / "final-v4-enriched.csv"
            )
            
            enrich_llm_stats = run_enrich_llm_phase(
                input_csv=_next_input_csv,
                html_dir=html_dir,
                output_csv=_enrich_llm_output,
                config=enrich_llm_config,
            )
            enrich_llm_csv = _enrich_llm_output
            
            if verbose:
                print_enrich_llm_summary(enrich_llm_stats)

        except LLMDisabledError:
            raise
        except Exception as e:
            log.error("Phase 7b (enrich LLM) échouée (pipeline non bloqué): %s", e)
    
    # Mettre à jour le prochain input
    if enrich_llm_csv:
        _next_input_csv = enrich_llm_csv
    
    # =====================================================================
    # PHASE 7c (optionnelle): NORMALIZE - Mapping canonique final
    # =====================================================================
    normalize_csv: Optional[Path] = None
    normalize_stats: Optional[Dict] = None
    
    if normalize_config and normalize_config.enabled:
        log.info("[7c] NORMALIZE - Mapping canonique des champs")
        try:
            _normalize_output = (
                normalize_config.output_csv
                or output_csv.parent / "final-v4-normalized.csv"
            )
            
            normalize_stats = run_normalize_phase(
                input_csv=_next_input_csv,
                output_csv=_normalize_output,
            )
            normalize_csv = _normalize_output
            
            if verbose:
                print_normalize_summary(normalize_stats)
                
        except Exception as e:
            log.error("Phase 7c (normalize) échouée (pipeline non bloqué): %s", e)
    
    # Mettre à jour le prochain input
    if normalize_csv:
        _next_input_csv = normalize_csv
    
    # =====================================================================
    # PHASE 7d (optionnelle): ENRICH_URL - Reconstruction des URLs
    # =====================================================================
    url_csv: Optional[Path] = None
    url_stats: Optional[Dict] = None
    
    if url_config and url_config.enabled:
        log.info("[7d] ENRICH_URL - Reconstruction des URLs depuis match_source")
        try:
            _url_output = (
                url_config.output_csv
                or output_csv.parent / "final-v4-with-urls.csv"
            )
            
            url_stats = run_enrich_url_phase(
                input_csv=_next_input_csv,
                output_csv=_url_output,
            )
            url_csv = _url_output
            
            if verbose:
                print_enrich_url_summary(url_stats)
                
        except Exception as e:
            log.error("Phase 7d (enrich URL) échouée (pipeline non bloqué): %s", e)
    
    # Mettre à jour le prochain input
    if url_csv:
        _next_input_csv = url_csv
    
    # =====================================================================
    # PHASE 7e (optionnelle, legacy): ENRICH_DESCRIPTIF (HTML parsing)
    # =====================================================================
    enrich_descriptif_csv: Optional[Path] = None
    enrich_descriptif_stats: Optional[Dict] = None
    
    if enrich_descriptif_config and enrich_descriptif_config.enabled:
        log.info("[7e] ENRICH_DESCRIPTIF (legacy) - Enrichissement depuis HTML")
        try:
            _enrich_output = (
                enrich_descriptif_config.output_csv
                or output_csv.parent / "final-v4-enriched-legacy.csv"
            )
            
            enrich_descriptif_stats = run_enrich_descriptif_phase(
                input_csv=_next_input_csv,
                html_dir=html_dir,
                output_csv=_enrich_output,
            )
            enrich_descriptif_csv = _enrich_output
            
            if verbose:
                print_enrich_descriptif_summary(enrich_descriptif_stats)
                
        except Exception as e:
            log.error("Phase 7e (enrich descriptif) échouée (pipeline non bloqué): %s", e)
    
    # =====================================================================
    # PHASE 8 (optionnelle): CONSOLIDATE
    # =====================================================================
    consolidated_csv: Optional[Path] = None
    consolidation_stats: Optional[Dict] = None

    if consolidation_config and consolidation_config.enabled:
        log.info("[8] CONSOLIDATE - Consolidation LLM des champs métier")
        try:
            _consolidated_output = (
                consolidation_config.output_csv
                or output_csv.parent / "final-v3-consolidated.csv"
            )
            _json_dir = consolidation_config.json_dir

            consolidation_stats = run_consolidation(
                input_csv=_next_input_csv,
                html_dir=html_dir,
                output_csv=_consolidated_output,
                config=consolidation_config,
                json_dir=_json_dir,
            )
            consolidated_csv = _consolidated_output

            if verbose:
                print_consolidation_summary(consolidation_stats)

        except LLMDisabledError:
            raise
        except EnvironmentError as e:
            log.error("Phase 8 annulée - configuration LLM manquante: %s", e)
        except Exception as e:
            log.error("Phase 8 échouée (pipeline non bloqué): %s", e)

    # =====================================================================
    # PHASE 9 (optionnelle): CLASSIFY_BUYERS
    # =====================================================================
    classification_csv: Optional[Path] = None
    classification_stats: Optional[Dict] = None

    # Déterminer le CSV d'entrée : consolidé > enrichi > export brut
    _classify_input = consolidated_csv or _next_input_csv

    if buyer_classification_config and buyer_classification_config.enabled:
        log.info("[9] CLASSIFY_BUYERS - Classification des acheteurs")
        try:
            classification_stats = run_buyer_classification(
                consolidated_csv=_classify_input,
                config=buyer_classification_config,
            )
            classification_csv = Path(classification_stats.get("output_csv", ""))

            if verbose:
                print_classification_summary(classification_stats)

        except Exception as e:
            log.error("Phase 8 échouée (pipeline non bloqué): %s", e)

    # =====================================================================
    # PHASE 10 (optionnelle): ENRICH_JURIDIQUE
    # =====================================================================
    juridique_csv: Optional[Path] = None
    juridique_stats: Optional[Dict] = None

    # Déterminer le CSV d'entrée : classification > consolidé > enrichi > export
    _enrich_input = classification_csv or consolidated_csv or _next_input_csv

    if enrich_juridique_config and enrich_juridique_config.enabled:
        log.info("[10] ENRICH_JURIDIQUE - Enrichissement juridique (regex)")
        try:
            _juridique_output = (
                enrich_juridique_config.output_csv
                or output_csv.parent / "final-v4-juridique.csv"
            )

            juridique_stats = run_enrich_juridique(
                input_csv=_enrich_input,
                output_csv=_juridique_output,
            )
            juridique_csv = _juridique_output

            if verbose:
                print_enrich_summary(juridique_stats)

        except Exception as e:
            log.error("Phase 9 échouée (pipeline non bloqué): %s", e)

    # =====================================================================
    # PHASE 10 (optionnelle): EXCEL_EXPORT
    # =====================================================================
    excel_output: Optional[Path] = None
    excel_stats: Optional[Dict] = None

    # Déterminer le CSV d'entrée : juridique si disponible, sinon classification/consolidé/export
    _excel_input = juridique_csv or classification_csv or consolidated_csv or output_csv

    if excel_export_config and excel_export_config.enabled:
        log.info("[10] EXCEL_EXPORT - Export Excel formaté")
        try:
            _excel_output = (
                excel_export_config.output_excel
                or output_csv.parent / "final-v4-juridique.xlsx"
            )

            excel_stats = run_excel_export(
                input_csv=_excel_input,
                output_excel=_excel_output,
            )
            excel_output = _excel_output

            if verbose:
                print_excel_summary(excel_stats)

        except Exception as e:
            log.error("Phase 10 échouée (pipeline non bloqué): %s", e)

    # =====================================================================
    # RÉSULTAT
    # =====================================================================
    print("=" * 70)
    print("PIPELINE TERMINÉ")
    print("=" * 70)

    return PipelineResult(
        success=validation_result.is_valid,
        output_csv=output_csv,
        output_report=report_path or output_csv.with_suffix('.json'),
        total_rows=len(merge_result.final_rows),
        new_rows=merge_result.new_count,
        validation_passed=validation_result.is_valid,
        consolidated_csv=consolidated_csv,
        consolidation_stats=consolidation_stats,
        classification_csv=classification_csv,
        classification_stats=classification_stats,
        enrich_descriptif_csv=enrich_descriptif_csv,
        enrich_descriptif_stats=enrich_descriptif_stats,
        enrich_txt_csv=enrich_txt_csv,
        enrich_txt_stats=enrich_txt_stats,
        enrich_llm_csv=enrich_llm_csv,
        enrich_llm_stats=enrich_llm_stats,
        normalize_csv=normalize_csv,
        normalize_stats=normalize_stats,
        url_csv=url_csv,
        url_stats=url_stats,
        juridique_csv=juridique_csv,
        juridique_stats=juridique_stats,
        excel_output=excel_output,
        excel_stats=excel_stats,
    )


def run_pipeline_safe(**kwargs) -> PipelineResult:
    """Version du pipeline avec gestion d'exceptions."""
    try:
        return run_pipeline(**kwargs)
    except Exception as e:
        log.exception("Erreur fatale dans le pipeline")
        return PipelineResult(
            success=False,
            output_csv=kwargs.get('output_csv', Path("")),
            output_report=kwargs.get('report_path', Path("")),
            total_rows=0,
            new_rows=0,
            validation_passed=False
        )
