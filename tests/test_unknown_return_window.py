"""Source-bound unresolved placement checks, synthetic mutations, fake clients."""
import copy
import json
import socket
import pytest
import requests
from src import document_answers as answers
from src import placement_conditions as placement
ERROR = 'unsupported_placement_exception_personal_window'


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('No network is allowed in return-window checks')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)


@pytest.fixture
def case():
    sources = [
        {'id':'SYNTHETIC-TABLE', 'text':'| Garments and bags | 12 days | fabric_x |', 'doc_type':'policy', 'status':'current', 'effective_from':'2030-01-01'},
        {'id':'SYNTHETIC-EXCEPTION', 'text':'Garments and bags from orders placed between 3 April and 11 April 2031 can be returned within 24 days of delivery.', 'doc_type':'policy', 'status':'current', 'effective_from':'2030-01-01'},
        {'id':'SYNTHETIC-PRODUCT', 'text':json.dumps({'sku':'BAG-X','title':'Orchid Canvas Tote, Blue','return_category':'fabric_x'}), 'doc_type':'catalog', 'status':'current'},
    ]
    facts = {'reference_date':'2031-05-01', 'public_context':{'category':'fabric_x'},
             'return_policy':{'category':'fabric_x','category_label':'Garments and bags','window_calendar_days':12,
                              'source_ids':['SYNTHETIC-TABLE'],'selection':'standard_window','placement_date_unavailable':True,
                              'placement_exception':{'placed_from':'2031-04-03','placed_through':'2031-04-11','window_calendar_days':24,'source_ids':['SYNTHETIC-EXCEPTION']}}}
    return facts, sources


def check(answer, case):
    facts, sources = case
    return placement.check_placement_exception_answer(answer, facts, sources, normalizer=answers._constraint_text)


@pytest.mark.parametrize('answer', [
    'You have 12 days to return it.', 'Your return window is twelve days from delivery.',
    'You may return your purchase within 12 days after delivery.', 'This item has a 12-day return window.',
    'Orchid Canvas Tote can be returned within 12 days after delivery.',
    'Orchid Canvas Tote के लौटाने के लिए 12 दिन का समय मिलेगा।',
    'आपको इसे लौटाने के लिए बारह दिन मिलेंगे।', 'आपकी रिटर्न अवधि १२ दिनों की है।',
    'Aapko ise lautane ke liye barah din milenge.', 'Aapka return window 12 din hai.',
    'Orchid Canvas Tote ko lautane ke liye 12 din milenge.',
    'The general policy is relevant. Your return window is 12 days.',
    'I cannot confirm the placement date, but your return window is 12 days.',
    'I cannot confirm the placement date and your return window is 12 days.',
    'If the item is unused, your return window is 12 days.',
    'If your refund was initiated before 3 April 2031, your return window is 12 days.',
    'If your other order was placed before 3 April 2031, your return window is 12 days.',
    'If your order was placed before 4 April 2031, your return window is 12 days.',
    'If your order was placed before 3 April 2032, your return window is 12 days.',
    'If your order was not placed before 3 April 2031, your return window is 12 days.',
    'If your order was not placed after 11 April 2031, your return window is 12 days.',
    'The standard refund clock is 12 days, but your return window is 12 days.',
    'Normally refunds take 12 days and your return window is 12 days.',
    'You always have 12 days to return it under the standard window.',
    'Your return window is 12 days before pickup.',
    'You have 12 days to request a return before pickup.',
    'Your return request deadline is 12 days before the shipment reaches the warehouse.',
    'You have 12 days from delivery to return Orchid Canvas Tote, as it has a standard 12-day return window.',
])
def test_unqualified_personal_or_named_window_rejected(case, answer):
    with pytest.raises(ValueError, match=ERROR): check(answer, case)


