# GaitLogic Observability

## Local platform (v0.16.5)

The optional local stack is `deploy/observability/`: GaitLogic sends filtered OTLP traces and metrics to one Collector, which fans out traces to Tempo and Jaeger and exposes metrics for Prometheus. Grafana provisions Prometheus, Tempo and Jaeger datasources plus four dashboards automatically. Start it with `docker compose -f deploy/observability/docker-compose.yml up -d`; see its README for local credentials, URLs and cleanup.

`DecisionOutcome` is a read-only view of existing Evidence Judge assessments: `full_answer`, `partial_answer`, or `global_block`. Runtime `global_block` is never an online estimate of `false_global_block`; the latter is served only from the fixed offline evaluation CSV by the local read-only exporter.

SafeTracer continues to allowlist trace attributes, and MetricsRecorder allowlists metric labels. Requests, prompts, responses, identifiers, credentials, raw tool results, training records and RAG chunks are excluded by construction. Local development samples 100%; production sampling, TLS, authentication, retention and HA require a separate design.

## Architecture

Business code uses `SafeTracer` only.  Completed, already-sanitized
`SpanRecord` objects are sent to an optional backend:

```text
Application / Agent -> SafeTracer -> domain schema -> Noop | JSONL | OpenTelemetry OTLP
```

Tracing is a best-effort side channel.  Exporter, serialization and collector
errors are caught and logged with a stable code; they never change Coach,
Weekly Review, proposal approval, or synchronization results.

## Domain span schema

The exporter normalizes legacy component/operation pairs into stable names.
Important names include:

```text
gaitlogic.http.request
coach.request
tool.call
evidence.judge
evidence.reflect
rule.evaluate
rag.retrieve
rag.metadata_filter
rag.vector_search
rag.rerank
llm.generate
validator.check
weekly_review.request
proposal.generate
proposal.validate
approval.evaluate
plan.apply
mcp.call
```

Only nodes that actually execute are emitted.  A `global_block` is not
automatically classified as a false global block: that requires offline ground
truth evaluation.

## Sensitive data policy

`SafeTracer` uses an allowlist.  Unknown metadata is discarded before it can
reach in-memory traces, JSONL or OTel.  This excludes user identity, headers,
credentials, Garmin tokens, complete prompts/responses, training records,
tool inputs/outputs and RAG chunk text.  Safe examples are status, duration,
tool name, provider category, aggregate result counts and stable error codes.

## Configuration

All settings default to local-safe, offline behavior:

```dotenv
AGENT_TRACING_ENABLED=false
AGENT_TRACE_EXPORTER=noop
AGENT_METRICS_ENABLED=false
```

To write local sanitized JSONL under an ignored directory:

```dotenv
AGENT_TRACING_ENABLED=true
AGENT_TRACE_EXPORTER=local
AGENT_TRACE_LOCAL_PATH=logs/traces.jsonl
```

To enable OTLP/HTTP, install the optional `observability` dependency and set a
credential-free endpoint:

```dotenv
AGENT_TRACING_ENABLED=true
AGENT_TRACE_EXPORTER=otlp
OTEL_SERVICE_NAME=gaitlogic-planner
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318/v1/traces
```

If the endpoint is absent, invalid, unavailable, or the SDK is not installed,
the application continues with tracing disabled.  No collector is required for
local development.

## Metrics

Completed spans produce bounded, low-cardinality aggregate metrics.  The
standard names are `gaitlogic.agent.requests`, `gaitlogic.agent.duration`,
`gaitlogic.tool.calls`, `gaitlogic.tool.failures`,
`gaitlogic.tool.duration`, `gaitlogic.rag.retrievals`,
`gaitlogic.rag.empty_retrievals`, `gaitlogic.rag.duration`,
`gaitlogic.evidence.reflects`, `gaitlogic.validator.rejections`, and proposal
created/approved/rejected counters.  Trace IDs, request IDs, user IDs and
prompts are never metric labels.

## Troubleshooting

- No trace: check `AGENT_TRACING_ENABLED` and the selected exporter.
- No OTLP spans: verify the endpoint has no credentials/query string and the
  optional dependencies are installed.  The application will log a safe
  `TRACE_EXPORTER_UNAVAILABLE` warning instead of failing requests.
- Empty local file: generate an instrumented Coach, Weekly Review, RAG or MCP
  request while local tracing is enabled.  The file is intentionally not
  created merely by application startup.
