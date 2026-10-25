# VoiceOps 2026 - brief checklist

Source: `voiceops_2026_capstone_brief.pdf`. Work lives in `ESD`. Implementation checks below describe inspectable behavior; final validation is recorded separately and must use regenerated outputs from the current revision.

## Implemented requirements

- [x] Prompt-only LLM baseline without company documents, catalog or private order access; preserve real outputs and errors.
- [x] KB section chunks retain IDs and authority/version/effective-date/status metadata.
- [x] Query-first lexical/multilingual hybrid retrieval at the agent's actual k=12, followed by source-scoped planning and source-text LLM generation.
- [x] Answer-only LLM JSON with code-attached provenance for the actual supplied full sections, conservative source-contract checks, version-bound static fallback, and abstention on missing evidence. Provenance is not per-claim semantic proof.
- [x] Separate explicit guard-policy lookups for authentication, privacy, urgent escalation and tool-result handling; guard sources are not presented as query-search success.
- [x] Session state, one clarification at a time, supplied lookup/ticket tools, per-order authentication failure counts and order/reason ticket deduplication.
- [x] Verify before private order disclosure; one retry; redact proof values and private contact fields from traces/model input.
- [x] Reference date 20 October 2026, Mon-Sat business days excluding holidays, calendar-day returns and successor-authorized historical scope.
- [x] Gnani STT -> same agent -> Gnani TTS adapter, served model selection, batch failure isolation and real-WAV validation.
- [x] Public repository, installation instructions, dependencies, `.env.example` and exact organizer batch command.
- [x] Frozen independent holdout fixture and checker: 64 singles + 10 scenarios/27 turns = 91 judged responses.

## Recorded verification

- [x] Engineering: **404/404 pytest tests**; official dataset validator passed.
- [x] Prompt-only selected-model baseline: **1/52**, errors 1; see `sample_outputs/eval_step1.json` for actual composition, configuration and timings.
- [x] Grounded practice questions (offline_compose_false): **52/52**, errors 0; see `sample_outputs/eval_step2.json` for actual composition, configuration and timings.
- [x] Conversation practice turns (offline_compose_false): **96/96**, errors 0; see `sample_outputs/eval_step3.json` for actual composition, configuration and timings.
- [x] Current LLM-enabled grounded questions: 52/52 planned; 52 evaluated; complete=True; errors 0; see `sample_outputs/eval_step2_live_current.json`.
  Composition: generated 16; checked fallbacks 25; guards 4; rules 2; abstentions 5.
- [x] Current LLM-enabled conversation turns: 96/96 planned; 96 evaluated; complete=True; errors 0; see `sample_outputs/eval_step3_live_current.json`.
  Composition: generated 8; checked fallbacks 9; guards 77; rules 2; abstentions 0.
- [x] Historical live subset preserved unchanged: 32/52 planned; 32 evaluated. This is not current complete-run evidence.

Optional regional-language preview remains experimental. The saved synthetic language run passed 5/11 voice cases; 6 failed and 0 are pending. This does not establish all ten languages as working; each language has only one refund-question check, and native intelligibility was not independently reviewed.

- [x] Development adversarial/stateful regression: **77/77**; development data, not blind evaluation.
- [x] The latest exposed-set offline regression passed 91/91, with 0 remaining failures in the evaluated cases. Old predictions scored 49/91 originally and 51/91 under scorer v2 without prediction changes: 2 points came from scoring normalization, not product improvement. The current product improved from 51 to 91 under that same scorer after runtime fixes. The first independent pass and original predictions remain preserved. Later results are exposed regressions, not a new blind holdout, live-generation test, organizer score, guarantee of placing or proof of universal semantic correctness.
- [x] Holdout privacy assertions: 191 recorded, 0 failed.
- [x] Real Gnani synthetic-audio round trips: **6/6** audio, **6/6** semantic/privacy checks. Human accent/noise robustness and subjective listening remain unverified.

Measured JSON and `VERIFICATION.md` preserve provenance, failures, timing and composition. A live run includes checked fallbacks and guards; it does not mean every reply was freshly generated.

## Final submission and additional validation

The required missing artifact is the user-recorded demo. Live holdout, controlled cold-start and noisy human-speech studies are additional validation; the final own-voice rehearsal accompanies the demo, which the user requested last.

- [ ] Live LLM holdout evaluation has **not** been performed. All recorded holdout results above are offline; do not present them as live-generation results or treat the later exposed regression as independent.
- [ ] Controlled cold-start latency has **not** been measured. Per-turn uncached and cache measurements exclude prior resource startup and are not cold-start measurements.
- [ ] Human speech testing and subjective listening have **not** been completed. Synthetic TTS-input round trips do not establish human accent/noise robustness.
- [x] Final `report.pdf` QA: four pages rendered and visually inspected against current results; see `sample_outputs/pdf_qa.json`.
- [x] Final ZIP extraction, import/answer smoke test and package allowlist checks passed; retain `sample_outputs/package_smoke.json`.
- [ ] Push the final submission revision containing demo.mp4 and final-ready package evidence; verify local and remote commit IDs after the demo is included.
- [ ] User records `demo.mp4` (maximum 120 seconds) after final validation; show actual generation mode, sources, verification/handover and live Gnani speech.
- [ ] Build final-ready `team_name_voiceops.zip` with the required report, demo and generated sample outputs. Keep draft status until required artifacts exist and verification passes.

Current measurements belong in `sample_outputs/*.json`, `VERIFICATION.md` and `SUBMISSION_STATUS.json`. A previous run or implemented feature is not evidence that a pending run passed.

## Frozen holdout

Fixture: `tests/holdout_cases.json`. Full rubric SHA-256:

```text
5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7
```

The fixture is evaluation data, never runtime retrieval or answer-generation knowledge. The preserved first independent offline pass scored **23/91 (25.3%)**. After inspecting failures and making general fixes, the exposed-set offline regression scored **91/91 (100%)** under scorer v2, leaving **0 failures in the evaluated cases**. The prior 49/91 predictions are preserved in `eval_holdout_before_normalization_v2.json`; rescoring those same unchanged predictions yields **51/91** in `eval_holdout_scorer_v2_same_predictions.json`. Thus **2 points** came from scoring normalization, and improvement from **51 to 91** is measured after runtime fixes under the same v2 scorer. This is an exposed-set regression, not a second independent holdout or proof of complete customer-question coverage. No live holdout run has been performed. All original fixtures and first-pass outputs remain retained; mechanical rubric matching does not replace semantic review.

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

Current additional speech checks: Hindi UPI 1/1 and real Gnani silent-audio recovery 1/1, including first-reply AI disclosure. See their separate evidence JSON files.
