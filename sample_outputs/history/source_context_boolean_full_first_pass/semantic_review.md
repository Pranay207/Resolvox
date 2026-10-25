# Semantic audit of the first live source-context run

This is a read-only assistant source-by-source review of saved answers, separate from the evaluator's mechanical results. No official score, source, runner or model output was changed. No model requests were made.

## Reviewed snapshot

- Evidence file: sample_outputs/eval_step2_live_current.json.
- Reviewed snapshot SHA-256: 2ee8b2d65b2442686e548c7cd4e0591d6d0d240048ee0cd5306292aec3c74c08.
- Reviewed all 52 saved rows, through PQ0060, after this frozen first pass completed.
- Those rows contain 36 mechanical passes. The six findings below concern mechanically passing answers.
- Compared each passing answer with its own prediction.generation_context_sources and prediction.facts. For deterministic guard replies, generation context is absent; their operation claims were checked against the saved tool trace rather than assumed to be model answers.
- This is not semantic certification of every unflagged sentence, and no revised pass percentage is computed.
- Reviewed row IDs: PQ0002, PQ0003, PQ0004, PQ0005, PQ0006, PQ0008, PQ0009, PQ0010, PQ0013, PQ0014, PQ0015, PQ0016, PQ0018, PQ0019, PQ0020, PQ0021, PQ0022, PQ0023, PQ0024, PQ0025, PQ0026, PQ0027, PQ0028, PQ0029, PQ0030, PQ0031, PQ0032, PQ0033, PQ0034, PQ0035, PQ0036, PQ0037, PQ0039, PQ0040, PQ0041, PQ0042, PQ0044, PQ0045, PQ0046, PQ0047, PQ0048, PQ0049, PQ0050, PQ0051, PQ0052, PQ0053, PQ0054, PQ0056, PQ0057, PQ0058, PQ0059, PQ0060.
- PQ0049 correctly applies the festive exception because facts.public_context.placed_on is 2026-10-05. Newly reviewed PQ0048/PQ0050/PQ0051 mechanically fail and are outside the pass-only findings.
- PQ0053/PQ0056/PQ0059/PQ0060 add no material error: missing store-pickup information is honestly declined, the festive date is supplied, the UPI date matches the host calculation, and third-party private data is refused. PQ0055 is not present in this evaluated subset.
- Archive destination supplied by root: sample_outputs/history/source_context_boolean_full_first_pass/eval_step2_live_current.json. The snapshot hash above identifies the reviewed file regardless of relocation.

## Material findings

| ID | Finding | Effect | Status |
| --- | --- | --- | --- |
| PQ0024 | Asserts an unknown order-placement date and applies the festive extension | Invents eligibility for 30 days instead of presenting 15 days plus a conditional exception | Already queued by root; confirmed |
| PQ0033 | Uses elapsed_business_days for the wrong interval | Says one business day separates initiation and the latest deadline, although that value describes elapsed time to reference_date | Already queued by root; confirmed |
| PQ0040 | Says the customer cannot refuse a shipped parcel at the door | Reverses an expressly permitted option | Additional finding |
| PQ0041 | Invents brand-warranty start date and positive coverage terms | Extends the supplied warranty facts beyond their actual scope | Additional finding |
| PQ0047 | Promises a late-Express credit without the paid-fee condition or Plus exclusion | Grants a benefit not established for this customer's order | Additional finding |
| PQ0057 | Invents delivery after the electronics-policy cutoff | Applies current historical eligibility without an actual delivery date | Additional finding |

### PQ0024 — invented festive eligibility

Question: "How long do I get to send back the Rangoli Cotton Straight Kurta?"

Saved answer: "You have 15 days from the delivery date ... However, since the order was placed between 1 October and 15 October 2026, it qualifies for the festive sale return window of 30 days instead."

Actual evidence:

- RET-2 supplies the standard 15-calendar-day fashion window from delivery.
- RET-8 permits 30 days only for clothing, footwear and bags from orders placed between 01 October and 15 October 2026.
- facts.return_policy.selection is standard_window.
- facts.return_policy.placement_date_unavailable is true.
- No order placement date appears in the public context or catalog record.

The conditional policy is real; this customer's eligibility is invented. A grounded answer must keep the extension conditional or ask for the placement date if it is needed to determine the actual applicable window. Merely including the required number 15 did not prevent the contradictory 30-day entitlement.

### PQ0033 — correct deadline, wrong elapsed-time interpretation

Question: "My refund to net banking was started on 17 October 2026. By which date should I have it?"

Saved answer gives the correct earliest and latest dates, then says: "with 1 business day elapsed between the initiation and the latest date."

Actual saved calculation:

- inputs.initiated_on: 2026-10-17.
- inputs.reference_date: 2026-10-20.
- inputs.minimum_business_days: 3.
- inputs.maximum_business_days: 5.
- result.earliest_date: 2026-10-22.
- result.latest_date: 2026-10-24.
- result.elapsed_business_days: 1.

