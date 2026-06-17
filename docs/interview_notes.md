# 面试问题与回答要点

## 1. 为什么要把数据分析拆成多个 Agent？

回答要点：

- 传统 notebook 容易把数据清洗、建模、检查和报告混在一起。
- 这个项目把职责拆成 Data Engineer、Statistician、Causal Agent、Heterogeneity Agent、Reviewer 和 Reporter。
- 拆分后更容易测试、调试，也更适合展示工程化思维。

## 2. 为什么使用 DoWhy？

回答要点：

- DoWhy 的核心流程是建模、识别、估计、反驳，和因果推断方法论一致。
- MVP 中使用 `backdoor.linear_regression` 做 ATE 估计。
- DoWhy 不可用时项目会 fallback 到线性调整估计，并在结果中提示 warning。

## 3. 为什么 EconML 是 optional？

回答要点：

- EconML 适合做 CATE 异质性分析，但依赖较重。
- 项目把 CATE 作为增强能力，未安装时返回 `skipped`。
- 这样可以保证 ATE、Reviewer 和 Markdown 报告主流程稳定运行。

## 4. Reviewer Agent 检查什么？

回答要点：

- 检查输入字段是否存在。
- 检查 ATE 是否成功估计。
- 检查三类 refutation 是否存在：`placebo_treatment`、`random_common_cause`、`data_subset`。
- 汇总 warning，提醒用户不要过度解读因果结果。

## 5. 这个项目的局限是什么？

回答要点：

- 当前不做自动因果发现。
- 混杂变量和 effect modifier 需要用户结合业务知识选择。
- refutation 能提高可信度，但不能自动证明因果识别成立。
- 第一阶段不接入 LangGraph、OpenAI API、数据库或部署系统。

## 6. 如果继续迭代，你会做什么？

回答要点：

- 增加变量推荐和数据质量诊断。
- 增加更多估计方法，例如 propensity score、matching、double robust。
- 增加更多可视化，并把 PDF 报告作为 optional export。
- 在稳定 MVP 之后再引入 LangGraph 或 LLM 做更智能的编排和解释。

## 7. LLM 变量推荐为什么不直接进入主流程？

回答要点：

- LLM 只适合做辅助建议，不能替代因果识别假设。
- 推荐结果必须经过字段校验，只能使用当前数据集中存在的列。
- 用户必须手动确认或修改变量，系统不会因为 LLM 推荐而自动运行因果分析。
- 没有 API key、请求失败或返回非法 JSON 时，功能会 skipped/fallback，不影响 deterministic MVP。

## 8. HTML 报告导出为什么不放进核心 pipeline？

回答要点：

- 报告导出是展示层能力，只应在 pipeline 运行完成后读取 `PipelineBundle`。
- HTML 报告不改变 ATE、CATE、refutation 或 Reviewer 的计算结果。
- 使用标准库生成 HTML，避免新增强制依赖。
- PDF 导出依赖更复杂，当前只作为未来 optional feature。

## 9. Data Quality Checks 为什么不直接影响因果估计？

回答要点：

- Data Quality 是分析前诊断和展示层增强，负责暴露缺失、重复、常量列、高基数分类列和 treatment imbalance 等风险。
- ATE、CATE 和 refutation 仍然由原有 deterministic pipeline 计算，避免因为展示层检查改变模型结果。
- 这样可以保持 v0.1/v0.2/v0.3 主流程稳定，同时让用户在解释结果前看到数据风险。
- 如果未来要做自动清洗或样本过滤，应作为单独功能显式设计，并保留用户确认步骤。

## 10. v0.5 为什么把 LangGraph 做成 optional adapter？

回答要点：

- 现有 deterministic orchestrator 已经稳定通过测试，所以 v0.5 不替换主流程。
- LangGraph adapter 只负责编排现有 Agent 节点，输出仍然是 `PipelineBundle`。
- 未安装 `langgraph` 时 UI 会 warning 并回退到 deterministic orchestrator，避免把实验能力变成强依赖。
- v0.5 不做 checkpoint、persistence、human-in-the-loop、动态路由或 LLM planner，边界更清晰。

## 11. v0.6 为什么只增强报告层？

回答要点：

- v0.6 没有修改因果估计核心逻辑，而是增强报告交付能力。
- HTML report 加入更清晰的结构、summary cards 和 print-friendly CSS。
- PDF export 被设计成 optional dependency，未安装 ReportLab 时系统会 graceful fallback。
- 这样不会破坏 deterministic pipeline、Data Quality、LangGraph adapter 或现有 Markdown/HTML 下载。

英文回答：

In v0.6, I improved the reporting layer rather than changing the causal estimation core. The HTML report became more polished and print-friendly, and PDF export was added as an optional dependency. If ReportLab is not installed, the app falls back gracefully, so the core analytics workflow remains stable.
