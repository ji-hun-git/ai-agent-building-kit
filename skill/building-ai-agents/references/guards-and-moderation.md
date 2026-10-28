# Guards and moderation: screening prompts, data, actions and answers

> Snapshot verified 2026-10-28. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default

Screen text at five checkpoints, with deterministic rules first and a classifier second:

| Checkpoint | What crosses it | Rules (always) | Classifier (when the risk tier needs it) |
| --- | --- | --- | --- |
| prompt | the user's message, before the model | strip invisible characters; redact credentials and protected identifiers | harm categories; refuse before the model runs |
| data | documents at ingestion, every tool result | strip invisible characters, HTML comments and script/style/template/noscript blocks; flag CSS-hidden markup and instruction-like text; redact credentials and identifiers | optional injection or harm scan, as telemetry |
| egress | arguments of any outbound tool | refuse (do not edit) if they carry invisible characters, credentials, protected identifiers or URLs to unlisted hosts | — |
| stored | string arguments of any write that lands in a store (a brief, a note, a record) | the output rules: strip invisible characters; redact; remove remote images and links to unlisted hosts | — (the turn was already screened) |
| output | the assembled answer, before the user | strip invisible characters; redact; remove remote images and links to unlisted hosts | harm categories; withhold |

Rules cost a string scan and cannot be argued with; classifiers are probabilities that adaptive attackers defeat (see 07-security.md), so they route, log and refuse obvious cases but are never the only boundary. A reference implementation is `template/kit/guard.py` in https://github.com/ji-hun-git/ai-agent-building-kit.

## Decide

