# Resolvox — Multilingual AI Voice Support

**VoiceOps 2026 Capstone**

Built for ZentroMart’s online shoppers. A customer support agent that retrieves company policies, verifies order access, creates handover tickets through the supplied tools, and uses Gnani for speech. Primary support is English, Hindi and Hinglish. An optional regional-language preview configures all ten Gnani languages plus Hinglish; its incomplete quality is reported separately. New regional-language handling uses a dedicated local translation model around the same support agent; measured per-language readiness is recorded separately.

**Public repository:** https://github.com/Pranay207/Resolvox

Built for From Tokens to Transformers, Consulting & Analytics Club, IIT Guwahati x Gnani.ai. This project lives in `ESD` and has no MobilityRelay dependency.

## Current status

The implementation includes query-first hybrid retrieval, source-text LLM generation, checked deterministic fallbacks, session verification, and the Gnani speech wrapper. The selected local model is `qwen3:1.7b`. The latest broader offline regression passes **91/91**, with **0 remaining failures in these evaluated cases**; the engineering suite passes **404/404**. Offline practice remains 52/52 questions and 96/96 conversation turns with `compose=False`. Current LLM-enabled grounded questions: 52/52 planned; 52 evaluated; complete=True; errors 0. Current LLM-enabled conversation turns: 96/96 planned; 96 evaluated; complete=True; errors 0. A live run includes generated answers, checked fallbacks, guards and abstentions; it does not mean every reply was freshly generated. Offline results remain separate. Earlier live runs are historical evidence, not substitutes for current completed runs. Actual composition, cache status, provenance and timings are recorded in `sample_outputs/`. Request timeout settings do not establish a hard end-to-end bound; neither offline passes nor synthetic voice checks establish human-speech performance.

`tests/holdout_cases.json` is a frozen independent evaluation suite: 64 single questions and 10 stateful scenarios containing 27 turns, for 91 judged responses. Its full rubric SHA-256 is `5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7`. The suite is not runtime knowledge. Its first independent offline pass remains preserved at **23/91**. After exposure and general fixes, `sample_outputs/eval_holdout.json` records **91/91 offline** under scorer v2; this is an exposed-set regression, not a new blind result. The old **49/91** predictions score **51/91** under v2 without changing predictions: only **2 points** came from equivalent-wording normalization. The rise from **51 to 91 under the same scorer** reflects runtime fixes. Both old predictions and rescoring provenance are retained; zero failures here does not guarantee hidden-test correctness or placement.

The final `demo.mp4` must be recorded by the user and last at most 120 seconds. The package remains a draft until required artifacts and final verification are complete. See `BRIEF_CHECKLIST.md`, `VERIFICATION.md` and `SUBMISSION_STATUS.json`.

## Quick start

On Windows PowerShell, from this folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Setup creates `.venv`, installs pinned dependencies, validates the official synthetic dataset and obtains the revision-pinned quantized multilingual embedding model. Python 3.11 is the tested environment. Windows trust-store support keeps TLS verification enabled.

