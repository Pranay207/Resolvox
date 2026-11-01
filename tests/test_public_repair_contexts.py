"""Focused repair remains bound to mutable policies and every requested topic."""
import copy
import json
from datetime import date
import pytest
from src.repair_contexts import unresolved_return_window_inputs, delivery_attempt_inputs
from src.document_answers import document_reply


def window_fixture(ordinary=12, extended=24):
    sources = [
        {'id': 'WINDOW-2', 'text': f'| Garments and bags | {ordinary} days | cloth_x |', 'doc_type': 'policy', 'status': 'current', 'effective_from': '2030-01-01'},
        {'id': 'WINDOW-8', 'text': f'Garments and bags from orders **placed between 03 April and 11 April 2031** can be returned within {extended} days of delivery.', 'doc_type': 'policy', 'status': 'current', 'effective_from': '2030-01-01'},
        {'id': 'CLOCK-1', 'text': 'Return windows are counted in calendar days from the delivery date.', 'doc_type': 'policy', 'status': 'current', 'effective_from': '2030-01-01'},
        {'id': 'CATALOG-A', 'text': json.dumps({'sku': 'ITEM-X', 'title': 'Aster Bag', 'return_category': 'cloth_x'}), 'doc_type': 'catalog', 'status': 'current'},
    ]
    facts = {'reference_date': '2031-05-12', 'return_policy': {
        'category': 'cloth_x', 'category_label': 'Garments and bags', 'window_calendar_days': ordinary,
        'source_ids': ['WINDOW-2'], 'selection': 'standard_window', 'placement_date_unavailable': True,
        'placement_exception': {'placed_from': '2031-04-03', 'placed_through': '2031-04-11', 'window_calendar_days': extended, 'source_ids': ['WINDOW-8']}},
        'answer_constraints': [{'kind': 'quantity', 'value': ordinary, 'unit': 'calendar_day', 'key': 'return_policy.window_calendar_days', 'source_ids': ['WINDOW-2']}]}
    return facts, sources

@pytest.mark.parametrize('ordinary,extended', [(12,24), (17,31), (8,19)])
def test_unresolved_window_values_are_rebound_to_changed_source_and_inputs_stay_unchanged(ordinary, extended):
    facts, sources = window_fixture(ordinary, extended)
    before = copy.deepcopy((facts, sources))
    out = unresolved_return_window_inputs(facts, sources)
    assert out['placement_scope']['standard_window_calendar_days'] == ordinary
    assert out['placement_scope']['window_calendar_days'] == extended
    assert out['placement_scope']['placement_date'] is None
    assert out['placement_scope']['applicability'] == 'unknown'
    assert {s['id'] for s in out['sources']} == {s['id'] for s in sources}
    assert (facts, sources) == before

@pytest.mark.parametrize('placed', ['2031-04-05', '2031-04-15'])
def test_known_placement_never_uses_unknown_date_repair(placed):
    facts, sources = window_fixture()
    facts['return_policy']['placement_date_unavailable'] = False
    facts['public_context'] = {'placed_on': placed}
    assert unresolved_return_window_inputs(facts, sources) is None


def test_forged_window_value_is_rejected_instead_of_entering_repair():
    facts, sources = window_fixture()
    facts['return_policy']['placement_exception']['window_calendar_days'] += 1
    with pytest.raises(ValueError, match='unbound_placement_exception'):
        unresolved_return_window_inputs(facts, sources)


