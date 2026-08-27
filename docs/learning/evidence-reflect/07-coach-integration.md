# Coach Integration

Coach 在 `AgentTrainingContextBuilder` 完成初始工具获取后运行 Judge。若 relevant domain 缺失，`GaitLogicCoachAgent._reflect_context()` 进行最多一轮 targeted tool reacquisition，再 rejudge 后把 assessment/readiness 交给 LLM。

模型原有 Tool Calling loop、DeepSeek request-local `reasoning_content` 和 Provider execution state 不变。Reflect 不读取 chain-of-thought，也不增加模型调用。模型工具在后续轮次产生新结果时，系统会再次执行 Evidence rejudge。

最终公共 Coach Response 不包含 Evidence ID、tool fingerprint 或内部 conflict object。
