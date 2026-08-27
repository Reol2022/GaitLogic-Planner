# Reflect Loop

Reflect 不是让 LLM 再思考一次。`EvidenceReflectPlanner` 根据 assessment、Intent Policy、Tool capability 和已调用 fingerprint 生成 `MissingEvidencePlan`。

停止条件包括：证据已充分、没有可自动补充来源、调用预算耗尽、工具失败、补取后 fingerprint 不变、达到 `max_reflect_rounds`。默认只允许一轮。相同 `tool_name + normalized args` 成功调用后不会重复执行。

若缺少 RPE 且所有可提供 RPE 的现有工具都已调用，结果保持 BLOCKED；Coach 可以继续回答其他 READY/PARTIAL domain。
