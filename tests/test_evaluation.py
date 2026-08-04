from contract_bid_research.evaluation import binary_metrics, grounded_claim_rate, weighted_coverage


def test_binary_metrics_counts_false_positives_and_false_negatives() -> None:
    result = binary_metrics({"r1", "r2", "r3"}, {"r2", "r3", "r4"})

    assert result.true_positive == 2
    assert result.false_positive == 1
    assert result.false_negative == 1
    assert result.precision == 2 / 3
    assert result.recall == 2 / 3
    assert result.f1 == 2 / 3


def test_weighted_coverage_emphasizes_rejection_requirements() -> None:
    weights = {"ordinary": 1.0, "scored": 3.0, "rejection": 10.0}

    assert weighted_coverage(weights, {"ordinary", "rejection"}) == 11 / 14


def test_grounded_claim_rate_requires_evidence() -> None:
    rate = grounded_claim_rate(
        {"c1", "c2", "c3"},
        {"c1": ["doc:1#p3"], "c2": [], "c3": ["doc:2#p8", "rule:7"]},
    )

    assert rate == 2 / 3