def attempt_fixture(limit=4):
    sources = [
        {'id': 'ATTEMPT-4', 'text': f'The courier makes up to {limit} delivery attempts. After a failed attempt the customer gets an SMS to reschedule. If the last attempt fails, the parcel is returned to the warehouse and REFUND-6 applies.', 'doc_type': 'policy', 'status': 'current', 'effective_from': '2030-01-01'},
        {'id': 'REFUND-6', 'text': 'Prepaid orders not delivered after the last attempt receive a refund once the parcel reaches the warehouse.', 'doc_type': 'policy', 'status': 'current', 'effective_from': '2030-01-01'},
        {'id': 'UNRELATED-2', 'text': 'Reverse pickup is arranged from the delivery address.', 'doc_type': 'policy', 'status': 'current', 'effective_from': '2030-01-01'},
    ]
    constraint = {'kind': 'number', 'value': limit, 'key': 'delivery_policy.delivery_attempt_limit', 'source_ids': ['ATTEMPT-4']}
    facts = {'reference_date': '2031-05-12', 'delivery_policy': {'delivery_attempt_limit': limit, 'source_ids': ['ATTEMPT-4']}, 'answer_constraints': [constraint]}
    return facts, sources, [constraint]

@pytest.mark.parametrize('limit', [4,7,9])
def test_delivery_attempt_repair_uses_actual_limit_and_linked_sections(limit):
    facts, sources, constraints = attempt_fixture(limit)
    before = copy.deepcopy((facts, sources, constraints))
    out = delivery_attempt_inputs(facts, sources, constraints)
    assert out['facts']['delivery_policy']['delivery_attempt_limit'] == limit
    assert {s['id'] for s in out['sources']} == {'ATTEMPT-4','REFUND-6'}
    assert (facts, sources, constraints) == before

@pytest.mark.parametrize('change', ['missing_dependency','wrong_source_limit','wrong_fact_limit','nonpolicy','future'])
def test_unsupported_attempt_context_does_not_gain_authority(change):
    facts, sources, constraints = attempt_fixture()
    if change == 'missing_dependency': sources.pop(1)
    if change == 'wrong_source_limit': sources[0]['text'] = sources[0]['text'].replace('up to 4', 'up to 6')
    if change == 'wrong_fact_limit': facts['delivery_policy']['delivery_attempt_limit'] = 8
    if change == 'nonpolicy': sources[0]['doc_type'] = 'marketing'
    if change == 'future': sources[0]['effective_from'] = '2035-01-01'
    assert delivery_attempt_inputs(facts, sources, constraints) is None

class Client:
    def __init__(self, *responses): self.responses=list(responses); self.calls=[]
    def complete(self, system, user, **options):
        self.calls.append((system,json.loads(user),options)); assert self.responses
        return json.dumps(self.responses.pop(0))

def value(answer, covered=True): return {'answer': answer,'covered':covered,'needs_clarification':False}


def test_general_window_repair_never_assigns_the_missing_personal_date(monkeypatch):
    import src.document_answers as module
    monkeypatch.setattr(module,'REFERENCE_DATE',date(2031,5,12))
    facts, sources = window_fixture()
    good = 'The standard return window is 12 calendar days from delivery. For orders placed between 03 April and 11 April 2031, the window is 24 calendar days from delivery.'
    client = Client(value('Your item can be returned within 12 days.'),value(good))
    out = document_reply(client,'How long can I return my Aster Bag?','en',sources,facts=facts,context_provenance=True)
    assert out['answer'] == good and out['repair_mode'] == 'source_window_scope'
    assert out['repair_errors'] == ['unsupported_placement_exception_personal_window']
    payload = client.calls[1][1]
    assert payload['placement_scope']['input_origin'] == 'missing'
    assert client.calls[0][1]['deterministic_facts'] == payload['deterministic_facts']
    assert payload['question'] == 'How long can I return my Aster Bag?'
    assert 'previous_response' not in payload
    assert client.calls[1][2]['cache'] is False
    assert out['repair_scope_check']['focused_context_allowed'] is True


def test_delivery_repair_preserves_count_and_linked_conditions_with_full_final_validation(monkeypatch):
    import src.document_answers as module
    monkeypatch.setattr(module,'REFERENCE_DATE',date(2031,5,12))
    facts,sources,_ = attempt_fixture()
    good = 'The courier can make up to 4 delivery attempts. After a failed attempt the customer gets an SMS to reschedule. If the last attempt fails, the parcel would return to the warehouse.'
    client = Client(value('The courier makes up to 4 delivery attempts. I have issued your refund.'),value(good))
    out = document_reply(client,'What happens if I miss a courier delivery?','en',sources,facts=facts,context_provenance=True)
    assert out['answer'] == good and out['repair_mode'] == 'source_attempt_restatement'
    assert out['repair_errors'] == ['unsupported_action']
    payload = client.calls[1][1]
    assert {s['id'] for s in payload['source_text']} == {'ATTEMPT-4','REFUND-6'}
    assert 'question' not in payload and client.calls[1][2]['cache'] is False
    assert 'Do not discuss refunds or payment methods.' in client.calls[1][0]


