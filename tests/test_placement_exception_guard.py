"""Source-derived date-premise guard tests; no inference calls."""
import copy
import json

import pytest

@pytest.fixture(scope='module')
def staged():
    from src import placement_conditions as helper
    from src import document_answers as answers
    return helper, answers


@pytest.fixture
def placement():
    sources = [
        {'id':'WINDOWS-X','text':'| Garments and bags | 12 days | cloth_x |',
         'doc_type':'policy','status':'current','effective_from':'2030-01-01'},
        {'id':'EXCEPTION-Y','text':'Garments and bags from orders **placed between 03 April and 11 April 2031** can be returned within 24 days of delivery. All other categories follow the normal windows.',
         'doc_type':'policy','status':'current','effective_from':'2030-01-01'},
    ]
    facts = {'reference_date':'2031-05-01','public_context':{'sku':'ITEM-A'},
             'return_policy':{'category':'cloth_x','category_label':'Garments and bags',
                              'window_calendar_days':12,'source_ids':['WINDOWS-X'],'selection':'standard_window',
                              'placement_exception':{'placed_from':'2031-04-03','placed_through':'2031-04-11',
                                                     'window_calendar_days':24,'source_ids':['EXCEPTION-Y']},
                              'placement_date_unavailable':True}}
    return facts, sources


@pytest.fixture
def delivery():
    sources = [
        {'id':'WINDOWS-Z','text':'| Electrical devices and accessories | 6 days | devices_x |',
         'doc_type':'policy','status':'current','effective_from':'2030-01-01'},
        {'id':'HISTORY-Q','text':'From **4 March 2031**, the return window for electrical devices and accessories is 6 days. Electrical devices **delivered before 4 March 2031** keep the earlier 9-day window from version 2 of this policy.',
         'doc_type':'policy','status':'current','effective_from':'2030-01-01'},
    ]
    facts = {'reference_date':'2031-05-01','public_context':{'sku':'ITEM-B'},
             'return_policy':{'category':'devices_x','category_label':'Electrical devices and accessories',
                              'window_calendar_days':6,'source_ids':['WINDOWS-Z'],'selection':'standard_window',
                              'historical_exception':{'delivery_before':'2031-03-04',
                                                      'window_calendar_days':9,'source_ids':['HISTORY-Q']}}}
    return facts, sources


def check(staged, answer, fixture):
    helper, answers = staged
    facts, sources = fixture
    helper.check_placement_exception_answer(answer, facts, sources, normalizer=answers._constraint_text)


def test_missing_placement_remains_unknown_and_does_not_infer_from_reference_date(staged, placement):
    helper, _ = staged
    facts, sources = placement
    status = helper.placement_exception_status(facts, sources)
    assert status['applicability'] == 'unknown'
    assert status['placement_date'] is None and status['input_origin'] == 'missing'
    assert status['placed_from'] == '2031-04-03' and status['placed_through'] == '2031-04-11'
    assert status['window_calendar_days'] == 24


@pytest.mark.parametrize('answer',[
    'You have 12 days under the standard window. Since the order was placed between 3 April and 11 April 2031, it qualifies for 24 days.',
    'Because your order was placed during this period, it qualifies for 24 days.',
    'Your order was not placed during this period, so the standard window applies.',
    'You placed the order during this period.',
    'Agar item unused hai, since your order was placed in this period it qualifies for 24 days.',
    '\u0915\u094d\u092f\u094b\u0902\u0915\u093f \u0906\u092a\u0915\u093e \u0911\u0930\u094d\u0921\u0930 \u0907\u0938 \u0905\u0935\u0927\u093f \u092e\u0947\u0902 \u0915\u093f\u092f\u093e \u0917\u092f\u093e \u0925\u093e, \u0906\u092a\u0915\u094b 24 \u0926\u093f\u0928 \u092e\u093f\u0932\u0924\u0947 \u0939\u0948\u0902\u0964',
    'Kyunki aapka order is range mein place hua tha, aapko 24 din milte hain.',
])
def test_missing_placement_cannot_become_a_factual_customer_premise(staged, placement, answer):
    with pytest.raises(ValueError, match='invented_placement_premise'):
        check(staged, answer, placement)


