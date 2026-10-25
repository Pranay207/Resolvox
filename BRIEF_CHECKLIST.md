# VoiceOps 2026 - brief checklist

Source: `voiceops_2026_capstone_brief.pdf`. These checks describe inspectable behavior; current validation must use regenerated source-only outputs. Earlier passing scores remain historical evidence.

## Implemented requirements

- [x] Prompt-only LLM baseline without company documents, catalog or private order access; preserve real outputs and errors.
- [x] KB section chunks retain IDs and authority/version/effective-date/status metadata.
- [x] Query-first lexical/multilingual hybrid retrieval preserves 12 direct candidates plus up to 4 distinct source dependencies (maximum 16 KB candidates), with separate actual counts in traces. Generation receives actual source sections and sanitized verified/source-derived facts.
- [x] LLM JSON with answer and strict covered/needs_clarification booleans; host derives operational decisions and records model_flags/decision_origin; validated Boolean uncertainty stays covered=False with reply_kind=uncertainty and evidence_status=insufficient_evidence; save full actual generation chunks and IDs as host context provenance, not model-selected citations. Conservative quantity/privacy/action checks allow one repair, then abstention. Prewritten policy fallback is removed from normal answer generation. No per-claim semantic proof is claimed.
- [x] Finite source-derived checks also cover named navigation steps, arrival/scheduling-clock support, personal monetary roles, verification prerequisites on definite remedies, and explicit customer item-state premises. A recognized denial cannot be justified merely by missing documentation. An authenticated order does not prove claim verification; a policy fee does not establish a customer refund amount. New support facts are added only to a bounded repair; they are not authored policy replies or extra primary-prompt summaries. These checks cover defined language forms and do not prove every claim or condition.
- [x] Deterministic authentication/privacy/safety workflows and actual tool outcomes. Source-derived high-value-damage, overdue-refund and same-issue repeat-contact conditions are checked before business tickets; policy explanations are generated from actual sources, separately from confirmed ticket results.
- [x] Source-first selection retains actual policy/help context for unfamiliar public routes; no planner answer enters generation. Uncovered model output must pass strict non-substantive checks. Legacy explicit and deterministic privacy refusals retain their decisions.
- [x] Required source-table category/payment-method inputs use a neutral zero-LLM question; choices rebind current rows, hashes and order scope. Ambiguous “Bank” replies remain unresolved. Prospective public delivery capability reaches source-first generation, while compound private requests retain verification.
- [x] Session state, one clarification at a time, supplied lookup/ticket tools, per-order authentication failure counts and order/reason ticket deduplication.
- [x] Verify before private order disclosure; one retry; redact proof values and private contact fields from traces/model input.
- [x] Reference date 20 October 2026, Mon-Sat business days excluding holidays, calendar-day returns and successor-authorized historical scope.
- [x] Gnani STT -> same agent -> Gnani TTS adapter, served model selection, batch failure isolation and real-WAV validation.
- [x] Public repository, installation instructions, dependencies, `.env.example` and exact organizer batch command.
- [x] Frozen independent holdout fixture and checker: 64 singles + 10 scenarios/27 turns = 91 judged responses.

## Current verification

- [x] Current code `5c4df02`: **2069/2069 engineering cases passed**, no failures/errors/skips; **51.561 s JUnit**, **56.357 s pytest wall**. [Receipt](sample_outputs/engineering_verification.json) and [JUnit](sample_outputs/engineering_artifacts/20261025T160113690763Z_4f731e19/pytest.xml) bind actual bytes. Dataset validation passed 9 CSVs and 21 KB documents.
- [ ] Current source-only questions: **52 planned; local laptop run in progress**.
- [ ] Source-only live conversations: **96 turns planned; rerun pending**. Current output will be `sample_outputs/eval_step3_live_current.json`.
- [ ] Current same-model prompt-only baseline: **52 planned**, to run with `python scripts/resume_live_practice.py --step 1`.
- [ ] Current live adversarial/development checks: **77 planned**, pending.
- [ ] Current live exposed regression: **91 planned**, pending; this is not an independent blind holdout.
- [ ] Current Gnani end-to-end synthetic speech rerun pending.
- [ ] Current report rendering and package checks pending after revised measurements are saved.

The selected verification runs on the laptop using **Ollama `qwen3:4b-instruct` at `http://127.0.0.1:11435`**, with `LLM_TIMEOUT=300` and `RAG_LLM_TIMEOUT=300`. The fresh 52-question laptop run is in progress; its completion, the current-model baseline and other batches remain pending. Hosted inference is not selected for these evaluations. The supported `.env.example` defaults remain local Ollama on port 11434 with 120-second request timeouts. Timeouts do not bound a complete turn.

