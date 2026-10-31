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

`Retriever.search(query, k=12, historical=..., intent=...)` runs before the planner. It retains **12 direct candidates plus at most 4 distinct dependency candidates**, rather than evicting direct evidence for dependencies. Raw lexical and multilingual MiniLM scores are fused separately from narrowly expanded channels. Expansion uses reusable language aliases and operation context, not test IDs or expected answers. Intent is a weak hint gated by query evidence.

Lexical indexing preserves document topics and full tables. Dense indexing combines section text with heading/prose representations. Content/settings fingerprints identify cached vectors; read-only deployments may retain regenerated vectors in memory. Dependencies follow explicit references, named concepts and applicable calendar/exception rules within a bounded budget.

Only actual retrieved sections and independently obtained public catalog rows enter normal generation. The bounded source-first selector retains actual policy/help text and matched public catalog records even for unfamiliar routes. Planner IDs only order already retrieved sections; they cannot inject missing evidence. Style/guide, FAQ or metadata alone cannot establish domain coverage. Retrieval traces distinguish direct/dependency roles, their counts, the 12-direct/4-dependency limits and actual returned count (up to 16 KB candidates). Search candidates, selected generation context and operational rule lookups are separate; none proves answer correctness.

## Source-only generation

`src/document_answers.py` receives the question, language, actual source text/metadata, reference date and safe host-derived facts. It never imports the legacy policy planner or receives its authored policy answer, answer summary, expected answer or required source list. The selected verification runs on the laptop using **Ollama `qwen3:4b-instruct` at `http://127.0.0.1:11435`**, with `LLM_TIMEOUT=600` and `RAG_LLM_TIMEOUT=600`. The before-fix 52-question local run completed at **39/52 mechanical passes** and is archived; fresh validation of the applied fixes, the same-model baseline and other batches remain pending. Hosted inference is not selected for these evaluations. The supported `.env.example` defaults remain local Ollama on port 11434 with 120-second request timeouts. Timeouts do not bound a complete turn.

Compatible HTTP 429 responses honor valid numeric or HTTP-date `Retry-After`, with at most three throttle retries and 60 seconds planned wait per `complete()` call. Longer delays stop without early retry. Actual HTTP attempts/statuses and measured/planned waits are recorded without header or credential values. Cache hits make no HTTP request. This does not guarantee provider availability.

The normal agent invokes `document_reply(..., context_provenance=True)`. The model returns `answer` and strict boolean flags `covered` and `needs_clarification`. The host derives `clarify` for a missing detail and `answer` for covered policy content. Validated Boolean uncertainty also becomes an operational answer while retaining `covered=False`, `reply_kind=uncertainty`, `evidence_status=insufficient_evidence` and no domain-answer sources. Legacy explicit refusals and deterministic privacy decisions remain unchanged. Traces retain `model_flags` and `decision_origin=host_boolean_mapping`. It does not have to reproduce source IDs or verbatim quotes. The host records the exact full supplied sections in `generation_context_sources`, along with `context_source_ids` and `provenance_kind=generation_context`.

A covered response is validated against that actual context and safe facts, then receives the supplied context IDs as source provenance. Its normal `citations` field is empty: these IDs are not claimed as model-selected citations or per-claim support. An uncovered response must be non-substantive clarification or uncertainty and has no domain-answer source IDs. The attempted generation context remains recorded separately, including when generation fails.

Validation checks supported quantities/units, language, private identifiers and invented actions. It does not make every retrieved number, exclusion or table row an answer obligation. At most **one repair** follows invalid output. Context repairs regenerate from the original evidence without rejected prose; language-only repair retains the previous JSON under its fixed control contract. Repair is uncached; private turns bypass persistent output caching on every attempt. Unavailable inference or another invalid output causes abstention. **Prewritten policy fallback is removed from normal answer generation.**

A language-only repair instructs the model to translate the previous answer into the resolved language while preserving supported meaning, numbers, dates and conditions. The host fixes the original JSON fields, types and flags, then validates the repaired answer again. This contract does not prove translation equivalence.

Finite checks do not prove per-claim entailment or full coverage. A matching quantity elsewhere in the supplied context can still be misapplied; a model can omit a condition, confuse an actor or answer only part of a question. Both flags are model output, not independent semantic certificates. The host mapping does not validate facts by itself; existing evidence, quantity, privacy, action and language checks still apply. Exact legacy answer/decision/covered responses remain strictly validated for compatibility and are labeled `legacy_model_decision`; mixed schemas are rejected. Failed generation retains bounded validator codes and safe attempt metrics; rejected model prose and dynamic error suffixes are excluded from failure diagnostics.

