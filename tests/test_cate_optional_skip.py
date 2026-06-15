from __future__ import annotations

import builtins

from app.core.orchestrator import AnalyticsTeamOrchestrator
from app.core.schemas import AnalysisRequest
from app.services.cate_econml import estimate_cate
from data.generate_synthetic import make_synthetic_marketing_data


def _block_econml_import(monkeypatch) -> None:
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("econml"):
            raise ImportError("blocked econml import for optional dependency test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


def test_cate_skips_when_econml_import_fails(monkeypatch):
    _block_econml_import(monkeypatch)
    df = make_synthetic_marketing_data(n=300, seed=321)

    cate = estimate_cate(
        df=df,
        treatment="coupon",
        outcome="purchase",
        confounders=["age", "income", "prior_spend", "visits"],
        effect_modifiers=["visits"],
    )

    assert cate.status == "skipped"
    assert "EconML" in (cate.error or "")


def test_pipeline_continues_when_econml_import_fails(monkeypatch):
    _block_econml_import(monkeypatch)
    df = make_synthetic_marketing_data(n=300, seed=322)
    request = AnalysisRequest(
        question="优惠券是否提升购买概率？",
        dataset_path="in_memory.csv",
        treatment="coupon",
        outcome="purchase",
        confounders=["age", "income", "prior_spend", "visits"],
        effect_modifiers=["visits"],
    )

    bundle = AnalyticsTeamOrchestrator().run_dataframe(request, df)

    assert bundle.estimate is not None
    assert bundle.estimate.ate is not None
    assert bundle.cate is not None
    assert bundle.cate.status == "skipped"
    assert bundle.report_markdown
