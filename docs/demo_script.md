# 90 秒 Demo Script

## 目标

用 90 秒说明这个项目不是普通的 notebook，而是一个可运行、可测试、可展示的 Multi-Agent Causal Analytics Team。

## 演示脚本

0-15 秒：

打开 Streamlit 页面，介绍项目名称：Multi-Agent Causal Analytics Team。说明它是一个用于因果分析的多 Agent 数据分析团队。

15-30 秒：

展示 public demo 安全提示和 `Deployment / Optional Dependency Status` 面板。说明公开 demo 建议只使用内置样例数据，不上传真实业务数据、隐私数据或敏感数据。

30-45 秒：

选择内置营销样例数据，展示数据预览。说明样例数据模拟优惠券是否影响购买概率。

45-60 秒：

展示变量配置和 Data Quality Summary：

- Treatment: `coupon`
- Outcome: `purchase`
- Confounders: `age`, `income`, `prior_spend`, `visits`
- Effect Modifier: `visits`
- Data Quality: 行数、列数、缺失率、重复行、warning count、selected complete-case count

60-75 秒：

展示 `Use experimental LangGraph orchestration` 选项。说明 deterministic orchestrator 仍是默认稳定路径；Advanced LangGraph mode 用于展示 multi-agent workflow engineering。若本地安装了 LangGraph，勾选后运行并展示 graph execution trace / step timeline 和 graph state summary；未安装时会自动回退到 deterministic orchestrator。

75-85 秒：

打开稳健性检查、Reviewer warnings 和 Agent 日志。说明 Reviewer 检查 placebo treatment、random common cause 和 data subset 三类 refutation。

85-90 秒：

下载 Markdown、HTML 或 optional PDF 报告。说明 deployment readiness 是保留的过渡增强：有安全提示、demo mode indicator 和 optional dependency status。强调项目亮点：数据质量诊断、职责清晰的 Agent 流程、Advanced LangGraph trace、可选依赖 graceful skip、pytest 端到端测试、适合 GitHub 和简历展示。

## v0.8 演示补充

如果面试或 demo 时间允许，可以在结果区额外打开三个 expander：

- `Causal Trust Summary`：说明系统不会把 ATE 直接包装成确定结论，而是给出 effect direction、robustness level、key warnings 和 recommendations。
- `Robustness / Sensitivity Notes`：说明它基于现有 placebo treatment、random common cause、data subset refutation 做方向稳定性摘要；这是 conservative wrapper，不是新的强依赖。
- `Heterogeneity Explanation`：说明 CATE 可用时会把 effect modifiers 和分层结果翻译成业务解释；EconML 或 CATE 不可用时显示 skipped，不影响 ATE 主流程。

一句话讲法：

v0.8 的重点不是继续堆 Agent 概念，而是增强因果结果的可信度表达，让用户看到 observational data、confounding risk 和 sample quality risk。

## v0.9 演示补充

v0.9 的 demo 讲法可以放在最后 15 秒，突出工程可靠性：

1. 先展示正常 Streamlit 主流程：样例数据、Data Quality、ATE、Causal Trust、Sensitivity、Heterogeneity 和报告下载。
2. 再说明项目已经加入 Streamlit AppTest smoke tests，不依赖真实浏览器、截图、网络或 API key。
3. 展示 `python -m pytest tests\test_streamlit_app_smoke.py -q` 和全量 pytest 结果。
4. 强调 public demo safety message、optional dependency status、关键 UI section 和 report download 都纳入回归测试。
5. 说明这让项目更像一个可维护的数据产品，而不是一次性的 notebook demo。

一句话讲法：

v0.9 没有继续增加复杂因果功能，而是把 Streamlit demo 路径纳入自动化 smoke/regression tests，确保后续迭代不会破坏公开展示体验。