For macOS/Linux:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python setup.py --models
cp .env.example .env
.venv/bin/python -m streamlit run app.py
```

Configure the LLM in your local `.env`: `LLM_PROVIDER=ollama` and `LLM_MODEL=qwen3:1.7b`. Install the selected model:

```powershell
ollama pull qwen3:1.7b
```

Start Ollama if its service is not already running. Benchmark JSON records measured generation, fallback and latency behavior; model installation alone is not evidence of a successful run. A compatible hosted endpoint can instead use `LLM_PROVIDER=compatible`, `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY`; optional `LLM_FALLBACK_*` settings configure a second endpoint.

Set `GNANI_API_KEY` to your participant-owned key from https://app.gnani.ai/voice. It covers STT and TTS. Keep credentials in `.env` and out of source control. Use only synthetic or consented inputs.

## Organizer batch command

```powershell
.\.venv\Scripts\python.exe run.py --audio_dir .\input_audio --out_dir .\sample_outputs\batch
```

With the environment activated: `python run.py --audio_dir <in> --out_dir <out>`.

Each clip produces JSON, text, sources JSON, and a real Gnani reply WAV when speech succeeds. `manifest.json` records per-file failures; a failed call never creates substitute audio. Exit 0 means all inputs succeeded, exit 1 means failed/no inputs, and usage errors exit 2. Supported formats are WAV/MP3/OGG/FLAC/AAC/M4A; Gnani REST clips are limited to 60 seconds, and WAV duration is checked locally. Use `--language te-IN` for Telugu, `hi-IN` for Hindi, or any code in the language table below. `en-IN` accepts English/Hinglish.

Files are independent by default. In auto mode, `call_id__001.wav` and `call_id__002.wav` share a session. `--session_mode sequential` uses one session for the folder; optional `sessions.json` maps files to session/language metadata. Raw input audio is not copied into outputs. Verification proofs are removed from transcript, tool arguments and model context.

`--offline-rules` disables LLM answer generation. Speech still calls Gnani; there is no offline STT/TTS substitute.

## Demo interface

The Streamlit console opens in Voice support with a consistent light theme. Choose Record or Upload explicitly, select the spoken language, and send a clip of up to 60 seconds. Progress shows listening, checking and reply preparation.

Voice and Text support share one conversation and verification state. Redacted transcripts, answers and generated reply audio persist across reruns. If speech synthesis fails, the text answer remains available; Retry reply audio only synthesizes the existing answer. New conversation clears the conversation, authentication and audio inputs. Sources and actions are expandable; recorded evaluation separates offline checks, current live runs and historical results.

The packaged `.streamlit/config.toml` keeps native controls and page colors consistent. Uploads are limited to 20 MB. API credentials stay in the ignored `.env`; do not add `.streamlit/secrets.toml` to Git.

## Language support

Select the spoken language before recording. Primary choices are English/Hinglish and Hindi. For the optional regional preview, first run `python scripts/setup_translation.py` (approximately 907 MB of separately downloaded weights), then enable Demo settings → Preview additional languages. Primary-language setup does not download this optional model. The first all-language synthetic run passed 5/11 checks; six failures remain documented, so the preview is not claimed as fully working. Text supports script detection; choose Marathi explicitly because Hindi and Marathi share Devanagari. English/Hindi/Hinglish keep the existing path. Other languages use the local NLLB translation model to translate a masked query, run the same grounded agent and localize its checked reply. Numeric placeholders, script and translation checks reject malformed output; translation failure produces an honest localized retry instead of claiming a policy answer. These finite checks do not prove semantic equivalence. Offline rules mode does not provide regional translation.

| Language | Batch/STT code | TTS voice |
|---|---|---|
| English | en-IN | Kaveri |
| Hindi | hi-IN | Nalini |
| Bengali | bn-IN | Kirra |
| Gujarati | gu-IN | Falak |
| Kannada | kn-IN | Saanvi |
| Malayalam | ml-IN | Reshma |
| Marathi | mr-IN | Zahira |
| Punjabi | pa-IN | Mehuli |
| Tamil | ta-IN | Asmita |
| Telugu | te-IN | Suhana |
| Hinglish | en-IN (TTS hi-en) | Poorvi |

Mappings follow [Gnani's voice catalog](https://docs.gnani.ai/api/TTS/available-voices). Run `python scripts/validate_languages.py --languages te` for a Telugu synthetic speech pilot, or omit `--languages` for all ten plus Hinglish. This calls real Gnani speech, local translation and the configured answer LLM. Inspect `sample_outputs/language_validation.json`: configured routing, a successful audio file and a correct grounded reply are separate checks. Human accents, noise and subjective quality require separate listening tests.

## How answers are produced

```text
Audio -> Gnani STT -> normalization + session/verification gate
                  -> query-first KB search (k=12) + public factual lookups
                  -> rules scoped to retrieved sections + deterministic arithmetic
                  -> LLM reads actual source text and generates answer JSON
                  -> actual-context provenance + source-contract checks
                  -> accepted generation, evidence-bound fallback, or abstention
                  -> Gnani TTS + text, sources, composition and timing trace
