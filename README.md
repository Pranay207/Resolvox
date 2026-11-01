<p align="center">
  <img src="assets/resolvox-logo.svg" alt="Resolvox voice support logo" width="96" height="96">
</p>

<h1 align="center">Resolvox</h1>

<p align="center">
  <strong>Multilingual voice and text support for ZentroMart</strong><br>
  VoiceOps 2026 Capstone · From Tokens to Transformers
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&amp;logo=python&amp;logoColor=white" alt="Python 3.11">
  <img src="https://img.shields.io/badge/Streamlit-Support_Console-FF4B4B?style=flat-square&amp;logo=streamlit&amp;logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/Ollama-Local_LLM-111827?style=flat-square&amp;logo=ollama&amp;logoColor=white" alt="Ollama local LLM">
  <img src="https://img.shields.io/badge/Gnani-STT_%2B_TTS-16866C?style=flat-square" alt="Gnani STT and TTS">
  <img src="https://img.shields.io/badge/ONNX_Runtime-Local_Retrieval-005CED?style=flat-square&amp;logo=onnx&amp;logoColor=white" alt="ONNX Runtime">
</p>

## [Engineering Deep Dive →](ENGINEERING_DEEP_DIVE.md)

**Inside Resolvox: from voice to verified answers.**<br>
Design decisions, challenges and results behind the agent.

Resolvox answers customer questions from ZentroMart’s documents, looks up verified orders and creates human-support tickets when needed. Voice and text share the same conversation, retrieval and tools.

**Primary languages:** English, Hindi and Hinglish.

Capstone for **From Tokens to Transformers**, organized by the Consulting & Analytics Club, IIT Guwahati × Gnani.ai.

