# Verification record

These are local measurements, not organizer scores. The source-only answer correction on **25 October 2026** creates a new runtime boundary. Earlier authored-fallback results are preserved and must not be presented as current results.

## Current source-only runtime

| Check | Current record |
| --- | --- |
| Current full suite, code `5d08ca6` | **1016/1016 passed; 32.429 s JUnit duration** |
| Live grounded practice | **52 questions planned; rerun pending** |
| Live conversations | **96 turns planned; rerun pending** |
| Current-model prompt-only baseline | **52 planned; pending** |
| Live adversarial/development checks | **77 planned; pending** |
| Live exposed regression | **91 planned; pending** |
| Gnani synthetic end-to-end speech | Six round trips and silence recovery pending |
| Report rendering and four-page QA | Existing PDF is a stale draft; regeneration and QA pending |
| Revised ZIP extraction/hash/secret checks | Existing ZIP is stale; rebuild and verification pending |

The [engineering receipt](sample_outputs/engineering_verification.json) records exit code 0, no failures/errors/skips, matching start/end source hashes and unchanged verification inputs. Its [JUnit XML](sample_outputs/engineering_artifacts/20261025T124401715563Z_8aea71eb/pytest.xml) supplies the 1016 cases and **32.429-second JUnit duration**; the actual pytest process wall time was **35.405 seconds**. The [pytest log](sample_outputs/engineering_artifacts/20261025T124401715563Z_8aea71eb/pytest.log) and [dataset log](sample_outputs/engineering_artifacts/20261025T124401715563Z_8aea71eb/dataset_validation.log) are preserved as real artifacts. Engineering success does not certify live model or speech correctness.

The first real boolean-contract public Hinglish warranty pilot returned the supported duration and claim route, with a host-derived answer decision and no repair. Its 93.7-second turn included initial loading and concurrent pytest CPU load; it is not a controlled warm/cold latency result. These intermediate pilots are not complete suite or speech evidence. The planned verification order is questions, conversations, live development checks, live exposed regression, the current-model baseline, Gnani round trips and silence recovery. Full-stage results are pending; this plan does not mean every stage is queued or running.

The recorded local model is `qwen3:4b-instruct`, with `LLM_TIMEOUT=180` and `RAG_LLM_TIMEOUT=180` in `.env`. Code and `.env.example` defaults remain 120 seconds. The baseline used `qwen3:1.7b`; that historical comparison is not a controlled same-model baseline/RAG ablation. A new 52-question baseline on the current 4B model is planned and will be compared only after completion. Earlier 45-second 4B probes timed out. Two later 120-second diagnostic cases produced relevant Hinglish warranty content and the correct public-date projection, but the first had an inconsistent refusal label and the second failed the completed-action wording guard. They are diagnostic evidence, **not passed final checks**; targeted decision/action repairs require fresh validation. Current live runs must retain source/input/settings hashes, completion flags, failures, timings, actual generation context and composition. Current output filenames are `sample_outputs/eval_step2_live_current.json` and `sample_outputs/eval_step3_live_current.json`. Pending is not passed.

Ordinary domain answers now come from `document_reply`, which receives actual retrieved text and safe verified/source-derived facts. It returns an answer and strict `covered`/`needs_clarification` booleans. The host derives clarify if clarification is needed, otherwise answer if covered, otherwise refuse; traces retain `model_flags` and `decision_origin=host_boolean_mapping`. Legacy exact three-field responses remain strictly checked and labeled `legacy_model_decision`, without silently relabeling old refusals. The host saves the exact full supplied chunks and their IDs as `generation_context` provenance. The normal `citations` list is empty; no model-selected quotes or per-claim support are claimed. Invalid output gets one bounded repair; model failure or another invalid output produces abstention. **Prewritten policy fallback is removed from normal answer generation.** Deterministic operational/escalation messages may retain policy explanations bound to explicit evidence and actual tools; these are labeled separately.

Generation traces distinguish first attempts, repairs, provider failures and cache reuse. A cache hit is not fresh inference. Context mode records actual generation sources even on failed or uncovered responses; it does not force the model to reproduce quote JSON or require unrelated sections to be answered. `compose=False` and legacy `--offline-rules` now expose `document_excerpts` alongside operational guards. They do not run the earlier authored policy-answer path, so old offline scores are not new-runtime results.

