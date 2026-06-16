# 90 秒 Demo Script

## 目标

用 90 秒说明这个项目不是普通的 notebook，而是一个可运行、可测试、可展示的 Multi-Agent Causal Analytics Team。

## 演示脚本

0-15 秒：

打开 Streamlit 页面，介绍项目名称：Multi-Agent Causal Analytics Team。说明它是一个用于因果分析的多 Agent 数据分析团队。

15-30 秒：

选择内置营销样例数据，展示数据预览。说明样例数据模拟优惠券是否影响购买概率。

30-45 秒：

展示变量配置：

- Treatment: `coupon`
- Outcome: `purchase`
- Confounders: `age`, `income`, `prior_spend`, `visits`
- Effect Modifier: `visits`

45-65 秒：

点击运行分析，展示 ATE metric、估计方法、CATE 状态和 refutation 表格。强调 DoWhy 用于 ATE，EconML 是 optional。

65-80 秒：

打开稳健性检查、Reviewer warnings 和 Agent 日志。说明 Reviewer 检查 placebo treatment、random common cause 和 data subset 三类 refutation。

80-90 秒：

下载 Markdown 或 HTML 报告，强调项目亮点：职责清晰的 Agent 流程、可选依赖 graceful skip、pytest 端到端测试、适合 GitHub 和简历展示。
