# ZentroMart VoiceOps 2026

VoiceOps 2026

ZentroMart: support that listens

Technical report | Pranay207 | C&A Club, IIT Guwahati x Gnani.ai

A multilingual support agent grounded in the supplied synthetic retailer policies and order tools. Its priority is defensible answers and safe handovers, rather than unconstrained generation. A top-20 ranking is an aspiration, not an evaluated result.

One support agent, four build steps

| Stage | What was built |
| 1 - Baseline | Actual Ollama API call; role/limits; AI disclosure; no documents or order access. |
| 2 - Grounding | Section-ID KB index; BM25 + multilingual MiniLM dense search; authority-aware ranking; traceable policy plans and abstention. |
| 3 - Conversation | Session state, proof-gated supplied tools, date/eligibility rules, refusals and successful-ticket-only handover. |
| 4 - Voice | Official Gnani REST STT/TTS wrapper, spoken-number handling and fault-isolated audio-folder CLI. Six synthetic voice round trips and semantic checks verified. |

Observed local results

Baseline: 5/52 mechanical checks. Grounded: 52/52. Conversations: 96/96 turns. Original adversarial/stateful checks: 77/77. These are transparent local regression checks, not organizer scores or proof of hidden-test accuracy.

Release status: text, local LLM composition and six real Gnani speech round trips verified. Synthetic audio does not establish human-speech robustness. The user-recorded demo remains outstanding.


---

Design choices and boundaries

Grounding is a data contract

All 21 knowledge documents were read, preserving section IDs, version, status and effective dates. The public catalog and calendar are loaded separately. Customer and order tables are accessed only through the unchanged organizer tool module. Practice questions, expected answers and historical support logs never enter the runtime index.

Authority is current policy > agent guide > help > FAQ > marketing. KB-00 supplies the date and precedence rules. Superseded text cannot govern unless its successor explicitly preserves a historical case: RET-3 keeps the 10-day electronics window only for deliveries before 1 August 2026; otherwise 7 days applies. A marketplace badge cannot override MKS-3, which excludes seller items from Assured coverage.

Hybrid retrieval without a heavyweight training stack

BM25 uses stop-word removal and light plural normalization. Dense retrieval uses the official 118 MB int8 ONNX export of multilingual MiniLM (384 dimensions), pinned to an immutable model revision. Intent vocabulary expands Hinglish and colloquial queries into policy terminology. Reciprocal-rank fusion combines both searches, with a modest authority prior. Model and section embeddings load once and are cached on disk.

Search candidates and governing evidence are distinct. Policy rules retrieve specific source sections for decisions, while broad search candidates are logged independently. Explicit rule coverage helps structured policy cases but limits open-ended generalization; high answer-check pass rates must not hide weak search or intent coverage.

Deterministic decisions; constrained LLM composition

Code computes date windows, business-day deadlines, coupon arithmetic, proof limits and eligibility. Policy-derived statements are written in English, Hindi and Hinglish. The LLM arranges a verified sentence bank; its output must contain every sentence index exactly once. Invalid plans fall back to the original verified wording. This deliberately limits language freedom and prevents invented policy facts; it is not an unrestricted answer-generation model.

Dates and a documented ambiguity

The reference date is 20 October 2026. Refund/logistics days are Monday-Saturday excluding the four supplied holidays; initiation day is day zero. RET-2 says returns start on delivery, but does not spell out inclusive arithmetic. The supplied expected deadlines consistently use delivery + N calendar days. That operational convention is used globally and tested at category, sale-period and historical-policy boundaries; no question-specific date exceptions are coded.

Schema: 300 customers -> 1,000 orders -> 1,783 order lines -> 70 products. Delivery pincodes reference 36 serviceability rows; four holidays define the business calendar. Identifiers remain strings. Blank completion dates are not interpreted as completed refunds.


---

Evaluation and failure analysis

| Generated evaluation | Passes | Rate / interpretation |
| Prompt-only, same 52 questions | 5/52 | 9.6%; 3 invalid-output errors counted |
| Grounded single questions | 52/52 | 100.0% mechanical fact/decision checks |
| Conversation turns | 96/96 | 100.0%; 23 sequential sessions |
| Original adversarial + stateful | 77/77 | 65 authored questions + 12 stateful cases |
| Independent KB search recall@8 | Single questions | 75.3% |
| Used-source evidence recall | Single / conversation | 97.8% / 100.0% |

The scorer checks acceptable decisions, required factual alternatives, forbidden claims and expected tool names. Dates are canonicalized across English/Hindi forms. It does not judge every semantic entailment, language nuance or action argument, so a perfect local pass rate is not equivalent to a perfect support agent.

Single-turn LLM composition counts: {'llm_sentence_composition': 33, 'deterministic': 11, 'deterministic_invalid_model_plan': 8}. Conversation composition counts: {'deterministic': 79, 'llm_sentence_composition': 16, 'deterministic_invalid_model_plan': 1}. Deterministic gates and abstentions need no LLM call. Saved baseline results are real API outputs; identical prompts may subsequently use cache. Invalid baseline JSON remains an error, not an edited answer.

