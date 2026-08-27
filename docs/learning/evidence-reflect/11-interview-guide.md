# Interview Guide

30 秒回答：

> GaitLogic 不会因为数据不完整就直接让 Agent 猜，也不会一缺数据就整体失败。系统先通过 Evidence Judge 判断当前决策域有哪些可用证据、覆盖是否充分以及是否存在冲突，再结合 Decision Readiness 判断哪些结论可以生成。若关键证据缺失且已有工具可以补充，则 Reflect 会生成受控的 Missing Evidence Plan，调用白名单工具重新取证；如果无法补齐，就保留 PARTIAL/BLOCKED 状态，由 Validator 阻止模型对缺失领域做确定性判断。

常见追问：为什么不是 Multi-Agent？因为 Judge 和 Reflect 都是确定性的 Domain Service/Loop Stage，没有独立角色、Prompt、目标或自由工具权限。为什么不用 LLM Reflect？第一版的缺口到工具映射可以确定性完成，能避免额外成本、重复调用和不可解释选择。
