"""Adversarial grounding checks run entirely on supplied text and fake clients."""
import json

import pytest

from src.grounding import compatible, generate, validate_generated
from src.kb import KnowledgeBase


REFUND = 'UPI refunds take 1 to 3 business days after initiation.'
REFUND_SOURCE = {'id': 'REF-2', 'text': REFUND + ' Wallet refunds arrive within 2 hours.'}


def response(answer, quote=REFUND, source_id='REF-2'):
    return {'covered': True, 'answer': answer, 'citations': [{'id': source_id, 'quote': quote}]}


@pytest.mark.parametrize('answer', [
    'Your order has been cancelled.',
    'Your refund was issued.',
    'Your refund has been initiated.',
    'Your pickup was scheduled.',
    'Your refund has already been processed.',
    'Cancellation complete.',
    'Your ticket is created.',
    'We have just approved the replacement.',
    'Your refund was issued, though no bank transfer is possible.',
    'आपका ऑर्डर रद्द कर दिया गया है।',
    'आपका ऑर्डर रद्द किया गया है।',
    'आपका रिफ़ंड जारी कर दिया गया है।',
    'टिकट बनाया गया है।',
    'Order cancel kar diya hai.',
    'Refund ho gaya hai.',
])
def test_forged_completed_outcomes_are_rejected_including_passive_and_multilingual(answer):
    with pytest.raises(ValueError, match='unsupported_action'):
        validate_generated(response(answer), [REFUND_SOURCE], ['REF-2'])


@pytest.mark.parametrize('answer,quote,error', [
    ('UPI refunds take 1 to 3 calendar days.', REFUND, 'unsupported_quantity_unit'),
    ('UPI refunds take 1 to 3 days.', REFUND, 'unsupported_quantity_unit'),
    ('UPI refunds take ninety-nine business days.', REFUND, 'unsupported_number'),
    ('You receive five hundred rupees.', REFUND, 'unsupported_number'),
    ('आपको पांच सौ रुपये मिलेंगे।', REFUND, 'unsupported_number'),
    ('UPI refunds take 1 to 3 business days, and your fee is 2 rupees.', REFUND, 'unsupported_number'),
    ('UPI refunds take 1 to 3 business days, and your fee is 2 rupees.', REFUND_SOURCE['text'], 'unsupported_quantity_unit'),
])
def test_numbers_and_units_require_support_in_the_exact_quotes(answer, quote, error):
    with pytest.raises(ValueError, match=error):
        validate_generated(response(answer, quote), [REFUND_SOURCE], ['REF-2'])


def test_yearly_fee_does_not_authorize_a_return_window_with_the_same_number():
    source = {'id': 'PLS-1', 'text': 'Plus costs 999 rupees per year.'}
    value = response('Your return window is 999 days.', source['text'], source['id'])
    with pytest.raises(ValueError, match='unsupported_quantity_unit'):
        validate_generated(value, [source], [source['id']])


def test_unrelated_negation_cannot_replace_the_required_policy_exclusion():
    source = {'id': 'PLS-2', 'text': 'Plus does not extend return windows or refund timelines.'}
    value = response('Plus extends return windows; Wallet cannot transfer to a bank.', source['text'], source['id'])
    with pytest.raises(ValueError, match='omitted_negative_condition'):
        validate_generated(value, [source], [source['id']], required_text=source['text'])


@pytest.mark.parametrize('answer', [
    "You'll normally receive your UPI refund in one to three working days after it starts.",
    'UPI refunds take 1 to 3 business days after they start.',
    'UPI रिफंड शुरू होने के बाद एक से तीन कार्यदिवस लगते हैं।',
])
def test_supported_paraphrases_and_number_words_remain_valid(answer):
    actual, ids = validate_generated(response(answer), [REFUND_SOURCE], ['REF-2'], required_text=REFUND)
    assert actual == answer and ids == ['REF-2']


@pytest.mark.parametrize('source_text,answer', [
    ('Before shipping, cancellation is free in the app under My Orders.', 'Before shipping, you can cancel in My Orders.'),
    ('A shipped order cannot be cancelled; you can return an eligible item after delivery.', 'You cannot cancel after dispatch; returning an eligible item is another option.'),
    ('Wallet credit cannot be transferred to a bank.', 'Wallet credit cannot go to a bank account.'),
    ('Plus does not extend return windows or refund timelines.', 'Plus does not lengthen return windows or refund timelines.'),
])
def test_guidance_and_preserved_negative_conditions_are_not_completed_actions(source_text, answer):
    source = {'id': 'RULE-1', 'text': source_text}
    value = response(answer, source_text, source['id'])
    assert validate_generated(value, [source], ['RULE-1'], required_text=source_text)[0] == answer


def test_deterministic_facts_can_support_computed_dates_and_typed_amounts():
    source = {'id': 'RET-2', 'text': 'The return window is 7 calendar days.'}
    answer = 'Your deadline is 22 October 2026, and the pickup fee is 49 rupees.'
    facts = {'deadline': '2026-10-22', 'pickup_fee_inr': 49}
    value = response(answer, source['text'], source['id'])
    assert validate_generated(value, [source], [source['id']], facts)[0] == answer


@pytest.mark.parametrize('citation', [
    {'id': 'FORGED-1', 'quote': REFUND},
    {'id': 'REF-2', 'quote': 'UPI refunds take 90 business days.'},
    {'id': ['REF-2'], 'quote': REFUND},
])
def test_unknown_or_forged_citations_are_rejected(citation):
    value = response(REFUND)
    value['citations'] = [citation]
    with pytest.raises(ValueError, match='unsupported_citation'):
        validate_generated(value, [REFUND_SOURCE], ['REF-2'])


