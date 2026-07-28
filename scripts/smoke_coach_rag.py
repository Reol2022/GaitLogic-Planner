from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from planner_core.config import get_settings  # noqa: E402
from server.agent.smoke import CoachRagSmokeReport, CoachRagSmokeRunner  # noqa: E402
from server.knowledge_retrieval.readiness import (  # noqa: E402
    CoachRagReadinessService,
    ReadinessExitCode,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run real-provider Coach RAG scenarios with immutable fictional "
            "fixtures and no database access."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/rag/coach-rag-alpha-smoke-v1.md"),
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Run all scenarios without writing the Markdown report.",
    )
    return parser


def render_report(report: CoachRagSmokeReport) -> str:
    lines = [
        "# Coach RAG Alpha Smoke v1",
        "",
        "本报告使用完全虚构、固定且只读的训练 Fixture，并调用真实 Chat 与 "
        "Embedding Provider。Smoke Runner 不打开数据库连接，因此业务写入为 0。"
        "MySQL 5.7/8 兼容性由独立隔离测试矩阵验证。",
        "",
        "报告不保存原始回答、Prompt、Context、Tool Result、知识摘录、用户问题、"
        "reasoning_content 或任何凭据。",
        "",
        "## 环境",
        "",
        f"- Chat Provider：`{report.provider}`",
        f"- Chat Model：`{report.chat_model}`",
        f"- Embedding Model：`{report.embedding_model}`",
        "- 数据：完全虚构",
        "",
        "## 场景",
        "",
        "| 场景 | Intent | 状态 | Provider | 引用数 | 通过 |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for item in report.scenarios:
        lines.append(
            f"| {item.scenario} | {item.intent.value} | {item.status} | "
            f"{item.provider_status} | {item.knowledge_reference_count} | "
            f"{'是' if item.passed else '否'} |"
        )
    today = next(
        item for item in report.scenarios if item.scenario == "TODAY"
    )
    lines.extend(
        [
            "",
            "## TODAY 确定性一致性",
            "",
            *[
                f"- {field}：{'通过' if passed else '失败'}"
                for field, passed in sorted(today.canonical_invariance.items())
            ],
            "",
            "## 数据与安全",
            "",
            f"- 业务写入数量：{report.business_write_count}",
            "- Smoke Runner 数据库连接数量：0",
            "- 未触发 Garmin；未修改训练计划；未创建长期记忆。",
            "- Public Knowledge References 只记录公开 document ID；"
            "不记录内部请求级 Reference ID。",
            "",
            "## 结论",
            "",
            (
                "Alpha Smoke 通过。"
                if report.passed
                else "Alpha Smoke 存在失败场景，不能进入发布封版。"
            ),
            "",
            "当前仍不支持 Hybrid Retrieval、Reranker、长期记忆、写工具、"
            "Weekly Review Agent 或医疗诊断。",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    readiness = CoachRagReadinessService(
        settings,
        repository_root=REPOSITORY_ROOT,
    ).run(require_enabled=True)
    if readiness.exit_code != ReadinessExitCode.READY:
        print(
            f"ERROR: Coach RAG readiness failed with code "
            f"{int(readiness.exit_code)}.",
            file=sys.stderr,
        )
        return int(readiness.exit_code)
    output = (
        args.output
        if args.output.is_absolute()
        else (REPOSITORY_ROOT / args.output)
    ).resolve()
    try:
        output.relative_to(REPOSITORY_ROOT / "docs")
    except ValueError:
        print("ERROR: Smoke report must stay inside docs/.", file=sys.stderr)
        return int(ReadinessExitCode.SECURITY_BOUNDARY_FAILED)

    report = CoachRagSmokeRunner(settings).run()
    if not args.no_write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_report(report), encoding="utf-8", newline="\n")
    print(
        "Coach RAG smoke: "
        f"{'PASSED' if report.passed else 'FAILED'}; "
        f"scenarios={len(report.scenarios)}; "
        f"business_writes={report.business_write_count}."
    )
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
