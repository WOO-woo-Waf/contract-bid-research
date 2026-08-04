"""Small, deterministic metrics shared by future research experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class BinaryMetrics:
    """Set-based precision, recall, and F1 with explicit counts."""

    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float


def binary_metrics(expected_ids: Iterable[str], predicted_ids: Iterable[str]) -> BinaryMetrics:
    """Score detected risk/requirement IDs against a gold set."""

    expected = set(expected_ids)
    predicted = set(predicted_ids)
    true_positive = len(expected & predicted)
    false_positive = len(predicted - expected)
    false_negative = len(expected - predicted)
    precision = true_positive / len(predicted) if predicted else (1.0 if not expected else 0.0)
    recall = true_positive / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return BinaryMetrics(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def weighted_coverage(requirement_weights: Mapping[str, float], satisfied_ids: Iterable[str]) -> float:
    """Return weighted tender-requirement coverage in the inclusive range [0, 1]."""

    if any(weight < 0 for weight in requirement_weights.values()):
        raise ValueError("requirement weights must be non-negative")
    total = sum(requirement_weights.values())
    if total == 0:
        return 1.0
    satisfied = set(satisfied_ids)
    covered = sum(weight for requirement_id, weight in requirement_weights.items() if requirement_id in satisfied)
    return covered / total


def grounded_claim_rate(claim_ids: Iterable[str], evidence_by_claim: Mapping[str, Iterable[str]]) -> float:
    """Measure the share of output claims carrying at least one source evidence ID."""

    claims = set(claim_ids)
    if not claims:
        return 1.0
    grounded = sum(1 for claim_id in claims if any(evidence_by_claim.get(claim_id, ())))
    return grounded / len(claims)
