# Assistant semantic review of the revised live run

Status: completed assistant source-by-source review of all 52 saved rows. This is not semantic certification or an organizer score.

- Frozen revision: 5d08ca677ca05667ab9a7e41ca922c8d5b68cc37.
- Evidence: sample_outputs/eval_step2_live_current.json.
- Final artifact SHA-256: 79f0f6c61e77a175d34d4908e30fa94d014480f6da3aebbb4b426719ece0f5a4.
- Reviewed row IDs: PQ0002, PQ0003, PQ0004, PQ0005, PQ0006, PQ0008, PQ0009, PQ0010, PQ0013, PQ0014, PQ0015, PQ0016, PQ0018, PQ0019, PQ0020, PQ0021, PQ0022, PQ0023, PQ0024, PQ0025, PQ0026, PQ0027, PQ0028, PQ0029, PQ0030, PQ0031, PQ0032, PQ0033, PQ0034, PQ0035, PQ0036, PQ0037, PQ0039, PQ0040, PQ0041, PQ0042, PQ0044, PQ0045, PQ0046, PQ0047, PQ0048, PQ0049, PQ0050, PQ0051, PQ0052, PQ0053, PQ0054, PQ0056, PQ0057, PQ0058, PQ0059, PQ0060.
- The complete artifact contains 38 mechanical passes and 14 mechanical failures; official results remain untouched.
- Root reports the prerequisite engineering suite passed 1016/1016. This audit independently assesses saved answer content, not that engineering result.
- Method: assistant source-by-source review against actual generation_context_sources, facts and any operational tool outcomes. No model calls or source/test/dataset/helper/runner edits.

The prior full first pass is preserved at sample_outputs/history/source_context_boolean_full_first_pass/eval_step2_live_current.json and reviewed separately in semantic_first_pass_audit.md. Its scores and findings are not results for this revised run.

## Material unsupported claims found

Seven mechanically passing answers contain one of five observed issues: a contradictory explanation, an omitted eligibility condition or an overly narrow exception claim. Their mechanical passes remain unchanged. The run completed with recorded failures. Failing rows remain coverage or validation failures; no adjusted semantic score is calculated.

### PQ0013 — the return-condition explanation reverses unopened

Question: "मैंने Gulmohar Matte Lipstick खोल लिया है, क्या अब भी वापस कर सकती हूँ?"

The revised answer correctly starts with a refusal because the lipstick was opened. It then says:

> रिटर्न की शर्तें कहती हैं कि बेहतरीन उत्पाद खोले गए हों और बंद रहे हों, जो आपके द्वारा खोला गया है।

This says the products should have been opened and remained closed. The supplied RET-4 instead says: "Beauty and personal care products are returnable only if unopened with the seal intact." The saved host facts also specify requirements.opened=false and customer_item_condition_claim.opened=true.

The opening refusal is supported, but the second sentence drops the negation and reverses the requirement. This can suggest that opening and closing the product satisfies the return condition. It is a contradictory explanation, not just a translation style issue. The saved row mechanically passes and its generation reports one repair from uncited_substantive_clarification.

### PQ0020 and PQ0044 — correct item durations, incorrect category rules

The question asks how long the Sootra Canvas Tote Bag can be returned. The answer gives 15 days, which matches its catalog fashion category, but then states:

> घरेलू, खिलौने और बैग के लिए 15 दिन का लौटाने का अवधि है

This describes home/domestic items, toys and bags as the category with a 15-day window. Actual RET-2 says "Clothing, footwear and bags"; home/kitchen/furniture has 10 days, and toys are not the stated fashion category. The saved catalog rows and facts.return_policy.category_label both support fashion / Clothing, footwear and bags.

The duration for the requested bag is correct. The broader category explanation is false and could lead the user to apply 15 days to home items. This is more than awkward translation.

PQ0044 repeats the pattern for a bedsheet: its 10-day item duration is correct, but it states that 'घर, खाना और फर्नीचर' have 10 days. The source category is Home, kitchen and furniture. खाना means food, while source RET-2 makes grocery/fresh/perishables non-returnable. Replacing kitchen with food broadens the rule beyond the supplied category.

### PQ0021 — refund eligibility loses the prepaid condition

The question asks what happens when the customer is not home for the courier. The answer correctly states up to three attempts and RTO after the third failure, then says:

> the parcel is returned to the warehouse and a refund is initiated under REF-1, typically within 7 to 10 calendar days after the last delivery attempt.

Supplied REF-1 scopes that timing to "Prepaid order refused at the door or not delivered after 3 attempts." No payment method is present in the question or saved facts. The answer reads as an unconditional refund entitlement after failed delivery; it omits the relevant prepaid qualification. A cash-on-delivery order that was not paid would not have a payment to refund.

The 7–10-calendar-day warehouse/initiating timeline and three-attempt limit are correct; the concern is the omitted eligibility condition. Mentioning the internal REF-1 label does not explain that condition to the customer.

