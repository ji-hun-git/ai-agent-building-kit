# Threat model: <agent name>

Date: <YYYY-MM-DD> · Risk tier: <low / medium / high> · Reviewed by: <person>

## 1. Assets
What must not leak, change or be destroyed (data classes, systems, credentials, money, reputation).

## 2. Untrusted inputs
| Entry point | Example | Reaches which component | Can it influence tool choice? |
| --- | --- | --- | --- |
| User message | | | |
| Retrieved documents | | | |
| Tool / API results | | | |
| Web pages, email, files, images | | | |
| Long-term memory | | | |
| Other agents (A2A) | | | |

## 3. Lethal-trifecta check per flow
A flow is unsafe when one unsupervised session has all three: access to private data, exposure to untrusted content, and a channel that can send data out (outbound tools, links, images, email, web requests).

| Flow / session | Private data | Untrusted content | Outbound channel | Broken by |
| --- | --- | --- | --- | --- |

## 4. OWASP agentic top 10 mapping
| Risk | Applies? | Control | Eval case id |
| --- | --- | --- | --- |
| Goal hijack | | | |
| Tool misuse | | | |
| Identity and privilege abuse | | | |
| Supply chain (models, MCP servers, skills, packages) | | | |
| Unexpected code execution | | | |
| Memory poisoning | | | |
| Insecure inter-agent communication | | | |
| Cascading failures | | | |
| Human-trust exploitation | | | |
| Rogue agents | | | |

## 5. Containment
- Code execution sandbox (filesystem, network):
- Egress allow-list and proxy:
- Approval gates and who decides them:
- Credential handling (lifetime, holder, scope):
- Rate and spend limits:

## 6. Residual risks → red-team cases
| Residual risk | Likelihood | Impact | Accepted by | Red-team case id |
| --- | --- | --- | --- | --- |
