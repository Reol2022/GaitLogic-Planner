from __future__ import annotations

import json
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError

from server.agent.enums import AgentIntent, AgentToolStatus
from server.agent.errors import AgentErrorCode, AgentToolRegistrationError
from server.agent.schemas import AgentContext, AgentNotice, AgentToolDefinition, AgentToolResult
from server.agent.tool import AgentTool
from server.observability.tracing import active_trace_handle, active_tracer


class AgentToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        if not isinstance(tool, AgentTool):
            raise TypeError("only AgentTool instances can be registered")
        definition = tool.definition
        if definition.name in self._tools:
            raise AgentToolRegistrationError(AgentErrorCode.AGENT_INTERNAL_ERROR)
        self._tools[definition.name] = tool

    def get(self, name: str) -> AgentTool | None:
        return self._tools.get(name)

    def list_tools(self, intent: AgentIntent | None = None) -> list[AgentToolDefinition]:
        definitions = [tool.definition for tool in self._tools.values()]
        if intent is not None:
            definitions = [item for item in definitions if intent in item.allowed_intents]
        return sorted(definitions, key=lambda item: item.name)

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
                return result
        return self._invoke(name, arguments, context, tool_call_id=tool_call_id)

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
                message="The requested tool is not registered.",
            )

        definition = tool.definition
        if not definition.read_only or context.intent not in definition.allowed_intents:
            return self._failure(
                tool_call_id=call_id,
                tool_name=name,
                status=AgentToolStatus.NOT_ALLOWED,
                code=AgentErrorCode.AGENT_TOOL_NOT_ALLOWED,
                message="The requested tool is not allowed for this agent run.",
            )

        try:
            parsed_arguments = tool.input_model.model_validate(arguments)
        except ValidationError:
            return self._failure(
                tool_call_id=call_id,
                tool_name=name,
                status=AgentToolStatus.INVALID_ARGUMENTS,
                code=AgentErrorCode.AGENT_TOOL_ARGUMENTS_INVALID,
                message="The tool arguments are invalid.",
            )

        try:
            raw_output = tool.execute(parsed_arguments, context)
            if isinstance(raw_output, BaseModel):
                raw_output = raw_output.model_dump(mode="python")
            validated = tool.output_model.model_validate(raw_output)
            data = validated.model_dump(mode="json")
            json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False)
        except Exception:
            return self._failure(
                tool_call_id=call_id,
                tool_name=name,
                status=AgentToolStatus.FAILED,
                code=AgentErrorCode.AGENT_TOOL_EXECUTION_FAILED,
                message="The tool could not return a safe validated result.",
            )

        return AgentToolResult(
            tool_call_id=call_id,
            tool_name=name,
            status=AgentToolStatus.SUCCEEDED,
            data=data,
        )
