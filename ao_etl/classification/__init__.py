"""Module de classification des acheteurs publics.

Fournit la Phase 8 du pipeline ETL :
  DISCOVERY → RECONCILE → EXTRACT → MERGE → VALIDATE → EXPORT
  → [CONSOLIDATE] → [CLASSIFY_BUYERS]
"""

from .buyers import (
    ALLOWED_FONCTION_PUBLIQUE,
    ALLOWED_SOURCE,
    ALLOWED_TYPE_ACHETEUR,
    BuyerClassificationConfig,
    ClassificationInputError,
    ClassificationQAReport,
    REQUIRED_INPUT_COLUMNS,
    classify_buyers_llm_enrichment,
    classify_buyers_rule_based,
    print_classification_summary,
    report_buyer_classification_quality,
    run_buyer_classification,
)

__all__ = [
    "ALLOWED_FONCTION_PUBLIQUE",
    "ALLOWED_SOURCE",
    "ALLOWED_TYPE_ACHETEUR",
    "BuyerClassificationConfig",
    "ClassificationInputError",
    "ClassificationQAReport",
    "REQUIRED_INPUT_COLUMNS",
    "classify_buyers_llm_enrichment",
    "classify_buyers_rule_based",
    "print_classification_summary",
    "report_buyer_classification_quality",
    "run_buyer_classification",
]
