# Verification

The current core check set uses **Groq `openai/gpt-oss-120b`**, low reasoning effort, constrained JSON and an additional source-claim review. Speech uses **Gnani only**. These are selected development results; organizer hidden-audio scoring is separate.

| Check | Verified scope | Evidence |
| --- | --- | --- |
| Conversations | **18/18 turns** across four scenarios, with source-by-source review | [Current manifest](sample_outputs/targeted_live_validation.json) |
| Refund edges | **2/2**: coupon context and authenticated recorded completion date | [Case artifacts](sample_outputs/targeted_live_validation.json) |
| Primary speech | **3/3 assessed synthetic round trips** | [Text, sources, audio and hashes](sample_outputs/targeted_voice_validation.json) |
| Focused offline regressions | **432/432 passed**; zero failures, errors or skips | [Frozen receipt](sample_outputs/release_update_verification.json) |
| Refund and grounding regressions | **655/655 passed**; zero failures, errors or skips | [Frozen receipt](sample_outputs/refund_scope_verification_20261031.json) |
| Packaging and report regressions | **148/148 passed**; zero failures, errors or skips | [Frozen receipt](sample_outputs/targeted_release_tests_20261031.json) |
| Report | Four-page layout QA, bound to the actual PDF hash | [PDF QA](sample_outputs/pdf_qa.json) |

The offline selections overlap, so their totals are not additive. Receipts retain the exact selected files, console/JUnit artifacts and before/after source hashes. The [3,567-test engineering run](sample_outputs/reliability_engineering.json) belongs to an earlier revision and is historical rather than a current broad-suite claim.

## Actual live and speech evidence

The selected current core run contains all four conversation scenarios and both refund edges on one declared runtime/profile, with mechanical checks and independent text/source reviews. Earlier failed/incomplete runs remain preserved with their original outputs and hashes; their earlier mechanical passes do not override source-review failures.

The fresh Gnani batch transcribed and generated reply audio for the three synthetic primary-language inputs. Its original detector recorded **2/3** because it missed the equivalent Hindi spelling **फ़ोटो**. Only that spelling detector was extended; the exact original semantic logic was re-executed as **3/3** without changing predictions, LLM flags, numeric/source checks or WAVs. The [original manifest](sample_outputs/targeted_voice_20261101T181229Z/validation_before_unicode_fix.json), original driver and SHA-256 rescoring provenance are retained in the [current voice record](sample_outputs/targeted_voice_validation.json). Manual source review and WAV integrity checks do not establish subjective listening quality or human/noise performance.

## Supplementary return-date probes and quota

[Additional return-date probes](sample_outputs/return_date_validation.json) are outside the declared core six-scenario/three-clip release set. They were limited by provider token quota and are **not reported as 4/4**. An unconditional pickup-fee draft was rejected by source review; its conditional repair could not complete the further audit call under quota. An unfinished or unavailable probe is not assigned a pass.

Earlier Groq 20b calls reached the account's 200,000-token daily allowance; the recorded rejection showed 199,298 used and a 1,583-token request. The current core results explicitly use 120b on the same configured account/key, rather than mixing 20b and 120b outcomes. No new account key, paid tier or substitute speech provider is implied. Provider quotas, model work and network conditions affect latency; a selected result is not a general response-time guarantee.

## Historical required comparison

The recorded [prompt-only baseline](sample_outputs/eval_step1.json) is **1/52**, including one recorded error. The [grounded practice total](sample_outputs/eval_step2_latest_cases.json) is **52/52 accumulated checks** from preserved outputs and targeted retests across earlier model/source revisions. This is descriptive, not a controlled same-model ablation or a fresh full evaluation of the current version.

## Reproduce selected checks

```sh
python scripts/validate_targeted_live.py --hosted --pacing-seconds 30
python scripts/validate_targeted_voice.py --hosted
```

The supplementary driver is `python scripts/validate_return_dates.py --hosted`. Your ignored `.env.hosted` provides the explicit Groq profile and your key; ignored `.env` holds Gnani credentials and local settings. Omit `--hosted` only for the separately configured local Ollama profile. Drivers preserve actual outputs and execution profiles; model cache metrics remain visible in voice artifacts.

## Demonstration, data and packaging

[Resolovox Demo.mp4](<Resolovox Demo.mp4>) is a **105-second edited walkthrough** with synthetic customer speech/narration, actual application replies and disclosed shortened processing waits. [Demo provenance](sample_outputs/demo_validation.json) preserves source captures and output hashes.

The ordinary package checker uses its original `targeted_live_with_disclosed_limits` policy. It preserves selected evidence and its warnings rather than claiming an unseen organizer score or universal semantic accuracy. Supplementary return-date checks do not become a fabricated complete score. The archive's `SUBMISSION_STATUS.json` records the actual core release decision; ordinary final gates remain active.

Credentials, local chat history, private input speech, dataset copies, model weights and environments are excluded. The current store/ticket tools use the supplied capstone fixtures. Saved history is intended for one laptop and provides no shared-customer account isolation. Human-speaker/noise testing and deployment-scale behavior remain distinct from these selected checks.
