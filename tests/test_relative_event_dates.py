"""Production-import relative input and historical membership boundary tests."""
from datetime import date,timedelta
import socket
import types
import pytest
import requests
from src import event_dates as relative
from src import placement_conditions as placement
from src.document_answers import _constraint_text
REF=date(2034,10,20)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*a,**k): pytest.fail('No network permitted')
    monkeypatch.setattr(socket,'create_connection',forbidden)
    monkeypatch.setattr(requests.sessions.Session,'request',forbidden)


@pytest.mark.parametrize('text,event,days',[
    ('I ordered today.','placement',0),('I bought it yesterday.','placement',1),
    ('The package arrived yesterday.','delivery',1),('I received the laptop yesterday.','delivery',1),
    ('Yesterday I received the laptop.','delivery',1),('The parcel was delivered 3 days ago.','delivery',3),
    ('Three days ago I received the product.','delivery',3),('I purchased the bag twenty-one days ago.','placement',21),
    ('I ordered one hundred and five days ago.','placement',105),('I received the item 0 days ago.','delivery',0),
    ('The delivery was today.','delivery',0),('Order date is yesterday.','placement',1),
])
def test_relative_dates_use_supplied_reference_only(text,event,days):
    assert relative.event_date(text,event,REF)==REF-timedelta(days=days)


@pytest.mark.parametrize('reference,expected',[
    (date(2035,1,1),date(2034,12,31)),(date(2032,3,1),date(2032,2,29)),
    (date(2033,3,1),date(2033,2,28)),(date(2034,5,1),date(2034,4,30)),
])
def test_rollovers(reference,expected): assert relative.event_date('I received it yesterday.','delivery',reference)==expected


@pytest.mark.parametrize('text,event',[
    ('The refund arrived yesterday.','delivery'),('The payment was received today.','delivery'),
    ('The refund for my order was received three days ago.','delivery'),
    ('The parcel was delivered; the refund arrived yesterday.','delivery'),
    ('The parcel was delivered, and the refund arrived yesterday.','delivery'),
    ('I ordered the item, and the refund started yesterday.','placement'),
    ('It shipped yesterday.','delivery'),('It was picked up yesterday.','delivery'),
    ('I did not receive it yesterday.','delivery'),("The parcel wasn't delivered yesterday.",'delivery'),
    ("I haven't received the package today.",'delivery'),('I never ordered yesterday.','placement'),
    ('Maybe I received it yesterday.','delivery'),('If I received it yesterday, what changes?','delivery'),
    ('Did I order yesterday?','placement'),('Was it delivered yesterday?','delivery'),
    ('Have I received the item today?','delivery'),('Has the item been delivered today?','delivery'),
    ('The item will be delivered today.','delivery'),('The item may be delivered today.','delivery'),
    ('The item is going to be delivered today.','delivery'),('Delivery is expected today.','delivery'),
    ('The parcel was scheduled to be delivered yesterday.','delivery'),
    ('I received it tomorrow.','delivery'),('I received it in 2 days.','delivery'),
    ('I received it -1 days ago.','delivery'),('I received it - 1 days ago.','delivery'),
    ('I received it minus one day ago.','delivery'),('I received it 1.5 days ago.','delivery'),
    ('I received it one point five days ago.','delivery'),('I received it 999999999999999999999999 days ago.','delivery'),
    ('Kal delivery hui.','delivery'),('कल डिलीवरी हुई।','delivery'),
    ('I received it yesterday or today.','delivery'),('I received it 2 or 3 days ago.','delivery'),
    ('I ordered today and then ordered yesterday.','placement'),
])
def test_ambiguous_unasserted_other_event_and_future_inputs_declined(text,event):
    assert relative.event_date(text,event,REF) is None


