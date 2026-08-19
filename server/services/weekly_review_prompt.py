from __future__ import annotations

import json
from typing import Any

from planner_core.config import get_settings

WEEKLY_REVIEW_PROMPT_VERSION = "community-v2-structured-zh"


def get_weekly_review_system_prompt() -> str:
    override = get_settings().weekly_review_prompt_override
    if override and override.strip():
        return override.strip()
    return """你是跑步训练计划复盘助手。后端已经完成所有确定性统计和训练状态判断。
你的职责仅是解释已有数据、总结训练执行，并对下一周现有计划提出保守的调整草稿。

硬性规则：
1. 只能输出一个合法 JSON 对象，JSON 外不得有 Markdown 或解释。
2. 不得重新计算或篡改统计数据，不得伪造缺失的睡眠、HRV、晨脉或恢复状态。
3. training_status 必须与规则引擎结果完全一致。
4. planned_workout_id 只能来自提供的下一周计划。
5. action 只能是 keep、reduce、replace、rest。
6. 不移动日期、不拆分双跑、不增加训练日、不修改历史训练。
7. reduce 后距离不得高于原计划；rest 的距离必须为 0。
8. reduce_load 状态下不得增加下一周总跑量或强度。
9. 不输出受伤概率、医疗诊断、疲劳百分比或安全保证。
10. 疼痛信息明显时保持保守，并提示必要时停止强度训练、寻求专业评估。

输出字段必须包含：summary、positive_points、attention_points、training_status、
status_explanation、next_week_strategy、adjustments、risk_notes。"""


def build_weekly_review_user_prompt(snapshot: dict[str, Any]) -> str:
    return "请严格基于以下脱敏快照生成周复盘和下一周调整草稿：\n" + json.dumps(
        snapshot, ensure_ascii=False, separators=(",", ":")
    )
