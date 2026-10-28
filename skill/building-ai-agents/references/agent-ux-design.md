# Agent UX design

> Snapshot verified 2026-10-27. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default
Tell people at first contact that they are dealing with an AI, what it can do and where it stops, and keep that label visible. Before long or consequential work show the plan; while it runs show step-level progress and keep Stop and steering available; when it finishes show what changed, with undo where possible and a history of every action. Ask for approval only where it carries information (the plan, and each irreversible or external action with its exact target and consequence) and let the sandbox and policy rules handle routine steps, because people approve almost every prompt they are shown. Cite grounded claims at the passage level, say plainly when the evidence is missing, and hand off to a human with context on request or after repeated failure. Make every control keyboard- and screen-reader-operable.

## Decide
- If the agent interacts directly with people in the EU → disclose that it is an AI no later than the first interaction, clearly and accessibly, because EU AI Act Article 50 has applied since 2 August 2026 **[volatile]**; do it everywhere anyway, since NN/g finds users want upfront disclosure.
- If a task takes more than a few seconds or several tool calls → show a plan and step-level progress; if it takes minutes or more → let it run in the background with a notification and a progress view the user can reopen, because a slow, silent agent reads as broken (NN/g timed an agent at about 11 minutes for a 2-minute human task **[volatile]**).
- If an action is read-only → run it without asking; if it is a reversible write inside the agreed scope → run it, log it and offer undo; if it is irreversible or leaves the system (send, pay, publish, delete, share, change permissions) → confirm it individually with the exact action, because approval prompts only work when they are rare and specific.
- If your logs show near-universal acceptance of a prompt type → move that action behind a sandbox, policy rule or classifier and ask once at the plan level, because Claude Code users approve 93–97% of permission prompts but reject 39% of plans **[volatile]**.
- If the answer comes from retrieved sources → cite each claim inline and link to the passage; if retrieval finds nothing relevant → abstain and offer a next step, because a confident unsupported answer is the costliest failure and few users check citations.
- If you display confidence → use a few labelled categories, each tied to what the user should do, and show alternatives when confidence is low, because numeric scores presume users understand probability (Google PAIR).
- If the request is ambiguous and a wrong guess is costly → ask one targeted clarifying question before acting, because NN/g saw agents start vague tasks without asking and misfire.
- If the user asks for a human, a repair attempt fails twice, or frustration shows (repeated rephrasing) → hand off at once with a conversation summary, because NN/g: "Never gatekeep when the user explicitly asks to be connected to a human."
- If the agent acts on its own after an external event → notify with the reason in the user's terms and an undo or review link, because unexplained background actions generate "why did it do that?" tickets.
- If users must see or manipulate structured data, a form or an approval queue inside a chat host → MCP Apps (stable spec 2026-01-26) **[volatile]** with a text fallback; if you own the frontend → stream agent events over AG-UI **[volatile]** or your SDK's UI kit; use A2UI (public preview) **[volatile]** only to render native components from a trusted catalog across platforms.
- If the agent needs personal data or credentials → ask at the step that needs them, say why, show the minimum, and let the user enter secrets themselves (takeover), because NN/g participants were ready to abandon an agent that showed their full address too early.
- If the right level of autonomy differs by task type → offer per-task settings (observe and suggest, propose a plan, act with confirmation, act autonomously) with a conservative default, because trust is earned task by task (Smashing, Feb 2026; HAX G17 "Provide global controls").

