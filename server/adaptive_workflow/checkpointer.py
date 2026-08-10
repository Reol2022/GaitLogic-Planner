from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from planner_core.database.models import (
    AdaptiveWorkflowCheckpointRecord,
    AdaptiveWorkflowCheckpointWriteRecord,
)


class SQLAlchemyCheckpointSaver(BaseCheckpointSaver[int]):
    """Synchronous LangGraph saver backed by the product SQLAlchemy database."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        super().__init__()
        self.session_factory = session_factory

    @staticmethod
    def _parts(config: dict) -> tuple[str, str, str | None]:
        values = config.get("configurable", {})
        thread_id = str(values.get("thread_id") or "")
        if not thread_id:
            raise ValueError("thread_id is required for adaptive workflow persistence")
        return (
            thread_id,
            str(values.get("checkpoint_ns") or ""),
            str(values["checkpoint_id"]) if values.get("checkpoint_id") else None,
        )

    def get_tuple(self, config: dict) -> CheckpointTuple | None:
        thread_id, namespace, checkpoint_id = self._parts(config)
        with self.session_factory() as db:
            stmt = select(AdaptiveWorkflowCheckpointRecord).where(
                AdaptiveWorkflowCheckpointRecord.thread_id == thread_id,
                AdaptiveWorkflowCheckpointRecord.checkpoint_namespace == namespace,
            )
            if checkpoint_id:
                stmt = stmt.where(AdaptiveWorkflowCheckpointRecord.checkpoint_id == checkpoint_id)
            else:
                stmt = stmt.order_by(AdaptiveWorkflowCheckpointRecord.id.desc()).limit(1)
            row = db.scalar(stmt)
            if row is None:
                return None
            writes = list(
                db.scalars(
                    select(AdaptiveWorkflowCheckpointWriteRecord)
                    .where(
                        AdaptiveWorkflowCheckpointWriteRecord.thread_id == thread_id,
                        AdaptiveWorkflowCheckpointWriteRecord.checkpoint_namespace == namespace,
                        AdaptiveWorkflowCheckpointWriteRecord.checkpoint_id == row.checkpoint_id,
                    )
                    .order_by(AdaptiveWorkflowCheckpointWriteRecord.id)
                )
            )
            saved_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": namespace,
                    "checkpoint_id": row.checkpoint_id,
                }
            }
            parent = (
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": namespace,
                        "checkpoint_id": row.parent_checkpoint_id,
                    }
                }
                if row.parent_checkpoint_id
                else None
            )
            return CheckpointTuple(
                saved_config,
                self.serde.loads_typed((row.checkpoint_type, bytes(row.checkpoint_blob))),
                self.serde.loads_typed((row.metadata_type, bytes(row.metadata_blob))),
                parent,
                [
                    (
                        item.task_id,
                        item.channel,
                        self.serde.loads_typed((item.value_type, bytes(item.value_blob))),
                    )
                    for item in writes
                ],
            )

    def list(
        self,
        config: dict | None,
        *,
        filter: dict[str, Any] | None = None,
        before: dict | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        del filter, before
        if config is None:
            return
        thread_id, namespace, _ = self._parts(config)
        with self.session_factory() as db:
            ids = list(
                db.scalars(
                    select(AdaptiveWorkflowCheckpointRecord.checkpoint_id)
                    .where(
                        AdaptiveWorkflowCheckpointRecord.thread_id == thread_id,
                        AdaptiveWorkflowCheckpointRecord.checkpoint_namespace == namespace,
                    )
                    .order_by(AdaptiveWorkflowCheckpointRecord.id.desc())
                    .limit(limit)
                )
            )
        for checkpoint_id in ids:
            item = self.get_tuple(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": namespace,
                        "checkpoint_id": checkpoint_id,
                    }
                }
            )
            if item is not None:
                yield item

    def put(
        self,
        config: dict,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict,
    ) -> dict:
        del new_versions
        thread_id, namespace, parent_id = self._parts(config)
        checkpoint_id = str(checkpoint["id"])
        checkpoint_type, checkpoint_blob = self.serde.dumps_typed(checkpoint)
        metadata_type, metadata_blob = self.serde.dumps_typed(metadata)
        with self.session_factory.begin() as db:
            existing = db.scalar(
                select(AdaptiveWorkflowCheckpointRecord).where(
                    AdaptiveWorkflowCheckpointRecord.thread_id == thread_id,
                    AdaptiveWorkflowCheckpointRecord.checkpoint_namespace == namespace,
                    AdaptiveWorkflowCheckpointRecord.checkpoint_id == checkpoint_id,
                )
            )
            if existing is None:
                db.add(
                    AdaptiveWorkflowCheckpointRecord(
                        thread_id=thread_id,
                        checkpoint_namespace=namespace,
                        checkpoint_id=checkpoint_id,
                        parent_checkpoint_id=parent_id,
                        checkpoint_type=checkpoint_type,
                        checkpoint_blob=checkpoint_blob,
                        metadata_type=metadata_type,
                        metadata_blob=metadata_blob,
                    )
                )
            else:
                existing.parent_checkpoint_id = parent_id
                existing.checkpoint_type = checkpoint_type
                existing.checkpoint_blob = checkpoint_blob
                existing.metadata_type = metadata_type
                existing.metadata_blob = metadata_blob
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": namespace,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: dict,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id, namespace, checkpoint_id = self._parts(config)
        if checkpoint_id is None:
            raise ValueError("checkpoint_id is required for pending writes")
        with self.session_factory.begin() as db:
            for index, (channel, value) in enumerate(writes):
                existing = db.scalar(
                    select(AdaptiveWorkflowCheckpointWriteRecord).where(
                        AdaptiveWorkflowCheckpointWriteRecord.thread_id == thread_id,
                        AdaptiveWorkflowCheckpointWriteRecord.checkpoint_namespace == namespace,
                        AdaptiveWorkflowCheckpointWriteRecord.checkpoint_id == checkpoint_id,
                        AdaptiveWorkflowCheckpointWriteRecord.task_id == task_id,
                        AdaptiveWorkflowCheckpointWriteRecord.task_path == task_path,
                        AdaptiveWorkflowCheckpointWriteRecord.write_index == index,
                    )
                )
                value_type, value_blob = self.serde.dumps_typed(value)
                if existing is None:
                    db.add(
                        AdaptiveWorkflowCheckpointWriteRecord(
                            thread_id=thread_id,
                            checkpoint_namespace=namespace,
                            checkpoint_id=checkpoint_id,
                            task_id=task_id,
                            task_path=task_path,
                            write_index=index,
                            channel=channel,
                            value_type=value_type,
                            value_blob=value_blob,
                        )
                    )
                else:
                    existing.channel = channel
                    existing.value_type = value_type
                    existing.value_blob = value_blob

    def delete_thread(self, thread_id: str) -> None:
        with self.session_factory.begin() as db:
            db.execute(
                delete(AdaptiveWorkflowCheckpointWriteRecord).where(
                    AdaptiveWorkflowCheckpointWriteRecord.thread_id == thread_id
                )
            )
            db.execute(
                delete(AdaptiveWorkflowCheckpointRecord).where(
                    AdaptiveWorkflowCheckpointRecord.thread_id == thread_id
                )
            )