@pytest.mark.parametrize('answer', [
    'The standard return window is 12 days from delivery.', 'You have 12 days under the standard window.',
    'The ordinary return window for your category is 12 days.', 'Orchid Canvas Tote has a standard return window of 12 days.',
    'सामान्य रिटर्न अवधि डिलीवरी से 12 दिन है।', 'Orchid Canvas Tote की सामान्य रिटर्न अवधि 12 दिन है।',
    'Aam taur par return window delivery se 12 din hai.',
    'Your return window is unknown. The general return window is 12 days.',
    'I cannot confirm your return window is 12 days.', 'Your return window is not confirmed to be 12 days.',
    'मैं आपकी 12 दिन की रिटर्न अवधि की पुष्टि नहीं कर सकती।', 'Mujhe nahi pata aapka return window 12 din hai.',
    'Is your return window 12 days?', 'Do you have 12 days to return it?',
    'क्या आपकी रिटर्न अवधि 12 दिन है?', 'Kya aapka return window 12 din hai?',
    'When did you place the order?', 'आपने ऑर्डर कब दिया था?', 'Order ki placement date kya hai?',
    'The standard window is 12 days. If your order was placed during the stated period, you get 24 days.',
    'If your order was placed before 3 April 2031, your return window is 12 days.',
    'Your return window is 12 days if your order was placed after 11 April 2031.',
    'If your order was placed outside 3 April through 11 April 2031, you have 12 days to return it.',
    'If your order was not placed during this period, you have 12 days to return it.',
    'यदि आपका ऑर्डर 3 अप्रैल 2031 से पहले किया गया था, आपकी रिटर्न अवधि 12 दिन है।',
    'Agar aapka order 11 April 2031 ke baad place hua tha, aapka return window 12 din hai.',
])
def test_standard_scope_uncertainty_questions_and_conditions_allowed(case, answer): check(answer, case)


@pytest.mark.parametrize('answer', [
    'Your refund takes 12 days after the return is initiated.',
    'You receive the refund within 12 days after returning the item.',
    'Your return refund takes 12 days after initiation.', 'आपको रिटर्न के बाद रिफंड 12 दिन में मिलेगा।',
    'Aapko return ke baad refund 12 din mein milega.', 'Your refund is not due within 12 days after return.',
    'Your pickup takes 12 days.', 'Your warranty covers 12 days.',
    'Your refund takes 12 days and your return window is unknown.',
    'Your return pickup is scheduled within 12 days.', 'Your return shipment will reach the warehouse within 12 days.',
    'Your return parcel arrives at the warehouse within 12 days.', 'Orchid Canvas Tote return pickup takes 12 days.',
    'Your return collection takes twelve days.', 'Your return pickup window is 12 days.',
    'Your return courier transit takes 12 days.', 'आपका रिटर्न पिकअप 12 दिन में होगा।',
    'आपका रिटर्न पार्सल 12 दिन में गोदाम पहुँचेगा।', 'Aapka return pickup 12 din mein hoga.',
    'Aapka return shipment 12 din mein warehouse pahunchega.',
])
def test_unrelated_refund_logistics_and_other_clocks_allowed(case, answer): check(answer, case)


@pytest.mark.parametrize('record',['public_context','verified_order'])
@pytest.mark.parametrize('placed',['2031-04-02','2031-04-07','2031-04-12'])
def test_known_placement_preserves_existing_behavior(case, record, placed):
    facts, _ = case
    facts['return_policy'].pop('placement_date_unavailable')
    facts.setdefault(record,{})['placed_at' if record=='verified_order' else 'placed_on'] = placed
    check('Your return window is 12 days.', case)


def test_equal_windows_need_no_date(case):
    facts, sources = case
    sources[1]['text'] = sources[1]['text'].replace('24 days','12 days')
    facts['return_policy']['placement_exception']['window_calendar_days'] = 12
    check('Your return window is 12 days.', case)


