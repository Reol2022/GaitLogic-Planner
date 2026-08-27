# HITL and checkpoint

审批继续使用 LangGraph `interrupt()` / `Command(resume=...)` 和 SQLAlchemy checkpoint。approve/reject 保持兼容；revision 以父 Proposal 幂等地生成一个子 Proposal。