What broke, and what changed

The baseline predicted Wallet refunds take 3-5 business days. REF-2 instead says instant, within 2 hours. The grounded path resolves payment methods before choosing a timeline and cites the policy rather than the generic FAQ.

Product aliases initially missed a swimsuit because of the hyphenated product name and omitted colour. Matching now distinguishes exact variants from shared-category variants, using category evidence without inventing a specific variant. Initial return dates used inclusive counting and failed two expected dates; the globally applied day-zero convention above corrected that ambiguity.

Broad hybrid search alone initially recalled 44.2% of single-question gold KB sections at eight candidates. Removing filler words and expanding intent vocabulary raised it to the figure reported above. Used-source recall is higher because deterministic policy routing separately retrieves governing sections. Conversation search recall includes many non-search authentication/greeting turns, so it is not directly comparable to standalone search quality.

Live Gnani testing exposed stream-style WAV headers with unknown 0xffffffff lengths: short clips appeared longer than the STT limit. Header finalization now preserves identical PCM samples while recording actual lengths. Invalid transcripts and incomplete PCM frames are rejected; extra privacy tests cover spoken phone-ending phrases without masking ordinary product questions.

Original tests also exposed routing bugs for unused beauty items and delivery-address changes. Added corpus-wide coverage catches these alongside proof lockout, order switching, safety, fraud, unsupported services, historical returns, festive boundaries and payment calendars. All raw generated results remain in sample_outputs/.


---

Reproducibility, voice and next steps

Privacy and tool correctness

The initial lookup never discloses order status or existence. Caller proof is sent only to the unchanged supplied lookup function, then discarded. A maximum of two attempts is tracked per order per session, and changing orders clears verified order context without clearing its failed-attempt counter. Sanitized traces hide proof, phone, email, pincode and internal notes; the LLM never sees verification values.

Handover summaries record the issue, intent, order, checks and reason. Success wording requires created=True. No cancellation, compensation or replacement execution is fabricated: the provided tools cannot perform those actions. Their identity mechanism is an educational synthetic simulation, not secure real-world authentication.

Voice implementation and honest validation status

Gnani is the only STT/TTS provider. The REST adapter uses /stt/v3 and /api/v1/tts/inference, X-API-Key-ID authentication, explicit timbre-v2.5 and matching English/Hindi/Hinglish voices. WAV duration is checked against the 60-second REST limit. Multipart streams rewind on bounded 403/429/5xx retries, and returned audio must be a valid nonempty WAV.

The batch runner isolates malformed clips, records errors in manifest.json, and attempts a real Gnani spoken recovery. It never creates fake speech. Successful clips save redacted transcript/decision/tool JSON, text, source chunks and reply WAV. Session-named filenames preserve multi-turn calls; unrelated files remain independent.

Live speech status: tested. Six genuine Gnani TTS inputs passed STT, agent and spoken-reply checks: English UPI, Hindi damage, Hinglish net banking, spoken order ID, first wrong-proof clarification and second wrong-proof refusal. All six input-understanding, semantic, privacy and nonempty-speech checks passed. Live LLM composition is enabled for answer turns; verification gates remain deterministic.

The inputs are synthetic TTS, not human recordings. Human accent/noise robustness and subjective pronunciation are still unverified. The measured pipeline uses only Gnani speech services; 41 automated engineering tests also pass. generate_voice_samples.py reproduces the live checks; --reuse-inputs reuses the same genuine input clips without inventing speech.

Run and release

Repository: https://github.com/Pranay207/ESD. One-command Windows setup: powershell -File setup.ps1. Organizer CLI: python run.py --audio_dir <in> --out_dir <out>. Run eval_step1.py, eval_step2.py --live, eval_step3.py --live, eval_adversarial.py, and python -m pytest -q from the clean .venv. requirements-lock.txt captures the tested Windows dependency set; setup.py pins the model revision.

Before submitting: keep GNANI_API_KEY only in the ignored local .env, record demo.mp4 within 120 seconds using DEMO_SCRIPT.md, and regenerate the package. Rerun generate_voice_samples.py after speech-related changes. package_submission.py excludes the dataset, secrets, environments and model caches and marks remaining blockers. The brief allows at most four report pages and two video minutes.

Limitations and useful next work

Intent routing and sentence templates may miss unseen phrasing or nuanced multi-item cases. Numeric/fact checks do not replace semantic review. Improve unstructured-query fallback and native-language review; evaluate unseen audio, packet failures and latency; strengthen identity verification only for a separately scoped production system. No rank, prize or real customer outcome is claimed.

Sources: official 14-page capstone brief; supplied dataset README, dictionary, KB and tools; official Gnani STT/TTS API docs; official multilingual MiniLM model card. Dataset and model are downloaded separately and are not redistributed in the submission.