@pytest.mark.parametrize('answer',[
    'Your order qualifies for 24 days.',
    'It qualifies for twenty-four days.',
    'You get 24 days to return it.',
    'Aapko 24 din milte hain.',
    '\u0906\u092a\u0915\u094b 24 \u0926\u093f\u0928 \u092e\u093f\u0932\u0924\u0947 \u0939\u0948\u0902\u0964',
])
def test_exception_entitlement_requires_its_placement_premise(staged, placement, answer):
    with pytest.raises(ValueError, match='unsupported_placement_exception_entitlement'):
        check(staged, answer, placement)


@pytest.mark.parametrize('answer',[
    'You have 12 days under the standard window.',
    'The standard window is 12 days. If your order was placed between 3 April and 11 April 2031, you get 24 days.',
    'You get 24 days if your order was placed during the stated period.',
    'For orders placed between 3 April and 11 April 2031, the window is 24 days.',
    'I cannot confirm your order was placed during that period.',
    'Your order date is unavailable. The exception may apply depending on that date.',
    '\u0938\u093e\u092e\u093e\u0928\u094d\u092f \u0905\u0935\u0927\u093f 12 \u0926\u093f\u0928 \u0939\u0948\u0964 \u092f\u0926\u093f \u0906\u092a\u0915\u093e \u0911\u0930\u094d\u0921\u0930 \u0907\u0938 \u0905\u0935\u0927\u093f \u092e\u0947\u0902 \u0915\u093f\u092f\u093e \u0917\u092f\u093e \u0925\u093e, \u0906\u092a\u0915\u094b 24 \u0926\u093f\u0928 \u092e\u093f\u0932\u0947\u0902\u0917\u0947\u0964',
    'Agar aapka order is period mein place hua tha, aapko 24 din milenge.',
])
def test_standard_and_conditional_placement_explanations_need_no_date(staged, placement, answer):
    check(staged, answer, placement)


@pytest.mark.parametrize('record', ['public_context', 'verified_order'])
@pytest.mark.parametrize('value', ['2031-04-03', '2031-04-07', '2031-04-11'])
def test_known_placement_inside_inclusive_source_range_allows_exception(staged, placement, record, value):
    helper, _ = staged
    facts, sources = copy.deepcopy(placement)
    facts['return_policy'].pop('placement_date_unavailable')
    facts.setdefault(record, {})['placed_at' if record == 'verified_order' else 'placed_on'] = value
    status = helper.placement_exception_status(facts, sources)
    assert status['applicability'] == 'met'
    assert status['input_origin'] == ('verified_order' if record == 'verified_order' else 'customer_provided_unverified')
    check(staged, 'Your order qualifies for 24 days.', (facts, sources))


@pytest.mark.parametrize('value', ['2031-04-02', '2031-04-12'])
def test_known_placement_outside_source_range_cannot_claim_exception(staged, placement, value):
    facts, sources = copy.deepcopy(placement)
    facts['return_policy'].pop('placement_date_unavailable')
    facts['public_context']['placed_on'] = value
    with pytest.raises(ValueError, match='unsupported_placement_exception_entitlement'):
        check(staged, 'Your order qualifies for 24 days.', (facts, sources))


def test_verified_date_has_priority_without_promoting_public_claim(staged, placement):
    helper, _ = staged
    facts, sources = copy.deepcopy(placement)
    facts['return_policy'].pop('placement_date_unavailable')
    facts['verified_order'] = {'placed_at':'2031-04-02T10:20:00'}
    facts['public_context']['placed_on'] = '2031-04-07'
    status = helper.placement_exception_status(facts, sources)
    assert status['applicability'] == 'not_met' and status['input_origin'] == 'verified_order'


