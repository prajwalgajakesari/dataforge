"""
Normalization module for database schema normalization.

This module provides tools for analyzing and transforming database schemas
to various normal forms (1NF, 2NF, 3NF, BCNF) while preserving data integrity
and functional dependencies.

Available normalizers:
- Normalizer1NF: First Normal Form normalization (removes non-atomic values)
- Normalizer2NF: Second Normal Form normalization (removes partial dependencies)
- Normalizer3NF: Third Normal Form normalization with Bernstein's synthesis

Violation Detection:
- ViolationDetector: Detects normalization violations at all levels

Models:
- ViolationType: Enum of violation types
- SeverityLevel: Enum of violation severity levels
- Violation1NF: Represents a 1NF violation (non-atomic values)
- Violation2NF: Represents a 2NF violation (partial dependency)
- Violation3NF: Represents a 3NF violation (transitive dependency)
- ViolationBCNF: Represents a BCNF violation (non-superkey determinant)
- NormalizationStep1NF: A single step in 1NF normalization
- Normalization1NFResult: Complete result of 1NF normalization
- NormalizationStep2NF: A single step in 2NF normalization
- Normalization2NFResult: Complete result of 2NF normalization
- NormalizationStep3NF: A single step in 3NF normalization
- Normalization3NFResult: Complete result of 3NF normalization
- SchemaDecomposer: Utility for decomposing schemas
- DecompositionResult: Result of decomposition operations
"""

from core.normalization.violations import (
    ViolationType,
    SeverityLevel,
    NFViolation,
    Violation1NF,
    Violation2NF,
    Violation3NF,
    ViolationBCNF,
    ViolationDetector,
)
from core.normalization.decomposer import (
    SchemaDecomposer,
    DecomposedTable,
    DecompositionResult,
)
from core.normalization.normalizer_1nf import (
    Normalizer1NF,
    NormalizationStep1NF,
    Normalization1NFResult,
)
from core.normalization.normalizer_2nf import (
    Normalizer2NF,
    NormalizationStep2NF,
    Normalization2NFResult,
)
from core.normalization.normalizer_3nf import (
    Normalizer3NF,
    NormalizationStep3NF,
    Normalization3NFResult,
)

__all__ = [
    # Violation types and detection
    "ViolationType",
    "SeverityLevel",
    "NFViolation",
    "Violation1NF",
    "Violation2NF",
    "Violation3NF",
    "ViolationBCNF",
    "ViolationDetector",
    # Decomposer
    "SchemaDecomposer",
    "DecomposedTable",
    "DecompositionResult",
    # 1NF Normalizer
    "Normalizer1NF",
    "NormalizationStep1NF",
    "Normalization1NFResult",
    # 2NF Normalizer
    "Normalizer2NF",
    "NormalizationStep2NF",
    "Normalization2NFResult",
    # 3NF Normalizer
    "Normalizer3NF",
    "NormalizationStep3NF",
    "Normalization3NFResult",
]
