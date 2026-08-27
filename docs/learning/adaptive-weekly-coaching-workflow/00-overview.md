# Adaptive Weekly Coaching Workflow

周复盘先形成不可变 Snapshot，方案是可版本化候选状态。用户反馈只重新运行 Plan Design；只有事实指纹变化才允许重新运行 Weekly Review。

核心原则：周复盘是不可变的历史分析快照；Proposal 是可版本化候选方案；真正影响写入安全的当前事实，在每次生成和 Apply 前重新验证。
