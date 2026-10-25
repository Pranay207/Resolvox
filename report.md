# Resolvox - Multilingual AI Voice Support

VoiceOps 2026

Resolvox

Multilingual AI Voice Support for ZentroMart

Technical report | Pranay207 | C&A Club, IIT Guwahati x Gnani.ai

One multilingual support agent combines retrieval-first source-text generation, deterministic verification and arithmetic, supplied order/ticket tools, and Gnani speech. Recorded results distinguish generated answers, checked fallbacks, guardrails and abstentions. No organizer score or placing is claimed.

Four cumulative build steps

| Stage | Implementation |
| 1 - Baseline | Actual configured LLM; role/limits and AI disclosure; no company documents or order access. |
| 2 - RAG | Search first; scope policy rules to actual results; generate from supplied section text and checked facts; record source provenance. |
| 3 - Conversation | Session/order state, proof-gated lookup, calendar/coupon arithmetic, explicit guard policies and confirmed-ticket-only handover. |
| 4 - Voice | Official Gnani STT/TTS, spoken-number normalization, redaction, per-file failure isolation and JSON/text/WAV/source outputs. |

Evidence snapshot at report generation

Actual prompt-only baseline: 1/52. LLM-enabled grounded questions: 52/52 planned; 52 evaluated; complete=True; errors 0. LLM-enabled conversation turns: 96/96 planned; 96 evaluated; complete=True; errors 0. Offline checks remain separate: 52/52 questions, 96/96 conversation turns; development adversarial/stateful checks 77/77. Mechanical checks on development practice do not establish unseen semantic quality.

Grounded run model metadata: configured ollama/qwen3:1.7b; recorded calls ollama:qwen3:1.7b (40).

Engineering pytest result: 404/404 passed; exit code 0. Required report limit: four pages. The user records the final demo within 120 seconds after validation.


---

Architecture and evidence boundaries

Retrieval before policy planning

KB sections preserve IDs, file, authority, status, version and effective date. Raw-query BM25 and multilingual MiniLM channels are fused separately from narrow glossary expansion. Complete tables and concise heading/prose embeddings provide complementary views; Hindi tokenization retains combining marks. Intent is a weak hint, not a mapping from practice questions to evidence.

The agent searches at k=12 before planning. Explicit references, named policy concepts and bounded calendar/precedence/exception dependencies add governing context. Planning sees only retrieved sections, with public catalog/pincode facts supplied independently. A planner cannot append preferred citations from the full KB. Historical filtering excludes obsolete text unless the current successor authorizes that case.

Actual source-text generation; explicit provenance

The LLM receives actual section text, authority/version metadata, deterministic facts and an optional checked rule summary. It writes new reply wording. The current answer-only output contract avoids asking small models to reproduce section identifiers or select citation spans. Code records the IDs and exact full sections actually supplied as context provenance; this does not prove that every generated claim follows from those sections.

Source-contract validation checks source membership, required coverage, numeric values and units, selected omitted constraints, language, private identifiers and common invented completed actions. These are finite heuristics, not general semantic entailment. Broad section support can contain multiple payment rows or exceptions; a model can still misapply them. Citation provenance and factual correctness are reported separately.

Reviewed fallback and guard paths

Offline, invalid-output and timeout fallback uses a static policy answer only when every governing section was actually retrieved and matches its reviewed content/metadata SHA-256 in rule_bindings.json. Missing or changed evidence causes abstention. Policy edits require reviewing rules and bindings; hashes do not automatically update policy logic. Authentication, privacy, urgent escalation and tool-result wording use explicit guard-policy lookups, labeled separately from answer search.

Policy, time and private state

Current policy outranks agent guide, help, FAQ and marketing; historical support logs never govern. The frozen date is 20 October 2026. Business days are Monday-Saturday excluding supplied holidays. Return deadlines use delivery + N calendar days: the supplied wording leaves inclusive counting ambiguous, so the consistent day-zero convention is documented. Proof is discarded after the supplied lookup; order switches clear verified context while retaining per-order failure counts. Tickets are deduplicated by order and reason, and success requires created=True.


---

Evaluation and observed limitations

| Recorded evaluation | Passes | Interpretation |
| Prompt-only questions | 1/52 | 1.9%; errors 1 |
| Grounded questions (LLM-enabled) | 52/52 | 52/52 evaluated; complete=True; compose=True |
| Conversation turns (LLM-enabled) | 96/96 | 96/96 evaluated; complete=True; compose=True |
| Offline questions / conversations | 52/52 / 96/96 | compose=False; separate rules/guard checks |
| Development adversarial/stateful | 77/77 | 100.0%; used for development |
| First holdout (offline) | 23/91 | 25.3% |
| Post-fix holdout (offline) | 91/91 | 100.0% |
| Used-source recall (selected runs) | Single / conversation | 86.7% / 97.3% |

The scorer checks decisions, required/forbidden facts and expected tools; independent holdout checks also inspect language, evidence, tool arguments and privacy. Mechanical regex/fact checks can miss semantic errors or reject valid paraphrases. Conversation search includes many guard/verification turns and is not directly comparable with standalone query recall.

