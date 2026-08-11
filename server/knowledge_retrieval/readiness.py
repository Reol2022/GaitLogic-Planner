from __future__ import annotations

from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from planner_core.config import Settings
from server.agent.providers.security import validate_provider_base_url
from server.agent.tools.knowledge_tools import build_configured_knowledge_tool
from server.knowledge_retrieval.corpus_service import KnowledgeCorpusService
from server.knowledge_retrieval.embeddings.security import validate_embedding_base_url
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from server.knowledge_retrieval.sparse.index_service import Bm25IndexService
from server.knowledge_retrieval.vector_stores.factory import vector_store_name


class ReadinessExitCode(IntEnum):
    READY = 0
    FEATURE_DISABLED = 2
    CONFIG_INCOMPLETE = 3
    INDEX_MISSING_OR_STALE = 4
    PROVIDER_CONFIGURATION_INVALID = 5
    CORPUS_INVALID = 6
    SECURITY_BOUNDARY_FAILED = 7


class ReadinessCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["PASS", "FAIL", "DISABLED"]
    code: str


class CoachRagReadinessReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    exit_code: ReadinessExitCode
    coach_enabled: bool
    knowledge_enabled: bool
    chat_provider: str
    thinking_mode: str
    response_format_mode: str
    embedding_provider: str
    embedding_dimensions: int | None
    index_id_configured: bool
    checks: list[ReadinessCheck] = Field(default_factory=list)


