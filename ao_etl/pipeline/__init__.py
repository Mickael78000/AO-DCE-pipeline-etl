"""Pipeline principal ETL unifié pour AO-DCE.

Ce package implémente le pipeline canonique :
  discovery → extract → reconcile → merge → validate → export

Usage:
    from ao_etl.pipeline import run_pipeline
    result = run_pipeline(html_dir=Path('html_ao'), csv_path=Path('AO.csv'))
"""

from .run import run_pipeline, PipelineResult
from .consolidate import ConsolidationConfig
from ao_etl.classification import BuyerClassificationConfig
from .enrich_juridique import EnrichJuridiqueConfig
from .excel_export import ExcelExportConfig

__all__ = [
    'run_pipeline', 'PipelineResult',
    'ConsolidationConfig', 'BuyerClassificationConfig',
    'EnrichJuridiqueConfig', 'ExcelExportConfig',
]
