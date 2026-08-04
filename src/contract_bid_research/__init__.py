"""Reusable evaluation primitives for contract and bid research."""

from .evaluation import BinaryMetrics, binary_metrics, grounded_claim_rate, weighted_coverage

__all__ = [
    "BinaryMetrics",
    "binary_metrics",
    "grounded_claim_rate",
    "weighted_coverage",
]