def test_mutated_duration_and_product_name_drive_check(case):
    facts, sources = case
    sources[0]['text'] = sources[0]['text'].replace('12 days','19 days')
    facts['return_policy']['window_calendar_days'] = 19
    sources[2]['text'] = sources[2]['text'].replace('Orchid Canvas Tote','Lilac Travel Bag')
    with pytest.raises(ValueError,match=ERROR): check('Lilac Travel Bag के लौटाने के लिए 19 दिन मिलेंगे।',case)
    check('Lilac Travel Bag की सामान्य रिटर्न अवधि 19 दिन है।',case)


@pytest.mark.parametrize('mutation',['missing','duration','dates','category','inactive','future'])
def test_actual_source_must_rebind(case, mutation):
    facts, sources = case
    if mutation=='missing': sources.pop(1)
    elif mutation=='duration': sources[1]['text']=sources[1]['text'].replace('24 days','25 days')
    elif mutation=='dates': sources[1]['text']=sources[1]['text'].replace('3 April','4 April')
    elif mutation=='category': sources[0]['text']=sources[0]['text'].replace('fabric_x','other_x')
    elif mutation=='inactive': sources[1]['status']='superseded'
    else: sources[1]['effective_from']='2099-01-01'
    with pytest.raises(ValueError,match='unbound_'): check('Your return window is 12 days.',case)


def test_rebound_interval_requires_new_condition(case):
    facts, sources = case
    sources[1]['text']=sources[1]['text'].replace('3 April','5 June').replace('11 April','17 June')
    facts['return_policy']['placement_exception'].update(placed_from='2031-06-05',placed_through='2031-06-17')
    with pytest.raises(ValueError,match=ERROR): check('If your order was placed after 11 April 2031, your return window is 12 days.',case)
    check('If your order was placed after 17 June 2031, your return window is 12 days.',case)


def test_unaffected_category_has_no_obligation(case):
    facts,sources=case
    facts['return_policy']={'category':'another_category','window_calendar_days':12}
    check('Your return window is 12 days.',(facts,sources))


def test_named_other_category_is_not_bound(case):
    _,sources=case
    sources.append({'id':'SYNTHETIC-OTHER','doc_type':'catalog','status':'current','text':json.dumps({'title':'Lilac Travel Speaker','return_category':'device_y'})})
    check('Your Lilac Travel Speaker return window is 12 days.',case)


def test_named_catalog_evidence_must_be_current(case):
    _,sources=case
    sources[2]['status']='superseded'
    check('Orchid Canvas Tote के लौटाने के लिए 12 दिन का समय मिलेगा।',case)


class Client:
    def __init__(self,*values): self.values,self.calls,self.last_metrics=list(values),[],{}
    def complete(self,system,user,**options):
        self.calls.append((system,json.loads(user),options))
        assert self.values,'Unexpected third attempt'
        return json.dumps(self.values.pop(0))


def generated(answer,covered=True,clarify=False):
    return {'answer':answer,'covered':covered,'needs_clarification':clarify}


def test_fake_generation_uses_existing_uncached_repair(case):
    facts,sources=case
    good='The standard return window is 12 days. If your order was placed during the stated period, you get 24 days.'
    client=Client(generated('You have 12 days to return it.'),generated(good))
    out=answers.document_reply(client,'What is the return window?','en',sources,facts=facts,context_provenance=True)
    assert out['answer']==good and out['repair_errors']==[ERROR]
    assert out['generation_attempts']==len(client.calls)==2
    assert client.calls[0][2]['cache'] is True and client.calls[1][2]['cache'] is False
    assert all(call[2]['attempts']==1 for call in client.calls)
    assert client.calls[1][1]['repair_validation_error']==ERROR
    assert client.calls[0][1]['source_text']==client.calls[1][1]['source_text']
    assert client.calls[0][1]['deterministic_facts']==client.calls[1][1]['deterministic_facts']