The value 1 measures elapsed business days from initiation to the reference date, not the interval ending on 24 October. The latest deadline uses the five-business-day bound. The numerical values individually occur in the host facts, but the relationship asserted between them is false.

### PQ0040 — cancellation alternative reversed in Hindi

Question: "ऑर्डर शिप हो गया है, क्या अब कैंसिल हो सकता है?"

Saved answer begins "हां, जब ऑर्डर शिप हो जाता है तो इसे कैंसिल नहीं किया जा सकता है" and later says "दरवाजे पर पैकेट को रिफस नहीं कर सकते हैं".

Actual generation context contains CAN-2:

> A shipped order cannot be cancelled. The customer can:
> - refuse the parcel at the door. For cash-on-delivery orders nothing is charged. For prepaid orders the refund follows REF-1 once the parcel returns to the warehouse; or
> - accept the delivery and return the item within its return window, if the category is returnable.

The opening yes is inconsistent with the refusal to cancel. More materially, "रिफस नहीं कर सकते हैं" says the customer cannot refuse the parcel, directly reversing CAN-2. The COD/prepaid discussion does not repair that contradiction. The permitted door-refusal option must remain affirmative.

### PQ0041 — unsupported warranty scope and start date

Question: "What warranty comes with the Nimbus X2 Pro Wireless Earbuds, Blue (SKU ELE-0003)?"

Saved answer correctly supplies a 12-month catalog brand warranty plus an additional 12-month Assured warranty, but adds:

> Both warranties are valid from the delivery date and cover defects in materials and workmanship ...

Actual generation context:

- Product row: warranty_months is 12 and assured is True.
- WAR-1: most electronics come with the manufacturer's warranty; the period is in warranty_months; brand claims go to the manufacturer's service centre.
- WAR-2: assured products have a 12-month ZentroMart Assured warranty from delivery, in addition to any brand warranty; app/My Orders claims trigger pickup and repair or replacement.
- WAR-3: physical damage, liquid damage, normal wear and unauthorised repairs are excluded.

Only Assured's start date is specified. No supplied source says the brand warranty also starts on delivery, or defines positive coverage as "defects in materials and workmanship." The exclusion list does not establish every remaining kind of positive coverage. These are substantive warranty terms, not harmless wording variants. The answer also omits the supplied manufacturer-service-centre claim route, though the question did not explicitly ask how to claim; the principal finding is the invented terms.

### PQ0047 — late-Express credit conditions omitted

Question: "My express order arrived a day late. Do I get anything back?"

Saved answer:

> Yes, you get a credit of ₹79 to your ZentroMart Wallet because your Express order arrived a day late. This credit is automatically applied within 48 hours of the late arrival. Note that this only applies to Express orders; Standard deliveries do not qualify for any credit.

Actual supplied DEL-4:

> If an Express order arrives after its promised date, the ₹79 express fee the customer paid is credited to ZentroMart Wallet automatically within 48 hours. ZentroMart Plus members, who pay no express fee, get no credit. There is no compensation for late Standard deliveries. Agents must not offer any other compensation.

Saved facts contain no membership or paid Express fee. The answer preserves the Standard exclusion but drops the more relevant Plus/fee-paid qualification while guaranteeing entitlement. It should explain that the paid ₹79 Express fee is credited, while Plus members who paid no Express fee receive no credit. This can change the user's expected compensation.

### PQ0057 — invented delivery date for the historical exception

Question: "Is it still ten days to return electronics like the Orbix Fit 3 Pro Smartwatch?"

The saved answer correctly states the current 7-day window but adds: "Since the delivery date of the product is after this date, the current return window applies, and the earlier 10-day window does not apply."

RET-3 says electronics delivered before 1 August 2026 keep the earlier 10-day window. The saved public_context contains only sku; neither the question, catalog record nor facts supplies a delivery date. facts.return_policy.historical_exception expressly preserves that cutoff. A current-policy explanation can state the current 7-day rule and describe the historical exception conditionally, but it cannot assert this customer's delivery occurred after the cutoff. This is the same unsupported applicability inference as PQ0024, with a delivery date rather than placement date.

## Additional review notes

- PQ0020 handles the same festive exception correctly: it says the order date is unavailable and makes the 30-day extension conditional. That passing answer shows the policy context itself is sufficient; PQ0024's error is generation semantics.
- PQ0027's holiday explanation mentions a holiday outside its 13–15 October projected range. The holiday fact is true and the projected dates are correct; this was not escalated as a material error.
- PQ0014/PQ0044 provide the correct requested duration but omit the delivery-date/calendar-day basis. These are possible completeness improvements, not counted as material unsupported claims in this audit.
- Existing failing rows such as PQ0013 are outside this pass-only review. Their failures were not relabelled or duplicated as new findings.
- Generation-context provenance proves which material was supplied, not sentence-level entailment. These examples illustrate why mechanical numbers, units, language and action checks must not be described as full semantic correctness.
