from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import ceil
from time import perf_counter
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from planner_core.database.models import (
    CoachConversation,
    CoachMessage,
    PlanAdjustmentDraft,
    PlannedWorkout,
    TrainingCycle,
    WeeklyReviewReport,
)
from planner_core.config import get_settings
from server.common.exceptions import BadRequestError, ConflictError, NotFoundError
from server.observability.tracing import NOOP_TRACER, SafeTracer, active_trace_handle
from server.schemas.coach_agent import CoachQueryRequest, CoachQueryResponse
from server.schemas.coach_conversation import (
    CoachConversationCreate,
    CoachConversationMessageCreate,
    CoachConversationMessageResult,
    CoachConversationPage,
    CoachConversationRead,
    CoachConversationTurnStatusRead,
    CoachConversationUpdate,
    CoachMessagePage,
    CoachMessageRead,
    CoachProgressItem,
    CoachTurnProgressRead,
)
from server.services.coach_agent_query_service import CoachAgentQueryService
from server.services.conversation_context_builder import ConversationContextBuilder
from server.services.conversation_summary import ConversationSummarizer, ConversationSummary
from server.services.coach_turn_progress import CoachTurnStage, safe_facts_summary, stage_is_terminal


MAX_TITLE_CHARS = 36


class CoachConversationService:
    """Persistent, user-isolated orchestration around the existing read-only Coach."""

    def __init__(
        self,
        db: Session,
        *,
        coach_service_factory=CoachAgentQueryService,
        context_builder: ConversationContextBuilder | None = None,
        summarizer: ConversationSummarizer | None = None,
        tracer: SafeTracer | None = None,
        now=None,
    ) -> None:
        self.db = db
        self.coach_service_factory = coach_service_factory
        settings = get_settings()
        self.context_builder = context_builder or ConversationContextBuilder(
            max_messages=settings.coach_conversation_history_messages,
            token_budget=settings.coach_conversation_history_token_budget,
            summary_token_budget=settings.coach_conversation_summary_token_budget,
        )
        self.summarizer = summarizer or ConversationSummarizer()
        self.processing_timeout = timedelta(
            seconds=settings.coach_conversation_turn_timeout_seconds
        )
        self.tracer = tracer or NOOP_TRACER
        self.now = now or (lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def create(self, *, user_id: int, payload: CoachConversationCreate) -> CoachConversationRead:
        title = (payload.title or "新对话").strip() or "新对话"
        conversation = CoachConversation(user_id=user_id, title=title, status="active")
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return self._conversation_read(conversation, message_count=0)

    def list(
        self, *, user_id: int, page: int, page_size: int, status: str | None = None
    ) -> CoachConversationPage:
        stmt = select(CoachConversation).where(CoachConversation.user_id == user_id)
        count_stmt = select(func.count()).select_from(CoachConversation).where(CoachConversation.user_id == user_id)
        if status:
            stmt = stmt.where(CoachConversation.status == status)
            count_stmt = count_stmt.where(CoachConversation.status == status)
        total = int(self.db.scalar(count_stmt) or 0)
        conversations = list(
            self.db.scalars(
                stmt.order_by(CoachConversation.last_message_at.desc(), CoachConversation.updated_at.desc(), CoachConversation.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        ids = [item.id for item in conversations]
        counts: dict[int, int] = {}
        if ids:
            counts = dict(
                self.db.execute(
                    select(CoachMessage.conversation_id, func.count())
                    .where(CoachMessage.conversation_id.in_(ids))
                    .group_by(CoachMessage.conversation_id)
                ).all()
            )
        return CoachConversationPage(
            items=[self._conversation_read(item, message_count=int(counts.get(item.id, 0))) for item in conversations],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get(self, *, user_id: int, conversation_id: str) -> CoachConversationRead:
        conversation = self._get_conversation(user_id=user_id, public_id=conversation_id)
        count = int(self.db.scalar(select(func.count()).select_from(CoachMessage).where(CoachMessage.conversation_id == conversation.id)) or 0)
        return self._conversation_read(conversation, message_count=count)

    def update(
        self, *, user_id: int, conversation_id: str, payload: CoachConversationUpdate
    ) -> CoachConversationRead:
        conversation = self._get_conversation(user_id=user_id, public_id=conversation_id, lock=True)
        if payload.title is not None:
            conversation.title = payload.title.strip()
        if payload.status is not None:
            conversation.status = payload.status
        self.db.commit()
        self.db.refresh(conversation)
        count = int(self.db.scalar(select(func.count()).select_from(CoachMessage).where(CoachMessage.conversation_id == conversation.id)) or 0)
        return self._conversation_read(conversation, message_count=count)

    def delete(self, *, user_id: int, conversation_id: str) -> None:
        conversation = self._get_conversation(user_id=user_id, public_id=conversation_id, lock=True)
        self.db.delete(conversation)
        self.db.commit()

    def list_messages(
        self, *, user_id: int, conversation_id: str, page: int, page_size: int
    ) -> CoachMessagePage:
        conversation = self._get_conversation(user_id=user_id, public_id=conversation_id)
        total = int(self.db.scalar(select(func.count()).select_from(CoachMessage).where(CoachMessage.conversation_id == conversation.id)) or 0)
        page_count = ceil(total / page_size) if total else 0
        # Chat clients need the newest bounded window first. Items within each
        # page remain chronological, so older pages can be prepended safely.
        offset = max(total - page * page_size, 0)
        messages = []
        if page <= page_count:
            messages = list(
                self.db.scalars(
                    select(CoachMessage)
                    .where(CoachMessage.conversation_id == conversation.id)
                    .order_by(CoachMessage.sequence_no)
                    .offset(offset)
                    .limit(page_size)
                )
            )
        return CoachMessagePage(
            items=[self._message_read(item) for item in messages],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_turn_status(
        self, *, user_id: int, conversation_id: str, client_turn_id: str
    ) -> CoachConversationTurnStatusRead:
        """Read a stored turn snapshot without lifecycle maintenance or writes."""
        conversation = self._get_conversation(user_id=user_id, public_id=conversation_id)
        user_message = self.db.scalar(
            select(CoachMessage).where(
                CoachMessage.conversation_id == conversation.id,
                CoachMessage.client_turn_id == client_turn_id,
                CoachMessage.role == "user",
            )
        )
        if user_message is None:
            raise NotFoundError("Coach conversation turn not found.")
        assistant_message = self.db.scalar(
            select(CoachMessage)
            .where(CoachMessage.reply_to_message_id == user_message.id)
            .order_by(CoachMessage.sequence_no.desc())
        )
        if assistant_message is None:
            raise NotFoundError("Coach conversation turn not found.")
        return CoachConversationTurnStatusRead(
            conversation_id=conversation_id,
            message_id=assistant_message.public_id,
            message_status=assistant_message.status,
            client_turn_id=client_turn_id,
            progress=self._progress_read(assistant_message),
        )

    def send_message(
        self,
        *,
        user_id: int,
        conversation_id: str,
        payload: CoachConversationMessageCreate,
    ) -> CoachConversationMessageResult:
        self._verify_context_ref(user_id=user_id, context_ref=payload.context_ref)
        handle = active_trace_handle() or self.tracer.start_trace()
        with self.tracer.span(
            handle,
            component="conversation",
            operation="message.submit",
            metadata={"conversation_status": "active", "message_role": "user"},
            root=active_trace_handle() is None,
        ) as span:
            user_message, assistant_message, replay, lease_id = self._reserve_turn(
                user_id=user_id, conversation_id=conversation_id, payload=payload
            )
            if replay:
                return self._result_from_message(conversation_id, assistant_message)
            try:
                self._update_turn_progress(
                    assistant_message_id=assistant_message.id,
                    client_turn_id=payload.client_turn_id,
                    lease_id=lease_id,
                    stage=CoachTurnStage.CONTEXT_LOADING,
                )
                conversation = self.db.get(CoachConversation, user_message.conversation_id)
                if conversation is None:
                    raise NotFoundError("Conversation was deleted before context could be built.")
                existing_summary = ConversationSummary.from_json(conversation.context_summary_json)
                history = list(
                    self.db.scalars(
                        select(CoachMessage)
                        .where(
                            CoachMessage.conversation_id == user_message.conversation_id,
                            CoachMessage.sequence_no < user_message.sequence_no,
                            CoachMessage.sequence_no > existing_summary.through_sequence,
                            CoachMessage.status == "completed",
                        )
                        .order_by(CoachMessage.sequence_no)
                    )
                )
                with self.tracer.span(
                    handle,
                    component="conversation",
                    operation="context.build",
                    metadata={"message_count_bucket": self._bucket(len(history))},
                ) as context_span:
                    context = self.context_builder.build(
                        history,
                        summary_content=existing_summary.render() if existing_summary.version else None,
                    )
                    summary_generated = False
                    summary_failed = False
                    if context.omitted_messages:
                        refreshed_summary, summary_generated, summary_failed = self._refresh_context_summary(
                            conversation_id=user_message.conversation_id,
                            messages=context.omitted_messages,
                        )
                        context = self.context_builder.build(
                            history,
                            summary_content=refreshed_summary.render()
                            if refreshed_summary.version
                            else None,
                        )
                    context_span.add_metadata(
                        context_token_count=context.total_estimated_tokens,
                        conversation_recent_message_count=len(context.messages),
                        conversation_recent_token_count=context.estimated_tokens,
                        conversation_summary_used=bool(context.summary_content),
                        conversation_summary_token_count=context.summary_estimated_tokens,
                        conversation_summary_generated=summary_generated,
                        conversation_summary_failed=summary_failed,
                    )
                with self.tracer.span(handle, component="conversation", operation="coach.execute"):
                    coach_payload = CoachQueryRequest(
                        message=user_message.content or "",
                        conversation_context=context.messages,
                        conversation_summary=context.summary_content,
                    )
                    progress_callback = lambda stage, results=None: self._update_turn_progress(
                        assistant_message_id=assistant_message.id,
                        client_turn_id=payload.client_turn_id,
                        lease_id=lease_id,
                        stage=CoachTurnStage(stage),
                        summary=safe_facts_summary(results or [])
                        if stage == CoachTurnStage.FACTS_READY.value
                        else None,
                    )
                    coach_service = self.coach_service_factory(self.db, tracer=self.tracer)
                    try:
                        response = coach_service.query(
                            user_id=user_id,
                            payload=coach_payload,
                            progress_callback=progress_callback,
                        )
                    except TypeError as exc:
                        # Keep third-party/offline test adapters written before
                        # v1.2.5 compatible; the production service always
                        # accepts the callback. Do not swallow unrelated errors.
                        if "progress_callback" not in str(exc):
                            raise
                        response = coach_service.query(user_id=user_id, payload=coach_payload)
                if response.status in {"SUCCEEDED", "DEGRADED"} and response.answer:
                    finalized = self._complete_turn(
                        assistant_message_id=assistant_message.id,
                        client_turn_id=payload.client_turn_id,
                        lease_id=lease_id,
                        response=response,
                    )
                else:
                    finalized = self._fail_turn(
                        assistant_message_id=assistant_message.id,
                        client_turn_id=payload.client_turn_id,
                        lease_id=lease_id,
                        response=response,
                    )
                    span.set_status("FAILED", error_code="COACH_RESPONSE_UNAVAILABLE")
                self.db.expire_all()
                fresh = self.db.get(CoachMessage, assistant_message.id)
                if fresh is None:
                    raise NotFoundError("Conversation was deleted before the response could be saved.")
                if not finalized:
                    span.set_status("FAILED", error_code="CONVERSATION_TURN_SUPERSEDED")
                return self._result_from_message(conversation_id, fresh)
            except Exception:
                self._fail_turn(
                    assistant_message_id=assistant_message.id,
                    client_turn_id=payload.client_turn_id,
                    lease_id=lease_id,
                    response=None,
                )
                span.set_status("FAILED", error_code="CONVERSATION_EXECUTION_FAILED")
                raise

    def _refresh_context_summary(
        self,
        *,
        conversation_id: int,
        messages: list[CoachMessage],
    ) -> tuple[ConversationSummary, bool, bool]:
        """Incrementally summarize only completed messages leaving the window.

        The summary lease mirrors turn leases: a delayed summary can neither
        overwrite a newer one nor recreate a conversation deleted in between.
        Summary errors deliberately fall back to the existing recent window.
        """
        if not messages:
            return ConversationSummary(), False, False
        target_sequence = max(item.sequence_no for item in messages)
        conversation = self.db.scalar(
            select(CoachConversation)
            .where(CoachConversation.id == conversation_id)
            .with_for_update()
        )
        if conversation is None:
            return ConversationSummary(), False, True
        previous = ConversationSummary.from_json(conversation.context_summary_json)
        if conversation.context_summary_lease_id:
            return previous, False, False
        source_messages = list(
            self.db.scalars(
                select(CoachMessage)
                .where(
                    CoachMessage.conversation_id == conversation.id,
                    CoachMessage.status == "completed",
                    CoachMessage.sequence_no > previous.through_sequence,
                    CoachMessage.sequence_no <= target_sequence,
                )
                .order_by(CoachMessage.sequence_no)
            )
        )
        if not source_messages:
            return previous, False, False
        lease_id = str(uuid4())
        conversation.context_summary_status = "GENERATING"
        conversation.context_summary_lease_id = lease_id
        conversation.context_summary_started_at = self.now()
        self.db.commit()
        started = perf_counter()
        try:
            generated = self.summarizer.summarize(
                previous=previous,
                messages=source_messages,
                token_budget=self.context_builder.summary_token_budget,
            )
        except Exception:
            self._mark_summary_failed(conversation_id=conversation_id, lease_id=lease_id)
            return previous, False, True
        conversation = self.db.scalar(
            select(CoachConversation)
            .where(CoachConversation.id == conversation_id)
            .with_for_update()
        )
        if conversation is None or conversation.context_summary_lease_id != lease_id:
            self.db.rollback()
            return previous, False, True
        conversation.context_summary_json = generated.to_json()
        conversation.context_summary_version = generated.version
        conversation.context_summary_through_sequence = generated.through_sequence
        conversation.context_summary_updated_at = self.now()
        conversation.context_summary_status = "IDLE"
        conversation.context_summary_lease_id = None
        conversation.context_summary_started_at = None
        self.db.commit()
        # This trace carries only bounded counts/timing, never summary text.
        handle = active_trace_handle()
        if handle is not None:
            with self.tracer.span(
                handle,
                component="conversation",
                operation="summary.refresh",
                metadata={
                    "conversation_summary_generated": True,
                    "conversation_summary_token_count": self.context_builder._tokens(generated.render()),
                    "latency": (perf_counter() - started) * 1000,
                },
            ):
                pass
        return generated, True, False

    def _mark_summary_failed(self, *, conversation_id: int, lease_id: str) -> None:
        conversation = self.db.scalar(
            select(CoachConversation)
            .where(CoachConversation.id == conversation_id)
            .with_for_update()
        )
        if conversation is None or conversation.context_summary_lease_id != lease_id:
            self.db.rollback()
            return
        conversation.context_summary_status = "FAILED"
        conversation.context_summary_lease_id = None
        conversation.context_summary_started_at = None
        self.db.commit()

    def _reserve_turn(
        self, *, user_id: int, conversation_id: str, payload: CoachConversationMessageCreate
    ) -> tuple[CoachMessage, CoachMessage, bool, str | None]:
        conversation = self._get_conversation(user_id=user_id, public_id=conversation_id, lock=True)
        if conversation.status != "active":
            raise BadRequestError("Archived conversations cannot receive new messages.")
        now = self.now()
        if self._is_stale_processing(conversation, now):
            self._expire_stale_turn(conversation=conversation, now=now)
        user_message = self.db.scalar(
            select(CoachMessage).where(
                CoachMessage.conversation_id == conversation.id,
                CoachMessage.client_turn_id == payload.client_turn_id,
            )
        )
        if user_message is not None:
            if user_message.role != "user" or user_message.content != payload.message:
                raise BadRequestError("client_turn_id cannot be reused with a different message.")
            assistant_message = self.db.scalar(
                select(CoachMessage)
                .where(CoachMessage.reply_to_message_id == user_message.id)
                .order_by(CoachMessage.sequence_no.desc())
            )
            if assistant_message is not None and assistant_message.status == "completed":
                return user_message, assistant_message, True, None
            if conversation.processing_turn_id:
                raise ConflictError("This conversation is already generating a Coach response.")
            if assistant_message is None:
                assistant_message = CoachMessage(
                    conversation_id=conversation.id,
                    role="assistant",
                    status="pending",
                    sequence_no=user_message.sequence_no + 1,
                    reply_to_message_id=user_message.id,
                )
                self.db.add(assistant_message)
            else:
                assistant_message.status = "pending"
                assistant_message.content = None
                assistant_message.response_kind = None
                assistant_message.response_metadata_json = None
                assistant_message.evidence_refs_json = None
                assistant_message.trace_id = None
                assistant_message.completed_at = None
                assistant_message.progress_stage = CoachTurnStage.QUEUED.value
                assistant_message.progress_sequence = 0
                assistant_message.progress_summary_json = None
                assistant_message.progress_updated_at = now
            lease_id = str(uuid4())
            conversation.processing_turn_id = payload.client_turn_id
            conversation.processing_lease_id = lease_id
            conversation.processing_started_at = now
            self.db.commit()
            self.db.refresh(assistant_message)
            return user_message, assistant_message, False, lease_id
        if conversation.processing_turn_id:
            raise ConflictError("This conversation is already generating a Coach response.")
        max_sequence = int(
            self.db.scalar(
                select(func.max(CoachMessage.sequence_no)).where(CoachMessage.conversation_id == conversation.id)
            )
            or 0
        )
        user_message = CoachMessage(
            conversation_id=conversation.id,
            role="user",
            content=payload.message,
            status="completed",
            sequence_no=max_sequence + 1,
            client_turn_id=payload.client_turn_id,
            completed_at=now,
        )
        assistant_message = CoachMessage(
            conversation_id=conversation.id,
            role="assistant",
            status="pending",
            sequence_no=max_sequence + 2,
            progress_stage=CoachTurnStage.QUEUED.value,
            progress_sequence=0,
            progress_updated_at=now,
        )
        self.db.add_all([user_message, assistant_message])
        self.db.flush()
        assistant_message.reply_to_message_id = user_message.id
        lease_id = str(uuid4())
        conversation.processing_turn_id = payload.client_turn_id
        conversation.processing_lease_id = lease_id
        conversation.processing_started_at = now
        conversation.last_message_at = now
        if conversation.title == "新对话":
            conversation.title = self._title_for(payload.message)
        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(assistant_message)
        return user_message, assistant_message, False, lease_id

    def _update_turn_progress(
        self,
        *,
        assistant_message_id: int,
        client_turn_id: str,
        lease_id: str | None,
        stage: CoachTurnStage,
        summary: list[dict[str, str | int]] | None = None,
    ) -> bool:
        """Atomically persist an in-flight stage only for the active lease.

        A separate GET request may read this committed snapshot while the
        original POST is blocked on a provider.  The same lease conditions used
        by finalization ensure a delayed attempt cannot overwrite a newer one.
        """
        if stage_is_terminal(stage):
            return False
        self.db.expire_all()
        message = self.db.scalar(
            select(CoachMessage).where(CoachMessage.id == assistant_message_id).with_for_update()
        )
        if message is None:
            return False
        conversation = self.db.scalar(
            select(CoachConversation)
            .where(CoachConversation.id == message.conversation_id)
            .with_for_update()
        )
        if (
            conversation is None
            or message.status != "pending"
            or conversation.processing_turn_id != client_turn_id
            or conversation.processing_lease_id != lease_id
        ):
            self.db.rollback()
            return False
        message.progress_stage = stage.value
        message.progress_sequence = int(message.progress_sequence or 0) + 1
        if summary is not None:
            message.progress_summary_json = summary
        message.progress_updated_at = self.now()
        self.db.commit()
        return True

    def _complete_turn(
        self,
        *,
        assistant_message_id: int,
        client_turn_id: str,
        lease_id: str | None,
        response: CoachQueryResponse,
    ) -> bool:
        return self._finalize_turn(
            assistant_message_id=assistant_message_id,
            client_turn_id=client_turn_id,
            lease_id=lease_id,
            response=response,
            succeeded=True,
        )

    def _fail_turn(
        self,
        *,
        assistant_message_id: int,
        client_turn_id: str,
        lease_id: str | None,
        response: CoachQueryResponse | None,
    ) -> bool:
        return self._finalize_turn(
            assistant_message_id=assistant_message_id,
            client_turn_id=client_turn_id,
            lease_id=lease_id,
            response=response,
            succeeded=False,
        )

    def _finalize_turn(
        self,
        *,
        assistant_message_id: int,
        client_turn_id: str,
        lease_id: str | None,
        response: CoachQueryResponse | None,
        succeeded: bool,
    ) -> bool:
        # Re-read under database locks.  This makes the lease check effective
        # across multiple Gunicorn/Uvicorn workers, not just within one Python
        # process.  A delayed provider response is never allowed to clear a
        # newer turn's processing lock or overwrite its assistant message.
        self.db.expire_all()
        message = self.db.scalar(
            select(CoachMessage)
            .where(CoachMessage.id == assistant_message_id)
            .with_for_update()
        )
        if message is None:
            return False
        conversation = self.db.scalar(
            select(CoachConversation)
            .where(CoachConversation.id == message.conversation_id)
            .with_for_update()
        )
        if conversation is None:
            return False
        if (
            message.status != "pending"
            or conversation.processing_turn_id != client_turn_id
            or conversation.processing_lease_id != lease_id
        ):
            self.db.rollback()
            return False
        if succeeded and response is not None:
            message.content = response.answer
            message.status = "completed"
            message.response_kind = response.status
            message.trace_id = str(response.trace_id)
            message.evidence_refs_json = [item.model_dump(mode="json") for item in response.knowledge_references]
            message.response_metadata_json = response.model_dump(
                mode="json", exclude={"answer", "knowledge_references"}
            )
        else:
            message.status = "failed"
            message.response_kind = response.status if response else "FAILED"
            message.trace_id = str(response.trace_id) if response else None
            message.response_metadata_json = (
                response.model_dump(mode="json", exclude={"answer", "knowledge_references"})
                if response
                else None
            )
        message.progress_stage = (
            CoachTurnStage.COMPLETED.value if succeeded else CoachTurnStage.FAILED.value
        )
        message.progress_sequence = int(message.progress_sequence or 0) + 1
        message.progress_updated_at = self.now()
        message.completed_at = self.now()
        if succeeded:
            conversation.last_message_at = message.completed_at
        conversation.processing_turn_id = None
        conversation.processing_lease_id = None
        conversation.processing_started_at = None
        self.db.commit()
        return True

    def _expire_stale_turn(self, *, conversation: CoachConversation, now: datetime) -> None:
        """Release an expired lease without silently leaving a pending reply."""
        stale_turn_id = conversation.processing_turn_id
        if stale_turn_id:
            user_message = self.db.scalar(
                select(CoachMessage).where(
                    CoachMessage.conversation_id == conversation.id,
                    CoachMessage.client_turn_id == stale_turn_id,
                    CoachMessage.role == "user",
                )
            )
            if user_message is not None:
                assistant_message = self.db.scalar(
                    select(CoachMessage)
                    .where(CoachMessage.reply_to_message_id == user_message.id)
                    .with_for_update()
                )
                if assistant_message is not None and assistant_message.status == "pending":
                    assistant_message.status = "failed"
                    assistant_message.response_kind = "INTERRUPTED"
                    assistant_message.response_metadata_json = {"error_code": "COACH_TURN_LEASE_EXPIRED"}
                    assistant_message.completed_at = now
                    assistant_message.progress_stage = CoachTurnStage.FAILED.value
                    assistant_message.progress_sequence = int(assistant_message.progress_sequence or 0) + 1
                    assistant_message.progress_updated_at = now
        conversation.processing_turn_id = None
        conversation.processing_lease_id = None
        conversation.processing_started_at = None

    def _is_stale_processing(self, conversation: CoachConversation, now: datetime) -> bool:
        if not conversation.processing_turn_id:
            return False
        if conversation.processing_started_at is None:
            return True
        return now - conversation.processing_started_at >= self.processing_timeout

    def _get_conversation(self, *, user_id: int, public_id: str, lock: bool = False) -> CoachConversation:
        stmt = select(CoachConversation).where(
            CoachConversation.public_id == public_id,
            CoachConversation.user_id == user_id,
        )
        if lock:
            stmt = stmt.with_for_update()
        conversation = self.db.scalar(stmt)
        if conversation is None:
            raise NotFoundError("Coach conversation not found.")
        return conversation

    def _verify_context_ref(self, *, user_id: int, context_ref) -> None:
        if context_ref is None:
            return
        try:
            resource_id = int(context_ref.id)
        except ValueError as exc:
            raise BadRequestError("Conversation context reference is invalid.") from exc
        model = {
            "workout": PlannedWorkout,
            "training_cycle": TrainingCycle,
            "weekly_review": WeeklyReviewReport,
            "proposal": PlanAdjustmentDraft,
        }[context_ref.kind]
        row = self.db.scalar(select(model.id).where(model.id == resource_id, model.user_id == user_id))
        if row is None:
            raise NotFoundError("Conversation context reference not found.")

    @staticmethod
    def _title_for(message: str) -> str:
        normalized = " ".join(message.split())
        return normalized[:MAX_TITLE_CHARS] or "新对话"

    @staticmethod
    def _bucket(value: int) -> str:
        if value == 0:
            return "0"
        if value <= 4:
            return "1_4"
        if value <= 10:
            return "5_10"
        return "11_plus"

    @staticmethod
    def _conversation_read(item: CoachConversation, *, message_count: int) -> CoachConversationRead:
        return CoachConversationRead(
            id=item.public_id,
            title=item.title,
            status=item.status,
            created_at=item.created_at,
            updated_at=item.updated_at,
            last_message_at=item.last_message_at,
            message_count=message_count,
        )

    @staticmethod
    def _message_read(item: CoachMessage) -> CoachMessageRead:
        metadata = item.response_metadata_json or {}
        return CoachMessageRead(
            id=item.public_id,
            role=item.role,
            content=item.content,
            status=item.status,
            sequence_no=item.sequence_no,
            response_kind=item.response_kind,
            evidence_refs=item.evidence_refs_json or [],
            proposal_ref=item.proposal_ref,
            trace_id=item.trace_id,
            created_at=item.created_at,
            completed_at=item.completed_at,
            warnings=metadata.get("warnings", []),
            limitations=metadata.get("limitations", []),
            tool_calls=metadata.get("tool_calls", []),
            today_recommendation=metadata.get("today_recommendation"),
            training_fact_context=metadata.get("training_fact_context"),
            progress=CoachConversationService._progress_read(item),
        )

    @staticmethod
    def _progress_read(item: CoachMessage) -> CoachTurnProgressRead:
        stage = CoachTurnStage(item.progress_stage or CoachTurnStage.QUEUED.value)
        raw_summary = item.progress_summary_json or []
        summary = [
            CoachProgressItem.model_validate(value)
            for value in raw_summary
            if isinstance(value, dict)
        ]
        return CoachTurnProgressRead(
            stage=stage.value,
            sequence=int(item.progress_sequence or 0),
            updated_at=item.progress_updated_at,
            summary=summary,
            terminal=stage_is_terminal(stage),
        )

    def _result_from_message(
        self, conversation_id: str, message: CoachMessage
    ) -> CoachConversationMessageResult:
        if message.status != "completed":
            return CoachConversationMessageResult(
                conversation_id=conversation_id,
                message_id=message.public_id,
                status=message.status,
                content=None,
            )
        payload: dict[str, Any] = dict(message.response_metadata_json or {})
        payload["answer"] = message.content
        payload["knowledge_references"] = message.evidence_refs_json or []
        return CoachConversationMessageResult(
            conversation_id=conversation_id,
            message_id=message.public_id,
            status="completed",
            content=message.content,
            response=CoachQueryResponse.model_validate(payload),
        )
