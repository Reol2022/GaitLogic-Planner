# Coach Agent Evaluation v1

## 评测目的

使用完全虚构、固定日期的数据，对 Coach Agent 的只读工具编排、确定性决策一致性、降级能力和安全边界进行可重复检查。评测不访问网络、真实 Provider 或生产数据库。

## 运行信息

- Evaluation：`coach-agent-eval-1.0.0`
- Case set：`cases-v1`
- Prompt：`coach-agent-system-1.0.0`
- Git commit：`c38edaa263848ac6797beb84738ccbe0ea4ab82b`
- Generated at：`2026-07-23T05:26:56.504829+00:00`
- Cases：32

## 总体结果

| 指标 | 结果 |
| --- | ---: |
| Case Pass Rate | 100.00% |
| Intent Accuracy | 100.00% |
| Required Tool Recall | 100.00% |
| Forbidden Tool Call Rate | 0.00% |
| Tool Argument Validity | 100.00% |
| Decision Consistency | 100.00% |
| Planned Status Consistency | 100.00% |
| Warning Retention Rate | 100.00% |
| Limitation Retention Rate | 100.00% |
| Fallback Success Rate | 100.00% |
| Unsupported Claim Rate | 0.00% |
| Rule Violation Rate | 0.00% |

## 分类结果

| 分类 | 通过 / 总数 | 通过率 |
| --- | ---: | ---: |
| degraded | 4 / 4 | 100.00% |
| explain_runner_state | 6 / 6 | 100.00% |
| general_training_question | 4 / 4 | 100.00% |
| security | 4 / 4 | 100.00% |
| today_recommendation | 10 / 10 | 100.00% |
| unknown_data | 4 / 4 | 100.00% |

## 失败案例

本次运行没有失败案例。

## 指标定义

- Required Tool Recall：实际执行的必需工具数 / 预期必需工具数；Context 工具与模型工具分别记录。
- Forbidden Tool Call Rate：调用任一禁止工具的案例数 / 总案例数。
- Tool Argument Validity：没有产生 INVALID_ARGUMENTS 的案例比例。
- Decision / Planned Status Consistency：结果是否保持确定性规则和计划事实。
- Unsupported Claim / Rule Violation：使用确定性字符串与结构断言检测，不使用第二个 LLM 裁判。

## 已知限制

- v1 使用固定的虚构 Tool 输出和 Mock Gateway，不能代表真实 Provider 的语言质量。
- v1 不评估 RAG、Weekly Review Agent、写工具、长期记忆、Streaming 或多 Agent。
- 文本断言刻意保守，只检测已定义的越权声明和规则冲突。

## 如何复现

```powershell
python scripts/evaluate_coach_agent.py
```

## 安全边界

报告不包含 Prompt 全文、Context、工具完整结果、Provider 原始响应、API Key、用户身份、数据库连接或思维链。
