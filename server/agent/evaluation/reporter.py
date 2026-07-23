from __future__ import annotations

import json
from pathlib import Path

from server.agent.evaluation.schemas import CoachEvaluationReport

_METRIC_LABELS = {
    "case_pass_rate": "Case Pass Rate",
    "intent_accuracy": "Intent Accuracy",
    "required_tool_recall": "Required Tool Recall",
    "forbidden_tool_call_rate": "Forbidden Tool Call Rate",
    "tool_argument_validity": "Tool Argument Validity",
    "decision_consistency": "Decision Consistency",
    "planned_status_consistency": "Planned Status Consistency",
    "warning_retention_rate": "Warning Retention Rate",
    "limitation_retention_rate": "Limitation Retention Rate",
    "fallback_success_rate": "Fallback Success Rate",
    "unsupported_claim_rate": "Unsupported Claim Rate",
    "rule_violation_rate": "Rule Violation Rate",
}


def report_to_markdown(report: CoachEvaluationReport) -> str:
    summary = report.summary.model_dump()
    lines = [
        "# Coach Agent Evaluation v1",
        "",
        "## 评测目的",
        "",
        "使用完全虚构、固定日期的数据，对 Coach Agent 的只读工具编排、确定性决策一致性、降级能力和安全边界进行可重复检查。评测不访问网络、真实 Provider 或生产数据库。",
        "",
        "## 运行信息",
        "",
        f"- Evaluation：`{report.evaluation_version}`",
        f"- Case set：`{report.case_set_version}`",
        f"- Prompt：`{report.prompt_version}`",
        f"- Git commit：`{report.git_commit}`",
        f"- Generated at：`{report.generated_at.isoformat()}`",
        f"- Cases：{report.summary.total_cases}",
        "",
        "## 总体结果",
        "",
        "| 指标 | 结果 |",
        "| --- | ---: |",
    ]
    for key, label in _METRIC_LABELS.items():
        lines.append(f"| {label} | {summary[key] * 100:.2f}% |")
    lines.extend(
        [
            "",
            "## 分类结果",
            "",
            "| 分类 | 通过 / 总数 | 通过率 |",
            "| --- | ---: | ---: |",
        ]
    )
    for name, item in report.categories.items():
        lines.append(
            f"| {name} | {item.passed_cases} / {item.total_cases} | {item.pass_rate * 100:.2f}% |"
        )
    failures = [item for item in report.cases if not item.passed]
    lines.extend(["", "## 失败案例", ""])
    if not failures:
        lines.append("本次运行没有失败案例。")
    else:
        for item in failures:
            failed = [assertion.code for assertion in item.assertions if not assertion.passed]
            lines.append(f"- `{item.case_id}`：{', '.join(failed)}")
    lines.extend(
        [
            "",
            "## 指标定义",
            "",
            "- Required Tool Recall：实际执行的必需工具数 / 预期必需工具数；Context 工具与模型工具分别记录。",
            "- Forbidden Tool Call Rate：调用任一禁止工具的案例数 / 总案例数。",
            "- Tool Argument Validity：没有产生 INVALID_ARGUMENTS 的案例比例。",
            "- Decision / Planned Status Consistency：结果是否保持确定性规则和计划事实。",
            "- Unsupported Claim / Rule Violation：使用确定性字符串与结构断言检测，不使用第二个 LLM 裁判。",
            "",
            "## 已知限制",
            "",
            "- v1 使用固定的虚构 Tool 输出和 Mock Gateway，不能代表真实 Provider 的语言质量。",
            "- v1 不评估 RAG、Weekly Review Agent、写工具、长期记忆、Streaming 或多 Agent。",
            "- 文本断言刻意保守，只检测已定义的越权声明和规则冲突。",
            "",
            "## 如何复现",
            "",
            "```powershell",
            "python scripts/evaluate_coach_agent.py",
            "```",
            "",
            "## 安全边界",
            "",
            "报告不包含 Prompt 全文、Context、工具完整结果、Provider 原始响应、API Key、用户身份、数据库连接或思维链。",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(
    report: CoachEvaluationReport,
    *,
    json_path: str | Path,
    markdown_path: str | Path,
) -> None:
    json_target = Path(json_path)
    markdown_target = Path(markdown_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    markdown_target.write_text(report_to_markdown(report), encoding="utf-8")
