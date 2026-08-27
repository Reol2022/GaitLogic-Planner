# Database lifecycle

运行 `python scripts/upgrade_v0164_adaptive_weekly_coaching.py upgrade`。迁移不回填旧 facts fingerprint，避免把不可验证历史误标记为 fresh。
