# VoiceOps 2026 - brief checklist

Source: `voiceops_2026_capstone_brief.pdf`. These checks describe inspectable behavior; current validation must use regenerated source-only outputs. Earlier passing scores remain historical evidence.

## Implemented requirements

- [x] Prompt-only LLM baseline without company documents, catalog or private order access; preserve real outputs and errors.
- [x] KB section chunks retain IDs and authority/version/effective-date/status metadata.
- [x] Query-first lexical/multilingual hybrid retrieval at actual k=12; generation receives actual source sections and sanitized verified/source-derived facts.
- [x] LLM JSON with answer and strict covered/needs_clarification booleans; host derives the decision and records model_flags/decision_origin; save full actual generation chunks and IDs as host context provenance, not model-selected citations. Conservative quantity/privacy/action checks allow one repair, then abstention. Prewritten policy fallback is removed from normal answer generation. No per-claim semantic proof is claimed.
- [x] Source-derived finite checks for missing table inputs, unopened/seal conditions, unknown date premises, conditional exceptions, permission direction, warranty scope and paid-fee/Plus credit conditions. Language-only repair preserves the JSON field/flag contract. These checks do not certify full semantic correctness.
- [x] Explicit deterministic operational guards for authentication, privacy, urgent escalation and confirmed tool outcomes. Their evidence-bound policy explanations remain distinct from normal model-generated domain answers and query-search success.
- [x] Recognized unsupported topics return generic uncertainty before normal generation. The guard does not establish complete routing: the saved “2 am” delivery case still asks for an order ID and remains a failed expected-uncertainty probe.
- [x] Session state, one clarification at a time, supplied lookup/ticket tools, per-order authentication failure counts and order/reason ticket deduplication.
- [x] Verify before private order disclosure; one retry; redact proof values and private contact fields from traces/model input.
- [x] Reference date 20 October 2026, Mon-Sat business days excluding holidays, calendar-day returns and successor-authorized historical scope.
- [x] Gnani STT -> same agent -> Gnani TTS adapter, served model selection, batch failure isolation and real-WAV validation.
- [x] Public repository, installation instructions, dependencies, `.env.example` and exact organizer batch command.
- [x] Frozen independent holdout fixture and checker: 64 singles + 10 scenarios/27 turns = 91 judged responses.

## Current verification

- [x] Code `5d08ca6`: **1016/1016 tests passed; 32.429 s JUnit duration**, recorded in the [engineering receipt](sample_outputs/engineering_verification.json) and [JUnit XML](sample_outputs/engineering_artifacts/20261025T124401715563Z_8aea71eb/pytest.xml). Earlier 678/678, 626-test and 590/590 revisions remain historical. Official dataset validation passed 9 CSVs and 21 KB documents.
- [ ] Source-only live questions: **52 planned; rerun pending**. Current output will be `sample_outputs/eval_step2_live_current.json`.
- [ ] Source-only live conversations: **96 turns planned; rerun pending**. Current output will be `sample_outputs/eval_step3_live_current.json`.
- [ ] Current same-model prompt-only baseline: **52 planned**, to run with `python scripts/resume_live_practice.py --step 1`.
- [ ] Current live adversarial/development checks: **77 planned**, pending.
- [ ] Current live exposed regression: **91 planned**, pending; this is not an independent blind holdout.
- [ ] Current Gnani end-to-end synthetic speech rerun pending.
- [ ] Current report rendering and package checks pending after revised measurements are saved.

The recorded local model is `qwen3:4b-instruct`, with both `LLM_TIMEOUT` and `RAG_LLM_TIMEOUT` selected at **180 seconds**. Code and `.env.example` defaults remain **120 seconds**; request timeouts do not bound a complete voice turn. The historical baseline used `qwen3:1.7b`, so that comparison is not controlled. A new current-model baseline is planned; its result remains pending.

Final runtime sources use LF under `.gitattributes`; current receipts bind actual Git HEAD and matching source/input hashes. CRLF conversion can change byte hashes even when Git reports no content change. Generated `tools/tickets_created.csv` is excluded from input fingerprints.

Generated document answers, uncached inference, cache hits, operational guards and abstentions are separate events. Context provenance and finite quantity/action checks are not organizer scoring or per-claim semantic certification.

## Historical measurements retained

These runs predate the final source-only revision and **do not establish its performance**. Legacy fallback runs and intermediate source-only pilots are distinguished below:

