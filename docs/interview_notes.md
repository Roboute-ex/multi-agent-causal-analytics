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
- 增加可视化和 PDF 报告。
- 在稳定 MVP 之后再引入 LangGraph 或 LLM 做更智能的编排和解释。

## 7. LLM 变量推荐为什么不直接进入主流程？

回答要点：

- LLM 只适合做辅助建议，不能替代因果识别假设。
- 推荐结果必须经过字段校验，只能使用当前数据集中存在的列。
- 用户必须手动确认或修改变量，系统不会因为 LLM 推荐而自动运行因果分析。
- 没有 API key、请求失败或返回非法 JSON 时，功能会 skipped/fallback，不影响 deterministic MVP。