@pytest.mark.parametrize('tamper', ['missing','superseded','future','category','interval','duration','flag','type','invalid_input'])
def test_placement_constraint_is_independently_bound_to_current_source(staged, placement, tamper):
    helper, _ = staged
    facts, sources = copy.deepcopy(placement)
    if tamper == 'missing': sources.pop()
    elif tamper == 'superseded': sources[1]['status'] = 'superseded'
    elif tamper == 'future': sources[1]['effective_from'] = '2099-01-01'
    elif tamper == 'category': sources[0]['text'] = sources[0]['text'].replace('cloth_x','other_x')
    elif tamper == 'interval': sources[1]['text'] = sources[1]['text'].replace('03 April','04 April')
    elif tamper == 'duration': sources[1]['text'] = sources[1]['text'].replace('24 days','25 days')
    elif tamper == 'flag': facts['return_policy']['placement_date_unavailable'] = False
    elif tamper == 'type': facts['return_policy']['placement_exception']['window_calendar_days'] = True
    else: facts['public_context']['placed_on'] = 'yesterday'
    with pytest.raises(ValueError, match='unbound_'):
        helper.placement_exception_status(facts, sources)


def test_changed_source_changes_constraint_instead_of_preserving_original_policy(staged, placement):
    helper, _ = staged
    facts, sources = copy.deepcopy(placement)
    sources[1]['text'] = sources[1]['text'].replace('03 April','20 April').replace('11 April','25 April').replace('24 days','28 days')
    facts['return_policy']['placement_exception'].update(placed_from='2031-04-20', placed_through='2031-04-25', window_calendar_days=28)
    facts['return_policy'].pop('placement_date_unavailable')
    facts['public_context']['placed_on'] = '2031-04-22'
    status = helper.placement_exception_status(facts, sources)
    assert status['applicability'] == 'met' and status['window_calendar_days'] == 28
    check(staged, 'Your order qualifies for 28 days.', (facts, sources))


@pytest.mark.parametrize('answer',[
    'The current window is 6 days. Since the delivery date of the product is after this date, the current window applies.',
    'Your item was delivered after this date, so the current return window applies.',
    'Because you received the item after the cutoff, you have 6 days.',
    'Your delivery date is before this date, so the earlier window applies.',
    'Your item was not delivered before that date.',
    'If it is unused, because your product was delivered after the cutoff it has the current window.',
    '\u0915\u094d\u092f\u094b\u0902\u0915\u093f \u0906\u092a\u0915\u093e \u0909\u0924\u094d\u092a\u093e\u0926 \u0907\u0938 \u0924\u093f\u0925\u093f \u0915\u0947 \u092c\u093e\u0926 \u0921\u093f\u0932\u0940\u0935\u0930 \u0939\u0941\u0906 \u0925\u093e\u0964',
    'Kyunki aapka item is date ke baad deliver hua tha, current window applies.',
])
def test_missing_delivery_cannot_become_a_factual_customer_premise(staged, delivery, answer):
    with pytest.raises(ValueError, match='invented_delivery_premise'):
        check(staged, answer, delivery)


@pytest.mark.parametrize('answer',[
    'No, the current return window is 6 days.',
    'The current window is 6 days. Items delivered before 4 March 2031 keep the earlier 9-day window.',
    'If your item was delivered before 4 March 2031, you get 9 days. Otherwise the current window is 6 days.',
    'You have 9 days if your item was delivered before the cutoff.',
    'For products delivered before this date, the earlier window applies.',
    'I do not know whether your item was delivered before the cutoff.',
    'Your delivery date is unavailable. The current general policy is 6 days.',
])
def test_default_current_and_conditional_historical_explanations_need_no_delivery_date(staged, delivery, answer):
    check(staged, answer, delivery)


@pytest.mark.parametrize('answer', ['You have 9 days.', 'Your product has nine days to be returned.'])
def test_historical_entitlement_requires_delivery_before_actual_cutoff(staged, delivery, answer):
    with pytest.raises(ValueError, match='unsupported_delivery_exception_entitlement'):
        check(staged, answer, delivery)


