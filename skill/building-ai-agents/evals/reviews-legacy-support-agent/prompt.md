---
tags: [building-ai-agents]
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, WebSearch, WebFetch]
---

here's our customer support agent, built in early 2024. tell me what to change so it's up to today's standard, prioritized. save it as review.md

- LangChain 0.1 AgentExecutor, GPT-4-turbo
- one ~6,000-token system prompt with every support policy pasted in
- Pinecone, top-5 cosine similarity over ~2,000 help-center articles, fixed 512-token chunks
- Redis semantic cache keyed on the question text, shared across all customers
- Salesforce tools (look up orders, issue refunds) called with one admin API key
- prompt-injection defense = an input classifier in front of the model
- full prompts and responses logged to S3
- no automated evals, we test by hand before each release