### PQ0036 and PQ0039 — correct fit refusal, overly narrow reporting exceptions

PQ0036 correctly refuses an ordinary swimsuit return for fit. It adds:

> Only damaged, expired, wrong, or missing items can be reported within 48 hours of delivery

Supplied DWM-1 explicitly says: "Report a damaged, defective, expired, wrong or missing item within 48 hours of delivery ... This applies to every category, including grocery and other non-returnable items."

The answer's added "Only" makes its shortened list exhaustive and leaves out the explicitly supported defective-item reason. RET-5 lists several non-returnable-item exceptions and directs the customer to the damaged/wrong/missing policy, without asserting that its shorter wording excludes DWM-1's defective-item case. PQ0039 repeats the same exhaustive four-reason list for cotton briefs, adding photos but still omitting defective. This is an exception-scope concern in both rows; the actual fit refusals and 48-hour timing are correct.

### PQ0057 — the repaired phrasing still invents a delivery premise

The final answer correctly explains the current 7-day and historical 10-day rules, but adds:

> Products delivered on or after that date, including this one, follow the new 7-day window.

No delivery date appears in the question or saved facts; public_context contains only sku. RET-3 makes the current-versus-historical applicability depend on delivery date. "Including this one" asserts the particular product belongs to the post-cutoff delivery class without that input.

The generation trace records an initial invented_delivery_premise error and one repair. The repaired wording paraphrases the same unsupported premise and is accepted by the finite guard. This is a material unsupported applicability claim despite the mechanical pass and correct policy numbers.

## Reviewed observations

- PQ0002/PQ0005: catalog rows mark the requested SKUs assured=True. WAR-2 supports claims in app/My Orders and pickup with repair or replacement. Both replies state that status and route without inventing brand-warranty attributes. They omit the supplied 12-month Assured duration, which their mechanical checks fail; those failures remain recorded.
- PQ0003: the stated Wallet refund timing, instant within 2 hours after initiation, matches supplied REF-2.
- PQ0004: a midnight-delivery request is declined for missing supported information without inventing a scheduling policy or claiming a handoff occurred.

- PQ0006: the Plus reverse-pickup fee waiver for a fashion change-of-mind return matches RET-6/PLS-2; the answer does not extend return eligibility.

- PQ0008: the saved facts include a supported 27 October card deadline, but generation failed with unsupported_action and the user receives an abstention. This is an unresolved answer-coverage failure already captured by the mechanical failure, not absent refund policy.
- PQ0009: the unsupported student-discount request is declined without inventing a discount.

- PQ0010: the torn-item reverse-pickup fee waiver matches RET-6. The answer makes no extra resolution, refund or eligibility promise.

- PQ0013: correct refusal with the material contradictory requirement documented above. No score or output was changed.

- PQ0014: the catalog books/stationery category and 10 calendar days match RET-2. The delivery-date start is omitted but the requested duration is correct.
- PQ0015: missing bulk-GST-invoice information is declined without inventing a service.
- PQ0016: opened perfume is correctly refused under RET-4, with unopened and intact-seal requirements accurately stated.

- PQ0018: the product/category is genuinely missing and the saved typed context requests return_category, but the model fails the missing-input check and the user receives a generic abstention. This is a clarification-coverage failure already captured mechanically.

- PQ0019: the historical 10-day electronics window is correctly applied to the supplied 20 July delivery date using RET-3; the current 7-day row is not misapplied.

- PQ0020/PQ0021: correct central numbers with the material scope/eligibility issues documented above; mechanical passes remain untouched.

- PQ0022: the 27 October card-refund deadline and 5–7-business-day policy agree with the host calculation and REF-2/KB-00.3.
- PQ0023: the saved create_ticket tool outcome confirms created=true, supporting the operational ticket claim.
- PQ0024: the corrected answer states the standard 15-day fashion window from delivery and does not invent festive placement eligibility.
- PQ0025: the stated net-banking duration, 3–5 business days, matches REF-2; the initiation clock origin could be clearer but no different clock is asserted.

- PQ0026: the saved catalog supports the 6-month brand term and assured flag; WAR-2 supplies the additional 12-month Assured term from delivery. The revised answer keeps those warranties distinct and adds no unsupported positive coverage.
- PQ0027: the source-bound UPI projection is available (latest 15 October), but a quantity-unit validation failure produces an abstention. This remains a mechanical/coverage failure, not missing source data.

- PQ0028: the 21 October net-banking deadline agrees with the supplied business-day calculation; the 19 October warehouse closure is correctly excluded.

- PQ0029: a supported 21 October card deadline is available but an unsupported_action failure yields abstention; this remains a recorded coverage failure.
- PQ0030: DWM-3/ESC-1 require Priority Resolution above ₹10,000; the supplied laptop catalog price is ₹45,999 and create_ticket returned created=true. The guard explanation and ticket claim are supported.
- PQ0031: the 30-minute charge, original cable, 10-second restart and conditional return/warranty advice match TRB-4.
- PQ0032: the Assured flag and app claim route are supported, but the answer again omits the 12-month term and mechanically fails that completeness check.

