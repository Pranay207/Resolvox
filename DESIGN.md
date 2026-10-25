# Design - ZentroMart VoiceOps

## Four cumulative steps

1. Prompt-only baseline: the configured LLM receives its role, limits and disclosure requirements without company documents, catalog or order access. Store actual predictions and failures.
2. RAG: retrieve KB sections before planning, then generate replies from their actual source text. Preserve source IDs, metadata, search candidates, generation mode and validation failures. No practice or holdout answers enter the runtime index.
3. Conversation: deterministic verification, arithmetic and tool boundaries surround retrieval and generation. State is session-scoped. Urgent safety, fraud, legal and requested-human handovers do not wait for authentication.
4. Gnani speech: STT -> the same agent -> TTS, with explicit served TTS model, independent per-file failures and redacted JSON/text/WAV/source outputs. Speech failures produce no substitute audio.

## Data and authority

The supplied synthetic dataset links customers -> orders -> order items -> products, with pincodes and holidays for delivery and date arithmetic. Identifiers remain strings. Public catalog/pincode lookups are separate from private order access, which uses the supplied tools unchanged. Missing records or fields do not imply completed actions. Historical support logs are not policy evidence.

Current policy > agent guide > help > FAQ > marketing; meta instructions govern precedence and the fixed reference date. Chunks preserve section ID, file, status, version and effective date. Superseded sections are excluded except for the earlier electronics window explicitly authorized by the successor policy for pre-1-August-2026 deliveries. The old free-pickup rule remains excluded even for historical queries. A generic FAQ or marketing benefit cannot override a current payment-specific or membership policy.

## Query-first retrieval

`Retriever.search(query, k=12, historical=..., intent=...)` is invoked before the policy planner. Raw-query BM25 and multilingual MiniLM scores are fused separately from lighter query-expanded channels. Expansion uses reusable language aliases and requested-operation context, not question IDs or expected answers. Intent is a weak hint, gated by query evidence. Hindi tokenization preserves combining marks; the dense model provides cross-language retrieval beyond the glossary.

The lexical index includes each section's document topic and complete table/body context. Dense retrieval has full-section and concise heading/prose representations, so a numeric table cannot hide its subject. A settings/content fingerprint identifies cached vectors; read-only deployments can retain regenerated vectors in memory. Strong expanded lexical candidates remain available when semantic models mishandle negation or unfamiliar product names.

Source dependencies follow explicit section references, named policy concepts and applicable calendar/precedence/exception rules. The dependency budget is bounded so direct query evidence remains the majority of a bundle. Historical eligibility is checked before ranking and again before the agent uses a source. Search recall at the agent's actual **k=12** is reported separately from sources used in a reply. Retrieval coverage does not establish answer correctness.

## Source-text generation and fallback

The agent constructs a policy view from actual retrieved chunks; rules do not first select their preferred IDs from the full KB. Public catalog/pincode records and verified order facts are added through their own factual lookup boundaries. The LLM receives actual section text with status/version/date metadata, deterministic facts, requested language and an optional checked rule summary. The selected local model is `qwen3:1.7b`; it generates new reply wording as answer-only JSON.

The model does not select source IDs or citation spans. Code attaches the IDs and exact full sections actually supplied as context to the validator and provenance trace. Source-contract checks reject foreign/absent required sources, unsupported numeric values or quantity units, selected omitted numeric/negative constraints, wrong output language, private identifiers and common fabricated completed-action language. Full-section provenance establishes what the model received; it is not per-claim semantic proof. Finite lexical checks can miss actor, condition and paraphrase errors, and can reject valid wording.

A deterministic policy fallback is permitted only when every governing section was retrieved and matches its reviewed SHA-256 binding in `src/rule_bindings.json`. The fingerprint includes ID, text, status, effective date, version and document type. It is a reviewed compatibility check, not automatic rule extraction. Policy edits therefore require reviewing the static rules and bindings. Missing/changed evidence causes abstention; failure to validate model text does not authorize a canned answer from a stale policy.

