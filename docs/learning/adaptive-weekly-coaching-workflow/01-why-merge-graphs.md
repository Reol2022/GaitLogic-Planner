# Why merge graphs

此前 Weekly Review 与 Approval 彼此独立，拒绝后只能重跑完整分析。统一生命周期使 revision 复用 Snapshot，减少一次 Weekly Analysis Provider 调用，同时保留 HITL 和确定性校验。
