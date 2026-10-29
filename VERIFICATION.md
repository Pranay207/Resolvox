# Verification record

These are local measurements, not organizer scores. The source-only answer correction on **25 October 2026** creates a new runtime boundary. Earlier authored-fallback results are preserved and must not be presented as current results.

## Resumed local verification — 29 October 2026

The previous controller and evaluator stopped after a nine-question checkpoint: **8 passed, 1 failed, 43 pending**. The termination cause is unverified. The [unchanged prefix](sample_outputs/history/interrupted_local_nine_20261029T162629Z/predictions.json), [interruption receipt](sample_outputs/history/interrupted_local_nine_20261029T162629Z/interruption_receipt.json) and [assistant source review](sample_outputs/history/interrupted_local_nine_20261029T162629Z/assistant_review.json) are retained. Source, dataset, inference and scoring fingerprints matched before resuming the original output; completed responses were not rerun or counted twice.

The one mechanical failure describes missing policy information with an inconsistent coverage flag and uncertainty wording. Source review also found an omitted verification prerequisite in a mechanically passing remedy explanation. Generic repairs are under test in an isolated preview. They have not been applied to the active frozen batch. This checkpoint is not a complete 52-question score or evidence that the repairs passed live verification.

## Current source-only runtime

The [five-case development rerun](sample_outputs/history/applied_repair_five_20261028T162543Z/predictions.json) passed **5/5** after the latest repairs. The [assistant source review](sample_outputs/history/applied_repair_five_20261028T162543Z/assistant_review.json) records the meaning and limits of those answers. This subset does not replace the fresh 52-question run, which is now in progress with an initially empty application response cache; model/prompt caches were not reset.


| Check | Current record |
| --- | --- |
| Engineering of applied fixes | **2770/2770 passed**; no failures/errors/skips; [receipt](sample_outputs/engineering_verification.json) |
| Historical engineering at `5c4df02` | **2069/2069 passed**; no failures, errors or skips; [JUnit](sample_outputs/engineering_artifacts/20261025T160113690763Z_4f731e19/pytest.xml) |
| Live grounded practice | **Fresh 52-question run pending**; [before-fix run completed at 39/52](sample_outputs/history/local_52_before_fixes_20261026T161207Z/eval_step2_live_current.json) |
| Live conversations | **96 turns planned; rerun pending** |
| Current-model prompt-only baseline | **52 planned; pending** |
| Live adversarial/development checks | **77 planned; pending** |
| Live exposed regression | **91 planned; pending** |
| Gnani synthetic end-to-end speech | Six round trips and silence recovery pending |
| Report rendering and page QA (maximum four) | Existing PDF is a draft; regeneration and QA pending |
| Repository access | Private during development; owner will make it public after verification and final pushes. [Access record](sample_outputs/repository_access_check.json) |
| Final ZIP extraction/hash/secret checks | No ZIP exists; create and verify only after all required evidence and the demo are complete |

The current [engineering receipt](sample_outputs/engineering_verification.json) records **2770/2770 passed**, no failures/errors/skips, and unchanged runtime, test, dataset and verification-helper hashes. The [JUnit XML](sample_outputs/engineering_artifacts/20261028T174308921749Z_dc857670/pytest.xml) records **126.457 seconds**; pytest process wall time was **141.927 seconds**. The [dataset log](sample_outputs/engineering_artifacts/20261028T174308921749Z_dc857670/dataset_validation.log) records a passed official validation: 9 CSVs, 21 KB documents, 1,000 orders, 1,783 items, 244 support logs, 52 practice questions and 23 conversations. This offline pass does not certify model answers or speech. The receipt started from HEAD `0c74024` with a dirty working tree and certifies recorded file hashes; it must not be described as a run started at a later commit.

The final release check compared **165 Python and fixture files byte-for-byte with Git HEAD**. Local source and fixture line endings were aligned with their existing Git representation; JSON values and the canonical frozen question/rubric hashes are unchanged. Captured measurements retain their original bytes through `.gitattributes`. The subsequent 2,770-case engineering receipt binds those exact release files.

The historical 2069-case suite was offline and made no model inference. Its [unchanged receipt](sample_outputs/engineering_artifacts/20261025T160113690763Z_4f731e19/engineering_verification.json) retains the compatible/Groq settings selected when that engineering run started; those settings are not evidence of a hosted question evaluation and have not been rewritten for the current laptop configuration.