class CoachRagReadinessService:
    """Validate deploy-time RAG dependencies without making network requests."""

    def __init__(
        self,
        settings: Settings,
        *,
        repository_root: Path | None = None,
        now: datetime | None = None,
    ) -> None:
        self.settings = settings
        self.repository_root = (repository_root or Path.cwd()).resolve()
        self.now = now or datetime.now(timezone.utc)
        self.checks: list[ReadinessCheck] = []

    def _check(
        self,
        name: str,
        passed: bool,
        code: str,
        *,
        disabled: bool = False,
    ) -> bool:
        self.checks.append(
            ReadinessCheck(
                name=name,
                status="DISABLED" if disabled else "PASS" if passed else "FAIL",
                code=code,
            )
        )
        return passed

    def _report(self, exit_code: ReadinessExitCode) -> CoachRagReadinessReport:
        return CoachRagReadinessReport(
            ready=exit_code == ReadinessExitCode.READY,
            exit_code=exit_code,
            coach_enabled=self.settings.coach_agent_enabled,
            knowledge_enabled=self.settings.coach_agent_knowledge_retrieval_enabled,
            chat_provider=self.settings.coach_agent_provider,
            thinking_mode=self.settings.coach_agent_thinking_mode,
            response_format_mode=self.settings.coach_agent_response_format_mode,
            embedding_provider=self.settings.knowledge_embedding_provider,
            embedding_dimensions=self.settings.knowledge_embedding_dimensions,
            index_id_configured=bool(
                self.settings.coach_agent_knowledge_bm25_index_id
                if self.settings.knowledge_retrieval_strategy == "bm25"
                else self.settings.coach_agent_knowledge_index_id
            ),
            checks=self.checks,
        )

    def _provider_configuration_valid(self, *, requires_embedding: bool) -> bool:
        chat_complete = all(
            (
                self.settings.coach_agent_provider,
                self.settings.coach_agent_api_key,
                self.settings.coach_agent_base_url,
                self.settings.coach_agent_model,
            )
        )
        embedding_complete = all(
            (
                self.settings.knowledge_embedding_provider,
                self.settings.knowledge_embedding_api_key,
                self.settings.knowledge_embedding_base_url,
                self.settings.knowledge_embedding_model,
                self.settings.knowledge_embedding_dimensions,
            )
        )
        if not self._check(
            "chat_configuration",
            bool(chat_complete),
            "CHAT_CONFIGURED" if chat_complete else "CHAT_CONFIG_INCOMPLETE",
        ):
            return False
        if requires_embedding and not self._check(
            "embedding_configuration",
            bool(embedding_complete),
            (
                "EMBEDDING_CONFIGURED"
                if embedding_complete
                else "EMBEDDING_CONFIG_INCOMPLETE"
            ),
        ):
            return False
        if not requires_embedding:
            self._check("embedding_configuration", True, "EMBEDDING_NOT_REQUIRED", disabled=True)
        allow_chat_local = (
            self.settings.app_env.lower() == "development"
            and self.settings.coach_agent_allow_local_provider_in_development
        )
        allow_embedding_local = (
            self.settings.app_env.lower() == "development"
            and self.settings.knowledge_embedding_allow_local_provider_in_development
        )
        try:
            validate_provider_base_url(
                self.settings.coach_agent_base_url,
                allow_local_development=allow_chat_local,
            )
            if requires_embedding:
                validate_embedding_base_url(
                    self.settings.knowledge_embedding_base_url,
                    allow_local_development=allow_embedding_local,
                )
        except ValueError:
            self._check("provider_urls", False, "PROVIDER_URL_INVALID")
            return False
        self._check("provider_urls", True, "PROVIDER_URLS_SAFE")
        return True

    def run(self, *, require_enabled: bool = False) -> CoachRagReadinessReport:
        coach_enabled = self.settings.coach_agent_enabled
        knowledge_enabled = self.settings.coach_agent_knowledge_retrieval_enabled
        self._check(
            "coach_feature",
            coach_enabled,
            "COACH_ENABLED" if coach_enabled else "COACH_DISABLED",
            disabled=not coach_enabled,
        )
        self._check(
            "knowledge_feature",
            knowledge_enabled,
            "KNOWLEDGE_ENABLED" if knowledge_enabled else "KNOWLEDGE_DISABLED",
            disabled=not knowledge_enabled,
        )
        if not coach_enabled or not knowledge_enabled:
            return self._report(
                ReadinessExitCode.FEATURE_DISABLED
                if require_enabled
                else ReadinessExitCode.READY
            )
        is_bm25_only = self.settings.knowledge_retrieval_strategy == "bm25"
        uses_bm25 = self.settings.knowledge_retrieval_strategy in {"bm25", "hybrid", "rerank"}
        embedding_enabled = self.settings.knowledge_embedding_enabled
        self._check(
            "embedding_feature",
            embedding_enabled or is_bm25_only,
            (
                "EMBEDDING_ENABLED" if embedding_enabled else "EMBEDDING_NOT_REQUIRED"
                if is_bm25_only
                else "EMBEDDING_DISABLED"
            ),
            disabled=is_bm25_only or not embedding_enabled,
        )
        if not embedding_enabled and not is_bm25_only:
            return self._report(ReadinessExitCode.CONFIG_INCOMPLETE)
        if self.settings.coach_agent_thinking_mode == "enabled":
            self._check(
                "thinking_mode",
                False,
                "THINKING_MODE_UNSUPPORTED",
            )
            return self._report(
                ReadinessExitCode.PROVIDER_CONFIGURATION_INVALID
            )
        self._check("thinking_mode", True, "THINKING_MODE_SAFE")
        if self.settings.knowledge_retrieval_strategy == "rerank":
            reranker_ready = bool(
                self.settings.knowledge_reranker_enabled
                and self.settings.knowledge_reranker_effective_api_key
            )
            if not self._check(
                "reranker_configuration",
                reranker_ready,
                "RERANKER_CONFIGURED" if reranker_ready else "RERANKER_INCOMPLETE",
            ):
                return self._report(ReadinessExitCode.CONFIG_INCOMPLETE)
        if not self._provider_configuration_valid(requires_embedding=not is_bm25_only):
            if any(
                item.code.endswith("INCOMPLETE")
                for item in self.checks
                if item.status == "FAIL"
            ):
                return self._report(ReadinessExitCode.CONFIG_INCOMPLETE)
            return self._report(ReadinessExitCode.PROVIDER_CONFIGURATION_INVALID)
        try:
            corpus = KnowledgeCorpusService(
                repository_root=self.repository_root
            ).validate()
        except Exception:
            self._check("corpus", False, "CORPUS_INVALID")
            return self._report(ReadinessExitCode.CORPUS_INVALID)
        self._check("corpus", True, "CORPUS_VALID")

        index_id = (
            self.settings.coach_agent_knowledge_bm25_index_id
            if is_bm25_only
            else self.settings.coach_agent_knowledge_index_id
        )
        if not index_id:
            self._check("index", False, "INDEX_ID_MISSING")
            return self._report(ReadinessExitCode.CONFIG_INCOMPLETE)
        try:
            service = Bm25IndexService(
                repository_root=self.repository_root,
                index_root=Path(self.settings.knowledge_bm25_index_runtime_directory),
            ) if is_bm25_only else KnowledgeIndexService(
                repository_root=self.repository_root,
                index_root=Path(
                    self.settings.knowledge_index_runtime_directory
                ),
                vector_store=self.settings.knowledge_vector_store,
                qdrant_url=self.settings.qdrant_url,
                qdrant_api_key=self.settings.qdrant_api_key,
                qdrant_collection_prefix=self.settings.qdrant_collection_prefix,
            )
            manifest = service.validate(index_id)
        except Exception:
            self._check("index", False, "INDEX_MISSING_OR_STALE")
            return self._report(ReadinessExitCode.INDEX_MISSING_OR_STALE)
        matches = manifest.corpus_root_hash == corpus.root_hash and (
            is_bm25_only
            or (
                manifest.embedding_provider
                == self.settings.knowledge_embedding_provider
                and manifest.embedding_model == self.settings.knowledge_embedding_model
                and manifest.embedding_dimensions
                == self.settings.knowledge_embedding_dimensions
                and manifest.vector_store
                == vector_store_name(self.settings.knowledge_vector_store)
            )
        )
        if not self._check(
            "index_configuration",
            matches,
            "INDEX_MATCHES_CONFIGURATION" if matches else "INDEX_CONFIG_MISMATCH",
        ):
            return self._report(ReadinessExitCode.INDEX_MISSING_OR_STALE)
        if uses_bm25 and not is_bm25_only:
            if not self.settings.coach_agent_knowledge_bm25_index_id:
                self._check("bm25_index", False, "BM25_INDEX_ID_MISSING")
                return self._report(ReadinessExitCode.CONFIG_INCOMPLETE)
            try:
                bm25_manifest = Bm25IndexService(
                    repository_root=self.repository_root,
                    index_root=Path(self.settings.knowledge_bm25_index_runtime_directory),
                ).validate(self.settings.coach_agent_knowledge_bm25_index_id)
                bm25_matches = bm25_manifest.corpus_root_hash == corpus.root_hash
            except Exception:
                bm25_matches = False
            if not self._check(
                "bm25_index", bm25_matches,
                "BM25_INDEX_MATCHES_CONFIGURATION" if bm25_matches else "BM25_INDEX_MISSING_OR_STALE",
            ):
                return self._report(ReadinessExitCode.INDEX_MISSING_OR_STALE)
        index_age_days = (self.now - manifest.created_at).total_seconds() / 86400
        if not self._check(
            "index_age",
            index_age_days <= self.settings.knowledge_index_max_age_days,
            (
                "INDEX_CURRENT"
                if index_age_days <= self.settings.knowledge_index_max_age_days
                else "INDEX_EXPIRED"
            ),
        ):
            return self._report(ReadinessExitCode.INDEX_MISSING_OR_STALE)

        configured_root = Path(
            self.settings.knowledge_bm25_index_runtime_directory if is_bm25_only else self.settings.knowledge_index_runtime_directory
        )
        if configured_root.is_absolute() or ".." in configured_root.parts:
            self._check("index_security", False, "INDEX_RUNTIME_PATH_INVALID")
            return self._report(ReadinessExitCode.SECURITY_BOUNDARY_FAILED)
        index_root = (self.repository_root / configured_root).resolve()
        web_root = (self.repository_root / "web").resolve()
        try:
            index_root.relative_to(web_root)
            outside_web_root = False
        except ValueError:
            outside_web_root = True
        normalized_root = configured_root.as_posix().rstrip("/") + "/"
        ignored = normalized_root in (
            self.repository_root / ".gitignore"
        ).read_text(encoding="utf-8")
        if not self._check(
            "index_security",
            outside_web_root and ignored,
            (
                "INDEX_RUNTIME_PRIVATE"
                if outside_web_root and ignored
                else "INDEX_RUNTIME_EXPOSED"
            ),
        ):
            return self._report(ReadinessExitCode.SECURITY_BOUNDARY_FAILED)

        tool = build_configured_knowledge_tool(self.settings)
        tool_safe = bool(
            tool
            and tool.definition.read_only
            and not tool.definition.requires_confirmation
        )
        if not self._check(
            "knowledge_tool",
            tool_safe,
            "KNOWLEDGE_TOOL_READ_ONLY" if tool_safe else "KNOWLEDGE_TOOL_UNSAFE",
        ):
            return self._report(ReadinessExitCode.SECURITY_BOUNDARY_FAILED)
        self._check("public_contract", True, "PUBLIC_REFERENCES_CANONICAL")
        return self._report(ReadinessExitCode.READY)
