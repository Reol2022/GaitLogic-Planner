# 30-second interview answer

最初 Weekly Review 和 Adaptive Approval 是两个独立 Graph，用户拒绝 Proposal 后只能重跑完整复盘。后来我将其收敛为状态化 Workflow：Review 基于固定训练事实生成不可变 Snapshot，Proposal 在 Snapshot 上可带反馈有限迭代；仅事实变化才 stale 并重算。这样减少 Provider 调用，同时所有 revision 与最终 Apply 仍重新经过确定性安全校验。