def test_relative_event_scope_and_nearest_barriers():
    text='I ordered three days ago and the parcel was delivered yesterday.'
    assert relative.event_date(text,'placement',REF)==REF-timedelta(days=3)
    assert relative.event_date(text,'delivery',REF)==REF-timedelta(days=1)
    text='The parcel arrived yesterday and the refund arrived today.'
    assert relative.event_date(text,'delivery',REF)==REF-timedelta(days=1)
    assert relative.event_date('I ordered yesterday and it shipped today.','placement',REF)==REF-timedelta(days=1)


def test_absolute_and_relative_same_date_agree_but_conflict_declines():
    assert relative.event_date('I received it yesterday, 19 October 2034.','delivery',REF)==date(2034,10,19)
    assert relative.event_date('I received it yesterday, 18 October 2034.','delivery',REF) is None


def test_date_underflow_declined():
    assert relative.event_date('I received it yesterday.','delivery',date.min) is None


@pytest.fixture
def history():
    sources=[{'id':'SYNTHETIC-TABLE','text':'| Portable devices and accessories | 11 days | device_x |','doc_type':'policy','status':'current','effective_from':'2032-01-01'},
             {'id':'SYNTHETIC-HISTORY','text':'Portable devices delivered before 13 June 2033 keep the earlier 17-day window from version 2 of this policy.','doc_type':'policy','status':'current','effective_from':'2032-01-01'}]
    facts={'reference_date':'2033-08-04','public_context':{'delivered_on':relative.event_date('I received the item yesterday.','delivery',date(2033,8,4)).isoformat()},
           'return_policy':{'category':'device_x','window_calendar_days':11,'source_ids':['SYNTHETIC-TABLE'],'selection':'standard_window',
           'historical_exception':{'delivery_before':'2033-06-13','window_calendar_days':17,'source_ids':['SYNTHETIC-HISTORY']}}}
    return facts,sources


def check(text,history):
    facts,sources=history
    return placement.check_placement_exception_answer(text,facts,sources,normalizer=_constraint_text)


def test_relative_input_remains_customer_unverified(history):
    facts,sources=history
    status=placement.delivery_exception_status(facts,sources)
    assert status['input_origin']=='customer_provided_unverified'
    assert status['applicability']=='not_met' and status['delivery_date']=='2033-08-03'
    assert 'verified_order' not in facts
    check('The item can be returned within its 11-day return window.',history)


@pytest.mark.parametrize('answer',[
    'It falls under the earlier 17-day return window.',
    'The item falls under the earlier seventeen-day return window.',
    'This product falls under the earlier 17-day window.',
    'Since it was delivered yesterday, it falls under the earlier 17-day window.',
])
def test_known_relative_date_cannot_claim_incompatible_historical_membership(history,answer):
    with pytest.raises(ValueError,match='unsupported_delivery_exception_entitlement'): check(answer,history)


@pytest.mark.parametrize('answer',[
    'The current window is 11 days. Items delivered before the cutoff keep 17 days.',
    'If it was delivered before the cutoff, it falls under the earlier 17-day window.',
    'I cannot confirm it falls under the earlier 17-day window.',
    'It does not fall under the earlier 17-day window.',
    'It falls under the current 11-day window.',
])
def test_generic_conditional_uncertain_negated_and_matching_membership_allowed(history,answer): check(answer,history)


def test_changed_source_cutoff_and_duration_rebound(history):
    facts,sources=history
    sources[1]['text']=sources[1]['text'].replace('13 June 2033','15 September 2033').replace('17-day','23-day')
    facts['return_policy']['historical_exception'].update(delivery_before='2033-09-15',window_calendar_days=23)
    assert placement.delivery_exception_status(facts,sources)['applicability']=='met'
    check('It falls under the earlier 23-day window.',history)
    facts['public_context']['delivered_on']='2033-09-16'
    with pytest.raises(ValueError,match='unsupported_delivery_exception_entitlement'): check('It falls under the earlier 23-day window.',history)


