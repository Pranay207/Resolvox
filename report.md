# Resolvox - VoiceOps 2026 Capstone

Resolvox

VoiceOps 2026 Capstone | Technical Report

## What we built in the four required steps

Resolvox is a document-grounded voice support agent for ZentroMart. It handles policy questions, verified order follow-ups and confirmed human handover using the supplied synthetic dataset. The same support agent serves text, microphone and folder-based audio input.

| Required step | Implemented behavior |
| --- | --- |
| 1 - Answer with an LLM | An LLM API role/limits prompt and a prompt-only baseline without company documents or order tools. The shared assistant identifies itself as AI at the start of a conversation. |
| 2 - Ground in documents | Policy sections retain IDs, authority, status, version and effective date. A local vector index and lexical search retrieve relevant original chunks. The LLM receives those chunks and source-derived facts; missing support leads to clarification or uncertainty. |
| 3 - Hold a conversation | Session state preserves order context and follow-ups. The agent asks one missing-detail question, verifies access before private order disclosure, uses the supplied lookup_order and create_ticket tools, and confirms handover only from an actual tool result. |
| 4 - Give it a voice | Gnani STT transcribes the customer clip, the same Step 3 agent responds, and Gnani TTS produces the spoken reply. English, Hindi and Hinglish are the primary supported languages. |

## Grounding and control of actions

Retrieval combines lexical matching with multilingual MiniLM embeddings in an ONNX int8 index and hybrid fusion. Current policy takes precedence over lower-authority material. Source-bound calculations handle return dates, business-day refund windows, payment-method units and membership conditions.

Operational authentication and tool confirmations are deterministic. When current policy requires an RRN, the host can append its exact authenticated event field; that record-reading step is identified in the trace. Business explanations are generated from actual evidence, with no practice-answer lookup or authored policy-answer fallback. Proof/contact fields are redacted from model input and public traces. Full generation chunks, model flags and tool outcomes are recorded separately from the spoken text.

## Runtime

Implemented application profile: Groq openai/gpt-oss-20b with low reasoning effort, constrained JSON output and an additional source-claim review. Requests and repairs have bounded time budgets; no answer-provider fallback is enabled. Gnani is the only STT/TTS provider. Retrieval and the Streamlit interface run on the laptop. A separate local Ollama profile remains available.


---

Evaluation: Step 1 vs Step 2

| Required comparison | Recorded score | Basis |
| --- | --- | --- |
| Step 1 - Prompt-only LLM | 1/52 | Baseline artifact; 1 recorded error. No company documents or order tools. |
| Step 2 - Document-grounded answers | 52/52 | Stored actual practice-question predictions and targeted retests across recorded revisions. |

The recorded baseline used qwen3:1.7b. The Step 2 total combines actual preserved outputs and targeted retests across earlier model/source revisions. Fresh selected checks now use the explicit Groq application profile. These configuration differences confound a causal comparison; a frozen same-model ablation is a remaining evaluation improvement.

## Verified checks and recorded results

| Selected check | Recorded result | Scope |
| --- | --- | --- |
| Current offline regression checks | 408/408 verified | Return-date scope, source-support flags, repair context and packaging/report guards. Scripted clients; no live inference. |
| Selected conversation scenarios | 18/18 turns | Earlier mechanical conversation checks for QC status, overdue refunds, Plus/wallet and Hindi follow-ups. |
| Selected refund edge cases | 2/2 | Earlier coupon-context and authenticated recorded-completion checks. |
| Primary-language Gnani speech | 3/3 | Recorded English, Hindi and Hinglish synthetic-audio round trips using actual Gnani STT/TTS. |

Verified scope: the current offline regression checks shown above. Conversation, refund-edge and speech results retain their original model/source revisions; they are recorded evidence, not a fresh complete evaluation of the latest version. Full execution traces and source hashes distinguish the scopes.

These are exposed development regressions, not hidden organizer scores or a new full-suite run. The checks establish the stated selected behavior; they do not certify every unseen question or arbitrary semantic claim. Synthetic speech does not establish human accents, noisy-room performance or subjective listening quality.

Recorded selected generated-turn latency: 3.0-12.7 seconds across 8 saved turns. Host-only steps and speech service time are separate. These timings can include provider quota waits and are not a universal latency guarantee. Per-stage timings are preserved in JSON.


---

What went wrong and the fixes