## Design rules
1. **Say what it is, what it can do and what it can't, at the start and persistently.** Why: users calibrate trust from the first screen (HAX G1 "Make clear what the system can do", G2 "…how well"), and Article 50 requires disclosure by the first interaction **[volatile]**. Example: header "AI assistant · looks up orders, starts returns, tracks refunds · can't change payment details", plus a persistent "AI" label on every agent message.
2. **Handle out-of-scope requests in three moves: acknowledge, state the limit, redirect.** Why: a bare refusal reads as broken, and an exhaustive capability list at the start goes unread (NN/g). Example: "I can't update billing addresses. I can open a ticket for the billing team, or show you where to change it in Settings."
3. **Clarify before acting when the request is ambiguous and mistakes are costly.** Why: one question is cheaper than a confident wrong action (HAX G10 "Scope services when in doubt"). Example: "'Next Tuesday': 3 November or 10 November?" with both dates as buttons.
4. **Preview the plan before long or consequential work.** Why: the plan is where users actually exercise judgment (39% of plans rejected vs about 3% of single permission prompts **[volatile]**). Example: "1 Cancel UA456 · 2 Rebook on DL789 · 3 Email you the new itinerary" with [Proceed] [Edit plan] [I'll do it myself].
5. **Show live progress at step level, with an estimate when you have one.** Why: showing the agent's planning steps is one of Anthropic's three core agent principles, and silence on a slow task looks like failure. Example: "Step 3 of 6 · Comparing 4 quotes · started 1 min ago" above a task list that ticks off as steps finish.
6. **Stream text and show tool activity as compact, expandable entries.** Why: streaming cuts perceived wait, and visible tool calls let users catch a wrong turn early. Example: "Searched the policy library (3 results) ▸" expanding to the query and titles; never style the agent's narration as a verified result.
7. **Keep Stop and steering available for the whole run, and make Stop safe.** Why: users must redirect without starting over (HAX G8 "Support efficient dismissal", G9 "…correction"). Example: Stop ends after the current tool call and reports "Stopped after step 3 of 6. Steps 1–3 are saved; nothing was sent."; messages typed mid-run are queued and delivered at the next tool boundary, as Claude Code does.
8. **Confirm irreversible or external actions with the exact action, target and consequence, and label buttons with the verb.** Why: a generic "Are you sure? OK" invites a reflexive click. Example: "Send email to dana@acme.com · subject 'Q3 invoice' · 1 attachment (invoice_Q3.pdf). Sent email can't be recalled. [Send email] [Edit] [Cancel]".
9. **Ration approvals and scope any standing permission.** Why: per-command prompts get rubber-stamped; in Anthropic's controlled study reviewers caught 13.6% of dangerous commands, about 5% after 50 or more prompts **[volatile]**. Example: "Allow file edits in /src for this session", listed in settings with its scope and revocable; never offer "Always allow everything".
10. **Cite at claim level and preview the source passage.** Why: people rarely click citations, a citation alone creates false confidence, and deep links cut checking effort (NN/g). Example: a marker after each claim opens a card with document title, date and the supporting passage highlighted, plus "Open at this passage"; label links descriptively, not "Source".
11. **Abstain plainly and tie uncertainty to an action.** Why: the goal is calibrated trust, not blanket trust (PAIR), and percentages mislead. Example: "I couldn't find gift-card refunds in the policies you shared. The closest is section 4.2 (card refunds), which doesn't cover them. Shall I ask the support team?" rather than "I'm 87% confident".
12. **Explain actions in the user's terms: "because you said X, I did Y."** Why: HAX G11 "Make clear why the system did what it did", and NN/g warns that step-by-step reasoning displays are often unfaithful, so show the decision's inputs instead. Example: "Rebooked you on DL789 because UA456 was cancelled and you pre-approved same-day non-stop rebooking."
13. **Offer undo for every reversible action, and state the window and the limits.** Why: undo turns autonomy from a gamble into a draft. Example: "Archived 12 emails · Undo (15 min)"; for coding agents a checkpoint per prompt with restore code / conversation / both, plus a note on what cannot be undone (sent messages, shell side effects).
14. **Keep an action history the user can audit and export.** Why: accountability and debugging both need who did what, when, on whose approval. Example: per run, a chronological list of time, tool, key arguments, result, approved by (you / policy / auto) and status (done, failed, undone), each linked to the turn that caused it.
15. **Write errors as what failed, what state things are in, and what to do next.** Why: users need to know whether anything happened; Smashing's repair pattern is acknowledge, correct, offer a human. Example: "The payment step failed: the bank declined the card. Nothing was charged, and your order is saved as a draft. [Try another card] [Talk to support]".
16. **Hand off to a human with context, immediately when asked.** Why: users do not yet treat bots as equivalent to human agents, and repeating themselves compounds frustration (NN/g). Example: "Connecting you to a support agent. I've passed on this conversation and order #4521, so you won't need to repeat yourself."
17. **Ask for personal data just in time, say why, and keep secrets out of the agent's hands.** Why: early or unexplained data use breaks trust (NN/g study of Qwen's agent). Example: "To check delivery options I need your ZIP code, not your full address yet."; for log-ins, pause and let the user take over the browser instead of typing credentials into chat.
18. **Render generated UI from trusted components and gate UI-initiated actions like model-initiated ones.** Why: MCP Apps hosts sandbox app iframes and can require approval for UI-initiated tool calls, and A2UI restricts agents to a client-side component catalog. Example: an expense-approval MCP App whose [Approve] button triggers the same confirmation and audit entry as the chat path, with a text summary when the host lacks the extension.
19. **Make streaming output and controls accessible.** Why: WCAG 2.2 SC 4.1.3 (AA) requires status messages assistive tech can read without focus, and Article 50 disclosures must meet accessibility requirements **[volatile]**. Example: transcript as `role="log"` with `aria-live="off"`; a visually hidden `role="status"` present from page load announcing "Generating response", "Response ready", "Stopped", "Failed"; focus stays in the input; Stop is a real `<button>`; hidden "You said" / "AI response" headings; status never shown by colour alone.
20. **Use plain, factual language instead of human-like claims.** Why: anthropomorphic phrasing inflates trust (NN/g), and empathy should acknowledge the situation without claiming feelings. Example: "Based on the 3 documents found…" instead of "I feel confident…"; "That delay is frustrating. Let's fix the delivery date" instead of "I feel terrible about this".