A fresh initially empty-cache run was interrupted after **4/52 checked, 4 passed** to reduce laptop memory pressure. Its unchanged predictions remain in the [archive](sample_outputs/history/before_remaining_live_20261028T173105879468Z_4049c7e9/sample_outputs/eval_step2_live_current.json). The replacement full run records [Ollama 0.40.12 with a verified 512 MiB prompt-cache limit](sample_outputs/local_ollama_configuration.json), an initially empty application response cache and unchanged model/context/answer rules. The partial results are not combined with the replacement run. The generic one-token preflight is separate from practice and is not a cold-start benchmark.

The earlier public Hinglish warranty pilot and other local probes remain intermediate diagnostics. Their timing includes loading and varying CPU contention and is not a controlled cold/warm latency study. Complete current local practice, baseline, development/exposed regression and speech results remain pending.

The selected verification runs on the laptop using **Ollama `qwen3:4b-instruct` at `http://127.0.0.1:11435`**, with `LLM_TIMEOUT=600` and `RAG_LLM_TIMEOUT=600`. The before-fix 52-question local run completed at **39/52 mechanical passes** and is archived; fresh validation of the applied fixes, the same-model baseline and other batches remain pending. Hosted inference is not selected for these evaluations. The supported `.env.example` defaults remain local Ollama on port 11434 with 120-second request timeouts. Timeouts do not bound a complete turn.

Ordinary domain answers come from `document_reply`, which receives actual retrieved text and safe verified/source-derived facts. It returns an answer and strict `covered`/`needs_clarification` booleans. Validated Boolean uncertainty keeps `covered=False`, `reply_kind=uncertainty`, `evidence_status=insufficient_evidence` and no domain-answer source IDs even when the host decision is answer. Legacy explicit and privacy refusals remain unchanged. Traces retain model flags, host decision origin and full actual generation context; normal `citations=[]` does not claim model-selected quotes or per-claim proof. One bounded repair precedes abstention. Prewritten policy fallback is removed from normal generation and from business handover explanations. Fixed security/workflow messages and actual tool-outcome wording remain deterministic.

Generation traces distinguish first attempts, repairs, provider failures and cache reuse. A cache hit is not fresh inference. Context mode records actual generation sources even on failed or uncovered responses; it does not force the model to reproduce quote JSON or require unrelated sections to be answered. `compose=False` and legacy `--offline-rules` now expose `document_excerpts` alongside operational guards. They do not run the earlier authored policy-answer path, so old offline scores are not new-runtime results.

Full-context quantity checks, source-bound numeric/date constraints and record/action/privacy checks remain finite safeguards. Finite source-derived checks also cover named navigation steps, arrival/scheduling-clock support, personal monetary roles, verification prerequisites on definite remedies, and explicit customer item-state premises. A recognized denial cannot be justified merely by missing documentation. An authenticated order does not prove claim verification; a policy fee does not establish a customer refund amount. New support facts are added only to a bounded repair; they are not authored policy replies or extra primary-prompt summaries. These checks cover defined language forms and do not prove every claim or condition. Relevant values retain actual context IDs and independent fact/calculation proof. Language-only repair retains control flags and rechecks the output, without proving semantic equivalence.

Retrieval retains 12 direct candidates plus up to 4 distinct source dependencies, with direct/dependency roles and actual counts in the trace; these are separate from selected generation context and public catalog lookups. Source-first selection retains actual policy/help text for unfamiliar public routes. Prospective public delivery capability does not force an order lookup; actual private order requests and compound status/items/amount/address/refund-detail requests retain verification. Required table inputs use a neutral zero-LLM host question; follow-ups rebind current rows, hashes and order scope. “Bank” alone remains unresolved rather than choosing a refund route. Actual context does not prove coverage.

Business escalation is derived from actual current sources before ticket creation: supported high-value damage, overdue verified refunds and same-issue repeat contact retain source hashes and calculation evidence. Unbound or ambiguous policy cannot authorize automatic business handover. The generated policy explanation and actual ticket outcome are separate; failed generation keeps the real outcome with uncertainty, not an authored business answer. Traces retain operational rule decisions and tool-outcome origin. Independent privacy, safety and requested-human workflows remain operational guards.

