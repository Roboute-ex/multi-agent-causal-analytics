from __future__ import annotations

from app.services.variable_recommender import parse_recommendation, recommend_variables


class FakeClient:
    def __init__(self, response: str | None = None, exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc

    def create_chat_completion(self, messages):
        if self.exc:
            raise self.exc
        return self.response or "{}"


def test_recommend_variables_skips_without_api_key(monkeypatch):
    from app.services import variable_recommender

    monkeypatch.setattr(variable_recommender.DeepSeekClient, "from_env", lambda: None)

    result = recommend_variables(
        question="优惠券是否提升购买率？",
        columns=["coupon", "purchase", "age"],
    )

    assert result.status == "skipped"
    assert result.treatment is None
    assert result.outcome is None
    assert result.warnings


def test_recommend_variables_parses_valid_json():
    result = recommend_variables(
        question="优惠券是否提升购买率？",
        columns=["coupon", "purchase", "age", "income", "visits"],
        client=FakeClient(
            """
            {
              "treatment": "coupon",
              "outcome": "purchase",
              "confounders": ["age", "income"],
              "effect_modifiers": ["visits"],
              "reason": "coupon is the intervention and purchase is the outcome"
            }
            """
        ),
    )

    assert result.status == "ok"
    assert result.treatment == "coupon"
    assert result.outcome == "purchase"
    assert result.confounders == ["age", "income"]
    assert result.effect_modifiers == ["visits"]
    assert result.reason


def test_invalid_columns_are_filtered_with_warnings():
    result = parse_recommendation(
        """
        {
          "treatment": "coupon",
          "outcome": "purchase",
          "confounders": ["age", "missing_col"],
          "effect_modifiers": ["visits", "unknown_modifier"],
          "reason": "test"
        }
        """,
        columns=["coupon", "purchase", "age", "visits"],
    )

    assert result.status == "ok"
    assert result.confounders == ["age"]
    assert result.effect_modifiers == ["visits"]
    assert any("missing_col" in warning for warning in result.warnings)
    assert any("unknown_modifier" in warning for warning in result.warnings)


def test_invalid_json_returns_fallback_without_exception():
    result = parse_recommendation(
        "treatment=coupon, outcome=purchase",
        columns=["coupon", "purchase"],
    )

    assert result.status == "fallback"
    assert result.treatment is None
    assert result.outcome is None
    assert result.warnings


def test_llm_request_exception_returns_error_without_breaking():
    result = recommend_variables(
        question="优惠券是否提升购买率？",
        columns=["coupon", "purchase", "age"],
        client=FakeClient(exc=RuntimeError("network down")),
    )

    assert result.status == "error"
    assert result.warnings
    assert "network down" in result.warnings[0]


def test_treatment_and_outcome_are_removed_from_other_lists():
    result = parse_recommendation(
        """
        {
          "treatment": "coupon",
          "outcome": "purchase",
          "confounders": ["coupon", "age", "age", "purchase"],
          "effect_modifiers": ["purchase", "visits", "coupon", "visits"],
          "reason": "test"
        }
        """,
        columns=["coupon", "purchase", "age", "visits"],
    )

    assert result.treatment == "coupon"
    assert result.outcome == "purchase"
    assert result.confounders == ["age"]
    assert result.effect_modifiers == ["visits"]
    assert len(result.warnings) >= 4