- Historical prompt-only baseline (`qwen3:1.7b`) **1/52**, one error; this baseline had no document-policy fallback. Actual output remains `sample_outputs/eval_step1.json`.
- Legacy offline practice **52/52 questions** and **96/96 turns**; original `eval_step2.json` and `eval_step3.json` retained. Current `compose=False` is an excerpt diagnostic, not that old answer path.
- Legacy live **52/52 questions**: 16 generated, 25 checked static fallbacks, 4 guards, 2 rules and 5 abstentions. Legacy live **96/96 turns**: 8 generated, 9 checked static fallbacks, 77 guards and 2 rules. Archived under `sample_outputs/history/pre_document_answers/`.
- Earlier incomplete 32-question live subset remains historical, not current complete-run evidence.
- Incomplete strict quote-generation pilot: **1/8 checked questions passed**; preserved in `sample_outputs/history/pre_document_answers/strict_quote_pilot.json`.
- Initial context-mode diagnostic: **10/30 checked questions passed out of 52 planned**, stopped and preserved in `sample_outputs/history/source_context_first_pass/eval_step2_live_current.json`. This predates the final language, source-derived numeric and quality fixes; no templates were restored.
- Complete pre-repair boolean-context diagnostic: **36/52 mechanical passes**, retained in the [diagnostic receipt](sample_outputs/history/source_context_boolean_full_first_pass/diagnostic_receipt.json). A separate [semantic review](sample_outputs/history/source_context_boolean_full_first_pass/semantic_review.md) found six material issues among mechanically passing answers (exception eligibility, elapsed interval, refusal permission, warranty scope, Express conditions and historical delivery applicability). No adjusted score or human certification is claimed.
- Legacy development adversarial/stateful **77/77**; development data, not a blind test.
- Legacy exposed offline regression **91/91**, with 191 privacy assertions and no failures. First independent offline result **23/91**. Old 49/91 predictions rescore unchanged to 51/91; only two points came from scoring normalization. Later 91/91 was an exposed development regression, not a new blind result.
- Earlier real Gnani synthetic speech **6/6**, Hindi UPI **1/1**, silence recovery **1/1**. These real calls do not validate the revised end-to-end runtime.
- Earlier dataset checks are preserved; the current validator also passed (see current verification above).
- Optional regional preview recorded **5/11**, six failures. It remains experimental and has not been rerun after this change.

Raw failures/provenance remain retained. Human accents/noise and subjective listening have not been verified. See `VERIFICATION.md` for the runtime boundary.

## Final submission and additional validation

Current boolean-contract engineering checks passed; formal live and speech checks remain pending. The existing report PDF and ZIP are stale drafts requiring regeneration and verification. The user-recorded demo remains the required uncreated artifact and will be done last. Live holdout, controlled cold-start and noisy-speech studies are additional validation.

- [ ] Current live exposed-regression evaluation is pending. Historical holdout results are offline; a new live run still does not make the exposed set independent.
- [ ] Controlled cold-start latency has **not** been measured. Per-turn uncached and cache measurements exclude prior resource startup and are not cold-start measurements.
- [ ] Human speech testing and subjective listening have **not** been completed. Synthetic TTS-input round trips do not establish human accent/noise robustness.
- [ ] Refresh `report.pdf` and render/inspect all four pages against source-only results. Earlier PDF QA is historical until regeneration.
- [ ] Rebuild the revised draft ZIP and repeat extraction, import/answer smoke, allowlist, hash and secret checks. Earlier checks do not certify revised bytes.
- [ ] Push the final submission revision containing demo.mp4 and final-ready package evidence; verify local and remote commit IDs after the demo is included.
- [ ] User records `demo.mp4` (maximum 120 seconds) after final validation; show actual generation mode, sources, verification/handover and live Gnani speech.
- [ ] Build final-ready `team_name_voiceops.zip` with the required report, demo and generated sample outputs. Keep draft status until required artifacts exist and verification passes.

Current measurements belong in `sample_outputs/*.json`, `VERIFICATION.md` and `SUBMISSION_STATUS.json`. A previous run or implemented feature is not evidence that a pending run passed.

## Frozen holdout

Fixture: `tests/holdout_cases.json`. Full rubric SHA-256:

```text
5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7
```

The fixture is evaluation data, never runtime retrieval or answer-generation knowledge. All holdout scores here belong to the historical authored-answer runtime. The preserved first independent offline pass scored **23/91 (25.3%)**. After inspecting failures and making general fixes, the exposed-set offline regression scored **91/91 (100%)** under scorer v2, leaving **0 failures in the evaluated cases**. The prior 49/91 predictions are preserved in `eval_holdout_before_normalization_v2.json`; rescoring those same unchanged predictions yields **51/91** in `eval_holdout_scorer_v2_same_predictions.json`. Thus **2 points** came from scoring normalization, and improvement from **51 to 91** is measured after runtime fixes under the same v2 scorer. This is an exposed-set regression, not a second independent holdout or proof of complete customer-question coverage. No live holdout run has been performed. All original fixtures and first-pass outputs remain retained; mechanical rubric matching does not replace semantic review.

## Rubric

| Criterion | Marks |
|---|---:|
| Correct grounded answers / abstention | 25 |
| Retrieval quality | 15 |
| Conversation handling | 20 |
| Own evaluation, Step 1 vs Step 2 | 10 |
| End-to-end voice | 10 |
| Voice experience (top 50 live judges) | 10 |
| Report/demo (top 50 live judges) | 10 |

## Submission constraints and resolved ambiguities

- The required video is at most two minutes; the user records it. The report is at most four pages.
- Return windows start on delivery, but inclusive arithmetic is not fully specified. Delivery + N elapsed calendar days matches supplied practice deadlines; document the day-zero convention.
- Superseded rules apply only to cases authorized by their successor. Historical electronics eligibility never revives the old free-pickup rule.
- Unverified initial lookup is permitted because it returns only a prompt. Proof must precede disclosure of private order data.
- The brief permits local or compatible hosted LLMs. Use measured selected-model output; do not imply a preferred model or guaranteed placement.
- The brief permits file-based SDK/REST voice despite the dataset README's WebSocket example. Gnani is the only STT/TTS provider, including retries/fallbacks.
- Outputs must be generated by the agent. Keep failures, and never type replacement answers or show simulated tool/speech success.
- Exclude `.env`, API keys, virtual environments, model/cache files, private input audio and dataset copies from the submission. Use synthetic/consented inputs and the participant's own Gnani account.

Historical speech follow-ups: Hindi UPI 1/1 and real Gnani silence recovery 1/1, including AI disclosure. Current source-only revalidation is pending.