## Build checklist
- [ ] Show an AI label on the first screen and on every agent message, and a first-run line stating capabilities and limits; cover both with a UI snapshot test.
- [ ] Classify every tool as read, reversible write or irreversible/external, and implement and test the UI gate for each class.
- [ ] Make every confirmation name the verb, target, key arguments and consequence, with verb-labelled buttons and no bare "OK".
- [ ] Log approve/reject rates per prompt type and review any type with near-universal approval for automation or plan-level approval.
- [ ] Show a plan preview with Proceed / Edit plan / Do it myself before any multi-step or consequential run.
- [ ] Show current step, completed steps and elapsed time during runs; let long runs continue in the background and notify on completion or when input is needed.
- [ ] Make Stop take effect within one tool call, leave consistent state and report what was and was not done; queue and deliver messages typed mid-run.
- [ ] Restore pending approvals from server-side state after a page reload or process restart.
- [ ] Give every grounded claim an inline citation that opens the supporting passage, and add eval cases that check each citation supports its claim.
- [ ] Add eval cases for no-evidence and out-of-scope requests that assert abstention or redirect wording.
- [ ] Show Undo with its time window on every reversible action, and test undo end to end.
- [ ] Provide an action history listing time, tool, arguments, result, approver and status for every action, with export.
- [ ] Make "Talk to a person" reachable from every screen, pass a conversation summary on handoff, and offer it automatically after two failed repairs.
- [ ] Write error messages for each tool failure that state what happened, the current state and the next options.
- [ ] Request personal data at the point of use with a reason, and route credential entry through user takeover, never chat.
- [ ] Pass a keyboard-only test and screen-reader tests (at least NVDA and VoiceOver) covering streaming, Stop, approvals and citation previews.
- [ ] Give generated UI (MCP Apps, A2UI, widgets) a text fallback, and route its actions through the same approval and audit path as chat.

