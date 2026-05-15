"""Module sources pour extraction HTML - Version 2."""

from .base_v2 import (
    BaseExtractor,
    ExtractionContext,
    ExtractionResult,
    ExtractionTrace,
    FieldCandidate,
)
from .boamp_xml_v2 import BoampExtractor
from .france_marches_v2 import FranceMarchesExtractor
from .marches_online_v2 import MarchesOnlineExtractor
from .place_numeric_v2 import PlaceNumericExtractor
from .router_v2 import (
    build_context,
    detect_source_type,
    extract_from_html,
    get_extractor,
)
from .validation_v2 import (
    is_valid_buyer,
    is_valid_title,
    normalize_text,
    pick_best_candidate,
    score_buyer,
    score_title,
)

__all__ = [
    # Base
    "BaseExtractor",
    "ExtractionContext",
    "ExtractionResult",
    "ExtractionTrace",
    "FieldCandidate",
    # Extracteurs
    "BoampExtractor",
    "FranceMarchesExtractor",
    "MarchesOnlineExtractor",
    "PlaceNumericExtractor",
    # Router
    "build_context",
    "detect_source_type",
    "extract_from_html",
    "get_extractor",
    # Validation
    "is_valid_buyer",
    "is_valid_title",
    "normalize_text",
    "pick_best_candidate",
    "score_buyer",
    "score_title",
]
