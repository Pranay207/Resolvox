"""Event/date claims use text relations and the supplied year, not policy dates."""
from datetime import date
from types import SimpleNamespace
import json
import re
import pytest
from src.event_dates import event_date

REF=date(2034,10,20)

@pytest.mark.parametrize('text,expected',[
    ('10 October ko order kiya tha.', '2034-10-10'),
    ('Sale mein 8 September ko order kiya tha, return period?', '2034-09-08'),
    ('I ordered on 6 October.', '2034-10-06'),
    ('On 6 October I ordered the item.', '2034-10-06'),
    ('I bought it 12 August 2033.', '2033-08-12'),
    ('12 August 2033 par order diya tha.', '2033-08-12'),
    ('The order was placed on 2032-02-29.', '2032-02-29'),
    ('I purchased it 3rd Sep 2034.', '2034-09-03'),
    ('Order date is 10 October 2033.', '2033-10-10'),
    ('10 \u0905\u0915\u094d\u091f\u0942\u092c\u0930 \u0915\u094b \u0911\u0930\u094d\u0921\u0930 \u0915\u093f\u092f\u093e \u0925\u093e', '2034-10-10'),
])
def test_placement_dates_before_and_after_generic_event_cues(text,expected):
    assert event_date(text,'placement',REF)==date.fromisoformat(expected)

@pytest.mark.parametrize('text,expected',[
    ('The parcel arrived 6 October.', '2034-10-06'),
    ('6 October ko delivery hui.', '2034-10-06'),
    ('My item was delivered on 2033-07-18.', '2033-07-18'),
    ('I received the item 12 August 2033.', '2033-08-12'),
])
def test_delivery_dates_remain_distinct(text,expected):
    assert event_date(text,'delivery',REF)==date.fromisoformat(expected)
    assert event_date(text,'placement',REF) is None

@pytest.mark.parametrize('text',[
    'I ordered on 10 October or 12 October.',
    'I ordered on 10 October and then ordered again 12 October.',
    '10 or 12 October ko order kiya tha.',
    'If I ordered on 10 October, what would the window be?',
    'Maybe I ordered on 10 October.',
    'I did not order on 10 October.',
    '10 October ko order nahi kiya tha.',
    'Did I order on 10 October?',
    'I ordered on 31 April.',
    'I ordered on 12 December.',
    'I ordered on 10 October 20340.',
    'I ordered on 10 October last year.',
    'I know the sale closes 10 October; what is the return window?',
    'What happens for orders placed between 1 October and 15 October?',
])
def test_ambiguous_hypothetical_negated_invalid_or_unbound_dates_are_not_inputs(text):
    assert event_date(text,'placement',REF) is None


def test_nearest_event_binding_does_not_swap_placement_and_delivery():
    text='I ordered on 5 October and the parcel was delivered on 12 October.'
    assert event_date(text,'placement',REF)==date(2034,10,5)
    assert event_date(text,'delivery',REF)==date(2034,10,12)


def test_date_before_each_event_is_bound_to_the_correct_event():
    text='5 October ko order kiya tha; 12 October ko delivery hui.'
    assert event_date(text,'placement',REF)==date(2034,10,5)
    assert event_date(text,'delivery',REF)==date(2034,10,12)


def test_refund_received_date_is_not_a_delivery_input():
    assert event_date('The refund was received on 10 October.','delivery',REF) is None


def test_date_before_placement_changes_with_supplied_reference_year_only():
    assert event_date('8 September ko order kiya tha','placement',date(2031,10,1))==date(2031,9,8)
    assert event_date('8 September ko order kiya tha','placement',date(2035,10,1))==date(2035,9,8)


def test_event_date_does_not_read_orders_or_choose_policy_values():
    assert event_date('10 October ko order kiya tha','placement',REF)==date(2034,10,10)
    with pytest.raises(ValueError,match='unsupported_event_kind'):
        event_date('10 October','refund',REF)


def test_source_parsed_placement_window_uses_extracted_date_with_mutated_values():
    from src.document_context import build_context
    sources=[{'id':'RET-2','text':'| Clothes | 19 days | `fashion` |','doc_type':'policy','status':'current'},
             {'id':'RET-8','text':'Clothing, footwear and bags from orders placed between 06 September and 13 September 2034 can be returned within 41 days of delivery. All other categories follow normal windows.',
              'doc_type':'policy','status':'current'}]
    public={'category':'fashion','placed_on':event_date('8 September ko order kiya tha','placement',REF).isoformat()}
    facts=build_context('What is the return window?',sources,SimpleNamespace(products={},holidays=set()),public_context=public)
    assert facts['return_policy']['window_calendar_days']==41
    assert facts['return_policy']['selection']=='placement_exception_window'
    assert facts['return_policy']['source_ids']==['RET-8']
    assert facts['answer_constraints'][0]['value']==41


def test_actual_query_shape_populates_public_date_without_private_lookup():
    from src.agent import Agent,Resources
    from src.config import REFERENCE_DATE
    r=Resources(dense=False)
    def blocked(*args,**kwargs): raise AssertionError('No model/private tool operations')
    r.llm.complete=blocked;r.tools.lookup=blocked;r.tools.ticket=blocked
    query='Sale mein 10 October ko order kiya tha (UrbanThread Slim Fit Jeans), return ke kitne din hain?'
    out=Agent(r,compose=False).respond(query,language_hint='hi-en')
    assert out['facts']['public_context']['placed_on']==date(REFERENCE_DATE.year,10,10).isoformat()
    assert out['facts']['return_policy']['selection']=='placement_exception_window'
    assert out['facts']['return_policy']['source_ids']==['RET-8']
    actual=next(s['text'] for s in out['sources'] if s['id']=='RET-8')
    days=int(re.search(r'within\s+(\d+)\s+days',actual)[1])
    assert out['facts']['return_policy']['window_calendar_days']==days
    assert not out['tool_calls']


@pytest.mark.parametrize('text,event',[
    ('The parcel was delivered; the refund started on 10 October.','delivery'),
    ('The parcel was delivered, and the refund started on 10 October.','delivery'),
    ('I ordered the item, and my refund started on 10 October.','placement'),
    ('The refund for my order was received on 10 October.','delivery'),
])
def test_other_event_dates_do_not_become_undated_order_or_delivery_inputs(text,event):
    assert event_date(text,event,REF) is None


def test_delivery_and_refund_dates_bind_to_their_own_events():
    assert event_date('The parcel was delivered on 5 October and the refund started on 12 October.','delivery',REF)==date(2034,10,5)


def test_placement_and_shipping_dates_do_not_compete_as_same_event():
    assert event_date('I ordered on 5 October and it shipped on 12 October.','placement',REF)==date(2034,10,5)


@pytest.mark.parametrize('text,expected',[
    ('Correction: delivery was actually 1 August 2026. Revise the period.', '2026-08-01'),
    ('The delivery is 12 September.', '2034-09-12'),
    ('Delivery date: 18 July 2033.', '2033-07-18'),
    ('The delivery occurred 6 October.', '2034-10-06'),
])
def test_asserted_nominal_delivery_link_populates_event_date(text,expected):
    assert event_date(text,'delivery',REF)==date.fromisoformat(expected)


@pytest.mark.parametrize('text',[
    'Delivery was not 1 August 2026.',
    'If delivery was 1 August 2026, what would the window be?',
    'Was delivery actually 1 August 2026?',
    'Delivery may happen on 1 August 2026.',
])
def test_nominal_delivery_link_still_declines_unasserted_or_negated_dates(text):
    assert event_date(text,'delivery',REF) is None
