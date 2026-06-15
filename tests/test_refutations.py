from __future__ import annotations

import builtins

from app.services.causal_dowhy import estimate_ate
from data.generate_synthetic import make_synthetic_marketing_data

REQUIRED_REFUTATIONS = {"placebo_treatment", "random_common_cause", "data_subset"}


def test_refutation_result_contains_required_keys():
    df = make_synthetic_marketing_data(n=500, seed=456)

    estimate = estimate_ate(
        df=df,
        treatment="coupon",
        outcome="purchase",
        confounders=["age", "income", "prior_spend", "visits"],
        effect_modifiers=["visits"],
    )

    assert estimate.status == "ok"
    assert REQUIRED_REFUTATIONS.issubset(estimate.refutations)
    for key in REQUIRED_REFUTATIONS:
        assert isinstance(estimate.refutations[key], dict)


def test_refutations_fallback_when_dowhy_import_fails(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("dowhy"):
            raise ImportError("blocked dowhy import for fallback test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    df = make_synthetic_marketing_data(n=300, seed=457)

    estimate = estimate_ate(
        df=df,
        treatment="coupon",
        outcome="purchase",
        confounders=["age", "income", "prior_spend", "visits"],
        effect_modifiers=["visits"],
    )

    assert estimate.status == "ok"
    assert estimate.method == "降级线性调整估计"
    assert estimate.warnings
    assert REQUIRED_REFUTATIONS.issubset(estimate.refutations)
