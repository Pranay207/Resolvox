# Verification record

These are local measurements, not organizer scores. The source-only answer correction on **25 October 2026** creates a new runtime boundary. Earlier authored-fallback results are preserved and must not be presented as current results.

## Current source-only runtime

| Check | Current record |
| --- | --- |
| Current boolean-contract full suite | Rerun pending; prior three-field revision passed **626 tests**, not current-contract validation |
| Live grounded practice | **52 questions planned; rerun pending** |
| Live conversations | **96 turns planned; rerun pending** |
| Gnani synthetic end-to-end speech | **Rerun pending** |
| Report rendering and four-page QA | Existing PDF is a stale draft; regeneration and QA pending |
| Revised ZIP extraction/hash/secret checks | Existing ZIP is stale; rebuild and verification pending |

The selected model is now `qwen3:4b-instruct`, with a 120-second per-request RAG timeout. The baseline used `qwen3:1.7b`; the comparison is not a controlled same-model baseline/RAG ablation. Earlier 45-second 4B probes timed out. Two later 120-second diagnostic cases produced relevant Hinglish warranty content and the correct public-date projection, but the first had an inconsistent refusal label and the second failed the completed-action wording guard. They are diagnostic evidence, **not passed final checks**; targeted decision/action repairs require fresh validation. Current live runs must retain source/input/settings hashes, completion flags, failures, timings, actual generation context and composition. Current output filenames are `sample_outputs/eval_step2_live_current.json` and `sample_outputs/eval_step3_live_current.json`. Pending is not passed.

Ordinary domain answers now come from `document_reply`, which receives actual retrieved text and safe verified/source-derived facts. It returns an answer and strict `covered`/`needs_clarification` booleans. The host derives clarify if clarification is needed, otherwise answer if covered, otherwise refuse; traces retain `model_flags` and `decision_origin=host_boolean_mapping`. Legacy exact three-field responses remain strictly checked and labeled `legacy_model_decision`, without silently relabeling old refusals. The host saves the exact full supplied chunks and their IDs as `generation_context` provenance. The normal `citations` list is empty; no model-selected quotes or per-claim support are claimed. Invalid output gets one bounded repair; model failure or another invalid output produces abstention. **Prewritten policy fallback is removed from normal answer generation.** Deterministic operational/escalation messages may retain policy explanations bound to explicit evidence and actual tools; these are labeled separately.

Generation traces distinguish first attempts, repairs, provider failures and cache reuse. A cache hit is not fresh inference. Context mode records actual generation sources even on failed or uncovered responses; it does not force the model to reproduce quote JSON or require unrelated sections to be answered. `compose=False` and legacy `--offline-rules` now expose `document_excerpts` alongside operational guards. They do not run the earlier authored policy-answer path, so old offline scores are not new-runtime results.

Full-context quantity checks, source-derived selected numeric/date constraints, record-field consistency and action/privacy checks are finite guards. Relevant constraints bind selected category windows, computed refund dates and parsed delivery attempts, with actual context IDs and independent typed-fact/calculation proof; unrelated facts are not mandatory. Echoed questions and one-word policy replies are rejected. The model flags and host-derived label are not independent semantic proof; unrelated supplied context may still be misapplied. They do not certify every claim, actor or condition or prove complete question coverage. Failures and abstentions remain part of the result.

## Preserved earlier evidence

Legacy fallback measurements and intermediate source-only pilots predate the final core revision:

| Check | Historical result |
| --- | --- |
| Historical prompt-only baseline, `qwen3:1.7b` | **1/52**, one error |
| Grounded practice, old offline composition | **52/52** |
| Conversations, old offline composition | **96/96** |
| Old LLM-enabled questions | **52/52**; 16 generated, 25 checked static fallbacks, 4 guards, 2 rules, 5 abstentions |
| Old LLM-enabled conversations | **96/96**; 8 generated, 9 checked static fallbacks, 77 guards, 2 rules |
| Earlier incomplete live subset | 32 checked of 52 planned |
| Strict quote-generation pilot, incomplete | **1/8 checked questions passed** |
| First context-mode diagnostic, incomplete | **10/30 checked of 52 planned**, then stopped |
| Development adversarial/stateful | **77/77** |
| First independent offline holdout | **23/91** |
| Later exposed-set offline regression | **91/91** |
| Holdout privacy assertions | 191 checked, no failures |
| Gnani synthetic round trips | **6/6** audio and semantic/privacy checks |
| Hindi UPI follow-up | **1/1** |
| Digital-silence recovery | **1/1** |
| Optional regional synthetic run | **5/11**, six failures |

Pre-change live files are archived under `sample_outputs/history/pre_document_answers/`. The strict pilot is retained as `strict_quote_pilot.json` there. The incomplete first context diagnostic is preserved under `sample_outputs/history/source_context_first_pass/`; it predates the final language, calculation and quality checks. Other historical files retain original predictions/timestamps. The baseline had no document-policy fallback; it remains genuine prompt-only evidence, but does not certify the revised grounded path.

Original 49/91 holdout predictions score 51/91 under scorer v2 without prediction changes; only two points came from wording normalization. Later legacy 91/91 followed fixes after inspecting failures and is exposed regression, not a new blind evaluation or current source-only result. Full frozen rubric SHA-256: `5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7`.

Historical development coverage probe **24/24** and its failed first pass remain development evidence. Number-word rescoring (“three” versus “3”) changed matching, not predictions. Old speech files describe real Gnani calls; changing answer generation requires fresh end-to-end validation before claiming a current speech pass.

Current dataset validation passed **9 CSVs, 21 KB documents, 1,000 orders, 1,783 order items and 244 support logs**, with **52 practice questions and 23 conversations**. Twelve Streamlit integration cases are included in the engineering suite. One initial full test attempt recorded 589 passes and one UI startup timeout at 40 seconds; that UI case passed on retry in 6.15 seconds, followed by the clean full **590/590** run in 20.30 seconds. Direct final browser review was unavailable. Earlier app-health, report, package and source-provenance artifacts certify only their recorded bytes and runtime and must be refreshed.

## Remaining validation and release

- Fresh source-only question/conversation runs and Gnani speech checks are pending.
- Rebuild/render the report and verify revised archive hashes, configured-secret scan and extracted-package smoke test.
- No current live LLM holdout or controlled cold-start study is complete.
- Human speech, noise robustness and subjective listening remain unverified.
- **Own-voice rehearsal and the user-recorded demo stay last.** `demo.mp4` must be at most 120 seconds. Keep the ZIP draft until current checks and that required artifact are complete.

Reproduce with `python -m pytest -q`, then `python scripts/resume_live_practice.py --step 2` and `--step 3`. Checkpoints resume only when inference inputs match. Earlier predictions are retained; missing results must never be filled manually.

A request timeout is not a hard end-to-end guarantee. Cold startup includes resource/model loading; warm uncached inference makes a new request on loaded resources; cache hits reuse stored output. Agent-turn time excludes previous resource loading; voice timing includes STT/TTS. No score guarantees placement or unseen-question correctness.