The legacy compatibility adapter in `src/grounding.py` ignores its authored-plan argument. Legacy policy prose can remain in routing code, but is not supplied as an answer summary or normal fallback. Business handover explanations also use actual source generation, separate from the confirmed tool outcome. Ordinary generated answers do not require preapproved policy SHA bindings.

## Verified facts and calculations

`src/document_context.py` builds an allowlisted context from verified tool records, public catalog/context slots and retrieved policy text. Verification proofs, phone numbers, email, street addresses, private delivery pincodes, customer identities and internal notes do not enter the model context.

Numeric policy inputs are parsed from retrieved text rather than copied from authored answer plans. Absent or ambiguous evidence produces no calculation. Traces retain calculation inputs, source IDs and source hashes. The reference date is **20 October 2026**. Business calendars come from governing weekday text plus supplied holidays; refund elapsed days begin after initiation. Return deadlines use delivery + N calendar days, treating delivery as day zero. This convention remains explicit because the return wording does not fully specify inclusive arithmetic.

For public refund questions, an explicitly supplied initiation date and payment method remain `customer_provided` and unverified. They may support a conditional policy-date calculation without granting private order access or asserting that a refund actually happened. Public deadline projections retain the earliest/latest range and omit the unrelated reference-date elapsed count. Elapsed facts on verified records still refer to the stated reference date.

Question-relevant `answer_constraints` contain only source-derived scalars: a selected category's calendar-day window, a calculated latest refund date, a parsed delivery-attempt limit or an entity-bound catalog/policy warranty duration. Constraint source IDs must be present in the actual generation context, and values must have independent typed-fact/calculation proof. Only covered answers to relevant questions are checked; unrelated supplied facts do not become answer obligations. A mismatched value gets one source-bound repair, then uncertainty. Full dates require ISO or explicit day/month/year; a bare day does not satisfy a date. These checks are finite coverage guards, not semantic entailment. The normal path also rejects an echoed question or a one-word policy reply.

Record-scoped statuses and refund completion dates must match authenticated fields. Only actual allowlisted refund references, explicitly labeled RRN/refund reference on private turns, bypass generic long-number filtering. These narrow exceptions do not authorize assistant-performed action claims.

## Source-derived finite guards

The guards reject recognized contradictions or request a bounded repair; they do not author a policy answer:

- `required_application_inputs` binds unresolved category or refund-arrival method lookups to actual source-table rows. Initiation-clock questions, table comparisons and COD option overviews do not force an irrelevant row selection. The host supplies a neutral question with zero LLM calls, labeled `source_input_clarification`; it does not render a policy-table answer. Follow-up resolution rechecks actual current rows, source hashes and order scope before fresh retrieval.
- `src/source_semantics.py` derives explicit permissions, documented brand-warranty attributes and paid-fee/member-exclusion conditions from actual current sections. Checks preserve permission direction and reject recognized invented warranty terms or omitted credit conditions.
- `src/return_conditions.py` binds necessary unopened/seal requirements to the actual catalog and source text. Customer condition statements remain unverified; ambiguous and damage-exception cases are not treated as established ordinary-return eligibility.
- `src/placement_conditions.py` checks recognized personal placement/delivery premises and definite exception entitlements against actual inputs and source-derived date rules. Missing dates remain unknown; a policy cutoff or reference date is not a customer date.
- Typed quantities are read recursively from safe records, including catalog lists. Exact source effective dates are permitted only in an explicit policy-effectivity role; their component digits do not authorize unrelated quantities. Narrow generic conditional timing is distinct from a claim that an operation was performed.

Finite source-derived checks also cover named navigation steps, arrival/scheduling-clock support, personal monetary roles, verification prerequisites on definite remedies, and explicit customer item-state premises. A recognized denial cannot be justified merely by missing documentation. An authenticated order does not prove claim verification; a policy fee does not establish a customer refund amount. New support facts are added only to a bounded repair; they are not authored policy replies or extra primary-prompt summaries. These checks cover defined language forms and do not prove every claim or condition.

The final public repair can restate a bounded view of actual evidence for documented navigation, source-bound item conditions or explicit policy choices. A requested-topic precheck declines this view when it would omit a recognized question topic. The primary prompt remains unchanged; final validation always receives the complete original source set. Customer attributes that were not reported remain unknown. The model supplies its own unconstrained evidence-support flag, including for negative eligibility explanations, and internal flags are rejected from spoken answers. Private, calculated, operational-handover and language-only repairs keep their existing context contract. These repairs do not import practice answers or render policy templates.

These parsers support defined language forms and policy structures. They do not establish every condition, actor, translation or answer relationship. Their engineering tests are separate from fresh live and semantic validation.

## Operational guards, state and actions

