# Resolvox - Demonstration Guide

The current production target is **1 minute 45 seconds (105 seconds)**. The brief allows at most 120 seconds. Show an actual document-grounded answer, a follow-up in the same conversation, and either a confirmed handover or a clear statement of uncertainty.

## This demonstration

Use one fresh conversation in the application with **AI policy answers on**, **English / Hinglish** selected, and **Speak** mode. The prepared walkthrough uses clearly labelled synthetic customer questions and narration through Gnani. Agent replies must come from the actual application, with its real Gnani STT and TTS path. It is an edited walkthrough, not an unedited real-time latency demonstration.

| Part | Screen action | Spoken content |
| --- | --- | --- |
| Introduction | Show Resolvox and the support workspace | Meet Resolvox, an AI support assistant for ZentroMart. This edited walkthrough uses synthetic customer speech and real application responses. |
| Grounded answer | Upload or record the first question, send it, show the reply and open View supporting policy | As a non-Plus customer, what is the standard return window for clothing? |
| Follow-up | Keep the same conversation and send the second question | And what reverse pickup fee applies if I change my mind about those clothes? |
| Uncertainty | Keep the same conversation and send the third question | What return policy will ZentroMart introduce in the year 2030? |
| Closing | Show the conversation and a compact pipeline summary | The same conversation connects Gnani speech recognition, document retrieval, a local language model, and Gnani speech synthesis. Supporting policies remain visible, and unsupported questions receive uncertainty. |

The edited version adds short, clearly labelled narrator explanations after each actual reply: why the policy supports the first answer, how context carries into the follow-up, and why the final question receives uncertainty. These explanations are separate from the unmodified agent replies.

## What to verify before using a take

- The first reply must use the actual clothing return policy: 15 calendar days from delivery, with any stated conditions supported by the document.
- The follow-up must preserve the clothing context. The policy states a Rs 49 reverse-pickup fee for change-of-mind returns of clothing, footwear and bags, waived for Plus members and damaged, defective or wrong items.
- The future-policy question must not invent a policy for 2030. Show the actual reply acknowledging the missing information. If the reply invents a policy, preserve the failed take and fix or investigate it before recording a new take.
- Speech playback must be an actual Gnani reply, not a substituted recording or a manually authored agent answer.
- Supporting policy text must be visible at least once. Internal style instructions are not customer-facing evidence.

## Recording and editing

Keep a visible label: **Edited walkthrough - synthetic customer speech - processing waits shortened**. Preserve the complete customer questions and actual spoken replies. Subtitles may reproduce the exact visible transcript and answer; do not rewrite a response to make it correct. Processing screens can be shortened, but do not imply instant or real-time performance. A rehearsed or cached turn is not fresh inference.

Do not show API keys, environment files, private verification proofs or customer tables. This policy-only flow needs no private order details. Do not add a ticket-created or order-verified claim, because this particular walkthrough does not demonstrate those actions.

## Final checks

- Total duration is at most 120 seconds, with a short margin.
- The picture and speech are readable and audible on a laptop and phone.
- All three replies are reviewed against the sources and their stated uncertainty.
- Save the approved video as `demo.mp4` at the repository root.
- Keep any generated-video provenance separate from the claim that a human recorded their own voice.
- Rebuild the draft ZIP after adding the video; confirm anonymous repository access before creating the final submission ZIP.

The recorded evaluation and its limits are in [VERIFICATION.md](VERIFICATION.md). The demo is a product walkthrough, not evidence that every unseen question passes.
