"""Utilitaires partagés pour les scripts AO-DCE."""

from .csv_utils import read_csv, write_csv, update_csv_rows
from .paths import get_data_path, get_output_path, get_html_dir, get_project_root, ProjectPaths
from .text import normalize, strip_accents, contains_any, starts_with_any, normalize_keywords

__all__ = [
    # CSV
    'read_csv', 'write_csv', 'update_csv_rows',
    # Paths
    'get_data_path', 'get_output_path', 'get_html_dir', 'get_project_root', 'ProjectPaths',
    # Text
    'normalize', 'strip_accents', 'contains_any', 'starts_with_any', 'normalize_keywords',
]
