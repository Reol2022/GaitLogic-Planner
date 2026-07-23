# Coach Agent Evaluation v1

## 实现概览

Evaluation v1 提供 32 条固定虚构案例、严格 JSONL Loader、离线 Runner、确定性 Assertions、12 项指标以及 JSON/Markdown Reporter。

主要入口：

```powershell
python scripts/evaluate_coach_agent.py
```

筛选示例：

```powershell
python scripts/evaluate_coach_agent.py --case-id today_001 --no-write
python scripts/evaluate_coach_agent.py --category degraded --fail-fast
```

默认输出：

- `docs/agent/evaluation/results/coach-agent-eval-v1.json`
- `docs/agent/evaluation/results/coach-agent-eval-v1.md`

## 案例组成

| 分类 | 数量 |
| --- | ---: |
| TODAY_RECOMMENDATION | 10 |
| EXPLAIN_RUNNER_STATE | 6 |
| GENERAL_TRAINING_QUESTION | 4 |
| UNKNOWN / 数据不足 | 4 |
| Provider / Tool 降级 | 4 |
| 安全拒绝与越权请求 | 4 |

## 可靠性边界

- 默认离线 Mock Gateway；
- 固定日期与时区；
- 生产 Tool Schema、Context Builder、Validator 和 Fallback；
- 不读取真实 API Key；
- 不访问网络、生产数据库或 Garmin；
- 不用模型判断模型；
- 失败案例默认不会阻断后续案例。

## 结果

真实运行结果见 [Coach Agent Evaluation v1 Results](results/coach-agent-eval-v1.md)。结果只代表该版本案例集与离线确定性链路，不代表真实 Provider 的答案质量或医学有效性。

## 当前限制

不包含 RAG、Weekly Review Agent、写工具、长期记忆、Streaming、多 Agent 或生产级分布式 Quota 评测。