Final runtime sources use LF under `.gitattributes`; current receipts bind actual Git HEAD and matching source/input hashes. CRLF conversion can change byte hashes even when Git reports no content change. Generated `tools/tickets_created.csv` is excluded from input fingerprints.

Generated document answers, uncached inference, cache hits, operational guards and abstentions are separate events. Context provenance and finite quantity/action checks are not organizer scoring or per-claim semantic certification.

The stopped local `qwen3:4b-instruct` run checked **13 of 52 planned questions**, with **11/13 mechanical passes**. Separate assistant source-by-source review classified **5 supported with limits, 4 material errors and 4 uncertain**. These categories are not an adjusted score or certification. The unchanged [predictions](sample_outputs/history/local_thirteen_stopped_before_hosted_20261025T155834Z/raw/eval_step2_live_current.json) and [assistant review](sample_outputs/history/local_thirteen_stopped_before_hosted_20261025T155834Z/assistant_semantic_review.json) are archived; the run predates the latest guards and the new local rerun.

## Historical measurements retained

These runs predate the final source-only revision and **do not establish its performance**. Legacy fallback runs and intermediate source-only pilots are distinguished below:

- Historical code `5d08ca6` engineering: **1016/1016**, with [archived receipt](sample_outputs/history/source_context_guarded_full_second_pass/engineering_verification.json) and [JUnit XML](sample_outputs/engineering_artifacts/20261025T124401715563Z_8aea71eb/pytest.xml).
- Historical prompt-only baseline (`qwen3:1.7b`) **1/52**, one error; this baseline had no document-policy fallback. Actual output remains `sample_outputs/eval_step1.json`.
- Legacy offline practice **52/52 questions** and **96/96 turns**; original `eval_step2.json` and `eval_step3.json` retained. Current `compose=False` is an excerpt diagnostic, not that old answer path.
- Legacy live **52/52 questions**: 16 generated, 25 checked static fallbacks, 4 guards, 2 rules and 5 abstentions. Legacy live **96/96 turns**: 8 generated, 9 checked static fallbacks, 77 guards and 2 rules. Archived under `sample_outputs/history/pre_document_answers/`.
- Earlier incomplete 32-question live subset remains historical, not current complete-run evidence.
- Incomplete strict quote-generation pilot: **1/8 checked questions passed**; preserved in `sample_outputs/history/pre_document_answers/strict_quote_pilot.json`.
- Initial context-mode diagnostic: **10/30 checked questions passed out of 52 planned**, stopped and preserved in `sample_outputs/history/source_context_first_pass/eval_step2_live_current.json`. This predates the final language, source-derived numeric and quality fixes; no templates were restored.
- Complete pre-repair boolean-context diagnostic: **36/52 mechanical passes**, retained in the [diagnostic receipt](sample_outputs/history/source_context_boolean_full_first_pass/diagnostic_receipt.json). A separate [semantic review](sample_outputs/history/source_context_boolean_full_first_pass/semantic_review.md) found six material issues among mechanically passing answers (exception eligibility, elapsed interval, refusal permission, warranty scope, Express conditions and historical delivery applicability). No adjusted score or human certification is claimed.
- Second complete pre-repair diagnostic: **38/52 mechanical passes**. Its [receipt](sample_outputs/history/source_context_guarded_full_second_pass/diagnostic_receipt.json) and [assistant review](sample_outputs/history/source_context_guarded_full_second_pass/semantic_review.md) retain seven passing-row semantic issues across five patterns. No predictions, gold answers or score were changed; it is not a current-runtime pass claim.
- Legacy development adversarial/stateful **77/77**; development data, not a blind test.
- Legacy exposed offline regression **91/91**, with 191 privacy assertions and no failures. First independent offline result **23/91**. Old 49/91 predictions rescore unchanged to 51/91; only two points came from scoring normalization. Later 91/91 was an exposed development regression, not a new blind result.
- Earlier real Gnani synthetic speech **6/6**, Hindi UPI **1/1**, silence recovery **1/1**. These real calls do not validate the revised end-to-end runtime.
- Earlier dataset checks are preserved; the current validator also passed (see current verification above).
- Optional regional preview recorded **5/11**, six failures. It remains experimental and has not been rerun after this change.

Raw failures/provenance remain retained. Human accents/noise and subjective listening have not been verified. See `VERIFICATION.md` for the runtime boundary.

## Final submission and additional validation

Current offline engineering at `5c4df02` is complete. Model verification is selected to run locally on the laptop; the 52-question stage is in progress, while its completion and the same-model baseline remain pending. Full live/speech checks, regenerated report and verified final package remain pending. The user records the demo last.

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
