# Two-minute demo runbook (brief limit: <=2 minutes)

Record your own screen and narration; save the finished file as `demo.mp4` at the project root. Do not exceed 120 seconds. Do not show `.env`, raw CSV customer records or unredacted verification input. No fake/generated success screens. Gnani speech must actually work before recording.

## Before recording

1. Add your own Gnani key to `.env`. Run `python generate_voice_samples.py`; confirm `sample_outputs/voice_validation.json` says tested and every real batch entry succeeds.
2. Start Ollama and `python -m streamlit run app.py`. Warm the app with one UPI question, then start a new conversation. Enable LLM sentence composition.
3. Prepare a synthetic order and its proof privately from the provided tables. Enter proof off-screen or mask only the input area in the recording; do not edit the agent's answers. The displayed history must show `[verification value redacted]`.
4. Open the Evaluation tab and the saved baseline Wallet example. It genuinely predicts 3-5 business days, which disagrees with REF-2's instant/within-2-hours rule. Do not type a fake baseline answer.

## Timed narration and actions

| Time | Action and suggested narration |
|---|---|
| 00:00-00:10 | Title. "This is ZentroMart's AI support agent. It answers from company policies, verifies orders, and uses Gnani to listen and speak." |
| 00:10-00:25 | Evaluation tab + saved Wallet baseline output. "The document-free baseline passed only five of fifty-two mechanical checks. Here it guessed the Wallet timeline. Grounding fixes this with the actual refund policy." |
| 00:25-00:45 | Text: "What is the UPI refund timeline?" Open Sources. "The answer is one to three business days, supported by REF-2. The AI disclosure appears on the first turn, and the model cannot add unsupported policy facts." |
| 00:45-01:10 | New conversation; ask for a synthetic order's status, provide order ID. Show the verification prompt, complete proof off-screen, show redacted history and actual `lookup_order` success. "No order details appear before verification. The trace hides the credential." |
| 01:10-01:30 | Follow-up about the same order, then "I want to speak to a human." Open ticket trace. "The conversation retains its order context, and claims a handover only after the real mock tool creates a ticket." |
| 01:30-01:50 | Voice tab, record your own Hinglish question about UPI refunds, play the real Gnani reply. "The same agent handles the transcript and replies through Gnani. English, Hindi and Hinglish are supported." |
| 01:50-02:00 | Ask an uncovered service question or show abstention; end with the evaluation table. "Unknown policies are not invented. Scores shown are local checks, and hidden-test quality still depends on generalization." |

If the key is still missing, do not claim the voice requirement is complete and do not record a simulated voice success. Keep the package marked draft until actual validation and recording are done.