@pytest.mark.parametrize('record', ['public_context', 'verified_order'])
@pytest.mark.parametrize('value, expected', [('2031-03-03','met'), ('2031-03-04','not_met'), ('2031-03-05','not_met')])
def test_known_delivery_uses_strict_source_cutoff(staged, delivery, record, value, expected):
    helper, _ = staged
    facts, sources = copy.deepcopy(delivery)
    facts.setdefault(record, {})['delivered_on'] = value
    status = helper.delivery_exception_status(facts, sources)
    assert status['applicability'] == expected
    if expected == 'met':
        check(staged, 'You have 9 days.', (facts, sources))
    else:
        with pytest.raises(ValueError, match='unsupported_delivery_exception_entitlement'):
            check(staged, 'You have 9 days.', (facts, sources))
        check(staged, 'Your item was delivered after this date. You have 6 days.', (facts, sources))


@pytest.mark.parametrize('mutation', ['date','duration','missing','superseded','category','type'])
def test_historical_cutoff_is_rebound_to_actual_current_source(staged, delivery, mutation):
    helper, _ = staged
    facts, sources = copy.deepcopy(delivery)
    if mutation == 'date': sources[1]['text'] = sources[1]['text'].replace('4 March 2031','5 March 2031')
    elif mutation == 'duration': sources[1]['text'] = sources[1]['text'].replace('9-day','11-day')
    elif mutation == 'missing': sources.pop()
    elif mutation == 'superseded': sources[1]['status'] = 'superseded'
    elif mutation == 'category': sources[1]['text'] = sources[1]['text'].replace('Electrical devices','Wooden furniture')
    else: facts['return_policy']['historical_exception']['window_calendar_days'] = '9'
    with pytest.raises(ValueError, match='unbound_'):
        helper.delivery_exception_status(facts, sources)


def test_changed_historical_source_changes_cutoff_and_earlier_duration(staged, delivery):
    helper, _ = staged
    facts, sources = copy.deepcopy(delivery)
    sources[1]['text'] = sources[1]['text'].replace('4 March 2031','8 February 2031').replace('9-day','11-day')
    facts['return_policy']['historical_exception'].update(delivery_before='2031-02-08', window_calendar_days=11)
    facts['public_context']['delivered_on'] = '2031-02-07'
    status = helper.delivery_exception_status(facts, sources)
    assert status['applicability'] == 'met' and status['window_calendar_days'] == 11
    check(staged, 'You have 11 days.', (facts, sources))


def test_actual_selected_historical_shape_is_supported(staged, delivery):
    helper, _ = staged
    facts, sources = copy.deepcopy(delivery)
    exception = facts['return_policy'].pop('historical_exception')
    facts['return_policy'].update(exception, selection='historical_window')
    facts['public_context']['delivered_on'] = '2031-03-02'
    assert helper.delivery_exception_status(facts, sources)['applicability'] == 'met'


class ScriptedClient:
    def __init__(self, *values):
        self.values, self.calls, self.last_metrics = list(values), [], {}

    def complete(self, system, user, *args, **options):
        self.calls.append((json.loads(user), options))
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, str):
            value = {'answer':value, 'covered':True, 'needs_clarification':False}
        return json.dumps(value)


@pytest.mark.parametrize('kind', ['placement','delivery'])
def test_normal_generation_repairs_an_invented_date_premise_once(staged, placement, delivery, kind):
    _, answers = staged
    facts, sources = placement if kind == 'placement' else delivery
    bad = 'Since the order was placed during this period, it qualifies for 24 days.' if kind == 'placement' else 'Since the delivery date of the product is after this date, the current window applies.'
    good = 'The standard window is 12 days. If your order was placed during the stated period, the window is 24 days.' if kind == 'placement' else 'The current return window is 6 days. Items delivered before 4 March 2031 keep the earlier 9-day window.'
    client = ScriptedClient(bad, good)
    out = answers.document_reply(client, 'What is the return window?', 'en', sources,
                                 facts=facts, context_provenance=True)
    assert len(client.calls) == 2 and out['repair_attempted'] is True
    assert out['repair_errors'] == ['invented_' + kind + '_premise']
    assert out['answer'] == good and out['citations'] == []
    assert out['provenance_kind'] == 'generation_context'
    assert client.calls[0][0]['source_text'] == client.calls[1][0]['source_text']
    assert client.calls[0][0]['deterministic_facts'] == client.calls[1][0]['deterministic_facts']
    assert 'verified_rule_summary' not in client.calls[1][0]