**Byte provenance.** Runtime sources were normalized to LF under `.gitattributes` before the `5d08ca6` measurements. Receipts record actual Git HEAD and source/input byte hashes, including matching runtime start/end maps. Newline conversion may change a raw hash despite a clean Git content diff. Do not promote pre-normalization receipts as current. Append-only `tools/tickets_created.csv` is generated output and is excluded from input fingerprints.

## Stopped local partial run

The stopped local `qwen3:4b-instruct` run checked **13 of 52 planned questions**, with **11/13 mechanical passes**. Separate assistant source-by-source review classified **5 supported with limits, 4 material errors and 4 uncertain**. These categories are not an adjusted score or certification. The unchanged [predictions](sample_outputs/history/local_thirteen_stopped_before_hosted_20261025T155834Z/raw/eval_step2_live_current.json) and [assistant review](sample_outputs/history/local_thirteen_stopped_before_hosted_20261025T155834Z/assistant_semantic_review.json) are archived; the run predates the latest guards and the new local rerun.

## Preserved earlier evidence

Legacy fallback measurements and intermediate source-only pilots predate the final core revision:

| Check | Historical result |
| --- | --- |
| Historical code `5d08ca6` engineering | **1016/1016**, 32.429 s JUnit duration; predates latest changes |
| Earlier boolean-contract engineering revision | **678/678**, 85.94 seconds; historical |
| Prior three-field engineering revision | **626 passed**; historical |
| Historical prompt-only baseline, `qwen3:1.7b` | **1/52**, one error |
| Grounded practice, old offline composition | **52/52** |
| Conversations, old offline composition | **96/96** |
| Old LLM-enabled questions | **52/52**; 16 generated, 25 checked static fallbacks, 4 guards, 2 rules, 5 abstentions |
| Old LLM-enabled conversations | **96/96**; 8 generated, 9 checked static fallbacks, 77 guards, 2 rules |
| Earlier incomplete live subset | 32 checked of 52 planned |
| Strict quote-generation pilot, incomplete | **1/8 checked questions passed** |
| First context-mode diagnostic, incomplete | **10/30 checked of 52 planned**, then stopped |
| First complete boolean-context diagnostic | **36/52 mechanical passes**; separate semantic audit below |
| Second complete guarded-context diagnostic | **38/52 mechanical passes**; seven passing-row semantic findings below |
| Development adversarial/stateful | **77/77** |
| First independent offline holdout | **23/91** |
| Later exposed-set offline regression | **91/91** |
| Holdout privacy assertions | 191 checked, no failures |
| Gnani synthetic round trips | **6/6** audio and semantic/privacy checks |
| Hindi UPI follow-up | **1/1** |
| Digital-silence recovery | **1/1** |
| Optional regional synthetic run | **5/11**, six failures |

Pre-change live files are archived under `sample_outputs/history/pre_document_answers/`. The strict pilot is retained as `strict_quote_pilot.json` there. The incomplete first context diagnostic is preserved under `sample_outputs/history/source_context_first_pass/`; it predates the final language, calculation and quality checks. Other historical files retain original predictions/timestamps. The baseline had no document-policy fallback; it remains genuine prompt-only evidence, but does not certify the revised grounded path.

### Complete diagnostic and separate semantic audit

The pre-repair full run is preserved under `sample_outputs/history/source_context_boolean_full_first_pass/`. Its [diagnostic receipt](sample_outputs/history/source_context_boolean_full_first_pass/diagnostic_receipt.json) records **36/52 mechanical passes**. A separate assistant review compared all 52 saved rows with their supplied sources/facts and identified six material issues among mechanically passing answers:

| Saved row | Material issue |
| --- | --- |
| PQ0024 | Invented placement-date eligibility for a festive return extension |
| PQ0033 | Used a reference-date elapsed count for the interval to the refund deadline |
| PQ0040 | Reversed the permitted option to refuse a shipped parcel at the door |
| PQ0041 | Invented brand-warranty start date and positive coverage terms |
| PQ0047 | Omitted paid-fee/Plus conditions when promising an Express credit |
| PQ0057 | Invented a delivery date to apply the electronics-policy cutoff |

