# Verification

Resolvox records test scope, execution hashes and actual outputs separately from organizer scoring.

| Evidence | Recorded result | Scope |
| --- | --- | --- |
| [Current focused offline checks](sample_outputs/release_update_verification.json) | **408/408 verified**; no failures, errors or skips | Return-date scope, source-support flags, repair context and packaging/report safeguards. Scripted clients; source/test hashes match before and after the run. |
| [Recorded engineering suite](sample_outputs/reliability_engineering.json) | **3,567 passed** | Earlier execution revision; not a current complete-suite claim. |
| [Selected conversation run](sample_outputs/targeted_live_validation.json) | **18/18 turns** and **2/2 refund edges** | Original predictions and mechanical scores retained. Source changed during the run, and the record identifies that fact. |
| [Primary-language speech](sample_outputs/targeted_voice_validation.json) | **3/3 synthetic round trips** | Actual Gnani STT/TTS in English, Hindi and Hinglish on the recorded revision. |
| [Return-date check records](sample_outputs/return_date_validation.json) | **1 completed Hindi check passed** in the latest partial run | Interrupted at the user request; no result is assigned to unexecuted cases. |
| [Four-page report](report.pdf) | Four pages; visual QA recorded separately | Implementation, required baseline comparison, scoped checks, observed failures and bonus work. |

## What is verified

The 408 current offline tests passed on frozen source/test bytes. The receipt links the exact JUnit and console logs and lists every selected test file. These tests exercise source binding and negative cases without live inference or speech calls. They do not establish current live-model accuracy.

The saved conversation and speech artifacts retain their original source hashes. Their recorded passes remain inspectable, but they do not certify a fresh full run of the latest revision. The latest return-date live run stopped after its first passing case at the user request. No complete current live pass or overall submission-readiness certification is claimed.

## Model and speech profiles

The explicit hosted application profile uses Groq `openai/gpt-oss-20b` with low reasoning effort, constrained JSON and an additional source-claim review. Questions, retrieved policies and relevant synthetic record fields are sent to that provider. Gnani remains the only speech recognition and synthesis provider. Retrieval and the UI run locally.

The separate local profile uses Ollama `qwen3:4b-instruct`. Older CPU measurements and rejected smaller-model experiments retain their original settings in the repository evidence. Provider quotas, repairs, loading and network conditions affect latency; a selected fast result is not a general response-time guarantee.

Credentials stay in the ignored `.env` and `.env.hosted`. Saved chats stay in ignored `.local_data/`; the current history mode is for one laptop and provides no shared-customer account isolation. Supplied order and ticket tools operate on capstone fixtures rather than a live store backend.

## Required comparison

The recorded [prompt-only baseline](sample_outputs/eval_step1.json) is **1/52**, including one recorded error. The [grounded practice total](sample_outputs/eval_step2_latest_cases.json) is **52/52 accumulated checks** from preserved predictions and targeted retests. Model and source revisions differ, so this is a descriptive comparison, not a controlled same-model ablation or a new full evaluation.

## Reproduce selected checks

```sh
python scripts/validate_targeted_live.py --hosted --pacing-seconds 30
python scripts/validate_return_dates.py --hosted
python scripts/validate_targeted_voice.py --hosted
```

Use your own Groq and Gnani credentials. Omit `--hosted` only for the separately configured local model. These drivers select scenarios and retain real outputs; they do not run every practice question or conversation by default. Offline tests use scripted clients and are reported separately.

## Report and demonstration

[PDF QA](sample_outputs/pdf_qa.json) binds the visually reviewed pages to the exact report SHA-256. This checks document layout, not universal application correctness.

[Resolovox Demo.mp4](<Resolovox Demo.mp4>) is a **105-second edited walkthrough** of actual UI voice turns: a clothing return question, a pickup-fee follow-up and uncertainty about an undocumented future policy. Customer speech and narration are synthetic Gnani audio; replies are actual application outputs. Shortened waits are disclosed. [Demo provenance](sample_outputs/demo_validation.json) retains source captures, output hashes and observed processing bounds.

The final ZIP is deferred at the user request. Packaging still enforces its evidence, report, demo and repository-access checks; this update does not bypass them. Finite validators and model-based source review do not prove every qualitative claim or unseen question. Human speech, noise and subjective listening quality are separate from these synthetic recordings.