[Report](report.pdf) · [Watch Demo (1:45)](#demo-video) · [Quick Start](#quick-start) · [Batch Command](#organizer-batch-command) · [Architecture](#architecture) · [Evaluation](#evaluation) · [Documentation](#documentation)

## Demo Video

<video controls preload="metadata" src="https://raw.githubusercontent.com/Pranay207/Resolvox/09cce65f266ae2ccd40a8d49819fc5a0b6b668b3/Resolovox%20Demo.mp4" aria-label="Resolovox Demo — 1 minute 45 seconds" width="960"></video>

[Download Resolovox Demo (MP4)](<Resolovox Demo.mp4>) · **1 minute 45 seconds**

A policy-grounded answer, a follow-up and an uncertainty response in one voice conversation. The edited walkthrough uses synthetic customer speech and narration, actual application replies, and clearly disclosed shortened processing waits.

## Application Preview

<p align="center">
  <img src="assets/resolvox-desktop.jpg" alt="Resolvox desktop workspace with voice and text input, compact case details and visible support controls" width="1100">
</p>
<p align="center"><em>Desktop workspace</em></p>

<p align="center">
  <img src="assets/resolvox-mobile.jpg" alt="Resolvox mobile layout with Speak and Type controls, microphone recording and audio upload" width="300">
</p>
<p align="center"><em>Mobile layout</em></p>

## What Resolvox Does

| Capability | How it works |
| --- | --- |
| Policy answers with sources | Searches policy sections, supplies actual text to the answer model and saves the complete generation context. |
| Context across turns | Handles follow-up questions, missing details and clarification within one conversation. |
| Verified order support | Checks a phone suffix or delivery pincode before revealing private order information. |
| Confirmed handover | Creates a ticket with the supplied tool and reports success only after confirmation. |
| Voice and text | Uses one shared agent for typed questions and Gnani speech input/output. |
| Uncertainty handling | Attempts one bounded repair of invalid model output, then abstains if a supported answer is unavailable. |

### Using the Application

Choose **Speak** to record a message or **Type** to write a question. **Upload an audio clip** accepts an existing recording. Both modes share the same conversation and audio playback.

**Your case** shows verified order details and confirmed ticket references. **Your next step** provides clarification or handover guidance. The layout adapts to phone, tablet and desktop screens.

**New conversation** clears the history and verification. **Retry reply audio** retries speech without repeating the agent action. Under **Advanced options**, AI policy answers are enabled by default and extra language previews are disabled.

## Quick Start

### Prerequisites

- **Python 3.11**, the tested Python version, and Git.
- **Ollama** installed for the default local LLM, or a compatible hosted LLM endpoint.
- Your own **Gnani API key** for speech, available from the [Gnani voice dashboard](https://app.gnani.ai/voice).
- Internet access for the initial dependency, dataset and model downloads, and for Gnani speech calls.

The tested environment is Windows with Python 3.11. Setup downloads and validates the official synthetic dataset and downloads the pinned embedding model. Regional translation weights are optional.

**Connectivity:** local retrieval and Ollama text generation can run offline after setup. Gnani speech recognition and synthesis require internet access; the complete voice application is not fully offline.

### 1. Clone and Install

```sh
git clone https://github.com/Pranay207/Resolvox.git
cd Resolvox
```

**Windows PowerShell:**

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

The Windows setup creates `.venv` and copies `.env.example` to `.env` if needed.

**macOS / Linux:**

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python setup.py --models
cp .env.example .env
```

### 2. Configure Speech and the LLM

Edit your local `.env` before launching the app:

```dotenv
GNANI_API_KEY=your_gnani_api_key
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen3:4b-instruct
LLM_TIMEOUT=600
RAG_LLM_TIMEOUT=600
COMPOSE_WITH_LLM=true
```

Keep the remaining defaults from [.env.example](.env.example), including `REFERENCE_DATE=2026-10-20`. Credentials belong only in the ignored `.env`; use synthetic or consented audio.

Start Ollama in a separate terminal if it is not already running:

```sh
ollama serve
```

Then download the model from another terminal:

```sh
ollama pull qwen3:4b-instruct
```

Use Ollama’s default port **11434**, matching `.env.example`. Keep the server port and `LLM_BASE_URL` consistent.

<details>
<summary>Use a compatible hosted LLM instead</summary>

Set `LLM_PROVIDER=compatible`, `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` in `.env`. Optional `LLM_FALLBACK_*` settings configure a second LLM endpoint. Gnani remains the only speech provider.

</details>

### 3. Launch the Support Console

**Windows PowerShell:**

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

**macOS / Linux:**

```sh
.venv/bin/python -m streamlit run app.py
```

Open [localhost:8501](http://localhost:8501). Choose a language and **Speak**, then record or upload a clip of up to **60 seconds**. Uploads are limited to **20 MB**. Choose **Type** to continue the same conversation by text.

## Organizer Batch Command

With the virtual environment activated, the required command is:

```sh
python run.py --audio_dir <in> --out_dir <out>
```

For example, on Windows:

```powershell
.\.venv\Scripts\python.exe run.py --audio_dir .\input_audio --out_dir .\sample_outputs\batch
```

Each clip produces answer text, JSON, full source chunks and an actual Gnani reply WAV when speech succeeds. `manifest.json` records per-file outcomes and failures. Speech failures are recorded without substitute audio.

<details>
<summary>Audio formats, sessions and exit codes</summary>

- Formats: WAV, MP3, OGG, FLAC, AAC and M4A; Gnani REST clips are limited to 60 seconds, and WAV duration is checked locally.
- Language: `--language hi-IN` selects Hindi; `en-IN` accepts English/Hinglish. Additional routes are listed under [Language support](#language-support).
- Sessions: files are independent by default. In auto mode, `call_id__001.wav` and `call_id__002.wav` share context. Use `--session_mode sequential` for one folder-wide session, or `sessions.json` for explicit mapping.
- Exit codes: `0` means all inputs succeeded, `1` means failed or no inputs, and `2` means usage errors.
- `--offline-rules` disables LLM generation and displays document excerpts for diagnosis, alongside operational guards. It does not enable offline speech/regional translation.
- Raw input audio is not copied to outputs. Verification proofs are redacted from transcripts, tool arguments and model context.

</details>

## Architecture

```mermaid
flowchart TD
    Audio["Recorded or uploaded audio"] --> STT["Gnani STT"]
    STT --> Agent["Shared agent: context, clarification and verification"]
    Text["Typed question"] --> Agent
    Agent <--> Tools["Supplied order lookup and ticket tools"]
    Agent --> Search["Hybrid policy retrieval"]
    Search --> Answer["Source-text LLM generation + verified facts"]
    Answer --> Check["Context, quantity and privacy checks; one repair"]
    Check --> Reply["Document answer or abstention + saved context"]
    Reply --> TTS["Gnani TTS and spoken playback"]
```

| Component | Implementation |
| --- | --- |
| Interface | Responsive Streamlit workspace with Speak/Type input, one conversation and verified case details |
| Answer model | Local Ollama `qwen3:4b-instruct` |
| Retrieval | Lexical search + multilingual MiniLM embeddings using quantized ONNX |
| Speech | Gnani STT and TTS only |
| State and tools | Shared agent session with supplied dataset lookup/ticket tools |
| Optional regional translation | Local NLLB-200 distilled 600M ONNX model |

See [DESIGN.md](DESIGN.md) for the state model, retrieval strategy and evidence boundaries, and [THIRD_PARTY.md](THIRD_PARTY.md) for pinned models and licenses.

## Evaluation

Recorded local development results:

| Check | Recorded result | Evidence |
| --- | --- | --- |
| Step 1: prompt-only baseline | **1/52**, including one recorded error | [Baseline outputs](sample_outputs/eval_step1.json) |
| Step 2: grounded practice questions | **52/52 accumulated checks** across recorded revisions | [Question records](sample_outputs/eval_step2_latest_cases.json) |
| Selected conversation scenarios | **18/18 turns**, plus **2/2 refund edge cases** | [Targeted evidence](sample_outputs/targeted_live_validation.json) |
| Refund and reporting regressions | **371 passed** | [Test receipt](sample_outputs/refund_scope_verification_20261031.json) |
| Packaging and report regressions | **148 passed** | [Test receipt](sample_outputs/targeted_release_tests_20261031.json) |
| English, Hindi and Hinglish speech | **3/3 selected synthetic round trips**; Hindi retested separately | [Speech evidence](sample_outputs/targeted_voice_validation.json) |
| Official dataset validation | **Passed**: 9 CSVs and 21 knowledge-base documents | [Validator output](sample_outputs/engineering_artifacts/20261031T060814584432Z_92c93db5/dataset_validation.log) |

**Scope:** the 52/52 total combines saved outputs and targeted retests across revisions, rather than a fresh complete run. The baseline used `qwen3:1.7b`, while the selected model is `qwen3:4b-instruct`; this is not a controlled same-model comparison.

These are local development results, not organizer scores. Synthetic speech checks do not establish real-speaker or noise performance. See [VERIFICATION.md](VERIFICATION.md) for provenance, latency, recorded runtime settings and limitations.

<details>
<summary>Verification commands</summary>

Activate the virtual environment before running these commands:

```sh
python Capstone_Project_Dataset_FTTT_2026/validate_dataset.py
python -m pytest -q
```

Selected live checks require the configured local LLM and, for speech, Gnani access:

```sh
python scripts/validate_targeted_live.py
python scripts/validate_targeted_voice.py
```

The original Step 1, Step 2 and Step 3 evaluation drivers remain available as `eval_step1.py`, `eval_step2.py` and `eval_step3.py`. Preserve previous outputs when changing the model or runtime configuration.

</details>

## Language Support

**English, Hindi and Hinglish are the primary scope.** Select a language before recording. Additional regional languages are an experimental preview, disabled by default and not validated for the current revision.

Setup instructions, translation details and the voice-route table are in [Optional regional languages](DESIGN.md#optional-regional-languages).

## Documentation

| Resource | Purpose |
| --- | --- |
| [report.pdf](report.pdf) | Four-page capstone technical report |
| [Engineering Deep Dive](ENGINEERING_DEEP_DIVE.md) | Design decisions, failure analysis and verified outcomes |
| [DESIGN.md](DESIGN.md) | Architecture, retrieval, session state and privacy boundaries |
| [VERIFICATION.md](VERIFICATION.md) | Detailed measurements, historical failures and limitations |
| [THIRD_PARTY.md](THIRD_PARTY.md) | Model revisions, dependencies and licensing |
| [.env.example](.env.example) | Configuration template without credentials |
| [sample_outputs/](sample_outputs/) | Recorded answer, source, tool and speech evidence |

### Data and API References

- [Official synthetic dataset](https://drive.google.com/file/d/1jeGjWgZJ4vdfmbB71kghovcCUYNeSHOY/view) — downloaded separately by setup.
- [VoiceOps 2026 capstone brief](https://d8it4huxumps7.cloudfront.net/uploads/submissions_case/6ad64c83eae85_voiceops_2026_capstone_brief.pdf).
- [Gnani speech-to-text API](https://docs.gnani.ai/api/STT/speech-to-text) and [text-to-speech API](https://docs.gnani.ai/api/TTS/tts-inference).
- [Multilingual MiniLM embedding model](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) — pinned quantized ONNX export; revision and Apache-2.0 attribution in [THIRD_PARTY.md](THIRD_PARTY.md).

## License

Resolvox’s original code is licensed under the [MIT License](LICENSE). Third-party software, model weights, datasets and services retain their own terms; see [THIRD_PARTY.md](THIRD_PARTY.md).

---

<p align="center">Built by <strong>R LAKSHMI PRANAY TEJ</strong></p>
