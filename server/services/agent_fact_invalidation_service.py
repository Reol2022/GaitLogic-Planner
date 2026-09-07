"""Explicit mutation hooks for Agent session facts.

Mutation services call these functions after a successful transaction.  The
store is optional and failures must never affect Garmin, log or plan writes.
"""
from __future__ import annotations

import logging

from server.agent.session_facts import (
    GARMIN_SYNC_INVALIDATES, LOG_MUTATION_INVALIDATES, PLAN_MUTATION_INVALIDATES, SESSION_FACTS,
)

logger = logging.getLogger(__name__)


def _invalidate(user_id: int, keys: set[str]) -> None:
    try:
        SESSION_FACTS.invalidate(user_id=user_id, keys=keys)
    except Exception:
        logger.warning("agent_fact_invalidation_failed event=mutation")


def after_garmin_sync(user_id: int) -> None:
    _invalidate(user_id, GARMIN_SYNC_INVALIDATES)


def after_training_log_mutation(user_id: int) -> None:
    _invalidate(user_id, LOG_MUTATION_INVALIDATES)


def after_plan_mutation(user_id: int) -> None:
    _invalidate(user_id, PLAN_MUTATION_INVALIDATES)