def test_policy_binding_changes_when_text_or_authority_metadata_changes():
    source = KnowledgeBase().chunks['REF-2'].public()
    assert compatible(['REF-2'], [source])
    changed = dict(source, text=source['text'] + '\nDifferent governing rule.')
    assert not compatible(['REF-2'], [changed])
    changed = dict(source, status='superseded')
    assert not compatible(['REF-2'], [changed])


def test_private_generation_disables_output_cache_and_revalidates_model_text():
    class FakeClient:
        def complete(self, system, user, json_mode, **kwargs):
            self.kwargs = kwargs
            self.payload = json.loads(user)
            value=response('Your refund was issued.');value.pop('covered');value['decision']='answer'
            return json.dumps(value)
    client = FakeClient()
    with pytest.raises(ValueError, match='unsupported_action'):
        generate(client, 'A safe policy question', 'en', [REFUND_SOURCE], private=True)
    assert client.kwargs['cache'] is False
    assert client.payload['question'] == 'A safe policy question'

@pytest.mark.parametrize('conditional', [
    'after the refund is initiated',
    'once a refund has been initiated',
    'when the refund is completed',
    'if the payment is processed',
])
def test_generic_conditional_prerequisites_do_not_claim_a_customer_action(conditional):
    answer = f'A refund to UPI typically takes 1 to 3 business days {conditional}.'
    # This test isolates forged-action detection. Completion/processing are
    # not equivalent to the required initiation clock, tested separately below.
    assert validate_generated(response(answer), [REFUND_SOURCE], ['REF-2'])[0] == answer


@pytest.mark.parametrize('answer', [
    'After I checked, your refund has been issued.',
    'Once approved, I have issued your refund.',
    'After the refund is initiated, I have processed your return.',
    'If the refund is processed, your ticket is created.',
    'Once your refund has been issued, the bank will credit it.',
])
def test_conditional_words_do_not_hide_completed_customer_or_agent_actions(answer):
    with pytest.raises(ValueError, match='unsupported_action'):
        validate_generated(response(answer), [REFUND_SOURCE], ['REF-2'])

@pytest.mark.parametrize('answer', [
    'UPI refunds take 1 to 3 business days.',
    'UPI refunds take 1 to 3 business days when the refund is completed.',
    'UPI refunds take 1 to 3 business days if the payment is processed.',
])
def test_generation_cannot_drop_or_replace_the_initiation_clock(answer):
    with pytest.raises(ValueError, match='omitted_policy_aspect:initiation'):
        validate_generated(response(answer), [REFUND_SOURCE], ['REF-2'], required_text=REFUND)


def test_source_background_does_not_create_unrequested_aspect_requirements():
    source = dict(REFUND_SOURCE, text=REFUND + ' A brand warranty claim requires packaging and photos.')
    assert validate_generated(response(REFUND, source['text']), [source], ['REF-2'], required_text=REFUND)[0] == REFUND


@pytest.mark.parametrize('required,answer,missing', [
    ('The seller follows the same return policy. The pickup fee is 49 rupees.',
     'The pickup fee is 49 rupees.', 'seller_policy_equivalence'),
    ('The product has 3 months of brand warranty plus 12 months of additional Assured coverage. Claim the brand warranty through the manufacturer service centre and Assured in My Orders.',
     'It has 3 months of brand warranty and 12 months of additional Assured cover in My Orders.', 'service_centre'),
    ('The return refund starts after quality check. The pickup fee is 49 rupees.',
     'The return refund starts after pickup and the pickup fee is 49 rupees.', 'quality_check'),
    ('Keep the original tags, packaging and accessories.',
     'Keep the original packaging and accessories.', 'tags'),
])
def test_missing_nonnumeric_multipart_aspects_are_rejected(required, answer, missing):
    source = {'id': 'RULE-1', 'text': required}
    with pytest.raises(ValueError, match='omitted_policy_aspect:' + missing):
        validate_generated(response(answer, required, 'RULE-1'), [source], ['RULE-1'], required_text=required)


@pytest.mark.parametrize('answer', [
    'Identical return rules apply; the pickup charge is 49 rupees.',
    'रिटर्न के समान नियम लागू हैं; पिकअप फ़ीस 49 रुपये है।',
    'Same return rules apply hote hain; pickup charge 49 rupees hai.',
])
def test_policy_aspect_synonyms_allow_ordinary_multilingual_paraphrases(answer):
    required = 'The seller follows the same return policy. The pickup fee is 49 rupees.'
    source = {'id': 'RULE-1', 'text': required}
    assert validate_generated(response(answer, required, 'RULE-1'), [source], ['RULE-1'], required_text=required)[0] == answer


def test_legacy_adapter_never_sends_an_authored_plan_even_if_long():
    from src.answering import Plan
    plan = Plan('return', 'answer', 'AUTHORED POLICY ' * 200, 'a' * 1801, 'a' * 1801, ['REF-2'])
    class Client:
        def complete(self, system, user, *args, **kwargs):
            payload=json.loads(user)
            assert 'verified_rule_summary' not in payload
            assert 'AUTHORED POLICY' not in user
            return json.dumps({'answer':REFUND,'decision':'answer',
                'citations':[{'id':'REF-2','quote':REFUND}]})
    assert generate(Client(), 'A multi-part question', 'en', [REFUND_SOURCE], plan)[0]==REFUND
