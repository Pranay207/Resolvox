"""Production-import delivery premise and personal window boundary tests."""
import json
import socket
import pytest
import requests
from src import placement_conditions as module
from src.document_answers import _constraint_text


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*a,**k): pytest.fail('No network permitted')
    monkeypatch.setattr(socket,'create_connection',forbidden)
    monkeypatch.setattr(requests.sessions.Session,'request',forbidden)


@pytest.fixture
def case():
    sources=[{'id':'SYNTHETIC-TABLE','text':'| Portable devices and accessories | 11 days | device_x |','doc_type':'policy','status':'current','effective_from':'2032-01-01'},
             {'id':'SYNTHETIC-HISTORY','text':'From 13 June 2033, the return window for portable devices and accessories is 11 days. Portable devices delivered before 13 June 2033 keep the earlier 17-day window from version 2 of this policy.','doc_type':'policy','status':'current','effective_from':'2032-01-01'}]
    facts={'reference_date':'2033-08-04','return_policy':{'category':'device_x','window_calendar_days':11,'source_ids':['SYNTHETIC-TABLE'],'selection':'standard_window',
           'historical_exception':{'delivery_before':'2033-06-13','window_calendar_days':17,'source_ids':['SYNTHETIC-HISTORY']}}}
    return facts,sources


def check(answer,case):
    facts,sources=case
    return module.check_placement_exception_answer(answer,facts,sources,normalizer=_constraint_text)


@pytest.mark.parametrize('answer',[
    'Since it was delivered yesterday (before 13 June 2033), it falls under the earlier window.',
    'It was delivered before 13 June 2033.', 'It was received yesterday.',
    'This was delivered on 12 June 2033.', 'That has been delivered after the cutoff.',
    'Because it had been delivered before this date, an earlier rule applies.',
    'It was not delivered before the cutoff.',
    'I cannot confirm the delivery date, but it was delivered before the cutoff.',
])
def test_unknown_pronoun_delivery_date_is_not_a_factual_premise(case,answer):
    with pytest.raises(ValueError,match='invented_delivery_premise'): check(answer,case)


@pytest.mark.parametrize('answer',[
    'The item can be returned within its 11-day return window.',
    'If the issue persists, the item can be returned within its eleven-day return window.',
    'The product may be returned within 11 days.', 'The unit must be returned within 11 days.',
    'It can be returned within its 11-day window.',
    'It may be returned within 11 days if it is unused.',
    'If your refund was initiated after 13 June 2033, the item can be returned within 11 days.',
    'If it was delivered after 20 June 2033, the item can be returned within 11 days.',
])
def test_unknown_individual_current_window_needs_actual_delivery_condition(case,answer):
    with pytest.raises(ValueError,match='unsupported_delivery_exception_personal_window'): check(answer,case)


@pytest.mark.parametrize('answer',[
    'The current general return window is 11 days.',
    'Portable devices have an 11-day return window under the current rule.',
    'Items delivered before 13 June 2033 keep the earlier 17-day window.',
    'If it was delivered before 13 June 2033, it qualifies for 17 days.',
    'When it was delivered before the cutoff, the earlier rule applies.',
    'I cannot confirm it was delivered before the cutoff.',
    'I cannot confirm the item can be returned within 11 days.',
    'If it was delivered after 13 June 2033, the item can be returned within 11 days.',
    'The item can be returned within 11 days if it was delivered on or after 13 June 2033.',
    'For products delivered after the cutoff, the item can be returned within its 11-day window.',
    'If delivered after 2033-06-13, it can be returned within 11 days.',
    'The return shipment will reach the warehouse within 11 days.',
    'It was delivered to the warehouse yesterday; a refund clock starts there.',
    'Your return pickup is scheduled within 11 days.',
    'The parcel can be returned to the warehouse within 11 days.',
    'The item will be returned to the warehouse within 11 days.',
])
def test_generic_conditional_uncertain_and_logistics_scopes_remain_allowed(case,answer): check(answer,case)


@pytest.mark.parametrize('record',['public_context','verified_order'])
def test_known_delivery_retains_existing_behavior(case,record):
    facts,_=case
    facts[record]={'delivered_on':'2033-06-15'}
    check('It was delivered after the cutoff. The item can be returned within 11 days.',case)


def test_source_duration_mutation_is_used(case):
    facts,sources=case
    sources[0]['text']=sources[0]['text'].replace('11 days','23 days')
    sources[1]['text']=sources[1]['text'].replace('11 days','23 days')
    facts['return_policy']['window_calendar_days']=23
    with pytest.raises(ValueError,match='unsupported_delivery_exception_personal_window'): check('The item can be returned within its 23-day window.',case)
    check('The current general return window is 23 days.',case)


def test_source_date_mutation_requires_actual_new_cutoff(case):
    facts,sources=case
    sources[1]['text']=sources[1]['text'].replace('13 June 2033','20 July 2033')
    facts['return_policy']['historical_exception']['delivery_before']='2033-07-20'
    with pytest.raises(ValueError,match='unsupported_delivery_exception_personal_window'): check('If it was delivered after 13 June 2033, the item can be returned within 11 days.',case)
    check('If it was delivered after 20 July 2033, the item can be returned within 11 days.',case)


@pytest.mark.parametrize('mutation',['missing','duration','cutoff','inactive','category','future'])
def test_actual_source_rebinding_runs_before_new_scope(case,mutation):
    facts,sources=case
    if mutation=='missing': sources.pop(1)
    elif mutation=='duration': sources[1]['text']=sources[1]['text'].replace('17-day','18-day')
    elif mutation=='cutoff': sources[1]['text']=sources[1]['text'].replace('13 June 2033','14 June 2033')
    elif mutation=='inactive': sources[1]['status']='superseded'
    elif mutation=='category': sources[0]['text']=sources[0]['text'].replace('device_x','other_x')
    else: sources[1]['effective_from']='2099-01-01'
    with pytest.raises(ValueError,match='unbound_'): check('The item can be returned within 11 days.',case)


def test_equal_windows_do_not_require_delivery_date(case):
    facts,sources=case
    sources[1]['text']=sources[1]['text'].replace('17-day','11-day')
    facts['return_policy']['historical_exception']['window_calendar_days']=11
    check('The item can be returned within 11 days.',case)

def test_fake_generation_repairs_new_pronoun_premise_once(case):
    facts,sources=case
    from src import document_answers as answer_module
    good='The current general return window is 11 days. Items delivered before 13 June 2033 keep the earlier 17-day window.'
    class Client:
        last_metrics={}
        def __init__(self): self.calls=[]
        def complete(self,system,user,**options):
            self.calls.append((json.loads(user),options))
            assert len(self.calls)<=2
            text='Since it was delivered yesterday before the cutoff, an earlier rule applies.' if len(self.calls)==1 else good
            return json.dumps({'answer':text,'covered':True,'needs_clarification':False})
    client=Client()
    out=answer_module.document_reply(client,'What is the return window?','en',sources,facts=facts,context_provenance=True)
    assert out['answer']==good and out['repair_errors']==['invented_delivery_premise']
    assert len(client.calls)==out['generation_attempts']==2
    assert client.calls[0][1]['cache'] is True and client.calls[1][1]['cache'] is False
    assert all(call[1]['attempts']==1 for call in client.calls)
    assert client.calls[0][0]['source_text']==client.calls[1][0]['source_text']
    assert client.calls[0][0]['deterministic_facts']==client.calls[1][0]['deterministic_facts']