def test_clarification_flag_cannot_bypass_an_invented_premise(staged, placement):
    _, answers = staged
    facts, sources = placement
    client = ScriptedClient(*[{'answer':'Since your order was placed during this period, it qualifies for 24 days. What date was it?', 'covered':True, 'needs_clarification':True}]*2)
    with pytest.raises(ValueError, match='invented_placement_premise'):
        answers.document_reply(client, 'What is the return window?', 'en', sources,
                               facts=facts, context_provenance=True)
    assert len(client.calls) == 2


def test_repeated_failure_has_no_authored_policy_fallback(staged, delivery):
    _, answers = staged
    facts, sources = delivery
    client = ScriptedClient(*['Since your product was delivered after this date, the current window applies.']*2)
    with pytest.raises(ValueError, match='invented_delivery_premise'):
        answers.document_reply(client, 'What is the return window?', 'en', sources,
                               facts=facts, context_provenance=True)
    assert len(client.calls) == 2


def test_provider_failure_never_generates_policy_prose(staged, placement):
    from src.llm import LLMUnavailable
    _, answers = staged
    facts, sources = placement
    client = ScriptedClient(LLMUnavailable('synthetic outage'))
    with pytest.raises(LLMUnavailable):
        answers.document_reply(client, 'What is the return window?', 'en', sources,
                               facts=facts, context_provenance=True)
    assert len(client.calls) == 1


def test_no_exception_and_no_return_policy_leave_unrelated_answers_untouched(staged):
    helper, _ = staged
    helper.check_placement_exception_answer('Your order was placed yesterday.', {}, [])
    helper.check_placement_exception_answer('The standard window is 8 days.', {'return_policy':{'category':'x'}}, [])


def test_selected_historical_window_can_bind_its_own_source_without_current_table(staged, delivery):
    helper, _ = staged
    facts, sources = copy.deepcopy(delivery)
    exception = facts['return_policy'].pop('historical_exception')
    facts['return_policy'].update(exception, category='electrical_devices', selection='historical_window')
    facts['public_context']['delivered_on'] = '2031-03-02'
    sources.pop(0)
    status = helper.delivery_exception_status(facts, sources)
    assert status['applicability'] == 'met'
    assert status['standard_window_calendar_days'] is None
    check(staged, 'You have 9 days.', (facts, sources))
    facts['return_policy']['category'] = 'wooden_furniture'
    with pytest.raises(ValueError, match='unbound_delivery_exception'):
        helper.delivery_exception_status(facts, sources)


@pytest.mark.parametrize('answer', [
    'If your order was placed between 3 April and 11 April 2031, you get 24 days because the festive return policy applies.',
])
def test_causal_explanation_after_genuine_date_condition_is_allowed(staged, placement, answer):
    check(staged, answer, placement)


@pytest.mark.parametrize('answer', [
    'If the item is unused, your order was placed between 3 April and 11 April 2031 and you get 24 days.',
    'If the item is unused, your order was placed during that period.',
])
def test_unrelated_conditional_cannot_rescue_invented_date(staged, placement, answer):
    with pytest.raises(ValueError, match='invented_placement_premise'):
        check(staged, answer, placement)


def test_unrelated_condition_cannot_authorize_exception_duration(staged, placement):
    with pytest.raises(ValueError, match='unsupported_placement_exception_entitlement'):
        check(staged, 'If the item is unused, you get 24 days.', placement)
