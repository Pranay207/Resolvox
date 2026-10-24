# Verification record

All results below are local checks, not organizer scores.

- Organizer dataset validator: PASS (9 CSVs, 21 KB documents, relational integrity and verification gates).
- Clean Python 3.11 virtual environment; requirements.txt direct pins and requirements-lock.txt full Windows snapshot.
- pytest: 41 passed, including date boundaries, Unicode/ASR normalization, lockout/order changes, no proof retention, policy precedence, real Streamlit text flow, bounded retries, WAV validity and batch continuation. Additional checks cover unknown-length WAV finalization with identical PCM, truncated/incomplete sample rejection, null/blank/non-string STT rejection and broader credential phrases without masking ordinary phone-product questions.
- Actual Ollama baseline (no documents): 5/52 passes; 3 invalid/truncated JSON errors. Cached responses are reused on identical runs.
- Grounded evaluation with real LLM composition: 52/52 mechanical passes, 75.3% independent KB search recall@8, 97.8% used-source evidence recall. Invalid sentence-order plans fall back safely.
- Conversations with real LLM composition: 96/96 turns across 23 sessions; credentials stay outside the LLM.
- Original adversarial coverage: 65 questions and 12 multi-turn state checks, all passing.
- Four-page report rendered and visually inspected, including the architecture diagram and metric table.
- Live voice: PASS for all 6 audio round trips and all 6 semantic checks using real Gnani TTS-generated inputs -> Gnani STT -> the same support agent -> Gnani TTS replies. Cases cover English refund, Hindi damage, Hinglish refund, spoken order ID, first wrong-proof clarification and second wrong-proof refusal; proof redaction was verified.
- Validation scope: synthetic inputs, not human recordings. Human speech robustness and subjective listening remain unverified. Unit tests use isolated fake HTTP clients for failure handling only.
- Gnani WAV compatibility: unknown `0xffffffff` RIFF/data lengths are finalized while preserving identical PCM samples. The participant-owned key is configured locally and ignored by Git; no missing-key blocker remains.
- Video: user recording pending, maximum 120 seconds.

Exact commands are in README.md. Generated outputs are in sample_outputs/. Use `generate_voice_samples.py --reuse-inputs` to reuse the generated clips while rerunning live STT, semantic checks and reply TTS. The default uses the organizer CLI's LLM-composition path; `--offline-rules` selects deterministic sentence plans. The archive remains a draft until the user-recorded demo.mp4 is included.

The exact documented setup.ps1 command also completed successfully. The dependency check reports no broken requirements. An extracted ZIP was smoke-tested with the dataset supplied externally, proving the archive does not rely on accidentally packaged data.
