from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.database.models import (
    BlockReview,
    PaceRule,
    PlannedWorkout,
    TrainingBlock,
    TrainingCycle,
    WorkoutLog,
)
from planner_core.database.session import SessionLocal
from planner_core.enums import (
    BlockType,
    WorkoutMainTypeNormalized,
    WorkoutStatusNormalized,
)


def add_workout(
    cycle: TrainingCycle,
    block: TrainingBlock,
    workout_date: date,
    weekday: str,
    content: str,
    main_type_raw: str,
    main_type_normalized: WorkoutMainTypeNormalized,
    distance_km: float,
    sort_order: int,
) -> PlannedWorkout:
    return PlannedWorkout(
        cycle=cycle,
        block=block,
        workout_date=workout_date,
        date_text=workout_date.strftime("%Y-%m-%d"),
        weekday=weekday,
        month_text=f"{workout_date.month}月",
        phase_name=block.phase_name,
        planned_content=content,
        focus_note=block.focus,
        planned_distance_km=distance_km,
        main_type_raw=main_type_raw,
        main_type_normalized=main_type_normalized,
        source_sheet="计划索引",
        source_row=sort_order + 1,
        sort_order=sort_order,
        workout_log=WorkoutLog(
            status_raw=None,
            status_normalized=WorkoutStatusNormalized.not_started,
        ),
    )


def main() -> None:
    session = SessionLocal()
    try:
        cycle = TrainingCycle(
            name="2026夏训",
            goal="眉山东坡半马 1:11:30",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
            target_race_name="眉山东坡半马",
            target_race_date=date(2026, 9, 20),
            target_result="1:11:30",
            description="基于最新版 Excel 结构的夏训数据库示例。",
        )

        block1 = TrainingBlock(
            cycle=cycle,
            block_name="Week 1：重新启动周",
            block_type=BlockType.week,
            week_index=1,
            sort_order=1,
            date_range_text="6月1日-6月7日",
            target_text="重新建立训练节奏，恢复有氧基础。",
            target_distance_min_km=45,
            target_distance_max_km=55,
            planned_distance_km=50,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 7),
            phase_name="基础恢复",
            focus="轻松跑为主，避免过早堆强度。",
        )
        block2 = TrainingBlock(
            cycle=cycle,
            block_name="Week 2：恢复正常结构",
            block_type=BlockType.week,
            week_index=2,
            sort_order=2,
            date_range_text="6月8日-6月14日",
            target_text="恢复质量课结构，加入节奏跑。",
            target_distance_min_km=55,
            target_distance_max_km=65,
            planned_distance_km=60,
            start_date=date(2026, 6, 8),
            end_date=date(2026, 6, 14),
            phase_name="结构恢复",
            focus="一次节奏跑，一次长距离。",
        )
        block3 = TrainingBlock(
            cycle=cycle,
            block_name="6月最后两天",
            block_type=BlockType.transition,
            week_index=None,
            sort_order=3,
            date_range_text="6月29日-6月30日",
            target_text="衔接 7 月训练块。",
            target_distance_min_km=16,
            target_distance_max_km=22,
            planned_distance_km=18,
            start_date=date(2026, 6, 29),
            end_date=date(2026, 6, 30),
            phase_name="过渡衔接",
            focus="保持跑感，不额外增加疲劳。",
        )

        workouts = [
            add_workout(
                cycle,
                block1,
                date(2026, 6, 2),
                "周二",
                "轻松跑 10km",
                "E",
                WorkoutMainTypeNormalized.easy,
                10,
                1,
            ),
            add_workout(
                cycle,
                block1,
                date(2026, 6, 4),
                "周四",
                "轻松跑 + 加速跑 12km",
                "E+ST",
                WorkoutMainTypeNormalized.easy_with_speed,
                12,
                2,
            ),
            add_workout(
                cycle,
                block1,
                date(2026, 6, 7),
                "周日",
                "长距离 18km",
                "LSD",
                WorkoutMainTypeNormalized.long_run,
                18,
                3,
            ),
            add_workout(
                cycle,
                block2,
                date(2026, 6, 9),
                "周二",
                "节奏跑 4x2km",
                "T1",
                WorkoutMainTypeNormalized.tempo,
                14,
                4,
            ),
            add_workout(
                cycle,
                block2,
                date(2026, 6, 11),
                "周四",
                "间歇跑 6x1km",
                "I",
                WorkoutMainTypeNormalized.interval_speed,
                13,
                5,
            ),
            add_workout(
                cycle,
                block2,
                date(2026, 6, 14),
                "周日",
                "长距离 20km",
                "LSD",
                WorkoutMainTypeNormalized.long_run,
                20,
                6,
            ),
            add_workout(
                cycle,
                block3,
                date(2026, 6, 29),
                "周一",
                "恢复跑 8km",
                "REC",
                WorkoutMainTypeNormalized.recovery,
                8,
                7,
            ),
            add_workout(
                cycle,
                block3,
                date(2026, 6, 30),
                "周二",
                "轻松跑 10km",
                "E",
                WorkoutMainTypeNormalized.easy,
                10,
                8,
            ),
        ]

        block1.block_review = BlockReview(planned_distance_km=50, review_text="待复盘")
        block2.block_review = BlockReview(planned_distance_km=60, review_text="待复盘")
        block3.block_review = BlockReview(planned_distance_km=18, review_text="待复盘")

        pace_rules = [
            PaceRule(
                code="R",
                name="短速度",
                target_pace_text="短距离快速重复跑",
                physiological_purpose="提升速度、跑姿效率和神经肌肉募集。",
                sort_order=1,
            ),
            PaceRule(
                code="I",
                name="间歇跑",
                target_pace_text="接近最大摄氧强度",
                physiological_purpose="提升 VO2max 和高强度维持能力。",
                sort_order=2,
            ),
            PaceRule(
                code="T2",
                name="高阈值",
                target_pace_text="偏快阈值区间",
                physiological_purpose="提升乳酸阈值上沿能力。",
                sort_order=3,
            ),
            PaceRule(
                code="T1",
                name="稳阈值",
                target_pace_text="稳定阈值区间",
                physiological_purpose="提升阈值耐力。",
                sort_order=4,
            ),
            PaceRule(
                code="M",
                name="稳态跑",
                target_pace_text="马拉松或稳态配速",
                physiological_purpose="提升长时间稳定输出能力。",
                sort_order=5,
            ),
            PaceRule(
                code="E",
                name="轻松跑",
                target_pace_text="可对话强度",
                physiological_purpose="发展有氧基础并控制恢复成本。",
                sort_order=6,
            ),
            PaceRule(
                code="REC",
                name="恢复跑",
                target_pace_text="明显慢于轻松跑",
                physiological_purpose="促进恢复，维持跑感。",
                sort_order=7,
            ),
            PaceRule(
                code="LSD",
                name="长距离",
                target_pace_text="长时间有氧耐力配速",
                physiological_purpose="提升耐力、脂代谢和抗疲劳能力。",
                sort_order=8,
            ),
        ]

        session.add_all([cycle, *workouts, *pace_rules])
        session.commit()
        print("Demo data seeded successfully.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()

