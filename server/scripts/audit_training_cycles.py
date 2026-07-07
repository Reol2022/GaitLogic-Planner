from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import inspect, text

from planner_core.database.session import SessionLocal


@dataclass
class CycleRow:
    id: int
    user_id: int
    status: str
    start_date: date | None
    end_date: date | None
    actual_start_date: date | None
    actual_end_date: date | None


@dataclass
class AuditResult:
    no_cycle_users: list[int]
    single_active_users: list[int]
    multiple_active_users: dict[int, list[int]]
    overlapping_users: dict[int, list[tuple[int, int]]]
    missing_date_users: dict[int, list[int]]


def audit_training_cycles() -> AuditResult:
    with SessionLocal() as db:
        conn = db.connection()
        inspector = inspect(conn)
        columns = {column["name"] for column in inspector.get_columns("training_cycles")}
        users = [row[0] for row in conn.execute(text("SELECT id FROM user_account"))]
        rows = conn.execute(text(_cycle_query(columns))).mappings().all()

    by_user: dict[int, list[CycleRow]] = defaultdict(list)
    for row in rows:
        cycle = CycleRow(
            id=row["id"],
            user_id=row["user_id"],
            status=row["status"] or "draft",
            start_date=row["start_date"],
            end_date=row["end_date"],
            actual_start_date=row["actual_start_date"],
            actual_end_date=row["actual_end_date"],
        )
        by_user[cycle.user_id].append(cycle)

    no_cycle_users: list[int] = []
    single_active_users: list[int] = []
    multiple_active_users: dict[int, list[int]] = {}
    overlapping_users: dict[int, list[tuple[int, int]]] = {}
    missing_date_users: dict[int, list[int]] = {}

    for user_id in users:
        user_cycles = by_user.get(user_id, [])
        if not user_cycles:
            no_cycle_users.append(user_id)
            continue
        active = [cycle for cycle in user_cycles if cycle.status == "active"]
        if len(active) == 1:
            single_active_users.append(user_id)
        elif len(active) > 1:
            multiple_active_users[user_id] = [cycle.id for cycle in active]
        missing = [cycle.id for cycle in user_cycles if _range_start(cycle) is None]
        if missing:
            missing_date_users[user_id] = missing
        overlaps = _overlaps(user_cycles)
        if overlaps:
            overlapping_users[user_id] = overlaps

    return AuditResult(no_cycle_users, single_active_users, multiple_active_users, overlapping_users, missing_date_users)


def _cycle_query(columns: set[str]) -> str:
    status_expr = "`status`" if "status" in columns else "'draft'"
    actual_start_expr = "`actual_start_date`" if "actual_start_date" in columns else "NULL"
    actual_end_expr = "`actual_end_date`" if "actual_end_date" in columns else "NULL"
    return (
        "SELECT `id`, `user_id`, "
        f"{status_expr} AS `status`, "
        "`start_date`, `end_date`, "
        f"{actual_start_expr} AS `actual_start_date`, "
        f"{actual_end_expr} AS `actual_end_date` "
        "FROM `training_cycles` ORDER BY `user_id`, `id`"
    )


def _range_start(cycle: CycleRow) -> date | None:
    return cycle.actual_start_date or cycle.start_date


def _range_end(cycle: CycleRow) -> date | None:
    return cycle.actual_end_date or cycle.end_date


def _overlaps(cycles: list[CycleRow]) -> list[tuple[int, int]]:
    candidates = [
        cycle
        for cycle in cycles
        if cycle.status in {"active", "completed"} and _range_start(cycle) is not None
    ]
    overlaps: list[tuple[int, int]] = []
    for index, left in enumerate(candidates):
        left_start = _range_start(left)
        left_end = _range_end(left) or date.max
        if left_start is None:
            continue
        for right in candidates[index + 1 :]:
            right_start = _range_start(right)
            right_end = _range_end(right) or date.max
            if right_start is None:
                continue
            if left_start <= right_end and right_start <= left_end:
                overlaps.append((left.id, right.id))
    return overlaps


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit training cycle lifecycle data.")
    parser.add_argument("--dry-run", action="store_true", help="Only print audit result. No data is changed.")
    parser.parse_args()
    result = audit_training_cycles()
    print("Training cycle audit")
    print(f"- no_cycle_users: {result.no_cycle_users}")
    print(f"- single_active_users: {result.single_active_users}")
    print(f"- multiple_active_users: {result.multiple_active_users}")
    print(f"- overlapping_users: {result.overlapping_users}")
    print(f"- missing_date_users: {result.missing_date_users}")


if __name__ == "__main__":
    main()