LLM-enabled question composition: generated 16; checked fallbacks 25; guards 4; rules 2; abstentions 5. LLM-enabled conversation composition: generated 8; checked fallbacks 9; guards 77; rules 2; abstentions 0. These include cached generation, reviewed fallbacks and guards; a passing live run is not all fresh generation. Historical 32/52 partial subset remains preserved unchanged. Earlier complete live runs are separate historical evidence.

Frozen holdout and honest reruns

The independent fixture contains 64 single questions and 10 scenarios/27 turns: 91 judged responses. Full rubric SHA-256: 5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7. It is evaluation data, never runtime knowledge. Preserve the first pass before observing failures; later runs after fixes are regressions on an exposed set, not a new independent holdout.

The current exposed-set offline regression has 0 remaining evaluated failures. Old predictions scored 49/91 originally and 51/91 under scorer v2 unchanged; 2 points are scoring normalization, not runtime improvement. Runtime fixes then reached 91/91 under that same scorer. Zero evaluated failures would not establish unseen semantic correctness or live-generation performance. First-pass artifact: eval_holdout_first_pass.json; current: eval_holdout.json. Scorer provenance is retained in eval_holdout_scorer_v2_same_predictions.json.

Failures that shaped the implementation

Early sentence ordering concealed the distinction between retrieval and rules. The revised path scopes planning to actual search results. Product variants, historical return windows, policy precedence, order switching and ticket reuse require independent checks. Development model experiments produced correct-looking prose with missing/invalid citations or unsupported constraints; their factual pass and accepted-generation counts are kept separate. The answer-only contract now attaches actual context provenance in code. New wording, multilingual conditions and multi-item decisions still require semantic review.

Baseline model metadata: configured ollama/qwen3:1.7b; recorded calls ollama:qwen3:1.7b (51). Compare run configurations before attributing differences solely to retrieval.


---

Latency, voice and reproducibility

Model and latency evidence

Recorded LLM-enabled question timing: uncached_llm_attempt: n=29, p50 10.88s, p95 19.33s; cache_hit: n=12, p50 0.06s, p95 0.14s; no_model_call: n=11, p50 0.05s, p95 0.11s. Conversation timings are retained in eval_step3_live_current.json; offline measurements remain separate. All outliers are retained; request timeouts do not establish a hard end-to-end bound.

| Recorded model experiment | Accepted generation | Mean case wall | Warm-up wall |
| selected-model check: qwen3:1.7b (uncached requests) | 10/29 | 10.94 s | not recorded |
| selected-model check: qwen3:1.7b (output cache) | 6/12 | 0.08 s | not recorded |

Benchmarks use a small development sample and do not estimate unseen quality. Warm-up wall includes its request and may include loading; it is not automatically a controlled cold start. Warm uncached inference performs a new request, whereas an output-cache hit reuses stored text. Agent turn latency excludes resource creation before respond; inspect cache status and provider load/prompt/decode timings. Full prompt/source/fact/model settings enter cache keys; private-order calls bypass persistent output caching.

Optional regional-language preview

Primary support is English, Hindi and Hinglish. Additional regional choices are an optional preview using separate local translation with masked identifiers and round-trip checks. Optional regional-language preview remains experimental. The saved synthetic language run passed 5/11 voice cases; 6 failed and 0 are pending. This does not establish all ten languages as working; each language has only one refund-question check, and native intelligibility was not independently reviewed. Failures and prior attempts remain in language_validation.json; translation weights are excluded from the archive.

Real Gnani speech; separate time measures

Status: tested. Audio batches: 6/6 succeeded; semantic/privacy checks passed: 6, failed: 0. Results describe the saved run, not a human listening study.

Separate current speech checks: Hindi UPI 1/1; silent-clip recovery 1/1. Recovery required a genuine Gnani spoken clarification, first-reply AI disclosure, no hallucinated speech, and no actions or tickets. These are synthetic-input checks, not human listening evidence.

Saved voice processing wall range: 1.03-13.44 s; generated reply audio duration: 4.16-17.28 s. Processing time and playback length are different quantities. Gnani TTS input clips are synthetic, not human recordings; accent/noise robustness and subjective listening remain unverified.

Gnani is the only STT/TTS provider. Bounded retries rewind inputs; invalid transcripts, truncated PCM and empty speech are rejected. Stream-style WAV sizes are finalized without changing samples. Batch results retain redacted transcripts, sources, tool traces, timing and per-file errors. An offline-rules run disables answer generation but still requires Gnani speech.

Reproduce and release

Repository: https://github.com/Pranay207/Resolvox. Setup: powershell -File setup.ps1. Batch: python run.py --audio_dir <in> --out_dir <out>. Current live practice: python scripts/resume_live_practice.py --step 2, then --step 3; separate baseline/adversarial/holdout scripts retain earlier evidence. Run python -m pytest -q. Reproduce voice with generate_voice_samples.py --reuse-inputs. Generated JSON retains the measured configuration and failures.

After final checks, regenerate the report, visually inspect all pages, record demo.mp4 within 120 seconds, then build/verify the release ZIP. Packaging excludes .env, dataset copies, model weights, caches, environments and private audio. Educational proof checking is not production authentication. No rank, prize or real customer outcome is promised.

Sources: capstone brief; supplied dataset README, dictionary, KB and tools; official Gnani STT/TTS docs; pinned multilingual MiniLM model card; sample_outputs JSON named above. Report measurements are loaded when this file is generated.
