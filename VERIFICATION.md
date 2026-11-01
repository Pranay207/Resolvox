# Verification

Resolvox records the scope, source hashes and actual outputs of each check separately from organizer scoring.

| Evidence | Recorded result | Scope |
| --- | --- | --- |
| [Focused offline regressions](sample_outputs/release_update_verification.json) | **432/432 verified**; zero failures, errors or skips | Source-support flags, return-date and eligibility scope, repair context and release safeguards. Scripted clients. |
| [Refund and grounding regressions](sample_outputs/refund_scope_verification_20261031.json) | **655/655 verified**; zero failures, errors or skips | Source-bound dates, units, record reading and negative action/privacy cases. |
| [Packaging and report regressions](sample_outputs/targeted_release_tests_20261031.json) | **148/148 verified**; zero failures, errors or skips | Evidence freshness, document limits, archive filtering and release guards. |
| [Latest selected live run](sample_outputs/targeted_live_validation.json) | **Failed/incomplete** | The original mechanical checks and predictions are retained; source review rejected claims, and the coupon edge was unavailable. This is not a complete current live pass. |
| [Latest Gnani speech run](sample_outputs/targeted_voice_validation.json) | Audio batch **3/3 completed**; semantic checks **1/3 passed** | Actual Gnani STT/TTS with synthetic English, Hindi and Hinglish clips. Successful audio transport is separate from answer correctness. |
| [Return-date check records](sample_outputs/return_date_validation.json) | **1 completed Hindi check passed** in the partial run | The interrupted run has no result for unexecuted cases. |
| [Four-page report](report.pdf) | Layout QA recorded separately | Implementation, required comparison, observed failures, fixes and the stated verification limits. |

## Verified offline scope

The three automated selections overlap; their counts are not additive. Their receipts list selected files, actual JUnit/console artifacts and source/test hashes before and after each execution. They use scripted clients and negative cases, not live model inference. The broader [3,567-test engineering receipt](sample_outputs/reliability_engineering.json) belongs to an earlier revision and is not represented as current.

## Live results and daily quota

The preserved [selected conversation run](sample_outputs/targeted_live_validation.json) is marked failed and incomplete. Its original mechanical scores do not override the source-by-source review: unsupported eligibility/status claims were identified before the later fixes. The coupon edge encountered provider unavailability. The original artifacts remain unmodified and retain their actual inference source hashes.

Groq returned **HTTP 429** for the configured `openai/gpt-oss-20b` account's daily-token allowance: **200,000 tokens allowed, 199,298 used**, with the observed request needing 1,583 tokens. The user retained the existing quota and account. Further verification was limited by that allowance; no new key, paid tier or alternate provider was substituted. Later offline fixes are verified only to their recorded scope, and no complete current live-answer or speech pass is certified.

The [latest speech manifest](sample_outputs/targeted_voice_validation.json) preserves real transcriptions, generated replies and audio hashes. All three audio round trips completed, while English and Hinglish semantic checks failed and Hindi passed. An audio file's existence does not establish that its answer is correct. Synthetic clips do not establish real-speaker, accent, noise or subjective listening performance.

## Model, speech and data

The configured hosted profile uses Groq `openai/gpt-oss-20b` with low reasoning effort, constrained JSON and an additional source-claim review. Questions, retrieved policies and relevant synthetic record fields are sent to that provider. Gnani remains the only speech recognition and synthesis provider. Retrieval and the UI run locally; a separate local Ollama `qwen3:4b-instruct` profile remains available.

Credentials stay in the ignored `.env` and `.env.hosted`. Saved chats stay in ignored `.local_data/`; this mode is for one laptop and has no shared-customer account isolation. Supplied order and ticket tools operate on capstone fixtures rather than a live store backend. Response time depends on model work, loading, quota and network conditions; cached timings do not establish unseen-question performance.

## Required comparison

The recorded [prompt-only baseline](sample_outputs/eval_step1.json) is **1/52**, including one recorded error. The [grounded practice total](sample_outputs/eval_step2_latest_cases.json) is **52/52 accumulated checks** from preserved predictions and targeted retests. Model and source revisions differ, so the comparison is descriptive rather than a controlled same-model ablation or a fresh full evaluation of the current version.

## Reproduce selected checks

```sh
python scripts/validate_targeted_live.py --hosted --pacing-seconds 30
python scripts/validate_return_dates.py --hosted
python scripts/validate_targeted_voice.py --hosted
```

Use your own configured credentials and available account quota. Omit `--hosted` only for the separately configured local model. These drivers select scenarios and retain real outputs; they do not run every practice question or conversation by default. Offline scripted-client tests are reported separately.

## Report, demonstration and archive

[PDF QA](sample_outputs/pdf_qa.json) binds visual inspection to the exact report SHA-256. It verifies document layout, not universal application correctness.

[Resolovox Demo.mp4](<Resolovox Demo.mp4>) is a **105-second edited walkthrough** of actual UI voice turns: a return question, pickup-fee follow-up and uncertainty about an undocumented future policy. Customer speech and narration are synthetic Gnani audio; replies are actual application outputs. Shortened waits are disclosed. [Demo provenance](sample_outputs/demo_validation.json) retains source captures, output hashes and observed processing bounds.

The archive's `SUBMISSION_STATUS.json` preserves its actual release decision and scope. A current source snapshot is distinct from a fully verified release; ordinary final packaging checks remain active. Credentials, local chat history, input speech, dataset copies, model weights and environments are excluded. Finite validators and model-based source review do not prove every qualitative claim or unseen question.
