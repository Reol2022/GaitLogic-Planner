# Freshness and staleness

revision 与 apply 前重建 canonical Weekly Facts 并比较 `result_hash`。不相等时 Snapshot 标记 stale、待审批 Proposal 标记 invalidated，并返回 `REVIEW_STALE`。
