# ZentroMart VoiceOps 2026

An evidence-backed customer support agent with English, Hindi and Hinglish replies, verified order lookup, actual human-handover tickets, and Gnani-only speech.

**Public repository:** https://github.com/Pranay207/ESD

Built for From Tokens to Transformers, Consulting & Analytics Club, IIT Guwahati x Gnani.ai. This project is in `ESD`; it does not depend on MobilityRelay.

## Current status

The text/rules pipeline, multilingual dense retrieval, real Ollama baseline/composition and Streamlit text demo run locally. All 41 pytest tests pass. Six real Gnani voice round trips passed both audio and semantic checks using Gnani TTS-generated inputs. See `sample_outputs/` for generated results. Mechanical practice checks are not organizer scores or a guarantee of hidden-test performance.

**One external item remains:** record your own `demo.mp4`, maximum 120 seconds. The participant-owned Gnani key is configured locally and ignored by Git; there is no missing-key blocker. No alternate/fake speech is supplied. `SUBMISSION_STATUS.json` and `BRIEF_CHECKLIST.md` record the exact release status. The ZIP remains a draft until the user-recorded video is included.

## Quick start (Windows PowerShell)

From this folder, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

This creates a clean `.venv`, installs pinned dependencies, obtains/validates the official synthetic dataset and downloads a revision-pinned 118 MB quantized multilingual embedding model. Python 3.11 is tested. On a fresh Windows Python install, pip uses the Windows trust store; no TLS verification is disabled.

For macOS/Linux or an already selected Python:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python setup.py --models
cp .env.example .env
```

Use an installed Ollama server/model:

```powershell
ollama pull qwen3:4b-instruct
# Run ollama serve separately only if the desktop service is not already running.
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Edit `.env` locally: `GNANI_API_KEY` must be your participant-owned Gnani key from https://app.gnani.ai/voice. Never put a key in source control. The key covers both STT and TTS. No real customer data is permitted.

For a hosted compatible LLM, set `LLM_PROVIDER=compatible`, `LLM_BASE_URL` to a chat-completions base such as your provider's `/v1`, `LLM_MODEL`, and `LLM_API_KEY`. Optional `LLM_FALLBACK_*` settings select another provider. No cloud LLM key is required for installed Ollama.

## Exact organizer run command

```powershell
.\.venv\Scripts\python.exe run.py --audio_dir .\input_audio --out_dir .\sample_outputs\batch
```

Or, with the environment activated: `python run.py --audio_dir <in> --out_dir <out>`.

Each clip produces `NNN_name.json`, `NNN_name.txt`, `NNN_name_sources.json`, and a real Gnani `NNN_name_reply.wav` on speech success. JSON contains redacted transcript, intent, decision, sources, retrieved IDs, sanitized tool calls and timing. `manifest.json` records failures; malformed clips do not stop the rest. A failed speech call never creates fake audio. Exit 0 means all clips succeeded; exit 1 means failed clips or no audio; usage errors exit 2.

Supported inputs: WAV/MP3/OGG/FLAC/AAC/M4A. Gnani REST accepts clips up to 60 seconds; WAV duration is checked locally. Use `--language hi-IN` for Hindi or `en-IN` for English/Hinglish. Replies follow the customer's language.

Sessions default to independent files. In `auto` mode, `call_id__001.wav`, `call_id__002.wav` share state. `--session_mode sequential` treats the folder as one call. Optional `input_audio/sessions.json` maps filenames to `{"session_id":"call-a","language":"hi-IN"}`; it contains routing metadata only. Audio is never copied into outputs. Proof values are removed from transcripts, tool args and model context.

`--offline-rules` disables LLM composition but still uses Gnani for speech. There is no offline STT/TTS substitute.

## Reproduce evaluation

```powershell
.\.venv\Scripts\python.exe Capstone_Project_Dataset_FTTT_2026\validate_dataset.py
.\.venv\Scripts\python.exe eval_step1.py
.\.venv\Scripts\python.exe eval_step2.py --live
.\.venv\Scripts\python.exe eval_step3.py --live
.\.venv\Scripts\python.exe eval_adversarial.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe generate_voice_samples.py
.\.venv\Scripts\python.exe scripts\build_report.py
.\.venv\Scripts\python.exe package_submission.py
.\.venv\Scripts\python.exe scripts\verify_package.py
```

