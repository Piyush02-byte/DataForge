"""Stable import path for configuration (backed by ``src.utils.config``)."""

from src.utils.config import (
    FILTER_CONFIG,
    MISSING_VALUE_CONFIG,
    PROFILE_CONFIG,
    QUALITY_CONFIG,
    REPORT_CONFIG,
    SCORE_WEIGHTS,
    TYPE_COERCION_CONFIG,
)

__all__ = [
    "FILTER_CONFIG",
    "MISSING_VALUE_CONFIG",
    "PROFILE_CONFIG",
    "QUALITY_CONFIG",
    "REPORT_CONFIG",
    "SCORE_WEIGHTS",
    "TYPE_COERCION_CONFIG",
]