def test_fake_generation_asks_placement_without_duration(case):
    facts,sources=case
    client=Client(generated('आपको इसे लौटाने के लिए 12 दिन मिलेंगे।'),generated('कब ऑर्डर दिया था?',False,True))
    out=answers.document_reply(client,'वापस करने के लिए कितने दिन हैं?','hi',sources,facts=facts,private=True,context_provenance=True)
    assert out['answer']=='कब ऑर्डर दिया था?' and out['decision']=='clarify'
    assert out['generation_attempts']==len(client.calls)==2
    assert all(call[2]['cache'] is False for call in client.calls)


def test_two_failed_fake_attempts_stop(case):
    facts,sources=case
    bad=generated('You have 12 days to return it.')
    client=Client(copy.deepcopy(bad),copy.deepcopy(bad))
    with pytest.raises(ValueError,match=ERROR): answers.document_reply(client,'What is the return window?','en',sources,facts=facts,context_provenance=True)
    assert len(client.calls)==2


@pytest.mark.parametrize('answer', [
    "The ordinary window is 12 days, unless your order falls in the stated exception; but because the order date isn't provided, the 12-day window applies.",
    'Since the placement date is unknown, the standard return window of 12 days applies.',
    'The purchase date is missing. Therefore use the ordinary 12-day return window.',
    'Without your order date, we use the standard return period of twelve days.',
    'ऑर्डर की तारीख उपलब्ध नहीं है, इसलिए सामान्य 12 दिन की रिटर्न अवधि लागू है।',
    'Order ki date nahi pata, isliye standard return window 12 din lagu hai.',
])
def test_missing_placement_cannot_select_the_standard_branch(case, answer):
    with pytest.raises(ValueError, match=ERROR):
        check(answer, case)


@pytest.mark.parametrize('answer', [
    'The placement date is unknown. The standard return window is 12 days; the stated placement-date exception remains conditional.',
    'Because the placement date is unknown, I cannot confirm whether the 12-day return window applies.',
    'Without your order date, I can explain the standard return window of 12 days and its conditional exception.',
])
def test_missing_placement_still_allows_general_explanation_and_uncertainty(case, answer):
    check(answer, case)


def test_unicode_hindi_default_claim_without_repeated_return_noun_is_rejected(case):
    answer='सामान्य रिटर्न अवधि 12 दिन है। लेकिन चूँकि ऑर्डर की तिथि उपलब्ध नहीं है, हम सामान्य 12‑दिन की शर्त को लागू मानते हैं।'
    with pytest.raises(ValueError, match=ERROR):
        check(answer, case)


def test_missing_placement_does_not_confuse_refund_or_transport_clocks(case):
    check('The placement date is unknown. The standard return rule has a conditional exception. A refund takes 12 days after initiation.',case)


def test_hindi_conditional_exception_does_not_turn_general_rule_mention_into_default(case):
    check('सामान्य रिटर्न अवधि 12 दिन है। यदि ऑर्डर बताई अवधि में रखा गया हो तो 24 दिन की विशेष विंडो लागू हो सकती है, परन्तु चूँकि ऑर्डर की तिथि उपलब्ध नहीं है, हम सामान्य 12‑दिन नियम का उल्लेख कर रहे हैं।', case)


def test_general_duration_question_with_unknown_placement_requires_conditional_exception(case):
    facts,sources=case
    with pytest.raises(ValueError,match=ERROR):
        placement.check_placement_exception_answer('The return window is 12 calendar days.',facts,sources,
            normalizer=answers._constraint_text,query='How many days can I return it?')
    placement.check_placement_exception_answer('The standard return window is 12 calendar days.',facts,sources,
        normalizer=answers._constraint_text,query='What is the standard return window?')
    placement.check_placement_exception_answer('The standard return window is 12 days. If the order was placed during the stated exception period, it is 24 days.',facts,sources,
        normalizer=answers._constraint_text,query='What is the return window?')
