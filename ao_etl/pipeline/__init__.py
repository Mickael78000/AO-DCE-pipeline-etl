"""Pipeline principal ETL unifié pour AO-DCE.

Ce package implémente le pipeline canonique :
  discovery → extract → reconcile → merge → validate → export

Usage:
    from ao_etl.pipeline import run_pipeline
    result = run_pipeline(html_dir=Path('html_ao'), csv_path=Path('AO.csv'))
"""

from .run import run_pipeline, PipelineResult
from ao_etl.classification import BuyerClassificationConfig
from .enrich_juridique import EnrichJuridiqueConfig
from .excel_export import ExcelExportConfig
from .enrich_txt_phase import EnrichTxtConfig
from .normalize_final_phase import NormalizeConfig
from .enrich_url_phase import EnrichUrlConfig
from .enrich_descriptif_phase import EnrichDescriptifConfig

__all__ = [
    'run_pipeline', 'PipelineResult',
    'BuyerClassificationConfig',
    'EnrichJuridiqueConfig', 'ExcelExportConfig',
    'EnrichTxtConfig', 'EnrichDescriptifConfig',
    'NormalizeConfig', 'EnrichUrlConfig',
]