The [semantic review](sample_outputs/history/source_context_boolean_full_first_pass/semantic_review.md) retains the exact findings. No predictions, scorer or gold answers were changed, and no adjusted semantic pass rate was computed. This is assistant review, not human certification or proof that every other sentence is correct. The new guards require fresh live validation; engineering passes alone do not close these historical semantic findings.

### Second complete diagnostic and assistant review

The next frozen run at code `5d08ca6` is preserved under `sample_outputs/history/source_context_guarded_full_second_pass/`. Its [receipt](sample_outputs/history/source_context_guarded_full_second_pass/diagnostic_receipt.json) records **38/52 mechanical passes**, all 52 results, complete=true and no recorded evaluation errors. Questions exit 1 means completed-with-failures, not a crash/partial run. Final raw artifact SHA-256: `79f0f6c61e77a175d34d4908e30fa94d014480f6da3aebbb4b426719ece0f5a4`.

The [assistant source-by-source review](sample_outputs/history/source_context_guarded_full_second_pass/semantic_review.md) flags seven mechanically passing rows across five material patterns:

| Saved rows | Material issue |
| --- | --- |
| PQ0013 | Explanation reverses the unopened requirement |
| PQ0020, PQ0044 | Broader category labels are mistranslated |
| PQ0021 | Failed-delivery refund explanation omits prepaid qualification |
| PQ0036, PQ0039 | An exhaustive list excludes the documented defective-item reporting reason |
| PQ0057 | The answer invents delivery-cutoff applicability |

PQ0054 separately has an already-failing placement-date extraction/selection error. No official score, prediction or gold answer was changed, and no adjusted semantic score was calculated. This is finite assistant review, not human certification. The repaired runtime has new engineering evidence but still requires fresh complete live validation; neither historical diagnostic is its score.

Original 49/91 holdout predictions score 51/91 under scorer v2 without prediction changes; only two points came from wording normalization. Later legacy 91/91 followed fixes after inspecting failures and is exposed regression, not a new blind evaluation or current source-only result. Full frozen rubric SHA-256: `5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7`.

Historical development coverage probe **24/24** and its failed first pass remain development evidence. Number-word rescoring (“three” versus “3”) changed matching, not predictions. Old speech files describe real Gnani calls; changing answer generation requires fresh end-to-end validation before claiming a current speech pass.

Recorded dataset validation passed **9 CSVs, 21 KB documents, 1,000 orders, 1,783 order items and 244 support logs**, with **52 practice questions and 23 conversations**. Twelve Streamlit integration cases are included in the engineering suite. One initial full test attempt recorded 589 passes and one UI startup timeout at 40 seconds; that UI case passed on retry in 6.15 seconds, followed by the clean full **590/590** run in 20.30 seconds. Direct final browser review was unavailable. Earlier app-health, report, package and source-provenance artifacts certify only their recorded bytes and runtime and must be refreshed.

## Remaining validation and release

- Current engineering passed 2770/2770 against matching tested file hashes. Fresh full local practice, same-model baseline and speech results remain pending; the older 2069-case pass is historical.
- Rebuild/render the report and verify revised archive hashes, configured-secret scan and extracted-package smoke test.
- The current live exposed regression and same-model baseline are pending. No new blind holdout or controlled cold-start study is complete.
- Human speech, noise robustness and subjective listening remain unverified.
- **Own-voice rehearsal and the user-recorded demo stay last.** `demo.mp4` must be at most 120 seconds. Do not create or overwrite a ZIP until current checks and the required demo are complete.

Reproduce with `python -m pytest -q`, then `python scripts/resume_live_practice.py --step 1`, `--step 2` and `--step 3`. Optional live regressions use `python eval_adversarial.py --live --output sample_outputs/eval_adversarial_live_current.json` and `python eval_holdout.py --output sample_outputs/eval_holdout_live_current.json`. Checkpoints resume only when inference inputs match. Earlier predictions are retained; missing results must never be filled manually.

A request timeout is not a hard end-to-end guarantee. Cold startup includes resource/model loading; warm uncached inference makes a new request on loaded resources; cache hits reuse stored output. Agent-turn time excludes previous resource loading; voice timing includes STT/TTS. No score guarantees placement or unseen-question correctness.