`deterministic_guardrail` covers fixed security and workflow messages: verification, privacy refusal, safety/fraud/legal/requested-human handover, greeting/audio recovery and limited missing-record prompts. Business-policy explanations are generated from actual evidence, not rendered from the legacy planner.

Proof crosses only the supplied lookup boundary and is discarded. One failed proof permits one retry; another locks that order for the session. Order switches clear verified context and pending order-specific state while retaining per-order failed-attempt counts. Unverified lookup returns only a verification prompt. Follow-ups cannot inherit another order's private data or authentication.

Business handover rules are derived from current source text before the ticket side effect: high-value damage uses supported item value/comparison; repeat contact uses the source count/period with verified same-issue history; overdue refunds use verified initiation/method and source-bound calendar calculations. Explicit general or different-issue questions do not qualify as repeat contact. Missing, changed or ambiguous authority suppresses the automatic business action and yields clarification or uncertainty. Rule decisions retain their actual source hashes, facts and calculations.

After a supported business ticket attempt, `src/operational_explanations.py` generates the policy explanation from actual sources and safe facts. The host appends only the confirmed `created=True` or failed tool outcome. Generation failure preserves that actual outcome with uncertainty. Traces distinguish `source_generated_handover`, `uncertain_handover`, `operational_handover_generation_failed` and offline `document_excerpts_handover`, plus source rule decisions and `tool_outcome_origin=actual_create_ticket_result`. Normal `grounded_llm`, `grounded_clarification`, `source_input_clarification`, `deterministic_guardrail`, abstentions and excerpts remain separate. Host input questions record zero LLM attempts/model time. Urgent safety and explicit human requests retain their independent workflows; ticket success is never inferred from generated text. Tickets deduplicate by order/reason, and no cancellation/refund/replacement execution API exists.

Prospective public delivery-capability questions can reach source-first generation without an order-ID detour. Actual status/tracking requests and compound requests for private items, amount, address, payment/refund or contact details remain behind verification. Unfamiliar public routes can use retrieved answer-bearing sources, but selection does not establish coverage. Boolean uncovered uncertainty must pass strict non-substantive checks. Model failure or repeated invalid output still abstains. An ambiguous source-table reply such as “Bank” remains unresolved until an actual current payment-route row is identified.

## Privacy and speech

Credential normalization covers phone-ending and Hindi/Roman proof phrases without treating phone-product questions as credentials. Traces omit proofs and private contacts. Raw input audio is transient and not copied to outputs. Synthetic educational verification is not production authentication.

Only official Gnani STT/TTS is used, including retries. Multipart streams rewind; empty/invalid transcripts and incomplete WAVs fail validation. Unknown RIFF/data sizes are finalized without changing PCM. Optional regional translation stays local around the same agent and adds no speech provider.

Synthetic TTS-input round trips do not establish human accent/noise robustness or intelligibility. Own-voice/listening tests remain for the final rehearsal.

## Optional regional languages

English, Hindi and Hinglish remain the primary supported scope. Regional routes are experimental; the [recorded language checks](sample_outputs/language_validation.json) describe their verification limits.

```sh
python scripts/setup_translation.py
```

This separately downloads approximately **907 MB** of pinned NLLB weights. Enable **Advanced options → Extra languages** afterward. Other regional languages use masked local translation around the same agent; placeholder, script and translation checks reject malformed output with a localized retry. These checks do not prove semantic equivalence. Choose Marathi explicitly because Hindi and Marathi share Devanagari; English/Hindi/Hinglish retain their existing path.

| Language | Batch/STT code | TTS voice |
| --- | --- | --- |
| English | `en-IN` | Kaveri |
| Hindi | `hi-IN` | Nalini |
| Hinglish | `en-IN` (TTS `hi-en`) | Poorvi |
| Bengali | `bn-IN` | Kirra |
| Gujarati | `gu-IN` | Falak |
| Kannada | `kn-IN` | Saanvi |
| Malayalam | `ml-IN` | Reshma |
| Marathi | `mr-IN` | Zahira |
| Punjabi | `pa-IN` | Mehuli |
| Tamil | `ta-IN` | Asmita |
| Telugu | `te-IN` | Suhana |