```

Search independently fuses raw and narrowly expanded lexical/multilingual dense queries. Full sections retain table context, and a second heading/prose representation helps long tables. Authority weights, historical filtering, explicit references, named-policy links and a bounded dependency budget supply governing context. Current policy outranks agent guide, help, FAQ and marketing; superseded electronics windows are allowed only for deliveries covered by the successor policy. Historical support logs never govern answers.

The LLM receives actual retrieved section text, metadata, deterministic facts and an optional checked rule summary. It generates answer-only JSON rather than reordering prewritten sentences or selecting its own citations. Code attaches the IDs and exact full sections actually supplied to the model for source-contract validation and provenance. Validation checks source membership, required coverage, supported numeric values and units, selected negative conditions, language, private identifiers and common invented completed actions. This records the context used; it does not establish per-claim semantic support. The checks are conservative heuristics and can miss misapplied conditions or facts.

If generation fails, a static policy answer is allowed only when every required section was actually retrieved and matches its reviewed content/metadata fingerprint in `src/rule_bindings.json`. Changed or missing policy evidence causes abstention rather than an unsupported static answer. Authentication, privacy, urgent escalation and tool-result wording use explicit guard-policy lookups and deterministic handling, separately labeled from answer retrieval.

Order information is disclosed only after the supplied lookup verifies a phone suffix or delivery pincode. One retry is allowed; changing orders clears verified context without clearing that order's failure count. Successful handover tickets are reused only for the same order and reason; success is stated only after `created=True`. Cancellation, refunds and replacements are not executed by nonexistent tools. See `DESIGN.md` for state and evidence boundaries.

## Reproduce evaluation

```powershell
.\.venv\Scripts\python.exe Capstone_Project_Dataset_FTTT_2026\validate_dataset.py
.\.venv\Scripts\python.exe eval_step1.py
.\.venv\Scripts\python.exe eval_step2.py --live
.\.venv\Scripts\python.exe eval_step3.py --live
.\.venv\Scripts\python.exe eval_adversarial.py
.\.venv\Scripts\python.exe eval_holdout.py --check-only
.\.venv\Scripts\python.exe eval_holdout.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe generate_voice_samples.py --reuse-inputs
.\.venv\Scripts\python.exe scripts\build_report.py
.\.venv\Scripts\python.exe package_submission.py
.\.venv\Scripts\python.exe scripts\verify_package.py
```

Step 1 calls the configured LLM without company documents or catalog access. Steps 2/3 default to deterministic evaluation unless `--live` is supplied. `eval_holdout.py` uses live generation by default; `--offline` evaluates evidence-bound rules, and `--check-only` validates the frozen fixture. Saved outputs retain failures. Decisions, required/forbidden facts, tool calls, used-source recall and search recall at the configured **k=12** are separate measurements. Mechanical matching is not organizer scoring or semantic certification; the practice set was used during development.

Inspect `composition`, `validation_error`, `retrieval_k`, `timings`, `llm` and source traces alongside any aggregate score. `grounded_llm`, checked fallback, guardrail and abstention responses must not be merged into a claim that every answer was freshly model-generated.

The output cache includes provider/model/settings and the complete generation payload, including source text and facts. Verified-order turns do not use a persistent LLM output cache. A **cold** run includes process/resource/model loading; **warm uncached** inference uses an already loaded model but performs a new request; a **cache hit** reuses stored model text. They are different latency measurements. Agent turn latency excludes resource creation before the turn, while voice end-to-end latency also includes STT/TTS. Consult benchmark JSON for the actual run conditions.

`generate_voice_samples.py` creates genuine Gnani TTS input clips when needed, then runs Gnani STT -> the same agent -> Gnani TTS. `--reuse-inputs` reuses those clips for a fresh round trip. Results in `sample_outputs/voice_validation.json` describe synthetic TTS-input checks. Human speech testing and subjective listening have not been completed. Unit-test fake clients exercise failure handling and are not live voice evidence. Provider WAV headers with unknown RIFF/data lengths are finalized without changing PCM; incomplete audio and invalid transcripts are rejected.

## Submission and sources

The brief requires a public repository, source/dependencies, batch command, report of at most four pages, user-recorded video of at most two minutes, sample outputs and `team_name_voiceops.zip`. `pranay_voiceops.zip` uses the account owner's name as the documented team-name assumption.

Packaging excludes `.env`, dataset copies, model weights, caches, virtual environments, source brief and private input audio. Dataset source: https://drive.google.com/file/d/1jeGjWgZJ4vdfmbB71kghovcCUYNeSHOY/view . Brief: https://d8it4huxumps7.cloudfront.net/uploads/submissions_case/6ad64c83eae85_voiceops_2026_capstone_brief.pdf . Setup obtains the dataset separately.

Speech uses the official Gnani REST APIs: https://docs.gnani.ai/api/STT/speech-to-text and https://docs.gnani.ai/api/TTS/tts-inference . The embedding model is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, Apache-2.0, revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, using its quantized ONNX export. See `THIRD_PARTY.md`.
