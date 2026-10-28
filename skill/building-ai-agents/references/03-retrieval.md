# 03 · Retrieval and grounding

> Snapshot verified 2026-10-27. Items tagged **[volatile]** change often — re-check them with the freshness protocol in SKILL.md before relying on them.

## Default
Give the agent retrieval as a tool it calls, backed by a permission-aware hybrid index: layout-aware parsing, structure-aware chunks with a contextual prefix, BM25 + dense candidates (~100–150), a reranker, and a calibrated score threshold instead of a fixed top-k. Skip retrieval only when the whole corpus is under ~200K tokens, rarely changes and every user may see all of it; then put it in the prompt with prompt caching. Add a graph or tree index only when your golden set shows many multi-hop, comparison, temporal or whole-corpus questions; for code and small, fast-changing file trees, give the agent grep/read tools first. Enforce document ACLs inside the search engine with the end user's own token. Measure retrieval (recall@k against expected source documents) separately from answer faithfulness, and re-run that eval on every pipeline change.

## Pipeline
1. **Parse with layout.** Run a layout-aware parser (Docling-style: reading order, headings, table structure, formulas, OCR for scans, optional VLM pipeline; emits Markdown or lossless JSON) and keep its structure tree ([Docling](https://github.com/docling-project/docling)). *Replaces* flat text extraction that scrambles multi-column pages and flattens tables. *Gain:* no parser benchmark was opened for this snapshot — pick a parser by inspecting output on 20 of your hardest documents.
2. **Add a page-image path for visual documents.** For slides, scans, charts and statements, embed page images with a late-interaction VLM retriever (ColPali **[volatile]**-style) or a multimodal embedder, next to the text path. *Replaces* OCR → text → embed where meaning lives in layout. *Gain:* ColPali "largely outperforms" modern parsing pipelines on ViDoRe and indexes faster ([arXiv 2407.01449](https://arxiv.org/abs/2407.01449)); vendor-reported ViDoRe V3: Cohere Embed 5 Pro **[volatile]** 85.8 vs OpenAI text-embedding-3-large **[volatile]** 75.5 ([Cohere](https://cohere.com/blog/embed-5)).
3. **Chunk along structure.** Split at section/heading boundaries, keep each table (with header row) and list whole, and store heading path, doc id, version, page and last-modified on every chunk. *Replaces* fixed token windows, still the managed-tool default (Gemini File Search `chunking_config`, docs example 200 tokens / 20 overlap **[volatile]**, [Google](https://ai.google.dev/gemini-api/docs/file-search)). *Gain:* no opened source ranks structure vs semantic vs fixed chunking head-to-head; tune size on your eval.
4. **Contextualize every chunk.** Either prepend 50–100 LLM-written tokens that situate the chunk in its document — to both the embedded text and the BM25 text, with prompt caching over the document (Contextual Retrieval) — or use late chunking (embed the whole document with a long-context embedder, pool per chunk; no LLM calls, no training). *Replaces* context-free chunks ("the company's revenue grew 3%" with no company). *Gain:* top-20 retrieval failure 5.7% → 3.7% with contextual embeddings (−35%), → 2.9% adding contextual BM25 (−49%), Anthropic-reported **[volatile]** ([Anthropic](https://www.anthropic.com/news/contextual-retrieval)); late chunking reports "superior results" across retrieval tasks ([arXiv 2409.04701](https://arxiv.org/abs/2409.04701)).
5. **Hybrid first stage, retrieve wide.** Run BM25 and dense search in parallel, fuse the ranked lists, keep ~150 candidates. *Replaces* dense-only top-5 cosine, which misses exact identifiers, error codes and names. *Gain:* contextual BM25 on top of contextual embeddings is the −35% → −49% step above.
6. **Rerank, then threshold.** Rerank candidates with a cross-encoder or listwise reranker; pass what clears a score threshold calibrated on your golden set (cap ~20 chunks). *Replaces* fixed top-k by vector similarity. *Gain:* reranking 150 → 20 took total failure reduction to −67% (1.9%), and top-20 beat top-5 and top-10, Anthropic-reported **[volatile]**; Cohere Rerank 5 **[volatile]** reports calibrated scores (ECE ~0.06 vs ~0.23–0.38 for other rerankers tested) and span trimming that keeps 96% of answer quality with half the text, vendor-reported ([Cohere](https://cohere.com/blog/rerank-5)).
7. **Plan compound queries.** For multi-part, comparative or history-dependent questions, have an LLM turn query + chat history into focused subqueries, run them in parallel through steps 5–6, and merge with source references. *Replaces* one literal query string. *Gain:* not quantified; productized in Azure AI Search agentic retrieval (LLM query planning still in `2026-08-01-preview` **[volatile]**), which states it adds latency ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview)). Skip for single-ask lookups.
8. **Expose retrieval as tools.** Give the agent `search(query, filters, k)` returning ids, titles, snippets, scores, page/section and last-modified; `read(doc_id, section|page)`; and, for files or code, `grep`/keyword search. Let it iterate and rewrite the query when nothing clears the threshold. *Replaces* stuffing top-k into the prompt before the first turn ([Anthropic, context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)). *Gain:* a keyword-only agent (pdfgrep-style tools, no index) reached 94.5% of vector RAG's faithfulness and 88% of its context recall, and beat it on FinanceBench ([arXiv 2602.23368](https://arxiv.org/abs/2602.23368v1)); on code, capping reads lifted file precision 65% → 81% and adding semantic search → 87%, with grep and semantic finding different files (vendor talk **[volatile]**, [AI Engineer](https://www.ai.engineer/talks/zKk7sDMGDEQ-benchmarking-semantic-code-retrieval-on-claude)). Managed options **[volatile]**: OpenAI `file_search`, Gemini API File Search, Azure knowledge bases via retrieve action or MCP.
9. **Filter permissions inside the index.** At ingestion copy each document's ACL / sensitivity label onto every chunk row; at query time pass the end user's own identity token so the engine trims results. *Replaces* post-query filtering in app code and retrieval under a shared service account. *Evidence:* Azure AI Search **[volatile]** (ACL modes mostly preview) takes the user token in `x-ms-query-source-authorization`; ACL fields not projected onto chunk rows are not filtered; in-engine trimming is faster than post-query trimming; permission changes apply only after the next sync (indexer run, push, Purview refresh) and inherited SharePoint changes need an explicit refresh ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview)). Measure that re-sync lag.
10. **Index freshness rule: re-index on change, version with the release.** Re-index a document on every create/update/delete event (re-parse, re-chunk, re-contextualize, re-embed; delete its old chunks) and re-sync ACLs on permission events. Rebuild fully when parser, chunker, context prompt, embedder or reranker changes; never mix two embedders' vectors in one index. Name each index with its pipeline-config hash, pin that index in the agent release, swap via alias only after the golden-set eval passes, keep the previous index for rollback. *Replaces* nightly rebuilds of one mutable index. *Evidence:* incremental graph updates exist ([LightRAG](https://arxiv.org/abs/2410.05779)); keyword agents need no standing index for fast-changing corpora ([arXiv 2602.23368](https://arxiv.org/abs/2602.23368v1)); staleness was one reason given for Claude Code **[volatile]** dropping its vector index ([AI Engineer](https://www.ai.engineer/talks/zKk7sDMGDEQ-benchmarking-semantic-code-retrieval-on-claude)).
11. **Cite and abstain.** Return doc id, page/section and span with every chunk, require the answer to cite them, and have the agent say "not found" (or ask) when nothing clears the threshold. *Replaces* uncited answers. Managed tools emit citations natively **[volatile]**: OpenAI `file_citation` ([OpenAI](https://developers.openai.com/api/docs/guides/tools-file-search)), Gemini citations with page numbers, Azure source references plus an activity log.
12. **Evaluate retrieval separately from generation — minimal recipe.**
    a. Collect 100–200 real questions (search logs, tickets, SME interviews). Stratify: single-hop fact, multi-hop, comparison, temporal, whole-corpus summary, unanswerable, permission-restricted.
    b. For each, an SME records the expected source document ids (+ page/section) and a one-line reference answer. Label at document level so labels survive re-chunking.
    c. Add permission pairs: the same question run as two users with different ACLs; restricted documents must never appear (leak count = 0).
    d. Retrieval score: document-level recall@k at the k you actually pass to the model (report 1 − recall@20 as Anthropic does), plus MRR; unanswerables must return nothing above threshold.
    e. Generation score, separately: faithfulness/groundedness to the retrieved context, correctness vs the reference, citation correctness (cited doc is expected and supports the claim). RAGAS defines context recall/precision, faithfulness and response groundedness ([RAGAS](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)).
    f. Debias LLM judges: they reach >80% agreement with humans but show position, verbosity and self-enhancement bias ([arXiv 2306.05685](https://arxiv.org/abs/2306.05685)); order swaps flipped RAG-vs-GraphRAG verdicts ([arXiv 2502.11371v3](https://arxiv.org/html/2502.11371v3)). Swap orders, use a judge from another model family than the generator, prefer reference-based scoring, human-check a sample.
    g. Freeze the set, hold out a slice you never tune on, run it in CI on every parser/chunker/embedder/reranker/prompt change.

## Decide
- If the corpus is under ~200K tokens, stable, and every user may see all of it → put it all in the prompt with prompt caching and skip retrieval, because Anthropic recommends exactly this and you drop index upkeep ([Anthropic](https://www.anthropic.com/news/contextual-retrieval)).
- If the corpus would fit a 1M-token window but exceeds ~200K or is permissioned → retrieve anyway, because all 18 models Chroma tested did markedly better on focused ~300-token inputs than on ~113K-token full inputs (context rot), a shared prompt cannot trim per-user permissions, Claude Opus 4.6 **[volatile]** reports 76% (not 100%) on 8-needle MRCR v2 at 1M (vendor-reported), and LaRA found no RAG-vs-long-context winner across 11 LLMs — test both on your golden set.
- If the corpus is code or a small, fast-changing file tree → agentic keyword search first (glob/grep/read tools), semantic search as an optional second tool, because keyword-only agents reached ~90% of vector-RAG quality with no index, and grep and semantic search find different files.
- If the corpus is large, heterogeneous or permissioned (wikis, SharePoint, tickets, contracts) → hybrid index + rerank behind a search tool, because grep agents degrade on large documents, multimedia and ambiguous queries (the AWS paper's stated limits) and can read whatever their credentials reach.
- If pages carry meaning in layout (slides, scans, charts, financial statements) → add a page-image embedding path, because text extraction loses it and ColPali **[volatile]**-style retrieval beats parsing pipelines on ViDoRe.
- If an LLM call per chunk at ingestion is too slow or not permitted for the data → late chunking; otherwise Contextual Retrieval, because Contextual Retrieval has the stronger published numbers, but no opened source compares the two head-to-head.
- If most questions are single-hop fact or detail lookups → reranked hybrid RAG with no graph, because vanilla RAG beat GraphRAG on single-hop (NQ F1 64.78 vs 63.01) and RAG+rerank beat MS-GraphRAG on fact retrieval (60.92 vs 49.29).
- If many questions chain facts across documents (multi-hop) → HippoRAG 2, because it led multi-hop (HotpotQA F1 63.01; complex reasoning 53.38 vs RAG 42.93) at ~1K prompt tokens/query vs ~0.9K for vanilla RAG, and was built to avoid the factual-recall loss of earlier graph RAG.
- If many questions need whole-corpus sensemaking ("main themes across all incident reports"), comparison or timelines → try LazyGraphRAG first and full GraphRAG global search only if it still wins on your eval, because LazyGraphRAG builds its index with NLP noun-phrase extraction instead of LLM summaries and beat vector RAG, RAPTOR and GraphRAG local/global/DRIFT in Microsoft-reported **[volatile]** LLM-judged tests, while Community-GraphRAG Global wins comparison/temporal (64.02/53.34 vs RAG 57.59/30.70) but fails unanswerable queries, uses ~331K prompt tokens/query and took 5,560 s to index vs 135 s for RAG.
- If questions need understanding of long single documents (manuals, books, long reports) → RAPTOR tree summaries, because RAPTOR raised the best QuALITY result by 20 points absolute accuracy, at ~3.5K prompt tokens/query.
- If the question mix is genuinely mixed → run vector RAG and the graph retriever together and concatenate contexts, because integration gained +6.4% vs +1.1% for an LLM router on MultiHop-RAG.
- If a question has several asks, compares items, or depends on chat history → decompose into parallel subqueries; otherwise send one query, because planning adds latency and has no published gain on single asks.

## Build checklist
- [ ] Parser output on 20 hard sample documents is inspected: tables keep rows/columns, multi-column pages read in order, headings detected.
- [ ] Every chunk row stores doc id, version, heading path, page, last-modified, ACL fields and its contextual prefix.
- [ ] The contextual prefix is applied to both the dense text and the BM25 text.
- [ ] First stage runs BM25 and dense in parallel and returns ≥100 candidates to the reranker.
- [ ] The reranker threshold is chosen by sweeping on the golden set; unanswerable questions return zero chunks above it.
- [ ] The search tool returns ids, snippets, scores, page/section and last-modified; a separate read tool fetches full sections by id.
- [ ] The tool description tells the agent to rewrite the query, or report "not found", when no result clears the threshold.
- [ ] Every query runs with the end user's token; a test asserts a user without access never receives a restricted chunk, including via subqueries and citations.
- [ ] ACL re-sync lag (permission change → enforced) is measured, documented and alerted on.
- [ ] Document create/update/delete events re-index that document within a stated window; deletes remove all its chunks.
- [ ] The index name carries the pipeline-config hash and embedder version; the agent release pins it; the previous index is kept for rollback.
- [ ] The golden set (100–200 stratified questions, doc-level expected sources, permission pairs) is in version control with a held-out slice.
- [ ] CI reports document-level recall@k and permission-leak count on every retrieval change and blocks merge on regression.
- [ ] Faithfulness/groundedness and citation correctness are scored separately from recall@k.
- [ ] LLM-judge runs swap answer order and use a different model family from the generator; a human spot-checks a sample each release.
- [ ] Every stated company fact in an answer carries a citation that resolves to a document the user can open.
- [ ] Embedder and reranker were chosen on the in-domain golden set, and the comparison is saved with the decision log.
- [ ] Tokens and latency per retrieval tool call are logged per question.

## Avoid
- Fixed-size chunks from flat text extraction → layout-aware parse, structure chunks, contextual prefix (Anthropic-reported **[volatile]** 35–49% fewer top-20 failures).
- Dense-only top-5 → hybrid ~150 → rerank → ~20 (top-20 beat top-5/10; reranking reached −67% failures).
- Fixed top-k regardless of score → calibrated threshold, then rewrite or "not found" when empty (weak context invites confident unsupported answers).
- Permission filtering after retrieval in app code, or retrieval under a service account → in-engine trimming with the user's token (faster, and restricted text never reaches the model's context).
- ACLs on the parent document only → project ACL fields onto every chunk row (unprojected chunks are not filtered).
- Assuming revocations are instant → measure re-sync lag, force refresh for inherited permission changes (changes apply only after sync).
- Choosing embedder/reranker by leaderboard rank → in-domain golden-set comparison (the MTEB top spot changes within months, and vendor tables use different setups).
- Defaulting to full GraphRAG → reranked hybrid RAG plus a graph layer only for proven multi-hop/global needs (GraphRAG "frequently underperforms vanilla RAG" on real-world tasks per GraphRAG-Bench, and global search reads ~331K prompt tokens/query).
- Filling a 1M window because it fits → retrieve focused context (context rot across all 18 models tested).
- One blended "RAG quality" judge score → recall@k and faithfulness separately, with a debiased judge (otherwise you cannot tell whether search or generation failed).
- Re-embedding in place or mixing two embedders' vectors → new versioned index, alias swap after eval (vectors from different models are not comparable; in-place changes have no rollback).
- Synthetic-only golden questions → real user questions, LLM-generated ones only as a reviewed supplement (generated questions reuse document wording and flatter lexical matching).
- Letting retrieved text steer actions → treat chunks as untrusted data; see `07-security.md` (documents can carry injected instructions).

## Verify before relying
| Fact **[volatile]** | Snapshot (2026-10-27) | Where to check (URL) |
| --- | --- | --- |
| Contextual Retrieval gains (Anthropic-reported) | Top-20 failure 5.7% → 3.7% → 2.9% → 1.9% with reranking (−35/−49/−67%) | https://www.anthropic.com/news/contextual-retrieval |
| Cohere Embed 5 Pro/Fast, ViDoRe V3 (vendor-reported) | Pro 85.8, Fast 84.5; Voyage 4 Large 83.7; Gemini Embedding 2 83.2; OpenAI text-embedding-3-large 75.5; 128K context, released 2026-09-30 | https://cohere.com/blog/embed-5 |
| ColPali-family page-image retrievers | ICLR 2025; introduced ViDoRe. On ViDoRe v1&v2 (read 2026-10-28) Qwen3.5-based checkpoints lead (85.98) against ColPali v1.3 (76.17); `colpali-engine` is deprecated in favour of Sentence Transformers | https://arxiv.org/abs/2407.01449 |
| MTEB leader | Harrier-OSS-v1-27B still rank 1 on multilingual MTEB v2 at 74.27 when read on 2026-10-28; 78% of its tasks zero-shot | https://blogs.bing.com/search/April-2026/Microsoft-Open-Sources-Industry-Leading-Embedding-Model |
| Cohere Rerank 5 Pro/Fast (vendor-reported) | ECE ~0.06; Context Focus keeps 96%/87% quality at half/quarter text; BRIGHT 82.2; search agent 46% → 58% with 35% fewer tokens; 2026-10-21 | https://cohere.com/blog/rerank-5 |
| Voyage rerank-3 / rerank-3-lite (vendor-reported) | 32K context; NDCG@10 +2.72% vs Cohere Rerank v4.0 Pro, +3.02% vs Qwen3-Reranker-8B; 2026-09-30 | https://blog.voyageai.com/2026/09/30/rerank-3/ |
| Jina reranker v3.5 (vendor-reported) | 0.6B listwise; BEIR 63.20; weights under a non-commercial licence; 2026-08-03 | https://jina.ai/en-US/news/jina-reranker-v3-5-faster-listwise-reranking-hybrid-attention-self-distillation/ |
| Azure AI Search agentic retrieval status | Extractive retrieval GA (REST 2026-04-01); LLM query planning and answer synthesis in 2026-08-01-preview | https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview |
| Azure document-level access status | Security filters GA; ACL/RBAC scopes, Purview labels, SharePoint ACLs preview; incremental SharePoint ACL pickup in 2026-05-01-preview | https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview |
| Gemini API File Search | Managed store; `chunking_config` (example 200/20); gemini-embedding-2 for image chunks; not combinable with Google Search grounding in one request; page updated 2026-10-13 | https://ai.google.dev/gemini-api/docs/file-search |
| OpenAI `file_search` | Hosted Responses API tool; `max_num_results`, attribute filters, `file_citation` annotations | https://developers.openai.com/api/docs/guides/tools-file-search |
| Claude Opus 4.6 long context (Anthropic-reported) | 1M context (beta); 8-needle MRCR v2 at 1M 76% vs Sonnet 4.5 18.5% | https://www.anthropic.com/news/claude-opus-4-6 |
| Claude Code / Cursor retrieval (second-hand, vendor talk) | Claude Code uses agentic grep search, no vector index; Cursor reports semantic search +6.5–23.5% answer accuracy | https://www.ai.engineer/talks/zKk7sDMGDEQ-benchmarking-semantic-code-retrieval-on-claude |
| LazyGraphRAG (Microsoft-reported) | Beat all compared conditions on 100 synthetic queries, LLM-judged; integrated into Microsoft Discovery and Azure Local | https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/ |
| Docling | VLM pipeline (GraniteDocling); latest release version not confirmed | https://github.com/docling-project/docling |

## Sources
- [Introducing Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) — Anthropic, 2024-09-19
- [Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models (arXiv 2409.04701)](https://arxiv.org/abs/2409.04701) — Jina AI, 2024-09-07 (v3 2025-07-07)
- [docling-project/docling](https://github.com/docling-project/docling) — LF AI & Data (from IBM Research), accessed 2026-10-27
- [ColPali: Efficient Document Retrieval with Vision Language Models (arXiv 2407.01449)](https://arxiv.org/abs/2407.01449) — ICLR 2025, 2024-07
- [Embed 5](https://cohere.com/blog/embed-5) — Cohere, 2026-09-30
- [Rerank 5](https://cohere.com/blog/rerank-5) — Cohere, 2026-10-21
- [rerank-3](https://blog.voyageai.com/2026/09/30/rerank-3/) — Voyage AI, 2026-09-30
- [jina-reranker-v3.5](https://jina.ai/en-US/news/jina-reranker-v3-5-faster-listwise-reranking-hybrid-attention-self-distillation/) — Jina AI, 2026-08-03
- [Microsoft open-sources industry-leading embedding model (Harrier)](https://blogs.bing.com/search/April-2026/Microsoft-Open-Sources-Industry-Leading-Embedding-Model) — Microsoft Bing, 2026-04-07
- [Agentic retrieval overview](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview) — Microsoft Learn, 2026-09-16
- [Document-level access control](https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview) — Microsoft Learn, 2026-08-08
- [File Search](https://ai.google.dev/gemini-api/docs/file-search) — Google AI for Developers, 2026-10-13
- [File search](https://developers.openai.com/api/docs/guides/tools-file-search) — OpenAI API docs, accessed 2026-10-27
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Anthropic, 2025-09-29
- [Keyword search is all you need (arXiv 2602.23368)](https://arxiv.org/abs/2602.23368v1) — AWS, 2025-12-19
- [Benchmarking semantic code retrieval on Claude Code](https://www.ai.engineer/talks/zKk7sDMGDEQ-benchmarking-semantic-code-retrieval-on-claude) — AI Engineer Europe talk (turbopuffer speaker), 2026-04-10
- [From Local to Global: A Graph RAG Approach to Query-Focused Summarization (arXiv 2404.16130)](https://arxiv.org/abs/2404.16130) — Microsoft Research, v2 2025-02-19
- [LazyGraphRAG: setting a new standard for quality and cost](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/) — Microsoft Research, 2024-11-25 (note 2025-06-06)
- [RAG vs. GraphRAG: a systematic evaluation (arXiv 2502.11371v3)](https://arxiv.org/html/2502.11371v3) — arXiv, v3 2026-03-04
- [When to use graphs in RAG — GraphRAG-Bench (arXiv 2506.05690v3)](https://arxiv.org/html/2506.05690v3) — arXiv, v3 2026-02-22
- [From RAG to Memory: Non-Parametric Continual Learning for LLMs — HippoRAG 2 (arXiv 2502.14802)](https://arxiv.org/abs/2502.14802) — ICML 2025, v2 2025-06-19
- [RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval (arXiv 2401.18059)](https://arxiv.org/abs/2401.18059) — arXiv, 2024-01-31
- [LightRAG (arXiv 2410.05779)](https://arxiv.org/abs/2410.05779) — arXiv, v3 2025-04-28
- [Context Rot](https://www.trychroma.com/research/context-rot) — Chroma Research, 2025-07-14
- [Claude Opus 4.6](https://www.anthropic.com/news/claude-opus-4-6) — Anthropic, 2026-02-05
- [LaRA: benchmarking RAG and long-context LLMs (arXiv 2502.09977)](https://arxiv.org/abs/2502.09977) — arXiv, 2025-02
- [Available metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/) — RAGAS docs, 2025-12-09
- [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (arXiv 2306.05685)](https://arxiv.org/abs/2306.05685) — NeurIPS 2023 Datasets and Benchmarks, 2023-06-09
