"""
Analysis module for DataForge.

This module provides enhanced data profiling and analysis capabilities including:
- Statistical analysis (min, max, mean, median, stddev, percentiles)
- Distribution analysis (histograms, top values, outliers)
- Pattern detection (email, phone, URL, UUID, dates, etc.)
- String analysis (length stats, empty count)
- Data quality scoring (0-100)
- Candidate key discovery and primary key recommendations
- Functional dependency detection for normalization analysis
- Relationship inference (implicit FK detection)
"""

from core.analysis.profiler import (
    EnhancedProfiler,
    DatabaseConnector,
    PATTERNS,
)
from core.analysis.key_finder import (
    CandidateKeyFinder,
    analyze_table_keys,
)
from core.analysis.fd_detector import (
    FunctionalDependencyDetector,
    FDCandidate,
    FDVerificationResult,
)
from core.analysis.pattern_detector import (
    PatternDetector,
    PatternDefinition,
    PATTERN_DEFINITIONS,
    ADDITIONAL_PATTERNS,
    detect_patterns,
    get_best_pattern,
    validate_value,
)
from core.analysis.relationship_inferrer import (
    RelationshipInferrer,
    TableColumn,
    RelationshipCandidate,
)
from core.analysis.type_inference import (
    TypeInferenceEngine,
    TypeSignal,
    TypeInferenceResult,
    NAME_PATTERNS,
    DB_TYPE_MAPPINGS,
    PATTERN_TO_SEMANTIC,
)

__all__ = [
    # Profiler
    "EnhancedProfiler",
    "DatabaseConnector",
    "PATTERNS",
    # Key Finder
    "CandidateKeyFinder",
    "analyze_table_keys",
    # FD Detector
    "FunctionalDependencyDetector",
    "FDCandidate",
    "FDVerificationResult",
    # Pattern Detector
    "PatternDetector",
    "PatternDefinition",
    "PATTERN_DEFINITIONS",
    "ADDITIONAL_PATTERNS",
    "detect_patterns",
    "get_best_pattern",
    "validate_value",
    # Relationship Inferrer
    "RelationshipInferrer",
    "TableColumn",
    "RelationshipCandidate",
    # Type Inference
    "TypeInferenceEngine",
    "TypeSignal",
    "TypeInferenceResult",
    "NAME_PATTERNS",
    "DB_TYPE_MAPPINGS",
    "PATTERN_TO_SEMANTIC",
]
