# Design - ZentroMart VoiceOps

## Four cumulative steps
1. Prompt-only baseline: same LLM with role, limits and disclosure but NO policies, catalog or retrieval; store actual predictions without manufacturing hallucinations.
2. RAG: section-ID chunks, metadata, BM25 + multilingual dense vectors, authority-aware ranking; retain sources used by every answer. No practice files in runtime index.
3. Conversation: deterministic verification, date arithmetic, policy eligibility and actions; LLM language composition constrained to verified facts. State is scoped to a session; reset verification on order change; one retry. Immediate safety/fraud/legal/human handover must not wait for authentication.
4. Gnani speech wrapper around the same agent. Explicit timbre-v2.5; English, Hindi and Hinglish. Batch isolates bad clips, redacts proof, emits JSON/text/WAV/sources and manifest. No fake audio or alternate speech services.

## Schema
customers(customer_id, phone, is_plus) -> orders(order_id, customer_id) -> order_items(order_id, line_no, sku) -> products(sku). orders.delivery_pincode -> pincodes.pincode. holidays.date supplies business calendar. All identifiers stay strings. Tables: 300 customers, 1,000 orders, 1,783 lines, 70 products, 36 pincodes, 4 holidays, 244 historical support logs. 21 KB docs; practice 52 questions and 23 conversations / 96 turns. Missing cells are missing, not completed actions. Import supplied tools unchanged; write tickets only after create_ticket succeeds.

## Authority and versions
Current policy > agent guide > help > FAQ > marketing. Meta KB-00 governs precedence and dates. Preserve version/effective date/status. Exclude superseded retrieval except when successor RET-3 authorizes pre-August electronics windows (10 vs 7 days). FAQ-1's generic 5-7-day refund conflicts with payment-specific REF-2. Marketing promises cannot expand PLS-2. Marketplace MKS-3 denies Assured on seller items even when catalog badge is true. Historical support logs are never policy evidence.

## Deterministic boundaries
Reference date 2026-10-20. Business days exclude Sundays and holidays; elapsed refund days start after initiation, matching practice dates. Return deadline = delivery + window (delivery is day zero), matching the operational convention consistently used by the supplied practice dates. RET-2 says the window starts on delivery but does not spell out day-zero arithmetic; this is an explicitly documented ambiguity. Fashion placed 1-15 October gets 30 days; other fashion 15. Returns v4 defines category windows; conditions/nonreturnable exceptions, damaged/wrong/missing 48 hours, >10,000 claims human review. No cancellation API exists: guide to My Orders only. Never claim a cancellation/replacement/compensation was executed.

## Privacy
Proof is used only at the supplied tool boundary and immediately discarded. Never echo, persist or send verification secrets to an LLM. Tool traces contain only redacted args and an allowlisted result. No private customer/contact records in retrieval. Verified order context is sanitized; pincode, name, customer ID and internal notes are removed. Two failed proofs lock that order in the session. Resetting/changing order must not clear its attempt counter. Ticket summaries include issue, intent, order, checks and reason, but no proof. Raw voice is transient and not copied into output. This is synthetic educational authentication, not production auth.

## Retrieval and composition
Quantized multilingual MiniLM ONNX (50-language model) avoids a multi-gigabyte PyTorch dependency. Cache model and normalized section embeddings on disk; load once per process. BM25 reciprocal-rank fusion with dense search; exact catalog matching; lower-authority contradictions cannot govern. Relevant policy sections form evidence; deterministic rules create claim records with source IDs. The answer composer may translate/rephrase those facts only; validate numeric tokens and require source IDs, otherwise use safe deterministic wording. Offline mode remains usable and explicitly labeled. Hosted compatibility is optional; local Ollama is available.

## Evaluation and likely failures
Measure actual decisions, must-include facts, forbidden claims, evidence recall and expected tool presence separately. Do not equate retrieval recall or keyword matches with full semantic correctness. Practice failures target outdated returns, FAQ refund traps, Plus exceptions, multilingual product references, 3rd contact escalation, high-value damage, QC-vs-initiation, overdue refunds/RRN, cancellation limitations, coupon topic switching, wrong proof lockout, privacy refusal, unknown store/discount/invoice policies. Original adversarial suite extends these domains without matching practice strings or IDs. Preserve failures honestly; never silently edit generated answers or claim mocked voice success.

## Deliverables and unresolved external requirements
Max 4-page PDF report and max 2-minute user-recorded demo. Secret-free reproducible ZIP excludes dataset/model/cache/venv. Missing Gnani key blocks real speech tests; generation script must report blocked status and run as soon as the participant supplies GNANI_API_KEY. Public repository URL and recorded demo require final user-owned assets; do not invent either. A top-20 result cannot be guaranteed.
