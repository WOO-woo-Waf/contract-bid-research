"""Reusable document, knowledge, and evaluation infrastructure."""

from .document import CanonicalDocument, CanonicalDocumentBuilder, JsonDocumentRepository
from .evaluation import BinaryMetrics, binary_metrics, grounded_claim_rate, weighted_coverage

__all__ = [
    "BinaryMetrics",
    "CanonicalDocument",
    "CanonicalDocumentBuilder",
    "JsonDocumentRepository",
    "binary_metrics",
    "grounded_claim_rate",
    "weighted_coverage",
]
