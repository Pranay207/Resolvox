# Verification record

These are local measurements, not organizer scores. All raw failures and the first independent holdout are retained.

| Check | Recorded result |
|---|---|
| Engineering tests | 404/404 passed |
| Official dataset validator | Passed: 9 CSVs, 21 KB documents |
| Holdout privacy assertions | 191 checked; 0 failures |
| Prompt-only, selected model (mode not recorded) | 1/52; errors 1 |
| Grounded practice (offline_compose_false) | 52/52; errors 0 |
| Conversation practice (offline_compose_false) | 96/96; errors 0 |
| Current LLM-enabled questions | 52/52 planned; 52 evaluated; complete=True; errors 0 |
| Current LLM-enabled questions: composition | generated 16; checked fallbacks 25; guards 4; rules 2; abstentions 5 |
| Current LLM-enabled conversations | 96/96 planned; 96 evaluated; complete=True; errors 0 |
| Current LLM-enabled conversations: composition | generated 8; checked fallbacks 9; guards 77; rules 2; abstentions 0 |
| Historical post-fix live subset | 32/52 planned; 32 evaluated; incomplete; preserved unchanged |
| Development adversarial/stateful | 77/77 |
| First independent holdout, offline | 23/91 |
| Exposed holdout after fixes, offline | 91/91; 0 remaining evaluated failures |
| Real Gnani synthetic-audio round trips | 6/6 audio and 6/6 semantic checks |

The selected model is qwen3:1.7b. Current LLM-enabled grounded questions: 52/52 planned; 52 evaluated; complete=True; errors 0. Current LLM-enabled conversation turns: 96/96 planned; 96 evaluated; complete=True; errors 0. A live run includes generated answers, checked fallbacks, guards and abstentions; it does not mean every reply was freshly generated. Offline results remain separate. Earlier live runs are historical evidence, not substitutes for current completed runs. Actual timing outliers are retained; configured request timeouts do not prove a hard end-to-end latency bound. Human accent/noise robustness and subjective speech quality were not tested.

Number words and digits are scored consistently: the two conversation checks for “three” versus “3” were rescored without changing model predictions or gold expectations. Original checks are preserved.

The latest exposed-set offline regression passed 91/91, with 0 remaining failures in the evaluated cases. Old predictions scored 49/91 originally and 51/91 under scorer v2 without prediction changes: 2 points came from scoring normalization, not product improvement. The current product improved from 51 to 91 under that same scorer after runtime fixes. The first independent pass and original predictions remain preserved. Later results are exposed regressions, not a new blind holdout, live-generation test, organizer score, guarantee of placing or proof of universal semantic correctness.

The four-page report, archive inspection and configured-secret scan are verified separately in sample_outputs/pdf_qa.json, package_smoke.json and secret_audit.json. The dataset, .env, model caches and virtual environment are excluded from the ZIP.

The user-recorded demo.mp4 remains pending and must be at most 120 seconds. The ZIP is a reviewable draft until that required file is included.

Reproduce current live practice separately: python scripts/resume_live_practice.py --step 2, then --step 3. Run python -m pytest -q, rebuild/render the report, then package/verify/audit the ZIP. Earlier raw predictions remain preserved.

Optional regional-language preview remains experimental. The saved synthetic language run passed 5/11 voice cases; 6 failed and 0 are pending. This does not establish all ten languages as working; each language has only one refund-question check, and native intelligibility was not independently reviewed.

Fresh development coverage probe: 24/24. Earlier failures remain in coverage_probe_first_pass.json; these are exposed engineering checks, not an independent blind evaluation.

Final speech follow-ups: corrected Hindi UPI recognition passed 1/1 in primary_hindi_voice_validation.json; digital-silence recovery passed 1/1 in voice_recovery.json with actual Gnani STT/TTS, AI disclosure and no actions. The six normal speech cases preceded a batch-error-only AI-disclosure patch; normal speech behavior was unchanged, and the recovery replay used the final patch. Human speech and listening remain pending for the final rehearsal.

Eight Streamlit integration checks pass within the 404-test suite. Direct final browser review was unavailable; local server health returned HTTP 200. Current 52/96 inference source hashes match the final core and driver; see runtime_provenance_check.json.
