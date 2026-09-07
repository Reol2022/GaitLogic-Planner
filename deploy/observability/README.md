# GaitLogic local Observability Stack

Local development, demo, and evaluation only. It is not a Tencent Cloud or production deployment.

## Components

| Component | Pinned version | Local port | Purpose |
| --- | --- | --- | --- |
| OpenTelemetry Collector | 0.157.0 | 4317, 4318, 9464 | single OTLP ingress and fanout |
| Tempo | 2.7.2 | 3200 | primary trace store for Grafana |
| Jaeger all-in-one | 1.76.0 | 16686 | independent trace UI verification |
| Prometheus | 3.11.3 | 9090 | runtime and offline evaluation metrics |
| Grafana | 12.4.3-security-02 | 3000 | provisioned dashboards |

Tempo uses the compatible monolithic/local-storage configuration, so this local stack does not need Redpanda. All published ports are bound to `127.0.0.1`.

## Start

```powershell
Copy-Item deploy/observability/.env.example deploy/observability/.env
docker compose -f deploy/observability/docker-compose.yml up -d
```

Set a local-only Grafana password in `deploy/observability/.env`; this file is ignored. Stop with `docker compose -f deploy/observability/docker-compose.yml down`. To remove all local telemetry volumes too, run the same command with `-v`.

URLs: Grafana `http://127.0.0.1:3000`, Prometheus `http://127.0.0.1:9090`, Jaeger `http://127.0.0.1:16686`.

## GaitLogic configuration

```env
AGENT_TRACING_ENABLED=true
AGENT_TRACE_EXPORTER=otlp
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318/v1/traces
AGENT_METRICS_ENABLED=true
AGENT_METRICS_EXPORTER=otlp
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=http://127.0.0.1:4318/v1/metrics
OTEL_SERVICE_NAME=gaitlogic-planner
```

The defaults remain off. SafeTracer allowlists span attributes; prompts, responses, identities, credentials, training records and raw RAG/tool data are not exported. Local tracing samples 100%; any production sampling, TLS, authentication, retention and HA design is a future separate decision.
