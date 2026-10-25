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

- [x] Full engineering suite: **145/145 pytest tests**, exit code 0; official dataset validation also exited 0. Evidence: `sample_outputs/engineering_verification.json`.
- [x] Selected same-model comparison with `qwen3:1.7b`: prompt-only baseline **1/52**, with **1 error** retained; live RAG practice **52/52**; live conversation practice **96/96**. Evidence: `eval_step1.json`, `eval_step2.json`, `eval_step3.json` in `sample_outputs/`.
- [x] Judgment normalizes equivalent spelled-number/digit forms; raw model predictions remain unchanged and preserved. Mechanical passes do not certify every claim or hidden-test quality.
- [x] Composition is reported separately: single questions contain **17 grounded LLM**, **24 checked fallback**, **5 missing-evidence abstention**, **2 checked rule** and **4 guardrail** responses. Conversation turns contain **5 grounded LLM**, **12 checked fallback**, **2 checked rule** and **77 guardrail** responses. A live run does not mean every response was freshly generated.
- [x] Development adversarial/stateful checks: **77/77** in `sample_outputs/eval_adversarial.json`; these are development regressions, not an independent holdout.
- [x] Retrieval is measured separately at **k=12**: single-question search recall **96.1%**, used-source recall **85.6%**. Conversation search recall **29.5%**, used-source recall **97.3%**; many conversation turns use explicit authentication/guard sources rather than query search.
- [x] Selected-model actual-practice timing is separated by path: **38 uncached requests, mean 14.78 s**, versus **3 output-cache responses, mean 0.234 s**, in `sample_outputs/generation_benchmark_selected.json`. Accepted grounded-generation counts for those groups are 15 and 2 respectively; fallback and cache success are not fresh-generation success.
- [x] Real Gnani validation: **6/6 audio round trips** and **6/6 semantic/privacy checks** in `sample_outputs/voice_validation.json`. Inputs are synthetic Gnani TTS clips.
- [x] Frozen fixture integrity is preserved. First independent **offline** holdout: **23/91**; post-fix **offline exposed-set regression: 49/91**, with **42 unresolved**. Retain both `eval_holdout_first_pass.json` and `eval_holdout.json`; fixtures and original predictions are not rewritten to hide failures.

## Still incomplete

- [ ] Live LLM holdout evaluation has **not** been performed. The two recorded holdout results above are offline; do not present them as live-generation results or treat the later exposed regression as independent.
- [ ] Controlled cold-start latency has **not** been measured. Per-turn uncached and cache measurements exclude prior resource startup and are not cold-start measurements.
- [ ] Human speech testing and subjective listening have **not** been completed. Synthetic TTS-input round trips do not establish human accent/noise robustness.
- [ ] Complete final `report.pdf` QA: maximum four pages, render and inspect every page against the latest JSON evidence.
- [ ] Complete final ZIP/release-content QA and package allowlist checks; retain package-verifier output.
- [ ] Push the latest verified revision and final evidence to the public repository; earlier public commits do not establish that the final revision was pushed.
- [ ] User records `demo.mp4` (maximum 120 seconds) after final validation; show actual generation mode, sources, verification/handover and live Gnani speech.
- [ ] Build final-ready `team_name_voiceops.zip` with the required report, demo and generated sample outputs. Keep draft status until required artifacts exist and verification passes.

Current measurements belong in `sample_outputs/*.json`, `VERIFICATION.md` and `SUBMISSION_STATUS.json`. A previous run or implemented feature is not evidence that a pending run passed.

## Frozen holdout

Fixture: `tests/holdout_cases.json`. Full rubric SHA-256:

```text
5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7
```

The fixture is evaluation data, never runtime retrieval or answer-generation knowledge. The preserved first independent offline pass scored **23/91 (25.3%)**. After inspecting failures and making general fixes, the exposed-set offline regression scored **49/91 (53.8%)**, leaving **42 failures**. That improvement is a regression result on an exposed set, not a second independent holdout. No live holdout run has been performed. All original fixtures and first-pass outputs remain retained; mechanical rubric matching does not replace semantic review.

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