Step 1 makes real LLM calls with no KB/catalog. Identical calls use an output-only cache in `.cache/llm`; remove that cache for fresh inference. Three malformed/truncated baseline JSON outputs in the saved run are counted as errors, not repaired into successful answers. A baseline is allowed to be uncertain; hallucination is not manufactured.

Steps 2/3 default to offline deterministic rules for fast checks; `--live` adds the real LLM sentence-composition path. The model can order approved native-language sentences, but cannot invent new sentences or alter policy facts. This conservative design is deliberate; it is not unrestricted LLM generation. Unknown questions abstain.

The scorer tests decisions, required facts, forbidden claims and expected tool names; it cannot certify semantic correctness. Evidence recall on used sources and independent hybrid-search recall@8 are reported separately. Neither should be presented as the organizer's score. Practice-derived expectations are used only by evaluation, never the running agent/index.

`generate_voice_samples.py` creates six genuine Gnani input clips and runs Gnani STT -> the same support agent -> Gnani TTS replies. The latest run passed all 6 audio checks and all 6 semantic checks: English refund, Hindi damage, Hinglish refund, spoken order ID, first wrong-proof clarification and second wrong-proof refusal. Verification-proof redaction was checked. Inputs are synthetic Gnani TTS, not human recordings; human speech robustness and subjective listening remain unverified. Unit-test fake clients test failure handling only and are never claimed as live voice results.

To reuse the existing Gnani input clips while rerunning real STT, agent checks and reply TTS, run `.\.venv\Scripts\python.exe generate_voice_samples.py --reuse-inputs`. Validation uses the organizer CLI's LLM-composition path by default; add `--offline-rules` to use deterministic sentence plans. The adapter finalizes provider WAV headers with unknown `0xffffffff` RIFF/data lengths while preserving identical PCM samples, rejects truncated/incomplete WAV samples and null, blank or non-string STT transcripts, and redacts verification phrases without masking ordinary phone-product questions.

## Architecture and privacy

```text
Audio -> Gnani STT -> entity normalization -> session/verification gate
                                      -> hybrid KB retrieval + policy rules
                                      -> unchanged lookup_order/create_ticket tools
                                      -> verified sentence plan -> LLM ordering
                                      -> Gnani TTS -> text + WAV + source trace
```

- Current policy > agent guide > help > FAQ > marketing. Old electronics windows apply only where RET-3 grandfathers pre-1-August-2026 deliveries. Historical support logs never govern.
- Date: 20 October 2026. Business days: Monday-Saturday excluding supplied holidays. Return deadline uses delivery + N calendar days, matching supplied expected dates; see the documented inclusive-day ambiguity in `DESIGN.md`.
- Supplied tools are imported unchanged from the external dataset. Initial unverified lookup returns only a prompt. Private order results become available only after proof succeeds; one retry, then the order stays locked in that session.
- Verification secrets never reach the LLM or traces. Changing the order discards its verified context. Full phone, email, pincode and internal notes are never returned. This is educational synthetic verification, not production authentication.
- A ticket is claimed only after `created=True`; no nonexistent cancellation/refund/replacement tools are invented.

## Submission and source material

The brief requires a public repo, source/dependencies, batch command, **report <=4 pages**, **video <=2 minutes**, sample outputs, and a `team_name_voiceops.zip`. The requested longer demo outline is overridden by the brief. `pranay_voiceops.zip` uses the account owner's name as the documented team-name assumption.

The dataset, `.env`, embedding model, caches, source brief, environments and private audio inputs are excluded by an explicit packaging allowlist and `.gitignore`. Dataset source: https://drive.google.com/file/d/1jeGjWgZJ4vdfmbB71kghovcCUYNeSHOY/view . Brief: https://d8it4huxumps7.cloudfront.net/uploads/submissions_case/6ad64c83eae85_voiceops_2026_capstone_brief.pdf . Setup obtains the dataset separately rather than shipping it.

Speech API references checked against official docs: https://docs.gnani.ai/api/STT/speech-to-text and https://docs.gnani.ai/api/TTS/tts-inference . Direct REST is used to keep request/retry/error behavior explicit; this is the official Gnani API, not a substitute provider.

Model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, Apache-2.0, revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, official quantized ONNX export. See `THIRD_PARTY.md`.
