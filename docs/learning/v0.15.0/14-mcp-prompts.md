# MCP Prompts：可复用的安全工作模板

MCP Prompt 是 Host 可取得的模板，不是自动执行的工作流。v0.15.0-C 提供 `training_knowledge_explain` 和 `review_my_training`：前者要求先调用 `retrieve_training_knowledge` 再解释主题，后者建议先读取近期训练与 Runner State，并在需要理论依据时检索知识。

Prompt 本身不创建数据库 Session、不读取用户数据、不调用 Provider，也不改变计划。它强调只依据返回事实和 canonical reference 说明、保留限制，并避免医疗诊断。Prompt 获取生成 `mcp.prompt` span，但 Topic 和渲染后的文本不进入 metadata。