- If the agent reads anything written by someone other than the user (documents, web, email, tool output, memory) → apply the data rules to all of it, at ingestion for indexed corpora and on every tool result, because invisible-character payloads are read by models and not by people.
- If answers are rendered as Markdown or HTML → the output rules are mandatory: no remote images, links only to https URLs on listed hosts, images with no query string even on listed hosts, sanitized on the fully assembled answer (a streaming bypass beat GitLab Duo's filter), reference-style link definitions included (EchoLeak).
- If an allowed host could carry data out (open redirects, form services, signed proxies, capture services, an API that accepts any key) → allow (method, host, path prefix) instead of hosts, deny generic capture services, and let the harness inject credentials; reject any credential found in arguments the model built.
- If users or documents carry identifiers (cards, 주민등록번호, SSNs, account numbers) → redact them before the model sees them, and test that with a case asserting the model never received the value.
- If you need harm categories with no GPU and the data terms allow sending content out → a hosted moderation API (OpenAI `omni-moderation-latest` **[volatile]**; Azure Content Safety with Prompt Shields `documents` for injection in retrieved content; Google Model Armor; AWS Bedrock `ApplyGuardrail`).
- If content must stay on your infrastructure, or you need Korean → an open guard model: Qwen3Guard-Gen (0.6B/4B/8B, Apache-2.0, 119 languages) by default; Kanana Safeguard for Korean-only products; Llama Guard 4 only for its eight languages (not Korean).
- If your policy is not the stock taxonomy (tenant rules, limits on professional advice, community standards) → a policy-following guard (gpt-oss-safeguard, Shieldstral, Nemotron 3.5 Content Safety `custom_policy`) behind the fixed-taxonomy guard, sent only the ambiguous cases, because reasoning on every call is slow.
- If answers are long and streamed and must be stopped mid-stream → a streaming guard (Qwen3Guard-Stream) once your serving stack supports it **[volatile]**; otherwise screen the finished answer.
- If free text carries names, addresses or account numbers → a learned PII model (OpenAI Privacy Filter, English-first) or Presidio; for Korean, rules for identifiers plus a Korean-capable guard, because no learned PII model found lists Korean.

## Build checklist

- [ ] Invisible-character filter on every checkpoint: tag characters U+E0000–U+E007F; variation selectors U+FE00–U+FE0D and U+E0100–U+E01EF, and repeats of U+FE0E/U+FE0F; zero-width and format characters U+200B–U+200F, U+2060–U+2064, U+FEFF, U+00AD, U+180E, U+061C; bidi controls U+202A–U+202E and U+2066–U+2069; lone surrogates U+D800–U+DFFF. Log the count per source; a hit on untrusted input may drop the session to read-only.
- [ ] Source files contain none of those characters themselves; write them as escapes.
- [ ] Credential patterns from gitleaks' default rules (AWS, GitHub, OpenAI, Anthropic, Slack tokens and webhooks, Google, Stripe, private keys, JWT), matched in ASCII mode so they still match next to Hangul or other scripts; redaction over-matches rather than under-matches.
- [ ] Identifier patterns: card numbers with a Luhn check; 주민등록번호 and 외국인등록번호 without a checksum (numbers issued since October 2020 end in random digits, so a failed check digit must never clear a match); SSNs; e-mail and phone where the policy says so.
- [ ] Egress refuses instead of editing: a person approved that exact message.
- [ ] Guard settings (rules on, identifier types, host list, classifier and model) are part of the release bundle; a change ships through the eval gate.
- [ ] Every guard finding is a span attribute (rule and action, never the matched text).
- [ ] Eval cases: a hidden instruction in invisible characters, an answer told to embed a remote image carrying the user's question, a pasted card number and resident number (assert the model never saw them), a harmful request, a credential in an outbound message; each must fail with the guard off.
- [ ] Classifier adapters parse the exact reply format of the model you serve, and are tested on canned replies.

### Reply formats (for the adapter)

| Guard | Send | Reply |
| --- | --- | --- |
| Llama Guard 3/4 | the conversation; the chat template builds the guard prompt | `safe`, or `unsafe` and a line of codes such as `S1,S10` |
| Qwen3Guard-Gen | user turn (plus assistant turn to judge a response); no system prompt | `Safety: Safe\|Unsafe\|Controversial`, `Categories: …`, and `Refusal: Yes\|No` for responses |
| gpt-oss-safeguard | system: your policy (400–600 tokens works best), optionally `Reasoning: low\|medium\|high`; user: the content | whatever your policy asks for, e.g. `0`/`1` or JSON with `violation`, `policy_category`, `rationale` |
| OpenAI moderation | `{"model", "input"}` | `results[0].flagged`, `categories{name: bool}`, `category_scores` |
| Azure Prompt Shields | `{"userPrompt", "documents": [...]}` | `userPromptAnalysis.attackDetected`, `documentsAnalysis[].attackDetected` |

Kanana Safeguard generates one token (`<SAFE>` or `<UNSAFE-S4>`) after a rendered template, which needs a continued final turn or the completions endpoint (unverified behind a chat server). Granite Guardian, Shieldstral, WildGuard and Nemotron safety guards each have their own prompt; read the model card before adding an adapter.

## Avoid

- A classifier as the boundary → rules and architecture as the boundary, the classifier as telemetry and a router.
- Redacting egress silently → refuse the call and tell the user, because the approved message is not the one that would be sent.
- An allow-list of hosts as the only exfiltration control → path prefixes, no query strings on images, no capture services, credentials injected by the harness.
- Sanitizing streamed chunks → sanitize the assembled answer.
- Trusting a resident-number checksum to clear a match.
- Running secret scanners with live verification on user data (trufflehog's verification sends the key to the provider).
- Archived or stalled frameworks as a dependency (Protect AI LLM Guard archived 2026-07-09; LlamaFirewall no release since 2025-05) → borrow the ideas.
- Non-commercial weights in a commercial product without checking the licence on the model card.

## Verify before relying

| Fact **[volatile]** | Snapshot (2026-10-28) | Where to check (URL) |
| --- | --- | --- |
| Qwen3Guard sizes, languages, formats | Gen 0.6B/4B/8B, 119 languages; Stream needs `trust_remote_code`, vLLM support pending | https://huggingface.co/Qwen/Qwen3Guard-Gen-8B |
| Qwen3Guard vs Llama Guard 4 | English prompt F1 90.0 vs 75.9; response 83.9 vs 67.5 (vendor-run) | https://arxiv.org/abs/2510.14276 |
| Llama Guard 4 languages | EN, FR, DE, HI, IT, PT, ES, TH | https://huggingface.co/meta-llama/Llama-Guard-4-12B |
| Kanana Safeguard | 8B / Siren 8B / Prompt 2.1B, Apache-2.0, Korean-only training; F1 0.946 (vendor-run) | https://huggingface.co/kakaocorp/kanana-safeguard-8b |
| gpt-oss-safeguard | 20b / 120b, Apache-2.0; OpenAI Moderation F1 82.9 | https://huggingface.co/openai/gpt-oss-safeguard-20b |
| Shieldstral | 3B, Apache-2.0, 2026-08-04; yes/no logprob scoring | https://huggingface.co/mistralai/Shieldstral-1.0-3B |
| OpenAI moderation | `omni-moderation-latest`, 13 categories, text and images; no PII, injection or custom policy | https://developers.openai.com/api/docs/guides/moderation |
| Azure Prompt Shields | `text:shieldPrompt` with `documents`; not trained on Korean | https://learn.microsoft.com/en-us/azure/ai-services/content-safety/quickstart-jailbreak |
| OpenAI Privacy Filter | 2026-04-22, Apache-2.0, F1 96% on PII-Masking-300k, English-first | https://huggingface.co/openai/privacy-filter |
| Presidio | community-owned; Korean recognizers KR_RRN, KR_FRN, KR_DRIVER_LICENSE, KR_PASSPORT, KR_BRN | https://github.com/data-privacy-stack/presidio |
| gitleaks rules | config/gitleaks.toml last changed 2025-11-20; release v8.30.1 | https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml |
| NeMo Guardrails | 0.24.1 (2026-09-16) | https://pypi.org/project/nemoguardrails/ |

## Sources

- Qwen3Guard technical report, [arXiv 2510.14276](https://arxiv.org/abs/2510.14276), 2025-10-16
- gpt-oss-safeguard [technical report](https://cdn.openai.com/pdf/08b7dee4-8bc6-4955-a219-7793fb69090c/Technical_report__Research_Preview_of_gpt_oss_safeguard.pdf), 2025-10-29; [guide](https://developers.openai.com/cookbook/articles/gpt-oss-safeguard-guide)
- Model cards opened 2026-10-28: Llama Guard 4, Llama Prompt Guard 2, Qwen3Guard-Gen and -Stream, Kanana Safeguard, Granite Guardian 4.1, Nemotron 3.5 Content Safety, Shieldstral, WildGuard, OpenAI Privacy Filter
- Moderation APIs: [OpenAI](https://developers.openai.com/api/reference/resources/moderations/methods/create), [Azure Content Safety](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/overview), [Model Armor](https://docs.cloud.google.com/model-armor/reference/rest/v1/SanitizationResult), [Bedrock ApplyGuardrail](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ApplyGuardrail.html)
- Invisible characters: [Rehberger, Unicode tags](https://embracethered.com/blog/posts/2024/hiding-and-finding-text-with-unicode-tags/), 2024-01-14; [Butler, emoji smuggling](https://paulbutler.org/2025/smuggling-arbitrary-data-through-an-emoji/), 2025-02-08; [AWS](https://aws.amazon.com/blogs/security/defending-llm-applications-against-unicode-character-smuggling/), 2025-09-30; [garak](https://reference.garak.ai/en/latest/ascii_smuggling.html); [UAX #9](https://unicode.org/reports/tr9/)
- Exfiltration: [Willison, markdown exfiltration](https://simonwillison.net/tag/markdown-exfiltration/); [EchoLeak](https://simonwillison.net/2025/Jun/11/echoleak/), 2025-06-11
- Resident numbers after October 2020: [Seoul Shinmun](https://m.go.seoul.co.kr/news/2019/12/18/20191218014003), 2019-12-18
- Code-side filtering held when model-side defenses broke: [arXiv 2604.23887](https://arxiv.org/abs/2604.23887), 2026-05-12
