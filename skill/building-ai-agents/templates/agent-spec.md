# Agent spec: <agent name>

Owner: <person> · Date: <YYYY-MM-DD> · Stack lock: <path to agent-stack-lock.md> · Status: draft | reviewed | approved

## 1. Purpose and users
One paragraph: who uses it, for what, and what "good" looks like in their words.

## 2. Jobs (with real examples)
| # | Job | Example input | Expected outcome | Frequency |
| --- | --- | --- | --- | --- |
| J1 | | | | |

## 3. Out of scope
What the agent must refuse or hand off, and to whom.

## 4. Data sources
| Source | Owner | Sensitivity | Access model today (who can see what) | Freshness need | Retrieval mode (index / agentic search / long context) |
| --- | --- | --- | --- | --- | --- |

## 5. Actions
| Tool | System | Class (read / reversible write / irreversible) | Approval rule | Idempotency key | Audit record |
| --- | --- | --- | --- | --- | --- |

## 5b. Triggers and reply channels
| Trigger (chat, Slack, email, webhook, cron) | Runs as (identity) | Payload untrusted? | Where replies go |
| --- | --- | --- | --- |

## 6. Risk tier
Low / medium / high, and why (writes, money, personal data, external communication, irreversibility).

## 7. Architecture
Rung chosen on the ladder (single call / workflow / single agent / multi-agent), and the measured reason the rung below is not enough. Diagram or component list.

## 8. Model and harness
| Role | Model ID (dated snapshot) | Effort | Why |
| --- | --- | --- | --- |
| Main | | | |
| Small tier (routing, extraction, sub-agents) | | | |
Harness / SDK and pinned version:

## 9. Context plan
- System prompt sections:
- Skills (procedures loaded on demand):
- Retrieval: what is fetched just in time, what is placed up front:
- Memory: what persists across sessions, where, scoped to whom:

## 10. Identity and authorization
- Agent identity:
- How the user's identity reaches each tool and index (delegated token, act claim):
- Where permissions are enforced (index ACLs, tool, policy gateway):
- Approvals decided by:

## 11. Security
Link to threat model. Trifecta status per flow (private data / untrusted input / outbound channel) and the control that breaks it.

## 12. UX
How the agent states its identity and limits; progress display; confirmation wording for each write class; citations; undo; human handoff.

## 13. Cost and latency targets
Latency target per job (p50 / p95), caching layout, routing, batch jobs. Mechanisms only.

## 14. Observability
Trace exporter and backend, content-capture policy, redaction point, dashboards and alerts.

## 15. Evals and release
Link to eval plan. Gate threshold, rollout stages, rollback triggers, kill switch.

## 16. Open questions
- [ ] 