Mappings follow [Gnani's voice catalog](https://docs.gnani.ai/api/TTS/available-voices). Run `python scripts/validate_languages.py --languages te` for a Telugu synthetic pilot, or omit `--languages` for all ten plus Hinglish. Routing, valid audio and grounded meaning are checked separately.

## Evaluation and provenance

The source-only change invalidates earlier authored-fallback scores as evidence of current performance. Legacy offline practice 52/52 and 96/96, adversarial 77/77, exposed offline regression 91/91 and live practice 52/52 and 96/96 retain their actual composition. Pre-change live files are archived under `sample_outputs/history/pre_document_answers/`. They are not current pass claims.

Current engineering passed **2770/2770 tests**, with no failures/errors/skips, **126.457 seconds JUnit duration** and **141.927 seconds pytest wall time**. The [receipt](sample_outputs/engineering_verification.json), [JUnit XML](sample_outputs/engineering_artifacts/20261028T174308921749Z_dc857670/pytest.xml) and [dataset log](sample_outputs/engineering_artifacts/20261028T174308921749Z_dc857670/dataset_validation.log) bind actual tested file hashes. The official dataset validator passed. The 2069-case `5c4df02` result is historical. Fresh full local model, speech, report and package validation remain pending; engineering does not certify semantic or voice correctness.

The stopped local `qwen3:4b-instruct` run checked **13 of 52 planned questions**, with **11/13 mechanical passes**. Separate assistant source-by-source review classified **5 supported with limits, 4 material errors and 4 uncertain**. These categories are not an adjusted score or certification. The unchanged [predictions](sample_outputs/history/local_thirteen_stopped_before_hosted_20261025T155834Z/raw/eval_step2_live_current.json) and [assistant review](sample_outputs/history/local_thirteen_stopped_before_hosted_20261025T155834Z/assistant_semantic_review.json) are archived; the run predates the latest guards and the new local rerun.

The frozen holdout contains 64 singles plus 10 scenarios/27 turns (91 judged responses). Its rubric SHA-256 is `5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7`. The first independent offline result was **23/91**. Old 49/91 predictions rescore unchanged to **51/91** under scorer v2; only two points came from wording normalization. The later legacy **91/91** was exposed regression after fixes, not a new independent result. No current live exposed regression is complete; even when rerun, its exposed status remains unchanged. The incomplete strict quote pilot passed 1/8 checked questions. The initial context-mode diagnostic passed **10/30 checked of 52 planned** before being stopped and preserved under `sample_outputs/history/source_context_first_pass/`. These pilots predate the final source-derived numeric, language and quality fixes; neither is a final-runtime score.

The complete pre-repair boolean-context diagnostic recorded **36/52 mechanical passes**. A separate assistant source-by-source audit found six material issues among mechanically passing answers: invented festive eligibility, misapplied elapsed time, reversed parcel-refusal permission, invented warranty terms, omitted Express credit conditions and invented delivery-date applicability. Its [diagnostic receipt](sample_outputs/history/source_context_boolean_full_first_pass/diagnostic_receipt.json) and [semantic review](sample_outputs/history/source_context_boolean_full_first_pass/semantic_review.md) are preserved without changing predictions or gold; no adjusted semantic score or human certification is claimed. This complete run is distinct from the earlier incomplete 10/30 pilot.

The second complete diagnostic recorded **38/52 mechanical passes**. Its [receipt](sample_outputs/history/source_context_guarded_full_second_pass/diagnostic_receipt.json) and [52-row assistant review](sample_outputs/history/source_context_guarded_full_second_pass/semantic_review.md) retain seven material passing-row issues across five patterns: reversed opening condition, category mistranslations, missing prepaid qualification, overly narrow reporting exceptions and invented delivery applicability. No score was adjusted. The latest repairs require fresh live validation.

The historical prompt-only baseline used `qwen3:1.7b`; selected laptop inference uses Ollama `qwen3:4b-instruct`. Cross-model results are not a controlled RAG ablation. A fresh same-model 52-question baseline is planned with `python scripts/resume_live_practice.py --step 1`; it remains pending.

Report decisions, required/forbidden facts, tools, retrieval coverage, actual generation context, repairs, abstentions and failures separately. Current offline excerpts are not comparable with earlier authored-answer scoring.

Final runtime text was normalized to **LF** under `.gitattributes` before the recorded suite and fresh live run. Receipts bind actual source/input bytes and Git HEAD, with start/end runtime hashes. CRLF/LF conversion can change raw hashes even when Git reports no content change; evidence from before normalization is historical. The append-only `tools/tickets_created.csv` is an output, excluded from input fingerprints.

Distinguish cold startup, warm uncached inference and output-cache hits. Agent-turn time excludes previous resource loading; voice time includes STT/TTS. Request timeouts are not a hard end-to-end bound. Cache keys contain provider/model/settings and the full prompt. A cache hit is not a fresh inference.

## Release boundary

Report length is at most four pages. The user records `demo.mp4`, at most 120 seconds, **last** after own-voice rehearsal. The report PDF remains a draft awaiting current QA. No submission ZIP exists; creation waits for all required evidence and artifacts. Exclude credentials, dataset copies, caches, model weights, environments and private inputs. Release readiness remains draft until current evidence and required artifacts are complete. No ranking or hidden-test result is guaranteed.