def test_compound_question_keeps_original_context_when_focus_would_drop_a_topic(monkeypatch):
    import src.document_answers as module
    monkeypatch.setattr(module,'REFERENCE_DATE',date(2031,5,12))
    facts,sources = window_fixture()
    sources.append({'id':'ASSURED-1','text':'The Assured warranty is 17 months.','doc_type':'policy','status':'current'})
    client = Client(value('Your item can be returned within 12 days.'),value('I cannot confirm the full requested information.',covered=False))
    out = document_reply(client,'How long can I return my bag, and what Assured warranty applies?','en',sources,facts=facts,context_provenance=True)
    assert out.get('repair_mode') != 'source_window_scope'
    assert out['repair_scope_check']['focused_context_allowed'] is False
    assert 'question' in client.calls[1][1]
    assert {s['id'] for s in client.calls[1][1]['source_text']} == {s['id'] for s in sources}


@pytest.mark.parametrize('event', ['return','cancellation','rto'])
def test_operational_refund_view_keeps_record_roles_and_host_facts_unchanged(event):
    from src.repair_contexts import operational_refund_explanation_inputs
    facts={'reference_date':'2031-05-01','verified_order':{'status':'pending',event+'_refund_initiated_on':'2031-04-01',event+'_rrn':'REF-2468','phone':'private','items':[{'sku':'unrelated'}]},
           'operational_escalation':{'reason':'refund_overdue','binding_status':'bound','source_ids':['MUTABLE-RANGE'],
               'facts':{'refund_event':event,'maximum_date':'2031-04-09','maximum_business_days':7,'elapsed_business_days_past_maximum':18},
               'calculations':[{'result':{'elapsed_business_days_past_maximum':18}}]}}
    before=copy.deepcopy(facts)
    view=operational_refund_explanation_inputs('Where is my refund?',facts,[{'id':'MUTABLE-RANGE'}])
    assert view['verified_order'][event+'_rrn']=='REF-2468'
    assert view['operational_escalation']['facts']['maximum_business_days']==7
    assert view['operational_escalation']['facts']['maximum_date']=='2031-04-09'
    assert 'elapsed_business_days_past_maximum' not in view['operational_escalation']['facts']
    assert not {'phone','items'} & view['verified_order'].keys()
    assert facts==before
    assert operational_refund_explanation_inputs('What about the coupon discount?',facts,[{'id':'MUTABLE-RANGE'}]) is None
    assert operational_refund_explanation_inputs('Where is my refund?',facts,[]) is None



def test_unknown_public_return_window_keeps_requested_fee_evidence():
 facts,sources=window_fixture(12,24)
 fee={'id':'FEE-MUTATED','doc_type':'policy','status':'current','effective_from':'2030-01-01',
      'text':'A reverse pickup fee of 73 rupees applies to change-of-mind returns of Garments and bags.'}
 # Use the exact source category words; the value is read from text, never a runtime constant.
 fee['text']='A reverse pickup fee of 73 rupees applies to change-of-mind returns of '+facts['return_policy']['category_label']+'.'
 sources=sources+[fee,dict(fee,id='FUTURE-FEE',effective_from='2099-01-01')]
 before=copy.deepcopy((facts,sources))
 view=unresolved_return_window_inputs(facts,sources,query='What is the return window and pickup charge?')
 assert 'FEE-MUTATED' in {row['id'] for row in view['sources']}
 assert 'FUTURE-FEE' not in {row['id'] for row in view['sources']}
 assert (facts,sources)==before