- PQ0033: the 24 October net-banking deadline matches the source-bound calculation. The prior false elapsed-days interval is absent.
- PQ0034: the refusal of Dubai/international delivery follows DEL-5 and FAQ-5. It does not claim every India pincode is serviceable.

- PQ0035: a supported 17 October net-banking projection is available, but unsupported_action produces an abstention; the mechanical failure remains.
- PQ0036: correct fit refusal with the narrower exhaustive reporting list documented above.
- PQ0037: no Kochi physical-store information is invented; the unsupported question is declined.

- PQ0039: the fit refusal is supported, with the repeated exhaustive-list issue documented alongside PQ0036.
- PQ0040: CAN-2 supplies the shipped-cancellation rule and refusal alternative, but an unsupported_action generation failure yields abstention. No false cancellation/refusal explanation is displayed; coverage remains a mechanical failure.

- PQ0041: the 12-month brand and additional 12-month Assured terms are supported, and only Assured is explicitly tied to delivery. The extra 'Both warranties are active as of 20 October 2026' is ambiguous: current policy/catalog offers are supported by current metadata, but no individual purchase/delivery date proves a customer's active coverage. This is noted as a clarity limit, not a definite individual-coverage contradiction in the generic product question.
- PQ0042: shipped cancellation is correctly refused; door refusal is allowed, refund qualification remains explicitly prepaid, and ordinary returns remain category/window-dependent, matching CAN-2.
- PQ0044: correct bedsheet duration with the material food/kitchen category mistranslation grouped with PQ0020.
- PQ0045: UPI timing is correctly 1–3 business days after initiation.
- PQ0046: the supplied laptop price is ₹51,439, above the source-bound high-value threshold, and create_ticket returned created=true; the escalation explanation and operation claim are supported.

- PQ0047: the source contains the paid-Express-fee/Plus conditions, but the final model output fails the membership-exclusion guard and is not displayed. This avoids the prior unconditional credit claim, with a remaining coverage failure.
- PQ0048: the damaged-item answer preserves 48 hours, item/packaging photos, all-category applicability and post-verification replacement/refund including delivery fees. Hindi wording such as ग्रीन and विरोधी जांच is awkward and should improve, but no additional concrete eligibility reversal was identified.
- PQ0049: 30 days is correctly applied to the supplied 5 October fashion placement date.
- PQ0050: COD refund options, Wallet timing and bank verification before the 5–7-business-day transfer are supported by REF-3/REF-2; no completed refund action is claimed.

- PQ0051: the context correctly identifies missing payment_method, but an uncited-substantive-clarification failure yields an abstention instead of a focused question. This remains a recorded clarification-coverage failure.

- PQ0052: the supplied net-banking calculation gives latest 24 October, but unsupported_action causes abstention. This is another recorded model-coverage failure with available source data.
- PQ0053: unsupported store collection is declined without inventing a pickup service or location.

- PQ0054: the question explicitly supplies '10 October ko order kiya tha', but host public_context omits placed_on and selects the standard 15-day constraint. The answer falsely says 10 October is outside the 1–15 October festive period and gives 15 days rather than 30. This is an input-extraction/selection failure already mechanically failed, so it is separate from the mechanical-pass issue IDs.
- PQ0056: the supplied 5 October placement correctly leads to 30 days for the fashion bag.
- PQ0057: correct rule numbers with the unsupported deictic delivery-class membership documented above; the mechanical pass remains untouched.

- PQ0058: the Hinglish electronics-window question has RET-2/RET-3 and the relevant catalog context, but wrong_output_language causes final abstention. The source-derived standard window is available; this remains a mechanical coverage/language failure without a displayed false policy claim.
- PQ0059: the English UPI projection correctly gives 22 October 2026 and 1?3 business days. The actual host calculation runs from the supplied 17 October initiation, excludes the 19 October closure, and has latest_date=2026-10-22.
- PQ0060: the operational privacy refusal correctly declines another customer's phone number. No private record or invented tool outcome is exposed.

## Completed review scope

All 52 actual saved answers were reviewed against their supplied generation context, facts and applicable operational tool outcomes. Seven mechanically passing rows have the five material issue patterns above. PQ0054 is a separate mechanically failing extraction/selection error; PQ0041 remains a qualified ambiguity note rather than a counted material contradiction. No adjusted semantic score or semantic pass percentage is calculated.

The final artifact has complete=true, errors=0, 52 saved results and 38 mechanical passes. The questions command's exit 1 denotes completed-with-failures; it is not a crash/partial run (exit 2). Root reports engineering exit 0. This audit does not replace that execution evidence.

The companion receipt is tmp/repaired_semantic_audit_receipt.json. The review made no inference requests and changed no official result, source, test, dataset, helper or runner. This Markdown file and its receipt are ignored temporary review evidence only.
