"""Unknown individual membership in an actual source-dated delivery class."""
import copy
import pytest
from src.placement_conditions import check_placement_exception_answer

@pytest.fixture
def example():
    sources=[{'id':'WINDOW-Z','text':'| Electrical devices and accessories | 6 days | devices_x |',
              'doc_type':'policy','status':'current','effective_from':'2030-01-01'},
             {'id':'PAST-Q','text':'From 4 March 2031, the return window for electrical devices and accessories is 6 days. Electrical devices delivered before 4 March 2031 keep the earlier 9-day window from version 2 of this policy.',
              'doc_type':'policy','status':'current','effective_from':'2030-01-01'}]
    facts={'reference_date':'2031-05-01','public_context':{'sku':'ITEM-B'},
           'return_policy':{'category':'devices_x','category_label':'Electrical devices and accessories',
                            'window_calendar_days':6,'source_ids':['WINDOW-Z'],'selection':'standard_window',
                            'historical_exception':{'delivery_before':'2031-03-04','window_calendar_days':9,'source_ids':['PAST-Q']}}}
    return facts,sources

@pytest.mark.parametrize('answer',[
    'Products delivered on or after that date, including this one, follow the new window.',
    'Items delivered after the cutoff, including yours, follow the current window.',
    'Orders delivered before 4 March 2031, including your order, follow the earlier window.',
    'Products delivered before this date, excluding yours, retain their old window.',
    'For products delivered after that date, including this one, the new window applies.',
    'If an item is unused, products delivered after the cutoff, including yours, follow the current window.',
    'Products delivered after 2031-03-04 follow the current window. This one belongs to that group.',
    'Items delivered before the cutoff follow the old window. Yours is one of those items.',
    'Products delivered after that date, such as your item, follow the current window.',
    'If your item was received safely, products delivered after that date, including this one, use the current policy.',
    'If your item was received on time, products delivered after the cutoff, including yours, follow the current window.',
    'If this one was delivered intact, products delivered after the cutoff, including this one, follow the current window.',
])
def test_unqualified_personal_membership_needs_delivery_date(example,answer):
    facts,sources=example
    with pytest.raises(ValueError,match='invented_delivery_class_membership'):
        check_placement_exception_answer(answer,facts,sources)

@pytest.mark.parametrize('answer',[
    'Products delivered on or after that date follow the current window.',
    'Products delivered before 4 March 2031 keep the earlier window.',
    'The current general window is 6 days. Items delivered before the cutoff keep 9 days.',
    'If your item was delivered after that date, it follows the current window.',
    'If this one was delivered after the cutoff, products in that class, including this one, follow the current window.',
    'Products delivered after the cutoff, including this one if it was delivered after that date, follow the current window.',
    'Products delivered after the cutoff follow the current window. If yours is one of those items, that rule applies.',
    'Products delivered after the cutoff follow the current window. I cannot confirm yours is one of those items.',
    'Products delivered after the cutoff, including this model when applicable, follow the current window.',
    'This model follows the general category policy. Products delivered before the cutoff keep the earlier window.',
])
def test_general_model_scope_and_real_conditions_do_not_assert_individual_delivery(example,answer):
    check_placement_exception_answer(answer,*example)

@pytest.mark.parametrize('record,key',[('public_context','delivered_on'),('verified_order','delivered_on')])
def test_actual_customer_or_verified_delivery_input_is_not_unknown(example,record,key):
    facts,sources=example
    facts.setdefault(record,{})[key]='2031-03-05'
    check_placement_exception_answer('Products delivered after that date, including this one, follow the current window.',facts,sources)

@pytest.mark.parametrize('mutation',['cutoff','days','missing_source','superseded','wrong_category'])
def test_guard_independently_rebinds_actual_source_exception(example,mutation):
    facts,sources=copy.deepcopy(example)
    if mutation=='cutoff':sources[1]['text']=sources[1]['text'].replace('4 March 2031','8 April 2031')
    elif mutation=='days':sources[1]['text']=sources[1]['text'].replace('9-day','11-day')
    elif mutation=='missing_source':sources.pop()
    elif mutation=='superseded':sources[1]['status']='superseded'
    else:sources[1]['text']=sources[1]['text'].replace('Electrical devices','Wooden furniture')
    with pytest.raises(ValueError,match='unbound_'):
        check_placement_exception_answer('Products delivered after that date, including this one, follow the current window.',facts,sources)


def test_mutated_actual_cutoff_and_duration_are_used_without_static_dates(example):
    facts,sources=example
    sources[1]['text']=sources[1]['text'].replace('4 March 2031','8 April 2031').replace('9-day','11-day')
    facts['return_policy']['historical_exception'].update(delivery_before='2031-04-08',window_calendar_days=11)
    with pytest.raises(ValueError,match='invented_delivery_class_membership'):
        check_placement_exception_answer('Products delivered after 8 April 2031, including this one, follow the current window.',facts,sources)
    check_placement_exception_answer('Products delivered before 8 April 2031 retain 11 days.',facts,sources)


def test_unrelated_generic_class_is_not_a_date_exception_guard(example):
    facts,sources=example
    check_placement_exception_answer('Products sold by merchants, including this one, follow the same returns policy.',facts,sources)


def test_no_source_bound_historical_exception_does_not_invent_guard_scope():
    check_placement_exception_answer('Products delivered after that date, including this one, follow the current window.',
                                   {'return_policy':{'category':'devices_x'}},[])
