# Verification record

These are local measurements, not organizer scores. All raw failures and the first independent holdout are retained.

| Check | Recorded result |
|---|---|
| Engineering tests | 223/223 passed |
| Official dataset validator | Passed: 9 CSVs, 21 KB documents |
| Holdout privacy assertions | 191 checked; 0 failures |
| Prompt-only, selected model (mode not recorded) | 1/52; errors 1 |
| Grounded practice (offline_compose_false) | 52/52; errors 0 |
| Conversation practice (offline_compose_false) | 96/96; errors 0 |
| Post-fix live subset, incomplete | 32/52 planned; 32 evaluated; complete=False |
| Development adversarial/stateful | 77/77 |
| First independent holdout, offline | 23/91 |
| Exposed holdout after fixes, offline | 91/91; 0 remaining evaluated failures |
| Real Gnani synthetic-audio round trips | 6/6 audio and 6/6 semantic checks |

The selected model is qwen3:1.7b. Current complete Step 2/3 practice runs use offline compose=False; their passes do not measure LLM generation. Current live model evidence is the separate incomplete post-fix subset, with generated answers, checked fallbacks, guards and abstentions. Earlier complete live runs predate these fixes and do not establish current full live success. Actual timing outliers are retained; configured request timeouts do not prove a hard end-to-end latency bound. Human accent/noise robustness and subjective speech quality were not tested.

Number words and digits are scored consistently: the two conversation checks for “three” versus “3” were rescored without changing model predictions or gold expectations. Original checks are preserved.

The latest exposed-set offline regression passed 91/91, with 0 remaining failures in the evaluated cases. Old predictions scored 49/91 originally and 51/91 under scorer v2 without prediction changes: 2 points came from scoring normalization, not product improvement. The current product improved from 51 to 91 under that same scorer after runtime fixes. The first independent pass and original predictions remain preserved. Later results are exposed regressions, not a new blind holdout, live-generation test, organizer score, guarantee of placing or proof of universal semantic correctness.

The four-page report, archive inspection and configured-secret scan are verified separately in sample_outputs/pdf_qa.json, package_smoke.json and secret_audit.json. The dataset, .env, model caches and virtual environment are excluded from the ZIP.

The user-recorded demo.mp4 remains pending and must be at most 120 seconds. The ZIP is a reviewable draft until that required file is included.

Reproduce: python scripts/final_evaluate.py; python scripts/rescore_practice.py; python -m pytest -q; python scripts/build_report.py; python package_submission.py; python scripts/verify_package.py; python scripts/audit_release.py.

Fresh development coverage probe: 24/24. Earlier failures remain in coverage_probe_first_pass.json; these are exposed engineering checks, not an independent blind evaluation.

Live subset and voice artifacts retain their measured source hashes. The final verification-prompt wording and COD retrieval adjustments were checked in the subsequent full offline regressions; a complete live rerun of the final revision has not been performed.