## Avoid
- A permission prompt on every tool call → sandbox and policy for routine steps, approval for plans and irreversible actions (people approve almost everything and stop reading).
- "Are you sure?" with OK / Cancel → the exact action, target and consequence with verb-labelled buttons (generic dialogs get reflexive clicks).
- Silent long runs → a plan, step progress and a completion notification (users cannot tell slow from stuck).
- Showing raw chain-of-thought as the explanation → the inputs that drove the decision, plus sources (reasoning traces are often unfaithful).
- A source list at the end of the answer → claim-level markers with passage previews (users can't tell which claim a source supports).
- Percentage confidence → a few categories, each tied to a user action (users misread probabilities).
- Disclaimers in a footer or behind an icon → a plain-language limit next to the input, paired with what to do (users skip hidden disclaimers).
- Making users argue their way to a human → immediate handoff with context (gatekeeping destroys trust).
- A Stop that discards completed work or leaves half-written changes → stop at a tool boundary and report state (users stop pressing Stop if it is destructive).
- Human-like feelings and first-person warmth → neutral, factual phrasing (it inflates trust beyond capability).
- Requesting full address or credentials up front → just-in-time requests for the minimum, and takeover for secrets (early data exposure drives abandonment).
- Generated UI that runs arbitrary agent-written code in the host page → a sandboxed iframe or a trusted component catalog (agent output is untrusted).
- Making the streaming message body an `aria-live` region → a separate status region for lifecycle announcements (screen readers re-read fragments or skip updates).

## Additions (verified 2026-10-27)

- **Make checking fast.** At every human checkpoint show the diff, the highlighted change or the cited source passage, never a wall of text to re-read; review speed is the throughput limit of a supervised agent.
- **Autonomy levels by scope.** Define levels by how much the agent may change (suggest → edit a selection → edit an artifact → run multiple steps), start at the lowest that works, and raise a level only when logged acceptance and reversion rates support it.

## Verify before relying
| Fact **[volatile]** | Snapshot (2026-10-27) | Where to check (URL) |
| --- | --- | --- |
| EU AI Act Art. 50 AI-interaction disclosure | Applies from 2 Aug 2026; Digital Omnibus postponed high-risk duties, not Art. 50(1) | https://artificialintelligenceact.eu/article/50/ |
| Claude Code approval data | 93% of prompts approved (May 2026), 97% (Aug 2026); 39% of plans rejected; reviewers caught 13.6% vs auto mode 89%; ~17% → ~5% after 50+ prompts | https://claude.com/blog/auto-mode-default-in-claude-code |
| OS sandboxing effect on prompts | 84% fewer permission prompts in Claude Code | https://www.anthropic.com/engineering/how-we-contain-claude |
| Auto mode as default | Default for new Pro, Max and Team sessions (rolling out late Oct 2026); Enterprise and API opt-in | https://claude.com/blog/auto-mode-default-in-claude-code |
| MCP Apps | Official extension, spec 2026-01-26 stable; `_meta.ui.resourceUri`, `ui://`, `text/html;profile=mcp-app`; hosts incl. Claude, VS Code Copilot, M365 Copilot, Goose, ChatGPT | https://modelcontextprotocol.io/extensions/apps/overview |
| ChatGPT Apps SDK and MCP Apps | ChatGPT implements MCP Apps; `window.openai` only for extras; legacy aliases still work | https://developers.openai.com/apps-sdk/mcp-apps-in-chatgpt |
| OpenAI ChatKit / Agent Builder | ChatKit available; Agent Builder deprecated, shutdown scheduled 2026-11-30 | https://developers.openai.com/api/docs/guides/chatkit |
| AG-UI protocol | No protocol version on docs; interrupt outcome fields still draft; `THINKING_*` events removed at 1.0.0; OpenAI Agents SDK integration "In Progress" | https://docs.ag-ui.com/concepts/events |
| A2UI | v0.9.1 current, v1.0 release candidate, v0.8 legacy; "Early stage public preview" | https://github.com/google/A2UI |
| OpenAI Agents SDK approvals | `needs_approval`; durable `RunState`; approval is not exactly-once | https://openai.github.io/openai-agents-python/human_in_the_loop/ |
| Claude Code checkpoints | Snapshots for 100 most recent checkpoints, ~30-day retention, shell changes not tracked | https://code.claude.com/docs/en/checkpointing |
| Smashing agentic UX metrics | Plan acceptance >85%, reversion >5% disables automation, escalation 5–15% (author's representative benchmarks) | https://www.smashingmagazine.com/2026/02/designing-agentic-ai-practical-ux-patterns/ |

## Sources
- [Guidelines for Human-AI Interaction (HAX Design Library)](https://www.microsoft.com/en-us/haxtoolkit/library/) — Microsoft (Amershi et al., CHI 2019), accessed 2026-10-27
- [Explainability + Trust](https://pair.withgoogle.com/chapter/explainability-trust/) — Google PAIR People + AI Guidebook, undated (accessed 2026-10-27)
- [The 5 Qualities of Site-Specific AI Chatbots](https://www.nngroup.com/articles/dimensions-of-ai-chatbots/) — Nielsen Norman Group, 2026-07-10
- [Designing AI Agents: 4 Lessons from China's Qwen Agent](https://www.nngroup.com/articles/designing-ai-agents/) — Nielsen Norman Group, 2026-05-08
- [Explainable AI in Chat Interfaces](https://www.nngroup.com/articles/explainable-ai/) — Nielsen Norman Group, 2025-12-12
- [Initial Impressions of ChatGPT's Agent](https://www.nngroup.com/articles/impressions-chatgpt-agent/) — Nielsen Norman Group, 2025-08-08
- [AI Chatbots Discourage Error Checking](https://www.nngroup.com/articles/ai-chatbots-discourage-error-checking/) — Nielsen Norman Group, 2025-05-16
- [Designing For Agentic AI: Practical UX Patterns For Control, Consent, And Accountability](https://www.smashingmagazine.com/2026/02/designing-agentic-ai-practical-ux-patterns/) — Smashing Magazine (Victor Yocco), 2026-02-11
- [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) — Anthropic, 2024-12-19
- [Auto mode for Claude Code](https://claude.com/blog/auto-mode) — Anthropic, 2026-03-24
- [How we contain Claude across products](https://www.anthropic.com/engineering/how-we-contain-claude) — Anthropic, 2026-05-25
- [Auto mode is now the default in Claude Code](https://claude.com/blog/auto-mode-default-in-claude-code) — Anthropic, 2026-08-07 (updated 2026-10-22)
- [Checkpointing](https://code.claude.com/docs/en/checkpointing) and [Interactive mode](https://code.claude.com/docs/en/interactive-mode) — Claude Code docs, accessed 2026-10-27
- [Claude Managed Agents overview](https://platform.claude.com/docs/en/managed-agents/overview) — Anthropic docs, accessed 2026-10-27
- [Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/) — OpenAI Agents SDK docs, accessed 2026-10-27
- [SEP-1865: MCP Apps](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp.md) — Model Context Protocol, created 2025-11-21 (Final)
- [MCP Apps overview](https://modelcontextprotocol.io/extensions/apps/overview) and [MCP Apps launch post](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/) — Model Context Protocol, 2026-01-26
- [modelcontextprotocol/ext-apps](https://github.com/modelcontextprotocol/ext-apps) — MCP (GitHub), accessed 2026-10-27
- [MCP Apps compatibility in ChatGPT](https://developers.openai.com/apps-sdk/mcp-apps-in-chatgpt) and [ChatKit](https://developers.openai.com/api/docs/guides/chatkit) — OpenAI docs, accessed 2026-10-27
- [AG-UI introduction](https://docs.ag-ui.com/introduction) and [Events](https://docs.ag-ui.com/concepts/events) — AG-UI (CopilotKit), accessed 2026-10-27
- [A2UI](https://github.com/google/A2UI) — Google (GitHub), accessed 2026-10-27
- [Article 50: Transparency obligations](https://artificialintelligenceact.eu/article/50/) — EU AI Act (Future of Life Institute site), accessed 2026-10-27
- [What came into force with the EU's AI Act this week](https://www.aljazeera.com/economy/2026/8/6/what-came-into-force-with-the-eus-ai-act-this-week-and-what-didnt) — Al Jazeera, 2026-08-06
- [Understanding SC 4.1.3 Status Messages](https://w3c.github.io/wcag/understanding/status-messages.html) — W3C (editor's draft), accessed 2026-10-27
- [ARIA: status role](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/status_role) — MDN, accessed 2026-10-27
- [Accessible streaming chat UI](https://azukiazusa.dev/en/blog/accessible-streaming-chat-ui) — azukiazusa, 2026-08-11