Full-context quantity checks, source-derived selected numeric/date constraints, record-field consistency and action/privacy checks are finite guards. Added source-derived checks cover missing table inputs, unopened/seal conditions, unknown placement/delivery premises, conditional return exceptions, permission direction, warranty scope and paid-fee/Plus credit conditions. Language-only repair preserves the JSON field/flag contract and is checked again; it does not prove semantic equivalence. Relevant constraints bind selected category windows, computed refund dates and parsed delivery attempts, with actual context IDs and independent typed-fact/calculation proof; unrelated facts are not mandatory. Echoed questions and one-word policy replies are rejected. The model flags and host-derived label are not independent semantic proof; unrelated supplied context may still be misapplied. They do not certify every claim, actor or condition or prove complete question coverage. Failures and abstentions remain part of the result.

Recognized unsupported topics now bypass normal generation and return generic uncertainty. This is a conservative routing guard, not a policy-answer fallback or complete semantic classifier. The ad hoc routing probe at `sample_outputs/history/unsupported_routing_probe.json` recorded 2/3 strict checks; the “2 am” delivery question asked for an order ID instead of generic uncertainty. It invented no policy, but remains a failed expected-uncertainty check. No live inference is claimed for that spy-based routing probe.

**Byte provenance.** Runtime sources were normalized to LF under `.gitattributes` before the `5d08ca6` measurements. Receipts record actual Git HEAD and source/input byte hashes, including matching runtime start/end maps. Newline conversion may change a raw hash despite a clean Git content diff. Do not promote pre-normalization receipts as current. Append-only `tools/tickets_created.csv` is generated output and is excluded from input fingerprints.

## Preserved earlier evidence

Legacy fallback measurements and intermediate source-only pilots predate the final core revision:

| Check | Historical result |
| --- | --- |
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
| Later complete boolean-context diagnostic | **36/52 mechanical passes**; separate semantic audit below |
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

The [semantic review](sample_outputs/history/source_context_boolean_full_first_pass/semantic_review.md) retains the exact findings. No predictions, scorer or gold answers were changed, and no adjusted semantic pass rate was computed. This is assistant review, not human certification or proof that every other sentence is correct. The new guards require fresh live validation; the 1016 engineering passes alone do not close these findings.

Original 49/91 holdout predictions score 51/91 under scorer v2 without prediction changes; only two points came from wording normalization. Later legacy 91/91 followed fixes after inspecting failures and is exposed regression, not a new blind evaluation or current source-only result. Full frozen rubric SHA-256: `5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7`.

Historical development coverage probe **24/24** and its failed first pass remain development evidence. Number-word rescoring (“three” versus “3”) changed matching, not predictions. Old speech files describe real Gnani calls; changing answer generation requires fresh end-to-end validation before claiming a current speech pass.

Current dataset validation passed **9 CSVs, 21 KB documents, 1,000 orders, 1,783 order items and 244 support logs**, with **52 practice questions and 23 conversations**. Twelve Streamlit integration cases are included in the engineering suite. One initial full test attempt recorded 589 passes and one UI startup timeout at 40 seconds; that UI case passed on retry in 6.15 seconds, followed by the clean full **590/590** run in 20.30 seconds. Direct final browser review was unavailable. Earlier app-health, report, package and source-provenance artifacts certify only their recorded bytes and runtime and must be refreshed.

## Remaining validation and release

- Fresh source-only question/conversation runs and Gnani speech checks are pending.
- Rebuild/render the report and verify revised archive hashes, configured-secret scan and extracted-package smoke test.
- The current live exposed regression and same-model baseline are pending. No new blind holdout or controlled cold-start study is complete.
- Human speech, noise robustness and subjective listening remain unverified.
- **Own-voice rehearsal and the user-recorded demo stay last.** `demo.mp4` must be at most 120 seconds. Keep the ZIP draft until current checks and that required artifact are complete.

Reproduce with `python -m pytest -q`, then `python scripts/resume_live_practice.py --step 1`, `--step 2` and `--step 3`. Optional live regressions use `python eval_adversarial.py --live --output sample_outputs/eval_adversarial_live_current.json` and `python eval_holdout.py --output sample_outputs/eval_holdout_live_current.json`. Checkpoints resume only when inference inputs match. Earlier predictions are retained; missing results must never be filled manually.

A request timeout is not a hard end-to-end guarantee. Cold startup includes resource/model loading; warm uncached inference makes a new request on loaded resources; cache hits reuse stored output. Agent-turn time excludes previous resource loading; voice timing includes STT/TTS. No score guarantees placement or unseen-question correctness.
