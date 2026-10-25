# Resolvox — Engineering Design

## Four cumulative steps

1. **Prompt-only baseline:** call the LLM with its role, limits and AI-disclosure requirements, without company documents, catalog or private order access. Preserve actual predictions and failures.
2. **Document-driven RAG:** retrieve KB sections before routing and generate from actual text plus verified facts. Save full host-supplied generation chunks and IDs, source metadata, search candidates, composition and failures. Practice/holdout answers are never runtime knowledge.
3. **Conversation:** state, verification and supplied tools surround generation. Deterministic operational guards handle authentication, privacy, safety and confirmed handover.
4. **Gnani speech:** STT → the same agent → TTS, with explicit TTS model, per-file failure isolation and redacted JSON/text/WAV/source outputs. Failed speech produces no substitute audio.

## Data and authority

The synthetic dataset links customers → orders → order items → products, with public pincodes and holidays. IDs remain strings. Public catalog/calendar access is separate from private order lookup through supplied tools. Missing records do not imply completed actions; historical support logs are not policy evidence.

Current policy outranks agent guide, help, FAQ and marketing. Chunks retain ID, file, status, version and effective date. Superseded sections are excluded except for scope explicitly authorized by successor policy. A historical return-window exception does not revive an unrelated old pickup rule.

## Query-first retrieval

`Retriever.search(query, k=12, historical=..., intent=...)` runs before the planner. Raw lexical and multilingual MiniLM scores are fused separately from narrowly expanded channels. Expansion uses reusable language aliases and operation context, not test IDs or expected answers. Intent is a weak hint gated by query evidence.

Lexical indexing preserves document topics and full tables. Dense indexing combines section text with heading/prose representations. Content/settings fingerprints identify cached vectors; read-only deployments may retain regenerated vectors in memory. Dependencies follow explicit references, named concepts and applicable calendar/exception rules within a bounded budget.

Only actual retrieved sections and independently obtained public catalog rows enter normal generation. Legacy planner IDs are routing hints intersected with retrieved results; they cannot inject missing sections. Retrieval candidates are separate from selected generation context and operational guard lookups. Search recall at **k=12** is not answer correctness.

## Source-only generation

`src/document_answers.py` receives the question, language, actual source text/metadata, reference date and safe host-derived facts. It never imports the legacy policy planner or receives its authored policy answer, answer summary, expected answer or required source list. The selected LLM is `qwen3:4b-instruct` with a 120-second per-request RAG timeout. This timeout does not bound a complete turn including repair.

The normal agent invokes `document_reply(..., context_provenance=True)`. The model returns `answer` and strict boolean flags `covered` and `needs_clarification`. The host derives `clarify` when clarification is requested, otherwise `answer` when covered, otherwise `refuse`. Traces retain `model_flags` and `decision_origin=host_boolean_mapping`. It does not have to reproduce source IDs or verbatim quotes. The host records the exact full supplied sections in `generation_context_sources`, along with `context_source_ids` and `provenance_kind=generation_context`.

A covered response is validated against that actual context and safe facts, then receives the supplied context IDs as source provenance. Its normal `citations` field is empty: these IDs are not claimed as model-selected citations or per-claim support. An uncovered response must be non-substantive clarification or uncertainty and has no domain-answer source IDs. The attempted generation context remains recorded separately, including when generation fails.

Validation checks supported quantities/units, language, private identifiers and invented actions. It does not make every retrieved number, exclusion or table row an answer obligation. At most **one repair** follows invalid output. Repair is uncached; private turns bypass persistent output caching on every attempt. Unavailable inference or another invalid output causes abstention. **Prewritten policy fallback is removed from normal answer generation.**

Finite checks do not prove per-claim entailment or full coverage. A matching quantity elsewhere in the supplied context can still be misapplied; a model can omit a condition, confuse an actor or answer only part of a question. Both flags are model output, not independent semantic certificates. The host mapping does not validate facts by itself; existing evidence, quantity, privacy, action and language checks still apply. Exact legacy answer/decision/covered responses remain strictly validated for compatibility and are labeled `legacy_model_decision`; mixed schemas are rejected. Invalid output, repair reasons and timings remain recorded.

The legacy compatibility adapter in `src/grounding.py` also ignores its authored-plan argument. Legacy planner prose remains for routing and operational guards, not as normal prompt summaries or policy-answer fallback. Fingerprint-bound guard/escalation explanations may contain policy text. Ordinary generated answers do not require preapproved policy SHA bindings.

## Verified facts and calculations

`src/document_context.py` builds an allowlisted context from verified tool records, public catalog/context slots and retrieved policy text. Verification proofs, phone numbers, email, street addresses, private delivery pincodes, customer identities and internal notes do not enter the model context.

Numeric policy inputs are parsed from retrieved text rather than copied from authored answer plans. Absent or ambiguous evidence produces no calculation. Traces retain calculation inputs, source IDs and source hashes. The reference date is **20 October 2026**. Business calendars come from governing weekday text plus supplied holidays; refund elapsed days begin after initiation. Return deadlines use delivery + N calendar days, treating delivery as day zero. This convention remains explicit because the return wording does not fully specify inclusive arithmetic.

For public refund questions, an explicitly supplied initiation date and payment method remain `customer_provided` and unverified. They may support a conditional policy-date calculation without granting private order access or asserting that a refund actually happened.

