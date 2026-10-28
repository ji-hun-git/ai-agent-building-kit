# 09 · Observability

> Snapshot verified 2026-10-27. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default
Trace every agent run as OpenTelemetry spans that follow the GenAI semantic conventions: an `invoke_agent` span per agent turn, an inference span per model call, an `execute_tool` span per tool call, `retrieval` and memory spans, and MCP client/server spans joined by W3C trace context carried in `params._meta`. Prefer native emission (Claude SDKs, the Messages API and Managed Agents export GenAI-convention traces, public beta since 2026-10-14) and add your own spans only for application logic such as routing, approvals and guards. Export through an OpenTelemetry Collector that redacts and hashes before fanning out to an LLM-focused backend (Langfuse, Datadog Agent Observability or similar) and your general APM. Keep prompt and completion content off by default and opt in per environment to an access-controlled store. Stamp every span with the release bundle ID so each regression maps to exactly one release; the conventions are still at Development status, so pin versions and expect renames.

## Decide
- If your vendor SDK or platform emits OTel natively → enable it and add spans only for your own steps (routing, approvals, guards, retrieval ACL filtering), because wrapping the same calls again duplicates spans and double-counts tokens.
- If an MCP tool call happens inside an `execute_tool` span your framework already creates → add the MCP attributes to that span instead of opening a second one, because the MCP conventions say instrumentations SHOULD NOT duplicate a span outer GenAI instrumentation already records.
- If the agent runs in-process → record `invoke_agent` as an INTERNAL span; if you call a remote agent service → a CLIENT span **[volatile]**, because the conventions split the two in v1.41.0 and backends render and aggregate them differently.
- If you need prompts and completions for debugging → capture them through the opt-in `gen_ai.client.inference.operation.details` event (`gen_ai.input.messages`, `gen_ai.output.messages`) into a restricted dataset **[volatile]**; otherwise export metadata only, because prompts and tool arguments routinely carry personal data and secrets.
- If you use the OpenAI Agents SDK → set `trace_include_sensitive_data` to false (or `OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA=0`) unless content capture is approved, and add a trace processor to reach your own pipeline **[volatile]**, because the SDK traces by default to OpenAI's dashboard and includes inputs and outputs by default.
- If sensitive data must never leave the process → mask in-process (a custom span processor, or Langfuse `mask_otel_spans`) **[volatile]**; for everything else redact centrally in the Collector (`redaction`, `attributes`, `transform` processors), because Collector-side redaction protects only what sits downstream of the Collector.
- If you want an open-source, self-hostable LLM backend with prompt management and evals → Langfuse via OTLP/HTTP at `/api/public/otel` (no gRPC) **[volatile]**; if the organization already runs Datadog → Datadog Agent Observability via OTLP with header `dd-otlp-source=llmobs` **[volatile]**; other OTLP-accepting destinations include Arize, LangSmith, Braintrust, Honeycomb, Grafana Cloud, Sentry, Splunk and New Relic, because they ingest the same conventions and the Collector can feed two at once.
- If dashboards or alerts key on `gen_ai.*` names → pin the instrumentation and schema version and normalize names in a Collector `transform` step, because every `gen_ai.*` item is Development status and v1.42.0 already moved them all to a new repository.
- If you sample traces → keep 100% of traces with errors, guardrail or approval denials, low online-eval scores, max-turn exits or token outliers (tail sampling) and sample the rest, because the rare failures are the ones you will need to replay.
- If you run online evals or collect user feedback → attach the scores to the trace (the `gen_ai.evaluation.result` event or your backend's score API) **[volatile]**, because quality per release needs scores and traces joined on the same IDs.

## Build checklist
- [ ] Set resource attributes on every process: `service.name`, `service.version` = release bundle ID, `deployment.environment.name`; set `gen_ai.agent.name`, `gen_ai.agent.id`, `gen_ai.agent.version` on agent spans; for Langfuse also map the bundle ID to `langfuse.release` **[volatile]**.
- [ ] Open a root span per user turn carrying `gen_ai.conversation.id`; record tenant and user only as HMAC-hashed pseudonyms, never emails or names.
- [ ] Inference spans: `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.cache_creation.input_tokens`, `gen_ai.usage.reasoning.output_tokens` **[volatile]**. Record effort, speed, service tier and router-served model under your own namespace (for example `app.llm.effort`), because the conventions define no attributes for them.
- [ ] Tool spans named `execute_tool {gen_ai.tool.name}` with `gen_ai.tool.call.id`, `gen_ai.tool.type` and `error.type`, plus your side-effect class (read / reversible / irreversible), approval decision and idempotency key.
- [ ] Retrieval spans (`retrieval {gen_ai.data_source.id}`) with `gen_ai.retrieval.top_k`, index version and the count of chunks removed by permission filtering; memory spans (`create_memory`, `search_memory`, `upsert_memory`) with `gen_ai.memory.store.id` **[volatile]**.
- [ ] MCP client: inject `traceparent`, `tracestate` and `baggage` (unprefixed) into `params._meta` of every request and notification; MCP server: extract them and use them as the parent. Name spans `{mcp.method.name} {target}` with `mcp.method.name`, `mcp.session.id`, `mcp.protocol.version`, `jsonrpc.request.id` **[volatile]**.
- [ ] Run an OTel Collector with: the `redaction` processor in allow-list mode (`allowed_keys`), `blocked_values` regexes for emails, phone numbers, card-like numbers, API keys and bearer tokens, `hash_function: hmac-sha256` for identifiers; a `transform` processor for attribute renames; tail sampling; and two exporters (LLM backend + APM).
- [ ] Leave content capture off by default; enable it per environment only with the instrumentation's own switch (for example `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`; Claude Python SDK `ANTHROPIC_OPEN_TELEMETRY_TRACES_CONTENT_MODE=content`; Claude Console destinations "Full content" vs "Metadata only") **[volatile]**, and only toward a backend with data access controls or restricted datasets.
- [ ] Test the pipeline in CI: seed a fake secret and a fake email into a prompt and a tool argument, run one turn through the Collector into an in-memory or debug exporter, and fail if either string appears.
- [ ] Test every mask function; a Langfuse `mask_otel_spans` function that raises drops the whole export batch **[volatile]**. Alert on exporter errors and dropped spans.
- [ ] Emit metrics: `gen_ai.client.token.usage`, `gen_ai.client.operation.duration`, `gen_ai.client.operation.time_to_first_chunk`, `gen_ai.execute_tool.duration`, `mcp.client.operation.duration` **[volatile]**, plus a derived cache-hit ratio (cache-read ÷ total input tokens).
- [ ] Build dashboards sliced by `service.version` and agent: task success (online eval score); end-to-end latency p50/p95/p99 and TTFT; tokens per task split into uncached input, cached input, output and reasoning; cache-hit ratio; turns and tool calls per task; tool error rate per tool; MCP latency and errors per server; refusal, escalation and approval-denial rates; served-model and speed distribution.
- [ ] Set alerts: cache-hit ratio drop right after a deploy (prefix drift); per-tool error spike; p99 latency or TTFT regression; tokens-per-task or turns-per-task outliers (runaway loops); online eval score under threshold; refusal or guardrail-trip spike (possible injection campaign); exporter failures; any redaction-detector hit in exported data. Wire the release-critical ones to the rollback triggers in `10-evals-and-release.md`.
- [ ] Set retention per data class (metadata longest, content shortest) and a deletion path for user data requests that reaches every backend the Collector feeds.

## Avoid
- Prompts and tool arguments as span attributes by default → the opt-in content event into a restricted store (otherwise personal data and secrets land in every backend and APM index).
- Relying only on the backend's masking → redact before export (once data leaves the process or Collector it is already stored somewhere).
- Using the Collector `filter` processor to "redact" → `redaction` or `transform` (filter drops whole spans).
- Hard-coding `gen_ai.*` names in dashboards without a pinned version → normalize in the Collector (Development-status names change between releases).
- One tracing silo per vendor → one OTel pipeline with fan-out (a multi-vendor agent otherwise loses the trace at every hop).
- Duplicate MCP and `execute_tool` spans for one call → enrich a single span.
- Traces without the release version → `service.version` = bundle ID on every span (otherwise a regression cannot be attributed).
- Raw user identifiers in spans → HMAC-hashed pseudonyms.
- Head sampling that discards errors → tail sampling that keeps every failure.
- Injecting trace context into MCP requests without extracting it on the server → extract and parent server spans (otherwise the server side shows up as orphan traces).

## Verify before relying
| Fact **[volatile]** | Snapshot (2026-10-27) | Where to check (URL) |
| --- | --- | --- |
| GenAI semconv status | All `gen_ai.*` spans, metrics, attributes at Development; only `error.type`, `server.address`, `server.port` Stable | https://www.dash0.com/knowledge/opentelemetry-genai-semantic-conventions-explained |
| GenAI semconv home | Moved to `open-telemetry/semantic-conventions-genai` in core v1.42.0 (2026-06-12); no tagged release; schema URL "TODO" | https://github.com/open-telemetry/semantic-conventions-genai |
| Core semconv latest | v1.44.0 (2026-08-04), no GenAI changes | https://github.com/open-telemetry/semantic-conventions/releases |
| Operation names | `chat`, `generate_content`, `embeddings`, `create_agent`, `invoke_agent`, `invoke_workflow`, `plan`, `execute_tool`, `retrieval`, `create_memory`, `search_memory`, `upsert_memory` | https://www.dash0.com/knowledge/opentelemetry-genai-semantic-conventions-explained |
| Span kinds and naming | `invoke_agent` CLIENT vs INTERNAL (v1.41.0); tool name required in `execute_tool` span name | https://github.com/open-telemetry/semantic-conventions/releases |
| Token attributes | `gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.cache_creation.input_tokens` (v1.40.0); `gen_ai.usage.reasoning.output_tokens` (v1.41.0) | https://github.com/open-telemetry/semantic-conventions/releases |
| Content capture | Event `gen_ai.client.inference.operation.details`; switch left to each instrumentation | https://www.dash0.com/knowledge/opentelemetry-genai-semantic-conventions-explained |
| MCP conventions | Development; `{mcp.method.name} {target}`; `traceparent`/`tracestate`/`baggage` in `params._meta` (SEP-414); enrich instead of duplicating `execute_tool` | https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/mcp.md |
| Anthropic native traces | Public beta since 2026-10-14; Messages API, Managed Agents (Console destination), SDKs (automatic) | https://claude.com/blog/agent-observability-on-the-claude-platform |
| Claude SDK content default | Python SDK metadata-only; `ANTHROPIC_OPEN_TELEMETRY_TRACES_CONTENT_MODE=content` to capture | https://docs.datadoghq.com/llm_observability/instrument/otel_instrumentation/ |
| Datadog ingestion | "Agent Observability"; GenAI semconv 1.37+ and OpenInference; `dd-otlp-source=llmobs` | https://docs.datadoghq.com/llm_observability/instrument/otel_instrumentation/ |
| Langfuse ingestion | `/api/public/otel`, HTTP JSON/protobuf only; `x-langfuse-ingestion-version=4` for real-time; legacy ingestion API deprecated | https://langfuse.com/docs/opentelemetry/get-started |
| Langfuse masking | `mask_otel_spans` (Python) at export; failure drops the batch | https://langfuse.com/docs/observability/features/masking |
| Collector redaction processor | Config key `redaction`; traces beta, logs and metrics alpha | https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/redactionprocessor/README.md |
| OpenAI Agents SDK tracing | On by default to OpenAI Traces; `trace_include_sensitive_data` defaults true; `add_trace_processor()`; OTel export path not stated on the page | https://openai.github.io/openai-agents-python/tracing/ |

## Sources
- [semantic-conventions releases](https://github.com/open-telemetry/semantic-conventions/releases) — OpenTelemetry, GitHub, v1.40.0–v1.44.0 (Feb–Aug 2026)
- [semantic-conventions-genai](https://github.com/open-telemetry/semantic-conventions-genai) — OpenTelemetry, GitHub, accessed 2026-10-27
- [Semantic conventions for MCP](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/mcp.md) — OpenTelemetry, GitHub, accessed 2026-10-27
- [OpenTelemetry GenAI Semantic Conventions Explained](https://www.dash0.com/knowledge/opentelemetry-genai-semantic-conventions-explained) — Dash0, updated 2026-09-15
- [Agent observability on the Claude Platform](https://claude.com/blog/agent-observability-on-the-claude-platform) — Anthropic, 2026-10-14
- [OpenTelemetry instrumentation](https://docs.datadoghq.com/llm_observability/instrument/otel_instrumentation/) — Datadog, n.d. (accessed 2026-10-27)
- [OpenTelemetry: get started](https://langfuse.com/docs/opentelemetry/get-started) — Langfuse, n.d. (accessed 2026-10-27)
- [Masking](https://langfuse.com/docs/observability/features/masking) — Langfuse, n.d. (accessed 2026-10-27)
- [Redaction processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/redactionprocessor/README.md) — OpenTelemetry Collector Contrib, GitHub, accessed 2026-10-27
- [Tracing](https://openai.github.io/openai-agents-python/tracing/) — OpenAI Agents SDK docs, n.d. (accessed 2026-10-27)
