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

Baseline 1/52; current offline grounded questions 52/52; offline conversation turns 96/96; development adversarial/stateful checks 77/77. These are mechanical local checks. The practice and adversarial sets were used during development; answer quality is not established by retrieval recall or a successful fallback alone.

Grounded run model metadata: configured ollama/qwen3:1.7b.

Engineering pytest result: 229/229 passed; exit code 0. Required report limit: four pages. The user records the final demo within 120 seconds after validation.


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
| Grounded practice (offline) | 52/52 | 100.0%; compose=False; search 93.5% at k=12 |
| Conversation practice (offline) | 96/96 | 100.0%; compose=False; answer/auth turns |
| Development adversarial/stateful | 77/77 | 100.0%; used for development |
| Post-fix live subset | 32/52 planned | 32 evaluated; incomplete live rerun |
| First holdout (offline) | 23/91 | 25.3% |
| Post-fix holdout (offline) | 91/91 | 100.0% |
| Used-source evidence recall | Single / conversation | 86.7% / 97.3% |

The scorer checks decisions, required/forbidden facts and expected tools; independent holdout checks also inspect language, evidence, tool arguments and privacy. Mechanical regex/fact checks can miss semantic errors or reject valid paraphrases. Conversation search includes many guard/verification turns and is not directly comparable with standalone query recall.

Complete current practice runs are offline compose=False; earlier complete live results predate the fixes. Current live evidence is the separately recorded incomplete subset. Single-question composition: abstained_missing_evidence: 5; deterministic_guardrail: 4; evidence_validated_rules: 43. Conversation composition: deterministic_guardrail: 77; evidence_validated_rules: 19.

Frozen holdout and honest reruns

The independent fixture contains 64 single questions and 10 scenarios/27 turns: 91 judged responses. Full rubric SHA-256: 5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7. It is evaluation data, never runtime knowledge. Preserve the first pass before observing failures; later runs after fixes are regressions on an exposed set, not a new independent holdout.

The current exposed-set offline regression has 0 remaining evaluated failures. Old predictions scored 49/91 originally and 51/91 under scorer v2 unchanged; 2 points are scoring normalization, not runtime improvement. Runtime fixes then reached 91/91 under that same scorer. Zero evaluated failures would not establish unseen semantic correctness or live-generation performance. First-pass artifact: eval_holdout_first_pass.json; current: eval_holdout.json. Scorer provenance is retained in eval_holdout_scorer_v2_same_predictions.json.

Failures that shaped the implementation

Early sentence ordering concealed the distinction between retrieval and rules. The revised path scopes planning to actual search results. Product variants, historical return windows, policy precedence, order switching and ticket reuse require independent checks. Development model experiments produced correct-looking prose with missing/invalid citations or unsupported constraints; their factual pass and accepted-generation counts are kept separate. The answer-only contract now attaches actual context provenance in code. New wording, multilingual conditions and multi-item decisions still require semantic review.

Baseline model metadata: configured ollama/qwen3:1.7b; recorded calls ollama:qwen3:1.7b (51). Compare run configurations before attributing differences solely to retrieval.


---

Latency, voice and reproducibility

Model and latency evidence

Current live subset turn timing: uncached_llm_attempt: n=23, p50 20.26s, p95 24.12s; cache_hit: n=2, p50 0.09s, p95 0.09s; no_model_call: n=7, p50 0.10s, p95 0.13s. Offline timing is recorded separately. All outliers are retained; configured request timeouts do not establish a hard end-to-end latency bound.

| Recorded model experiment | Accepted generation | Mean case wall | Warm-up wall |
| selected-model check: qwen3:1.7b (uncached requests) | 5/23 | 74.83 s | not recorded |
| selected-model check: qwen3:1.7b (output cache) | 1/2 | 0.18 s | not recorded |

Benchmarks use a small development sample and do not estimate unseen quality. Warm-up wall includes its request and may include loading; it is not automatically a controlled cold start. Warm uncached inference performs a new request, whereas an output-cache hit reuses stored text. Agent turn latency excludes resource creation before respond; inspect cache status and provider load/prompt/decode timings. Full prompt/source/fact/model settings enter cache keys; private-order calls bypass persistent output caching.

Real Gnani speech; separate time measures

Status: tested. Audio batches: 6/6 succeeded; semantic/privacy checks passed: 6, failed: 0. Results describe the saved run, not a human listening study.

Saved voice processing wall range: 1.03-22.26 s; generated reply audio duration: 4.00-12.00 s. Processing time and playback length are different quantities. Gnani TTS input clips are synthetic, not human recordings; accent/noise robustness and subjective listening remain unverified.

Gnani is the only STT/TTS provider. Bounded retries rewind inputs; invalid transcripts, truncated PCM and empty speech are rejected. Stream-style WAV sizes are finalized without changing samples. Batch results retain redacted transcripts, sources, tool traces, timing and per-file errors. An offline-rules run disables answer generation but still requires Gnani speech.

Reproduce and release

Repository: https://github.com/Pranay207/ESD. Setup: powershell -File setup.ps1. Batch: python run.py --audio_dir <in> --out_dir <out>. Evaluate eval_step1.py, eval_step2.py --live, eval_step3.py --live, eval_adversarial.py, eval_holdout.py --check-only, eval_holdout.py, and python -m pytest -q. Reproduce voice with generate_voice_samples.py --reuse-inputs. Generated JSON retains the measured configuration and failures.

After final checks, regenerate the report, visually inspect all pages, record demo.mp4 within 120 seconds, then build/verify the release ZIP. Packaging excludes .env, dataset copies, model weights, caches, environments and private audio. Educational proof checking is not production authentication. No rank, prize or real customer outcome is promised.

Sources: capstone brief; supplied dataset README, dictionary, KB and tools; official Gnani STT/TTS docs; pinned multilingual MiniLM model card; sample_outputs JSON named above. Report measurements are loaded when this file is generated.
