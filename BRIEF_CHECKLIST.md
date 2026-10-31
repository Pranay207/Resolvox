# VoiceOps 2026 - brief checklist

Implementation and evidence for the supplied capstone brief. Recorded test scopes remain attached to their source artifacts.

## Four required steps

- [x] LLM role/limits prompt and prompt-only baseline; the shared agent announces its AI identity at conversation start.
- [x] Section-preserving document chunks, multilingual vector index and hybrid retrieval, metadata precedence, grounded generation and saved source chunks.
- [x] Session context, follow-ups, one missing-detail question, verified private order access, supplied lookup/ticket tools and confirmed handover.
- [x] Gnani-only STT -> the same support agent -> Gnani-only TTS, with voice/text UI and a folder-based runner.

## Current recorded verification

- [x] Affected refund/reporting regressions: **371 passed**, no failures/errors/skips. [Receipt](sample_outputs/refund_scope_verification_20261031.json).
- [x] Packaging/report regressions: **148 passed**, no failures/errors/skips. [Receipt](sample_outputs/targeted_release_tests_20261031.json).
- [x] Selected conversation scenarios and refund edges: **6/6 case groups passed**, with source review. Earlier actual outputs retain their inference epoch and current finite-guard revalidation. [Evidence](sample_outputs/targeted_live_validation.json).
- [x] Primary English/Hindi/Hinglish speech: **3/3 selected synthetic round trips passed**. Only the initially failing Hindi clip was retested; retained English/Hinglish audio and spoken-output checks are identified per clip. [Evidence](sample_outputs/targeted_voice_validation.json).
- [x] Required Step 1/Step 2 comparison is reported with its model/revision differences; the report makes no controlled same-model improvement claim.

## Required deliverables

- [x] README, setup instructions, exact organizer command and key-free .env.example.
- [x] Command: `python run.py --audio_dir <in> --out_dir <out>`; saves text, JSON, real reply WAV and source chunks.
- [x] Updated **four-page report**, covering every required report topic, with visual QA of every page.
- [ ] User-recorded demo.mp4, at most two minutes: document-based answer, follow-up and handover or uncertainty. The user records it last.
- [ ] Confirm anonymous public GitHub access before submission; repository visibility is controlled by the user.
- [ ] Create the final submission ZIP only after the real demo and release checks pass. No submission ZIP has been created.

## Rules and interpretation

Only the supplied synthetic customer records are used. Speech services are exclusively Gnani, including recovery attempts. Credentials and private proof/contact fields are excluded from public traces. Runtime policy answers are generated from actual source text; practice gold is used by evaluation drivers, not as an answer lookup. Existing record readings do not claim actions by the assistant.

The selected checks are development evidence. Human accents/noise, subjective listening quality and every possible unseen question are not certified. Earlier runs remain in the linked history; authoritative current submission blockers are in [SUBMISSION_STATUS.json](SUBMISSION_STATUS.json).
