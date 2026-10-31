# Verification

Updated 31 October 2026. These are recorded local development measurements. Organizer hidden-audio scoring is separate.

| Selected check | Verified result | Evidence |
| --- | --- | --- |
| Four conversation scenarios | 18/18 turns | [Live and retained-output evidence](sample_outputs/targeted_live_validation.json) |
| Coupon and recorded-date refund edges | 2/2 | [Case artifacts](sample_outputs/targeted_live_validation.json) |
| Affected refund/reporting automated tests | 371 passed; zero failures/errors/skips | [Receipt](sample_outputs/refund_scope_verification_20261031.json) |
| Packaging/report automated tests | 148 passed; zero failures/errors/skips | [Receipt](sample_outputs/targeted_release_tests_20261031.json) |
| Primary-language synthetic speech | 3/3 selected clips | [Speech provenance](sample_outputs/targeted_voice_validation.json) |
| Report | Four pages, every page visually reviewed | [PDF QA](sample_outputs/pdf_qa.json) |

## What the scopes mean

Actual outputs retain their original inference source hashes. Saved successful responses are checked against current finite validators without pretending that inference was repeated. Retained speech is bound to its original Gnani WAV bytes, recorded source chunks and current spoken-output checks. The initial Hindi abstention remains preserved; its corrected clip was the only speech retest.

The required report comparison is the recorded prompt-only baseline (1/52) and accumulated grounded practice checks (52/52). The baseline used qwen3:1.7b; the current selected model is qwen3:4b-instruct, and recorded model/source revisions differ. This is a descriptive comparison with a disclosed confound, not a controlled same-model ablation.

## Reproduce selected checks

```powershell
python scripts/validate_targeted_live.py
python scripts/validate_targeted_voice.py
```

These commands run the selected scenarios and three synthetic speech clips. Smaller retests can be selected with the documented driver options. They use the actual local model and Gnani APIs; credentials stay in the ignored .env. Automated unit tests use scripted clients and are reported separately from live model/speech evidence.

## Submission checks

`python scripts/check_repository_visibility.py` checks anonymous access without changing repository visibility. `python package_submission.py` requires current evidence, four-page-or-shorter report QA, the real user-recorded demo and public repository confirmation. Packaging excludes credentials, dataset copies, model weights, environments and private input speech. ZIP creation is deferred until the final user steps are complete.

Finite source/quantity/action/privacy guards do not establish universal semantic entailment. Own-voice/noise testing and subjective listening quality remain separate from the synthetic clip measurements. Historical runs remain available under `sample_outputs/history/` with their original scopes.
