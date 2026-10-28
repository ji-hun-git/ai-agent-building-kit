---
type: llm
focus: trace
weight: 1
---

design.md treats retrieved documents or tool output as untrusted input (indirect prompt injection) and names at least one structural control beyond an input classifier, such as separating data from tool selection, restricting outbound channels, or deterministic policy checks on tool calls.
