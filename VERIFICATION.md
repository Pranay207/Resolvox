# Verification record

All results below are local checks, not organizer scores.

- Organizer dataset validator: PASS (9 CSVs, 21 KB documents, relational integrity and verification gates).
- Clean Python 3.11 virtual environment; requirements.txt direct pins and requirements-lock.txt full Windows snapshot.
- pytest: 27 passed, including date boundaries, Unicode/ASR normalization, lockout/order changes, no proof retention, policy precedence, real Streamlit text flow, bounded retries, WAV validity and batch continuation.
- Actual Ollama baseline (no documents): 5/52 passes; 3 invalid/truncated JSON errors. Cached responses are reused on identical runs.
- Grounded evaluation with real LLM composition: 52/52 mechanical passes, 75.3% independent KB search recall@8, 97.8% used-source evidence recall. Invalid sentence-order plans fall back safely.
- Conversations with real LLM composition: 96/96 turns across 23 sessions; credentials stay outside the LLM.
- Original adversarial coverage: 65 questions and 12 multi-turn state checks, all passing.
- Four-page report rendered and visually inspected, including the architecture diagram and metric table.
- Live voice: BLOCKED because GNANI_API_KEY is missing. Voice unit tests use isolated fake HTTP clients; none are represented as live Gnani results.
- Video: user recording pending, maximum 120 seconds.

Exact commands are in README.md. Generated outputs are in sample_outputs/. Do not submit a draft archive as if live speech and the video were complete.

The exact documented setup.ps1 command also completed successfully. The dependency check reports no broken requirements. An extracted ZIP was smoke-tested with the dataset supplied externally, proving the archive does not rely on accidentally packaged data.
