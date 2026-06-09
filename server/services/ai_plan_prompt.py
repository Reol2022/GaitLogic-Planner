from __future__ import annotations

import json

from server.schemas.ai_plan import AIPlanGenerateRequest


def build_prompt(request: AIPlanGenerateRequest) -> str:
    payload = request.model_dump(mode="json")
    output_schema = {
        "title": "",
        "goal": "",
        "start_date": "",
        "end_date": "",
        "target_race_name": "",
        "target_race_date": "",
        "target_result": "",
        "summary": "",
        "risk_notes": [],
        "weeks": [
            {
                "block_name": "",
                "phase_name": "",
                "focus": "",
                "planned_distance_km": 0,
                "workouts": [
                    {
                        "date": "",
                        "weekday": "",
                        "planned_content": "",
                        "focus_note": "",
                        "planned_distance_km": 0,
                        "main_type": "",
                        "target_pace_text": "",
                    }
                ],
            }
        ],
    }
    return "\n".join(
        [
            "你是严肃跑者训练计划助手。",
            "你只生成训练计划草稿，不直接写入正式训练计划。",
            "你不提供医疗诊断；如果用户有伤病或疼痛风险，必须降低强度并给出风险提示。",
            "不要生成极端训练量，不要安排危险训练组合。",
            "输出必须是合法 JSON。",
            "不要输出 Markdown。",
            "不要输出解释性废话。",
            "训练规则：",
            "- 每周关键课不超过 2 次。",
            "- 每周至少 1 天恢复或休息。",
            "- 周跑量增长默认不超过 10-15%。",
            "- 长距离不超过周跑量 30%，除非用户明确选择 aggressive。",
            "- 不安排连续两天高强度。",
            "- 比赛前一周减量。",
            "- 初级用户不安排高密度 I/R。",
            "- 有伤痛时降低强度。",
            "输出 JSON 结构必须为：",
            json.dumps(output_schema, ensure_ascii=False),
            "用户输入：",
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        ]
    )
