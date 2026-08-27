#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.evidence_evaluation import run_evidence_reflect_cases


def main() -> int:
    cases, _ = run_evidence_reflect_cases()
    by_id = {str(item["case_id"]): bool(item["passed"]) for item in cases}
    smoke = {
        "smoke_a_today_missing_recovery_targeted_tool": by_id["evidence_reflect_02"],
        "smoke_b_volume_ignores_rpe": by_id["evidence_reflect_08"],
        "smoke_c_partial_recovery_stays_limited": by_id["evidence_reflect_09"],
        "smoke_d_weekly_missing_rpe_does_not_invent_tool": by_id["evidence_reflect_03"],
    }
    print(json.dumps(smoke, ensure_ascii=False, sort_keys=True))
    return 0 if all(smoke.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
