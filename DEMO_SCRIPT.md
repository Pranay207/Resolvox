# User-recorded demo runbook (maximum 120 seconds)

Record your screen and narration after final validation, and save `demo.mp4` at the project root. Leave a few seconds below the 120-second limit. Show real app/tool/speech output; do not replace answers, hide failures or display simulated success. Keep `.env`, private table rows and unredacted proof inputs off-screen.

## Prepare after the final run

1. Confirm the selected LLM/model and regenerated evaluation files. Run `python eval_holdout.py --check-only`; use actual `sample_outputs/eval_holdout.json`, practice results and model benchmarks if showing scores. Do not narrate a score from an older architecture or an evaluation that has not run.
2. Confirm real Gnani validation with `python generate_voice_samples.py --reuse-inputs` (omit `--reuse-inputs` if inputs do not yet exist). Inspect `sample_outputs/voice_validation.json` and the actual batch artifacts. Synthetic test inputs are not human speech evidence.
3. For the selected local model, run `ollama pull qwen3:1.7b` and set `LLM_MODEL=qwen3:1.7b` in your private `.env`. Start Ollama or the configured hosted endpoint, then `python -m streamlit run app.py`. Enable LLM generation. A `--offline-rules` CLI run has no answer generation even though it still calls Gnani for speech.
4. Rehearse the chosen query and inspect its JSON: `composition=grounded_llm` means accepted generated wording; checked fallback/guardrail/abstention modes must be described by their actual labels. Confirm `llm.cache_hit` and timing fields; keep the sanitized JSON trace ready for fields absent from the app caption. If warming the app before recording, disclose that the shown run is warm; a cache hit is not fresh inference. Turn timing also excludes startup/resource loading.
5. Prepare a synthetic order/proof privately. Mask only the input area or enter proof off-screen; the displayed history must show its redaction. Keep app session state clear before the recorded verification example.
6. Choose a documented query, an order follow-up and a handover or uncovered service question. Use a saved baseline only if its actual generated answer demonstrates the claimed difference. Keep the final recording within the time budget, including real provider latency; trim narration or examples rather than disguising wait time.

## Recording outline

| Time | Action and concise narration |
|---|---|
| 00:00-00:10 | Show app title. "This is ZentroMart's AI support assistant. It searches company policies, verifies order access, and uses Gnani for speech." |
| 00:10-00:35 | Ask a documented policy question, such as UPI refund timing. Open Sources and composition/timing evidence. "It retrieved these sections first. The model generated the answer from their actual text. The source trace records the exact sections supplied; checks can reject unsupported values, but do not prove every claim." State whether the response was warm uncached or cached; if fallback occurred, say so. |
| 00:35-01:00 | Ask about the prepared synthetic order, show the verification prompt, provide proof off-screen and reveal the redacted successful lookup trace. "Order details are withheld until verification succeeds. The credential is removed from the trace and model input." |
| 01:00-01:20 | Ask a follow-up on that order, then request a human if time permits. Show the actual ticket result. "The session keeps the verified order context. A ticket is reported only after the supplied tool confirms success." If creation fails, describe the failure honestly. |
| 01:20-01:45 | Record a short Hindi/Hinglish policy question in the Voice tab and play the real Gnani reply. "Gnani transcribes my voice; the same agent answers; Gnani speaks the reply." Include actual processing time in the recorded sequence. |
| 01:45-01:55 | Show an uncovered service question or saved current abstention, then a current evaluation result. "The agent can abstain. These are local measured checks, with generation, fallback and cache behavior recorded separately." |

The outline is a rehearsal budget, not a latency promise. If real waits would exceed 120 seconds, remove the optional score/baseline segment or use fewer examples. Do not describe cache playback as fresh generation. Existing voice checks use synthetic TTS inputs; human speech testing and subjective listening have not been completed. If speech validation fails, keep the release draft and fix the failure before recording the required live speech demonstration.
