# Verification record

These are local measurements, not organizer scores. All raw failures and the first independent holdout are retained.

| Check | Recorded result |
|---|---|
| Engineering tests | 145/145 passed |
| Official dataset validator | Passed: 9 CSVs, 21 KB documents |
| Prompt-only, selected model | 1/52; errors 1 |
| Grounded, full live evaluation | 52/52; errors 0 |
| Conversations, full live evaluation | 96/96; errors 0 |
| Development adversarial/stateful | 77/77 |
| First independent holdout, offline | 23/91 |
| Exposed holdout after fixes, offline | 49/91; 42 unresolved checks |
| Real Gnani synthetic-audio round trips | 6/6 audio and 6/6 semantic checks |

The baseline and grounded practice run use qwen3:1.7b. Grounded replies include generated answers, version-checked fallbacks, deterministic guards and abstentions; composition counts and separate cache/uncached timings are in the JSON. Human accent/noise robustness and subjective speech quality were not tested.

Number words and digits are scored consistently: the two conversation checks for “three” versus “3” were rescored without changing model predictions or gold expectations. Original checks are preserved.

The wider regression remains incomplete (42 failed checks). Remaining issues include safe abstentions, incomplete multi-part/follow-up coverage, evidence gaps and strict wording checks. This is not evidence of top-20 readiness or universal semantic correctness.

The four-page report, archive inspection and configured-secret scan are verified separately in sample_outputs/pdf_qa.json, package_smoke.json and secret_audit.json. The dataset, .env, model caches and virtual environment are excluded from the ZIP.

The user-recorded demo.mp4 remains pending and must be at most 120 seconds. The ZIP is a reviewable draft until that required file is included.

Reproduce: python scripts/final_evaluate.py; python scripts/rescore_practice.py; python -m pytest -q; python scripts/build_report.py; python package_submission.py; python scripts/verify_package.py; python scripts/audit_release.py.
