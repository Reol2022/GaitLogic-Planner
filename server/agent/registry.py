from __future__ import annotations

import json
import logging
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError

from server.agent.enums import AgentIntent, AgentToolStatus
from server.agent.capabilities import CapabilityKind, CapabilitySpec, active_execution_context
from server.agent.errors import AgentErrorCode, AgentToolRegistrationError
from server.agent.schemas import AgentContext, AgentNotice, AgentToolDefinition, AgentToolResult
from server.agent.skill import AgentSkill
from server.agent.tool import AgentTool
from server.observability.tracing import active_trace_handle, active_tracer


logger = logging.getLogger(__name__)


class AgentToolRegistry:
    """Compatibility name for the unified Tool + Skill capability registry."""
    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}
        self._capabilities: dict[str, CapabilitySpec] = {}

    def register(self, tool: AgentTool) -> None:
        if not isinstance(tool, AgentTool):
            raise TypeError("only AgentTool instances can be registered")
        definition = tool.definition
        if definition.name in self._tools:
            raise AgentToolRegistrationError(AgentErrorCode.AGENT_INTERNAL_ERROR)
        self._tools[definition.name] = tool
        self._capabilities[definition.name] = CapabilitySpec(
            name=definition.name,
            kind=CapabilityKind.SKILL if isinstance(tool, AgentSkill) else CapabilityKind.TOOL,
            required_capabilities=getattr(tool, "required_capabilities", ()),
            optional_capabilities=getattr(tool, "optional_capabilities", ()),
            cacheable=getattr(tool, "cacheable", True),
            visible_to_model=getattr(tool, "visible_to_model", True),
        )

    def get(self, name: str) -> AgentTool | None:
        return self._tools.get(name)

    def list_tools(self, intent: AgentIntent | None = None) -> list[AgentToolDefinition]:
        # Kept intentionally tool-only for existing callers and integrations.
        definitions = [
            tool.definition for name, tool in self._tools.items()
            if self._capabilities[name].kind is CapabilityKind.TOOL
        ]
        if intent is not None:
            definitions = [item for item in definitions if intent in item.allowed_intents]
        return sorted(definitions, key=lambda item: item.name)

    def capability_spec(self, name: str) -> CapabilitySpec | None:
        return self._capabilities.get(name)

    def list_capabilities(self, intent: AgentIntent | None = None) -> list[AgentToolDefinition]:
        """Definitions safe to expose to the model after skill subsumption."""
        definitions = [tool.definition for tool in self._tools.values()]
        if intent is not None:
            definitions = [item for item in definitions if intent in item.allowed_intents]
        visible_skills = {
            spec.name: spec
            for spec in self._capabilities.values()
            if spec.kind is CapabilityKind.SKILL and spec.visible_to_model
            and (intent is None or intent in (self.get(spec.name).definition.allowed_intents if self.get(spec.name) else []))
        }
        covered = {
            dependency
            for spec in visible_skills.values()
            for dependency in (*spec.required_capabilities, *spec.optional_capabilities)
        }
        return [
            item for item in definitions
            if self._capabilities[item.name].visible_to_model
            and not (item.name in covered and item.name not in visible_skills)
        ]

    def normalize_candidates(self, names: list[str]) -> list[str]:
        """Drop top-level atomic calls that a selected skill declares it owns."""
        selected = set(names)
        covered = {
            dependency
            for name in selected
            for dependency in (
                (*self._capabilities[name].required_capabilities, *self._capabilities[name].optional_capabilities)
                if name in self._capabilities and self._capabilities[name].kind is CapabilityKind.SKILL else ()
            )
        }
        return [name for name in names if name not in covered or name not in selected]

    @staticmethod
    def _failure(
        *,
        tool_call_id: UUID,
        tool_name: str,
        status: AgentToolStatus,
        code: AgentErrorCode,
        message: str,
    ) -> AgentToolResult:
        return AgentToolResult(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            status=status,
            safe_error_code=code,
            warnings=[AgentNotice(code=code.value, message=message)],
        )

    def invoke(
        self,
        name: str,
        arguments: dict,
        context: AgentContext,
        *,
        tool_call_id: UUID | None = None,
    ) -> AgentToolResult:
        runtime = active_execution_context()
        spec = self._capabilities.get(name)
        if runtime is not None and spec is not None and spec.cacheable:
            cached = runtime.get(name, arguments)
            if cached is not None:
                self._trace_fact_cache("hit", name)
                return cached.model_copy(update={"tool_call_id": tool_call_id or uuid4()})
            self._trace_fact_cache("miss", name)
        tracer = active_tracer()
        handle = active_trace_handle()
        if tracer is not None and handle is not None:
            with tracer.span(
                handle,
                component="tool",
                operation="invoke",
                metadata={"tool_name": name, "operation_type": "agent_tool"},
            ) as span:
                result = self._invoke(name, arguments, context, tool_call_id=tool_call_id)
                span.add_metadata(
                    status=result.status.value,
                    error_code=(
                        result.safe_error_code.value
                        if result.safe_error_code is not None
                        else None
                    ),
                )
                if result.status != AgentToolStatus.SUCCEEDED:
                    span.set_status(
                        "FAILED",
                        error_code=(
                            result.safe_error_code.value
                            if result.safe_error_code is not None
                            else "AGENT_TOOL_EXECUTION_FAILED"
                        ),
                    )
                if runtime is not None and spec is not None:
                    runtime.put(name, arguments, result)
                return result
        result = self._invoke(name, arguments, context, tool_call_id=tool_call_id)
        if runtime is not None and spec is not None:
            runtime.put(name, arguments, result)
        return result

    @staticmethod
    def _trace_fact_cache(result: str, name: str) -> None:
        tracer, handle = active_tracer(), active_trace_handle()
        if tracer is not None and handle is not None:
            with tracer.span(handle, component="fact", operation=result, metadata={"tool_name": name, "operation_type": "capability_cache"}):
                pass

    def _invoke(
        self,
        name: str,
        arguments: dict,
        context: AgentContext,
        *,
        tool_call_id: UUID | None = None,
    ) -> AgentToolResult:
        call_id = tool_call_id or uuid4()
        tool = self.get(name)
        if tool is None:
            return self._failure(
                tool_call_id=call_id,
                tool_name=name,
                status=AgentToolStatus.NOT_FOUND,
                code=AgentErrorCode.AGENT_TOOL_NOT_FOUND,
                message="请求的数据工具尚未注册。",
            )

        definition = tool.definition
        if not definition.read_only or context.intent not in definition.allowed_intents:
            return self._failure(
                tool_call_id=call_id,
                tool_name=name,
                status=AgentToolStatus.NOT_ALLOWED,
                code=AgentErrorCode.AGENT_TOOL_NOT_ALLOWED,
                message="当前教练请求不允许使用该数据工具。",
            )

        try:
            parsed_arguments = tool.input_model.model_validate(arguments)
        except ValidationError:
            return self._failure(
                tool_call_id=call_id,
                tool_name=name,
                status=AgentToolStatus.INVALID_ARGUMENTS,
                code=AgentErrorCode.AGENT_TOOL_ARGUMENTS_INVALID,
                message="数据工具参数无效。",
            )

        try:
            raw_output = tool.execute(parsed_arguments, context)
            if isinstance(raw_output, BaseModel):
                raw_output = raw_output.model_dump(mode="python")
            validated = tool.output_model.model_validate(raw_output)
            data = validated.model_dump(mode="json")
            json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False)
        except Exception as exc:
            # Tool exceptions can contain provider responses, storage paths,
            # request fragments, or other private content.  Keep structured
            # logs correlated by safe tool name and exception class only.
            logger.error(
                "agent_tool_execution_failed tool_name=%s exception_type=%s",
                name,
                type(exc).__name__,
            )
            return self._failure(
                tool_call_id=call_id,
                tool_name=name,
                status=AgentToolStatus.FAILED,
                code=AgentErrorCode.AGENT_TOOL_EXECUTION_FAILED,
                message="数据工具未能返回通过安全校验的结果。",
            )

        return AgentToolResult(
            tool_call_id=call_id,
            tool_name=name,
            status=AgentToolStatus.SUCCEEDED,
            data=data,
        )


# Public v0.16 name.  The historical import remains supported so existing
# Tools, tests and integrations do not need a risky flag-day migration.
CapabilityRegistry = AgentToolRegistry
