from __future__ import annotations

import json
from typing import Any

from server.schemas.ai_plan import AIPlanGenerateRequest


def build_ai_plan_system_prompt() -> str:
    return """
你是 GaitLogic Planner 的 AI 跑步训练计划草稿生成器。

你的角色是一名世界顶尖中长跑与马拉松训练教练，长期服务于严肃跑者、业余精英跑者和学生运动员。你精通运动生理学、运动训练学、能量代谢、周期化训练、疲劳管理、伤病风险控制和比赛专项能力构建。

你熟悉并能综合运用以下训练体系和思想：
1. Jack Daniels 丹尼尔斯训练体系：E、M、T、I、R、VDOT 配速思想，训练强度必须与训练目的匹配。
2. 阈值训练体系：LT1、LT2、T1、T2，阈值训练不应过度堆叠。
3. 极化训练思想：大部分训练保持低强度，高强度少而精，避免长期灰区强度。
4. 挪威双阈值思想：核心是控制乳酸、控制强度、提高可恢复性；不要机械安排普通跑者一天两次阈值课。
5. Renato Canova 卡诺瓦专项训练思想：越接近目标赛事，训练越接近专项需求；专项训练必须建立在足够有氧基础之上。
6. 经典周期化训练：基础期、强化期、专项期、调整期、比赛期、恢复期。
7. 伤病风险控制：跑量增长循序渐进，不连续安排高强度，不在疲劳和疼痛明显时强行增加强度。

你的目标不是生成看起来很猛的课表，而是生成安全、科学、可执行、可长期坚持的训练计划草稿。

生成训练计划时必须遵守以下规则：
1. 计划必须围绕用户目标赛事和当前能力制定。
2. 必须尊重用户当前周跑量和最近 4 周平均跑量。
3. 周跑量增长默认不超过 10%-15%。
4. 每周关键课不超过 2 次。
5. 每周至少安排 1 天恢复跑、休息或低负荷日。
6. 不安排连续两天高强度训练。
7. 长距离一般不超过周跑量的 30%，除非用户选择 aggressive 且能力充分。
8. 初级用户不得安排高密度 I/R 训练。
9. 有伤病说明时，应自动降低强度和跑量。
10. 比赛前一周应适度减量。
11. 每一堂课都必须有明确训练目的。
12. 配速建议应与训练目的匹配，不要所有训练都偏快。
13. 如果用户目标明显激进，应在 risk_notes 中指出风险，而不是盲目迎合。
14. 如果用户输入信息不足，应生成相对保守的计划。
15. 计划必须具体到每天，而不是泛泛而谈。
16. 每一堂非休息训练都必须在 focus_note 中说明：本次训练的主要目的、执行时最重要的注意事项、状态不佳时的安全降级方式。
17. 休息日可以简洁说明恢复目的，不需要生成冗长解释。

训练类型只能使用：
REC, E, LSD, M, T1, T2, I, R, Rest, Mixed

你必须只输出 JSON。
不要输出 Markdown。
不要输出解释性段落。
不要输出代码块。
不要在 JSON 外添加任何文字。

JSON 必须符合以下结构：
{
  "title": "训练计划标题",
  "goal": "训练目标",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "target_race_name": "目标赛事名称",
  "target_race_date": "YYYY-MM-DD",
  "target_result": "目标成绩",
  "summary": "计划总体说明",
  "risk_notes": ["风险提示1"],
  "weeks": [
    {
      "block_name": "Week 1：训练块名称",
      "phase_name": "基础期/强化期/专项期/调整期",
      "focus": "本周训练重点",
      "planned_distance_km": 80,
      "workouts": [
        {
          "date": "YYYY-MM-DD",
          "weekday": "周一",
          "planned_content": "具体训练内容",
          "focus_note": "目的：本次训练目的；注意：执行要点；降级：状态不佳时如何安全调整",
          "planned_distance_km": 10,
          "main_type": "E",
          "target_pace_text": "4:45-5:30/km"
        }
      ]
    }
  ]
}

输出 JSON 细节规则：
1. weeks 数量必须严格等于用户请求的 plan_weeks。
2. 不能只生成 Week 1，必须从 Week 1 连续生成到用户请求的最后一周。
3. 每周 workouts 数量应匹配用户每周可训练天数。
4. 每个 workout 必须包含 date、weekday、planned_content、focus_note、planned_distance_km、main_type、target_pace_text。
5. date 必须为 YYYY-MM-DD。
6. planned_distance_km 必须是数字，不要写字符串。
7. main_type 必须从 REC, E, LSD, M, T1, T2, I, R, Rest, Mixed 中选择。
8. 如果当天是休息日，planned_distance_km = 0，main_type = Rest。
9. target_pace_text 可以为空字符串，但字段必须存在。
10. risk_notes 必须至少包含 1 条。
11. summary 要简洁，不要超过 300 字。
12. 不要生成超过用户可训练天数的训练安排。
13. 不要生成与用户固定休息日冲突的训练。
14. 如果用户可以双跑，也只能谨慎安排，且不应默认天天双跑。
15. 如果用户不能双跑，不得安排双跑。
16. 非 Rest 训练的 focus_note 必须包含明确目的、注意事项和降级建议。

安全边界：
你不是医生，不提供医疗诊断。
如果用户有明显伤病风险，只能建议降低强度、减少跑量、休息或寻求专业人士评估。
不得鼓励用户带伤硬顶。
不得生成极端训练计划。
不得为了达成目标而忽视恢复。
不得使用羞辱、恐吓或过度鸡血语言。
不得承诺一定 PB 或一定达标。
""".strip()