| Observed problem | Correction and verification |
| --- | --- |
| Missing placement date selected a personal return window | A source-bound guard rejects selecting the ordinary window because a placement date is unknown, including Hindi Unicode-hyphen phrasing. General rules and conditional exceptions remain valid, and requested fee evidence is retained during repair. Common Hinglish clothing nouns now bind to the catalog category. |
| Missing QC data became an unsupported status claim | A bound pending-status view distinguishes an unrecorded QC/initiation date from a failed check. An absent RRN cannot be offered for bank tracing. The source initiation clock remains anchored to pickup, with QC pass as a prerequisite. The affected conversation was retested. |
| Wallet hours mixed with business days and an invented date | Known payment methods bind to the actual policy row. Wallet hour limits remain hours; other payment methods retain their business-day ranges and initiation anchor. Unsupported dated wallet estimates are rejected. |
| Compound refund questions lost requested coupon details | Coupon, partial-refund and amount requests retain the full original source/fact context through generation and repair. The live edge verifies both timing and the coupon deduction condition. |
| Valid conditional/record wording was rejected | Source-backed conditional timing is separated from claims of performed actions. Historical completion uses a compact authenticated record-reading view instead of a future policy estimate. The actual recorded date and action/authentication boundaries were checked. |
| Hindi damage guidance abstained on remedy prerequisites | A source-only first reporting view explains the actual reporting window and required photos without promising an unverified benefit. Selected English, Hindi and Hinglish clips used real Gnani STT/TTS with synthetic input and preserved source hashes. |

Interactive checks also exposed a credit-card phrase misread as a compensation-credit claim and a general paid-guarantee delivery request routed to order verification. The instrument scope and public-request routing were corrected. Targeted negative checks retain genuine credit conditions and private-record verification. Focused refund prompts now preserve the original question so requested membership facets remain visible.

## Safeguards retained

Identity verification precedes private order disclosure. A policy fee cannot establish a personal paid/refund amount. Missing records do not prove a prohibition or failed event. Claim/quality verification is distinct from identity verification. Source metadata and full original validators remain active for focused generation; a rejected draft gets one bounded repair before uncertainty.

## What we would improve next

Run a frozen same-model Step 1/Step 2 comparison and an independent unseen evaluation. Expand independent review of multi-part and qualitative claims: neither finite validators nor a model-based source review proves complete semantic entailment.

Measure hosted latency and throughput under deployment load and provider rate limits. Improve Hindi/Hinglish grammar and repetition, then test human speech with accents, background noise and unclear audio. Synthetic checks do not certify those conditions. Shared-customer deployment would additionally require authenticated private history and real store/ticket integrations.


---

Bonus work and reproducibility

## Additional engineering beyond the basic build

| Work | Practical benefit |
| --- | --- |
| Multilingual support | English, Hindi and Hinglish routing and spoken output share the same source-grounded agent. Only these primary routes are claimed here. |
| Local hybrid retrieval | Lexical/dense fusion, multilingual embeddings and ONNX int8 execution support document search on the laptop. Authority/effective-date metadata preserve policy precedence. |
| Source-bound safeguards | Checks cover recognized dates, units, amounts, prerequisites and unsupported action claims. Actual tool confirmations stay separate from generated explanations. |
| Inspectable evaluation and release | Saved input chunks, model flags, original execution epochs, audio hashes and machine-readable receipts make selected results reviewable. Retained outputs are labelled rather than presented as fresh inference. |
| Usable interface and batch processing | A responsive, single conversation supports Speak/Type, case details and supporting policies. Saved chats retain local text/audio/context; reopening does not restore private order verification. History databases stay outside Git and the archive. The batch runner saves text, JSON, real reply audio and source chunks. |

## Reproduce the agent

Code: https://github.com/Pranay207/Resolvox. Install the project dependencies, copy .env.example to the ignored .env, configure your own Gnani key in .env, provide the official extracted dataset and add your Groq key to the ignored .env.hosted for the configured application profile. The separate local profile uses Ollama qwen3:4b-instruct. Setup and environment details are in README.md.

Windows setup: powershell -ExecutionPolicy Bypass -File setup.ps1. Interactive profile: python scripts/run_app.py --hosted.

Hosted batch command: python run.py --hosted --audio_dir <in> --out_dir <out>. Omit --hosted only for the separately configured local Ollama profile. Each clip produces answer text, JSON, a real reply WAV and the source chunks supplied to generation; manifest.json records per-clip outcomes. Gnani remains the only speech service, including spoken recovery attempts.

## Evidence accompanying the report

Step comparison: sample_outputs/eval_step1.json and eval_step2_latest_cases.json. Selected conversations/refunds: targeted_live_validation.json. Return-date check records: return_date_validation.json. Recorded speech: targeted_voice_validation.json. Current offline checks: release_update_verification.json. Earlier automated receipts retain their original source and test hashes. All paths are under sample_outputs/; their referenced artifacts retain their actual scopes.

Only the supplied synthetic customer data is used. Credentials, private input speech, virtual environments, dataset copies and model weights are excluded from the submission archive. This report describes implemented behavior and recorded results; organizer marks are determined by the separate hidden-audio evaluation.
