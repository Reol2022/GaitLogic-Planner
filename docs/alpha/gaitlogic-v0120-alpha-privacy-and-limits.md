# GaitLogic v0.12.0 Alpha 隐私与限制

## 隐私

Alpha 是邀请制实验。公开仓库不保存真实 Coach 对话、Provider 原始回答、Prompt、Context、Tool Result、向量、训练快照、用户身份映射或 Garmin 凭据。测试参与者可以申请删除测试账号及其数据。

日志只允许记录 request ID、Intent、最终状态、Provider 状态、工具名、工具结果数量、知识引用数量、验证码、延迟和用量；禁止记录问题正文、训练数据正文、知识摘录、完整回答、Key 或 `reasoning_content`。

## 当前限制

- 不是医疗诊断、康复或专业教练处方；
- 知识库规模有限，可能没有匹配内容；
- Provider 和网络可能失败；
- 无 Hybrid Retrieval、Reranker 或新向量后端；
- 无长期记忆、写工具、Weekly Review Agent 或多 Agent；
- 不自动生成或修改正式训练计划；
- Quota 仍为进程内限制；
- 私有竞赛标签复核和人工盲评尚未完成。

产品 Alpha 通过不等于竞赛验证完成。
