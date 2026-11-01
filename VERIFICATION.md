# Verification

These are recorded local development measurements. Organizer hidden-audio scoring is separate.

| Selected check | Verified result | Evidence |
| --- | --- | --- |
| Four conversation scenarios | 18/18 turns | [Live and retained-output evidence](sample_outputs/targeted_live_validation.json) |
| Coupon and recorded-date refund edges | 2/2 | [Case artifacts](sample_outputs/targeted_live_validation.json) |
| Affected refund/reporting automated tests | 371 passed; zero failures/errors/skips | [Receipt](sample_outputs/refund_scope_verification_20261031.json) |
| Packaging/report automated tests | 148 passed; zero failures/errors/skips | [Receipt](sample_outputs/targeted_release_tests_20261031.json) |
| Primary-language synthetic speech | 3/3 selected clips | [Speech provenance](sample_outputs/targeted_voice_validation.json) |
| Report | Four pages, every page visually reviewed | [PDF QA](sample_outputs/pdf_qa.json) |

## Response reliability

The [current engineering receipt](sample_outputs/reliability_engineering.json) records **3,461 passing tests**, zero failures, errors or skips, and matching source/test hashes before and after execution. The [four focused response checks](sample_outputs/reliability_live_validation.json) pass with actual cache use disclosed per case. They cover wallet timing, a Plus pickup waiver, Hindi damage reporting and uncertainty about an unsupported future policy. These are targeted checks, not a fresh run of all 52 questions or 96 conversation turns.

The recorded [uncached wallet voice turn](sample_outputs/reliability_artifacts/previous_voice_20261101T103517Z.json) used actual Gnani STT, local Ollama generation and Gnani TTS. Answer generation took **36.297 seconds** and the whole turn took **38.299 seconds**, compared with **92.152 seconds** in the [earlier voice check](sample_outputs/reliability_artifacts/before_speed_wording_voice.json). The narrower source-only timing prompt reduced prompt tokens from 1,230 to 761. Both runs retain their actual source hashes; the comparison is observational and includes different model loading times. The final [current-runtime voice retest](sample_outputs/reliability_voice_validation.json) reused cached model output; its lower time is not an uncached inference result.

The [history manifest](sample_outputs/reliability_artifacts/history_manifest.json) distinguishes these historical timing records from current audio evidence. Historical WAV bytes were not retained when their output path was reused; the current published reply WAV is checked against its exact recorded SHA-256.

The laptop is CPU-only. This setup **does not meet a general 5–10 second response target** for unseen questions. Faster inference hardware remains necessary to pursue that target with the selected model; cached-response timing does not establish it. The [desktop UI checks](sample_outputs/reliability_ui_validation.json) confirm that a supported reply and an uncertainty reply are actually shown in the application.

Response scopes now bound model and speech waits, report busy/time-out/unavailable states separately from missing policy evidence, and keep validated text visible if reply audio fails. Only an active Windows request holds off automatic idle sleep; its previous execution state is restored afterward. Full input context and rejected drafts remain in audit evidence. No hosted LLM was used in these checks, and speech remains Gnani-only. The supplied orders and ticket tools remain capstone fixtures, not a live store backend.

## What the scopes mean

Actual outputs retain their original inference source hashes. Saved successful responses are checked against current finite validators without pretending that inference was repeated. Retained speech is bound to its original Gnani WAV bytes, recorded source chunks and current spoken-output checks. The initial Hindi abstention remains preserved; its corrected clip was the only speech retest.

The required report comparison is the recorded prompt-only baseline (1/52) and accumulated grounded practice checks (52/52). The baseline used qwen3:1.7b; the current selected model is qwen3:4b-instruct, and recorded model/source revisions differ. This is a descriptive comparison with a disclosed confound, not a controlled same-model ablation.

## Recorded local runtime

The recorded laptop checks used local Ollama `qwen3:4b-instruct` on port **11435**. The README and `.env.example` use the standard port **11434** for setup. To reproduce the recorded endpoint, start Ollama in a separate PowerShell terminal:

```powershell
$env:OLLAMA_HOST='127.0.0.1:11435'
ollama serve
```

Set `LLM_BASE_URL=http://127.0.0.1:11435` in the ignored `.env` when using that server. The server address and client configuration must match.

Selected generated turns took **12.4–257.1 seconds** on the recorded CPU setup. Per-stage timings and execution revisions are retained in the [targeted evidence](sample_outputs/targeted_live_validation.json); these timings do not establish a general latency guarantee. The [new-case UI smoke check](sample_outputs/ui_user_smoke_20261031.json) records interactive probes and their targeted fixes.

## Reproduce selected checks

```powershell
python scripts/validate_targeted_live.py
python scripts/validate_targeted_voice.py
```

These commands run the selected scenarios and three synthetic speech clips. Smaller retests can be selected with the documented driver options. They use the actual local model and Gnani APIs; credentials stay in the ignored .env. Automated unit tests use scripted clients and are reported separately from live model/speech evidence.

## Recorded demonstration

[Resolovox Demo.mp4](<Resolovox Demo.mp4>) is a **105-second edited walkthrough** of three actual UI voice turns: clothing return timing, a contextual pickup-fee follow-up, and uncertainty about an undocumented future policy. Customer speech and narration are synthetic Gnani audio; the replies are actual application outputs. Processing waits are shortened and disclosed. [Demo provenance](sample_outputs/demo_validation.json) preserves unmodified replies, source captures, speech hashes, round-trip transcripts and the observed processing-time bounds. This is a selected product demonstration, not a new full practice score or a human/noise listening study.

## Submission checks

`python scripts/check_repository_visibility.py` checks anonymous access without changing repository visibility. `python package_submission.py` requires current evidence, four-page-or-shorter report QA, the real recorded demo and public repository confirmation. Packaging excludes credentials, dataset copies, model weights, environments and private input speech. The [current readiness check](sample_outputs/reliability_packaging_status.json) records stale release evidence after these runtime changes. The existing ZIP predates the response reliability updates and must be rebuilt after the targeted release, speech and report checks are refreshed.

To prepare an archive before recording the demo, run `python package_submission.py --draft`. This creates `dist/pranay_voiceops_draft.zip` with a draft notice and `ready_to_submit=false`. It defers only the missing demo and unconfirmed public-access checks; all other release checks remain active. Rebuild without `--draft` after those steps are complete. The ZIP includes Engineering Deep Dive and excludes credentials, dataset copies and model weights.

Finite source/quantity/action/privacy guards do not establish universal semantic entailment. Own-voice/noise testing and subjective listening quality remain separate from the synthetic clip measurements. Historical runs remain available under `sample_outputs/history/` with their original scopes.
