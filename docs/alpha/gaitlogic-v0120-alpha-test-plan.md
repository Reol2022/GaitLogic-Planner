# GaitLogic v0.12.0 Alpha 测试计划

## 目标

验证公开 Coach API、训练知识引用、确定性 TODAY 边界、桌面与移动端展示以及 Provider/Index 故障降级。

## 建议矩阵

| 编号 | 场景 | 预期 |
| --- | --- | --- |
| A01 | 新用户、无训练数据 | UNKNOWN 与明确 limitation |
| A02 | 完整训练数据 | 状态、Evidence 和引用可读 |
| A03 | 数据不足 | 不虚构训练数字 |
| A04 | 无今日计划 | NO_PLAN 不显示为休息日 |
| A05 | 高疲劳 | Warning 默认可见，规则结论不被模型覆盖 |
| A06 | Chat Provider 故障 | DEGRADED，确定性建议保留 |
| A07 | Embedding/Index 故障 | 无引用、友好 limitation、不泄露路径 |
| A08 | 空检索 | 不伪造来源 |
| A09 | 360px 移动端 | 无横向溢出，引用可展开 |
| A10 | 1280px 桌面端 | 信息顺序正确 |

Garmin 不是本轮 Alpha 的必测项，不应为了 Coach 验收触发真实同步。

## 通过门槛

- TODAY canonical 字段一致率 100%；
- 无凭据、内部 Reference ID、绝对路径或原始 Provider 回答泄漏；
- Provider/Index 故障不修改训练计划或训练日志；
- 公开引用全部来自服务端 Canonical Catalog；
- 必需自动测试和 Readiness 检查通过。
