"""
Analysis module for DataForge.

This module provides enhanced data profiling and analysis capabilities including:
- Statistical analysis (min, max, mean, median, stddev, percentiles)
- Distribution analysis (histograms, top values, outliers)
- Pattern detection (email, phone, URL, UUID, dates, etc.)
- String analysis (length stats, empty count)
- Data quality scoring (0-100)
"""

from core.analysis.profiler import (
    EnhancedProfiler,
    DatabaseConnector,
    PATTERNS,
)

__all__ = [
    "EnhancedProfiler",
    "DatabaseConnector",
    "PATTERNS",
]