Question-relevant `answer_constraints` contain only source-derived scalars: a selected category's calendar-day window, a calculated latest refund date or a parsed delivery-attempt limit. Constraint source IDs must be present in the actual generation context, and values must have independent typed-fact/calculation proof. Only covered answers to relevant questions are checked; unrelated supplied facts do not become answer obligations. A mismatched value gets one source-bound repair, then uncertainty. Full dates require ISO or explicit day/month/year; a bare day does not satisfy a date. These checks are finite coverage guards, not semantic entailment. The normal path also rejects an echoed question or a one-word policy reply.

Record-scoped statuses and refund completion dates must match authenticated fields. Only actual allowlisted refund references, explicitly labeled RRN/refund reference on private turns, bypass generic long-number filtering. These narrow exceptions do not authorize assistant-performed action claims.

## Operational guards, state and actions

`deterministic_guardrail` covers verification, privacy refusal, safety/fraud/legal/requested-human handover, repeated-contact safeguards, greeting/audio recovery and limited missing-record prompts. Evidence-bound guard/escalation text and confirmed tool-result wording can be deterministic and policy-bearing. This is distinct from ordinary compensation, return, warranty, delivery and refund answers, which use document generation.

Proof crosses only the supplied lookup boundary and is discarded. One failed proof permits one retry; another locks that order for the session. Order switches clear verified context and pending order-specific state while retaining per-order failed-attempt counts. Unverified lookup returns only a verification prompt. Follow-ups cannot inherit another order's private data or authentication.

Urgent handover does not wait for authentication. Ticket success requires `created=True` and is reused only for the same order/reason. Failed creation is reported as failed. Summaries contain the issue, checks and reason without proofs. No cancellation/refund/replacement execution API exists.

Composition labels separate `grounded_llm`, `grounded_clarification`, `deterministic_guardrail`, abstentions and `document_excerpts`. With `compose=False`, ordinary domain output is explicitly labeled retrieved excerpts, not an authored-answer substitute. The legacy `--offline-rules` flag selects that diagnostic while retaining operational guards.

## Privacy and speech

Credential normalization covers phone-ending and Hindi/Roman proof phrases without treating phone-product questions as credentials. Traces omit proofs and private contacts. Raw input audio is transient and not copied to outputs. Synthetic educational verification is not production authentication.

Only official Gnani STT/TTS is used, including retries. Multipart streams rewind; empty/invalid transcripts and incomplete WAVs fail validation. Unknown RIFF/data sizes are finalized without changing PCM. Optional regional translation stays local around the same agent and adds no speech provider.

Synthetic TTS-input round trips do not establish human accent/noise robustness or intelligibility. Own-voice/listening tests remain for the final rehearsal.

## Evaluation and provenance

The source-only change invalidates earlier authored-fallback scores as evidence of current performance. Legacy offline practice 52/52 and 96/96, adversarial 77/77, exposed offline regression 91/91 and live practice 52/52 and 96/96 retain their actual composition. Pre-change live files are archived under `sample_outputs/history/pre_document_answers/`. They are not current pass claims.

Current boolean-contract core `1914516` passed **658/658 engineering tests in 53.74 seconds**. The prior three-field revision passed 626 tests; that remains historical. Earlier core `8e6992b` passed 590/590 in 20.30 seconds. The dataset validator passed 9 CSVs and 21 KB documents. The first real boolean-contract Hinglish warranty pilot returned a supported answer without repair; the card-refund pilot remains pending. These diagnostics are not a full benchmark. Current live 52-question/96-turn runs, speech, report and package checks remain pending. Final measurements must retain source/input/settings hashes, completion flags, composition and failures.

The frozen holdout contains 64 singles plus 10 scenarios/27 turns (91 judged responses). Its rubric SHA-256 is `5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7`. The first independent offline result was **23/91**. Old 49/91 predictions rescore unchanged to **51/91** under scorer v2; only two points came from wording normalization. The later legacy **91/91** was exposed regression after fixes, not a new independent result. No current live holdout is complete. The incomplete strict quote pilot passed 1/8 checked questions. The initial context-mode diagnostic passed **10/30 checked of 52 planned** before being stopped and preserved under `sample_outputs/history/source_context_first_pass/`. These pilots predate the final source-derived numeric, language and quality fixes; neither is a final-runtime score.

The historical prompt-only baseline used `qwen3:1.7b`; the current model is `qwen3:4b-instruct`. A comparison across those runs is not a controlled same-model baseline/RAG ablation. Earlier live and diagnostic small-model runs retain their actual model identity; offline authored-answer scores did not measure LLM generation.

Report decisions, required/forbidden facts, tools, retrieval coverage, actual generation context, repairs, abstentions and failures separately. Current offline excerpts are not comparable with earlier authored-answer scoring.

Distinguish cold startup, warm uncached inference and output-cache hits. Agent-turn time excludes previous resource loading; voice time includes STT/TTS. Request timeouts are not a hard end-to-end bound. Cache keys contain provider/model/settings and the full prompt. A cache hit is not a fresh inference.

## Release boundary

Report length is at most four pages. The user records `demo.mp4`, at most 120 seconds, **last** after own-voice rehearsal. The existing report PDF and ZIP are stale drafts; regeneration and current verification are pending. Exclude credentials, dataset copies, caches, model weights, environments and private inputs. Keep the archive draft until current evidence and required artifacts are complete. No ranking or hidden-test result is guaranteed.
