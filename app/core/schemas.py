from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    question: str = "优惠券是否提升购买概率？"
    dataset_path: str
    treatment: str
    outcome: str
    confounders: List[str] = Field(default_factory=list)
    effect_modifiers: List[str] = Field(default_factory=list)
    use_llm_report: bool = False
    unit_id: Optional[str] = None


class AgentResult(BaseModel):
    agent: str
    status: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class DataProfile(BaseModel):
    n_rows: int
    n_cols: int
    numeric_columns: List[str]
    categorical_columns: List[str]
    missing_rate: Dict[str, float]
    dtypes: Dict[str, str]
    preview_rows: List[Dict[str, Any]] = Field(default_factory=list)


class MethodRecommendation(BaseModel):
    primary: str
    secondary: str
    assumptions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class EstimationResult(BaseModel):
    status: str
    method: str
    estimand_text: str
    ate: Optional[float] = None
    confidence_intervals: Optional[List[float]] = None
    refutations: Dict[str, Any] = Field(default_factory=dict)
    graph_dot: str = ""
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class CateResult(BaseModel):
    status: str = "skipped"
    method: str = "EconML LinearDML"
    cate_mean: Optional[float] = None
    cate_std: Optional[float] = None
    n_effects: int = 0
    segment_summary: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class ReviewResult(BaseModel):
    status: str
    checks: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class PipelineBundle(BaseModel):
    request: AnalysisRequest
    plan: Dict[str, Any] = Field(default_factory=dict)
    profile: Optional[DataProfile] = None
    method: Optional[MethodRecommendation] = None
    estimate: Optional[EstimationResult] = None
    cate: Optional[CateResult] = None
    review: Optional[ReviewResult] = None
    report_markdown: Optional[str] = None
    agent_logs: List[AgentResult] = Field(default_factory=list)