@pytest.mark.parametrize('mutation',['missing','duration','cutoff','inactive','category'])
def test_actual_source_rebinding_is_still_required(history,mutation):
    facts,sources=history
    if mutation=='missing': sources.pop(1)
    elif mutation=='duration': sources[1]['text']=sources[1]['text'].replace('17-day','18-day')
    elif mutation=='cutoff': sources[1]['text']=sources[1]['text'].replace('13 June','14 June')
    elif mutation=='inactive': sources[1]['status']='superseded'
    else: sources[0]['text']=sources[0]['text'].replace('device_x','another_x')
    with pytest.raises(ValueError,match='unbound_'): check('It falls under the earlier 17-day window.',history)

def test_existing_agent_binding_carries_relative_date_as_public_unverified_input(monkeypatch):
    import src.agent as agent
    import src.answering as answering
    from src.config import REFERENCE_DATE
    monkeypatch.setattr(answering,'event_date',relative.event_date)
    def blocked(*args,**kwargs): raise AssertionError('No inference/private lookup allowed')
    monkeypatch.setattr(agent,'LLM',lambda:types.SimpleNamespace(last_metrics={},complete=blocked))
    resources=agent.Resources(dense=False)
    resources.tools.lookup=blocked
    resources.tools.ticket=lambda *a,**k:({'created':True},{'name':'create_ticket','result':{'created':True}})
    instance=agent.Agent(resources,compose=False)
    out=instance.respond('The laptop I received yesterday has a crack.','en')
    assert instance.state.public_context['delivered_on']==(REFERENCE_DATE-timedelta(days=1)).isoformat()
    assert out['verified'] is False
    assert instance.state.order is None and not any(call.get('name')=='lookup_order' for call in out['tool_calls'])

@pytest.mark.parametrize('text',[
    "Yesterday's order arrived.", "Yesterday’s order arrived.",
    'May I have received the item today?', 'Had the item been received today?',
])
def test_possessive_date_modifiers_and_additional_questions_are_not_asserted_delivery_inputs(text):
    assert relative.event_date(text,'delivery',REF) is None


def test_modal_question_word_does_not_hide_a_named_may_date():
    assert relative.event_date('I received the item on 10 May 2034.','delivery',REF)==date(2034,5,10)


@pytest.mark.parametrize('text',[
    'The item was received the day before yesterday.',
    'The item was received a week from today.',
    'The item was received two weeks ago yesterday.',
    'The item was received two weeks ago just yesterday.',
    'The item was received before yesterday.',
    'The item was received today minus two days.',
    'The item was received yesterday plus one day.',
    'The item was received today a week ago.',
    'The item was received about two days ago.',
    'The item was received approximately just two days ago.',
    'The item was received around yesterday.',
    'The item was received nearly three days ago.',
    'The item was received at least two days ago.',
    'The item was received two days ago or so.',
    'The item was received yesterday or last week.',
    'Last week or yesterday I received the item.',
    'It will definitely be delivered today.',
    'It may actually have been delivered yesterday.',
    'It will by mistake be delivered today.',
    'It might already have been received today.',
    'It can eventually be delivered today.',
    'It should probably have been received yesterday.',
])
def test_modified_or_approximate_relative_dates_and_modal_adverbs_are_not_exact_inputs(text):
    assert relative.event_date(text,'delivery',REF) is None


@pytest.mark.parametrize('text,expected',[
    ('The item was received yesterday.',date(2034,10,19)),
    ('The item was received today.',REF),
    ('The item was received three days ago.',date(2034,10,17)),
    ('The item was received exactly three days ago.',date(2034,10,17)),
    ('The item was received just yesterday.',date(2034,10,19)),
    ('On 10 May 2034 the item had been received.',date(2034,5,10)),
    ('I ordered yesterday and the item was received today.',REF),
])
def test_unmodified_exact_relative_dates_and_named_may_keep_existing_binding(text,expected):
    assert relative.event_date(text,'delivery',REF)==expected