def _format_optional(value: Any) -> str:
    if value in (None, "", []):
        return "未填写"
    if isinstance(value, list):
        return "、".join(str(item) for item in value) if value else "未填写"
    return str(value)


def build_ai_plan_user_prompt(
    request: AIPlanGenerateRequest,
    coach_preference: dict[str, Any] | None = None,
) -> str:
    data = request.model_dump(mode="json")
    plan_weeks = data.get("plan_weeks")
    lines = [
        "请根据以下用户信息生成结构化训练计划草稿。",
        f"非常重要：必须完整生成 {plan_weeks} 周，weeks 数组长度必须等于 {plan_weeks}，不能只输出第一周或部分周。",
        "",
        "跑者基本信息：",
        f"- 跑者水平：{_format_optional(data.get('runner_level'))}",
        f"- 近期 PB 距离：{_format_optional(data.get('recent_pb_distance'))}",
        f"- 近期 PB 成绩：{_format_optional(data.get('recent_pb_result'))}",
        f"- 当前周跑量：{_format_optional(data.get('current_weekly_mileage_km'))} km",
        f"- 最近 4 周平均跑量：{_format_optional(data.get('recent_4w_avg_mileage_km'))} km",
        f"- 每周可训练天数：{_format_optional(data.get('available_training_days_per_week'))}",
        f"- 是否可以双跑：{'可以' if data.get('can_double_run') else '不可以'}",
        f"- 固定休息日：{_format_optional(data.get('fixed_rest_days'))}",
        f"- 伤病说明：{_format_optional(data.get('injury_notes'))}",
        f"- 训练偏好/训练哲学：{_format_optional(data.get('training_preferences'))}",
        "",
    ]

    if coach_preference:
        lines.extend(
            [
                "当前用户保存的 AI 教练偏好配置：",
                f"- 训练体系偏好：{_format_optional(coach_preference.get('preferred_training_systems'))}",
                f"- 强度保守度：{_format_optional(coach_preference.get('intensity_conservatism'))}",
                f"- 关键课习惯：{_format_optional(coach_preference.get('key_workout_habit'))}",
                f"- 休息日策略：{_format_optional(coach_preference.get('rest_day_strategy'))}",
                f"- 禁用训练类型：{_format_optional(coach_preference.get('disabled_workout_types'))}",
                f"- 双跑策略：{_format_optional(coach_preference.get('double_run_policy'))}",
                f"- 长距离策略：{_format_optional(coach_preference.get('long_run_strategy'))}",
                f"- 伤病风险策略：{_format_optional(coach_preference.get('injury_risk_policy'))}",
                f"- 额外说明：{_format_optional(coach_preference.get('additional_notes'))}",
                "如果用户偏好与安全规则冲突，必须优先遵守安全规则。",
                "",
            ]
        )

    lines.extend(
        [
            "目标信息：",
            f"- 目标赛事名称：{_format_optional(data.get('target_race_name'))}",
            f"- 目标赛事日期：{_format_optional(data.get('target_race_date'))}",
            f"- 目标距离：{_format_optional(data.get('target_distance'))}",
            f"- 目标成绩：{_format_optional(data.get('target_result'))}",
            f"- 计划开始日期：{_format_optional(data.get('plan_start_date'))}",
            f"- 计划周数：{_format_optional(plan_weeks)}",
            f"- 强度风格：{_format_optional(data.get('intensity_style'))}",
            f"- 是否包含配速建议：{'是' if data.get('include_pace_guidance') else '否'}",
            "",
            "生成要求：",
            "- 请生成结构化训练计划草稿。",
            "- 必须遵守 system prompt 中的训练安全规则。",
            "- 必须输出合法 JSON。",
            "- 不要输出 Markdown。",
            "- 不要输出 JSON 之外的任何文字。",
            "- weeks 数组必须完整，不能省略后续周。",
            "- 每一堂非休息训练的 focus_note 必须写清楚目的、执行注意事项和状态不佳时的降级方式。",
            "",
            "原始用户输入 JSON：",
            json.dumps(data, ensure_ascii=False, sort_keys=True),
        ]
    )
    return "\n".join(lines)


def build_prompt(request: AIPlanGenerateRequest, coach_preference: dict[str, Any] | None = None) -> str:
    return "\n\n".join(
        [build_ai_plan_system_prompt(), build_ai_plan_user_prompt(request, coach_preference)]
    )
