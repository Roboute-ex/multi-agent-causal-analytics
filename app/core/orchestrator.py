from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.agents.team import (
    CausalAgent,
    CoordinatorAgent,
    DataEngineerAgent,
    HeterogeneityAgent,
    ReporterAgent,
    ReviewerAgent,
    StatisticianAgent,
)
from app.agents.llm_reporter import DeepSeekReporterAgent
from app.core.schemas import (
    AnalysisRequest,
    CateResult,
    DataProfile,
    EstimationResult,
    MethodRecommendation,
    PipelineBundle,
    ReviewResult,
)
from app.services.data_loader import read_dataset


class AnalyticsTeamOrchestrator:
    """确定性的 Multi-Agent Causal Analytics Team MVP 编排器。"""

    def __init__(self) -> None:
        self.coordinator = CoordinatorAgent()
        self.data_engineer = DataEngineerAgent()
        self.statistician = StatisticianAgent()
        self.causal = CausalAgent()
        self.heterogeneity = HeterogeneityAgent()
        self.reviewer = ReviewerAgent()
        self.reporter = ReporterAgent()
        self.llm_reporter = DeepSeekReporterAgent()

    def run(self, request: AnalysisRequest | dict) -> PipelineBundle:
        parsed_request = self._coerce_request(request)
        dataset_path = Path(parsed_request.dataset_path)
        df = read_dataset(dataset_path)
        return self.run_dataframe(parsed_request, df)

    def run_dataframe(
        self,
        request: AnalysisRequest | dict,
        df: pd.DataFrame,
    ) -> PipelineBundle:
        parsed_request = self._coerce_request(request)
        bundle = PipelineBundle(request=parsed_request)

        coordinator_result = self.coordinator.run(parsed_request)
        bundle.agent_logs.append(coordinator_result)
        bundle.plan = coordinator_result.payload

        profile_result = self.data_engineer.run(df)
        bundle.agent_logs.append(profile_result)
        bundle.profile = DataProfile(**profile_result.payload)

        method_result = self.statistician.run(parsed_request, bundle.profile)
        bundle.agent_logs.append(method_result)
        bundle.method = MethodRecommendation(**method_result.payload)

        estimate_result = self.causal.run(df, parsed_request)
        bundle.agent_logs.append(estimate_result)
        bundle.estimate = EstimationResult(**estimate_result.payload)

        cate_result = self.heterogeneity.run(df, parsed_request)
        bundle.agent_logs.append(cate_result)
        bundle.cate = CateResult(**cate_result.payload)

        review_result = self.reviewer.run(bundle)
        bundle.agent_logs.append(review_result)
        bundle.review = ReviewResult(**review_result.payload)

        report_result = self.reporter.run(bundle)
        bundle.agent_logs.append(report_result)
        bundle.report_markdown = report_result.payload["markdown"]

        llm_report_result = self.llm_reporter.run(bundle)
        bundle.agent_logs.append(llm_report_result)
        if llm_report_result.status == "ok":
            bundle.report_markdown = llm_report_result.payload["markdown"]

        return bundle

    @staticmethod
    def _coerce_request(request: AnalysisRequest | dict) -> AnalysisRequest:
        if isinstance(request, AnalysisRequest):
            return request
        return AnalysisRequest(**request)