Authentication, privacy refusal, urgent escalation, repeated-contact safeguards and confirmed tool outcomes have explicit guard-policy lookups. They are labeled `deterministic_guardrail`; these sources are distinguishable from query search candidates. Model generation, checked static fallback and abstention have separate composition labels and validation traces. Do not count a cache hit or fallback as a fresh successful model response.

## Deterministic dates, state and actions

The reference date is 20 October 2026. Business days are Monday-Saturday excluding supplied holidays; refund elapsed days begin after initiation. Return deadlines use delivery + N calendar days, treating delivery as day zero. The return-window wording does not fully specify inclusive arithmetic; this convention matches the supplied practice deadlines and remains an explicit ambiguity. Sale-date/category exceptions, post-initiation refund timelines, marketplace warranty limits and damage/safety thresholds must come from governing evidence.

Order proof is sent only to the supplied lookup boundary and discarded. One failed proof permits one retry; a second failure locks that order for the session. Switching order IDs clears verified order context and pending order-specific state, while retaining per-order failed-attempt counts. The initial unverified lookup discloses only a verification prompt. Follow-ups use the currently verified order; they must not inherit an earlier order's data or authentication.

Ticket success is reported only after `created=True`. Successful tickets are deduplicated by order and escalation reason, so a different order receives its own ticket. A failed creation is reported as failed and cannot be reused as success. Handover summaries include the issue, intent, order when available, checks and reason without proof values. There is no cancellation API: guide the customer to My Orders. Never invent execution of refunds, replacements or compensation.

## Privacy and speech

Credential recognition covers phone-ending and Hindi/Roman proof phrases without treating ordinary phone-product questions as credentials. Model inputs and traces omit verification secrets and private contact fields. Verified order context is sanitized; full phone numbers, email, street address, pincode, customer identity and internal notes are not returned to the customer. Raw voice is transient and is not copied into outputs. This synthetic educational verification is not production authentication.

Speech uses the official Gnani REST endpoints only. Multipart inputs are rewound for retries, empty/invalid STT transcripts are rejected, and WAV samples are checked. Provider `0xffffffff` RIFF/data sizes are finalized while preserving identical PCM; incomplete/truncated samples fail validation. `--offline-rules` affects answer generation only; it does not replace Gnani STT/TTS. Synthetic Gnani TTS inputs support repeatable round trips. Human speech testing and subjective listening have not been completed, so robustness to human accents or noise is unverified.

## Evaluation and timing

Keep practice, development adversarial cases and the frozen independent holdout distinct. The practice set was used during implementation. The frozen `tests/holdout_cases.json` contains 64 single questions plus 10 scenarios/27 turns: 91 judged responses. Full rubric SHA-256: `5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7`. Validate with `python eval_holdout.py --check-only`; `python eval_holdout.py` evaluates live generation and `--offline` evaluates rules. Results belong in `sample_outputs/eval_holdout.json`. No pending run has a claimed score.

Report decisions, required/forbidden facts, tools, retrieval coverage and answer-used evidence separately. Retain invalid JSON, timeouts, fallback frequency, abstentions and semantic failures. Exact keyword/rubric matching is not a semantic certificate or organizer score. Generated JSON, model benchmarks and final verification outputs are the source for current numbers; historical sentence-ordering scores must not be reused for this generation architecture.

Distinguish cold startup, warm uncached inference and output-cache hits. Resource/model loading may precede `Agent.respond`, so its turn latency is not cold-start time. Voice end-to-end latency includes STT and TTS as well as the agent. LLM traces expose cache status and provider timing where available. Cache keys include model/provider/settings and the complete prompt payload, including source text, facts and language. Verified-order turns bypass persistent model-output caching. A fast warm/cache response cannot be presented as fresh cold inference.

## Release boundary

The report is at most four pages; the user records `demo.mp4` at at most 120 seconds after final verification. Packaging excludes credentials, dataset copies, caches, model weights, environments and private audio. Keep the package marked draft until all required artifacts and checks pass. Report current measurements honestly; no placing or hidden-test result is guaranteed.
