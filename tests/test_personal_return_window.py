"""Personal current-window condition guard; no model/organizer scoring."""
import copy
import pytest
from src.placement_conditions import check_placement_exception_answer
from src.document_answers import _constraint_text

@pytest.fixture
def case():
 sources=[{'id':'TABLE-NEW','text':'| Portable devices and accessories | 11 days | device_z |','doc_type':'policy','status':'current','effective_from':'2032-01-01'},
          {'id':'CHANGE-NEW','text':'From **13 June 2033**, the return window for portable devices and accessories is 11 days. Portable devices **delivered before 13 June 2033** keep the earlier 17-day window from version 2 of this policy.','doc_type':'policy','status':'current','effective_from':'2032-01-01'}]
 facts={'reference_date':'2033-08-04','return_policy':{'category':'device_z','window_calendar_days':11,'source_ids':['TABLE-NEW'],'selection':'standard_window','historical_exception':{'delivery_before':'2033-06-13','window_calendar_days':17,'source_ids':['CHANGE-NEW']}}}
 return facts,sources

def check(answer,case):
 facts,sources=case
 return check_placement_exception_answer(answer,facts,sources,normalizer=_constraint_text)

@pytest.mark.parametrize('answer',[
 'The deadline for returning your portable device purchase is 11 days from delivery, as per the standard window, which applies from 13 June 2033 onwards.',
 'Your return window is 11 days.',
 'Your purchase can be returned within 11 days.',
 'For your item, the return window is 11 days.',
 'You have 11 days to return it.',
 'You get 11 days to return it if it is unused.',
 'If your item was received safely, you have 11 days to return it.',
 'If your order was placed after 13 June 2033, you have 11 days to return it.',
 'If your refund was initiated after 13 June 2033, you have 11 days to return it.',
 'If your item was delivered after 20 June 2033, you have 11 days to return it.',
 'The current window is 11 days. Your return deadline is 11 days.',
 'I do not know the delivery date, but you have 11 days to return it.',
 'Your return deadline is not 11 days.',
 'For items delivered on or after 13 June 2033, the return window is 11 days, and your item has an 11-day return window regardless of its delivery date.',
 'You have 11 days to return it, but if your item was delivered after 13 June 2033, a different rule applies.',
 'If your other item was delivered after 13 June 2033, you have 11 days to return this item.',
 'If your item was delivered after 13 June 2033, you have 11 days to return it regardless of the delivery date.',
])
def test_personal_current_window_requires_its_delivery_condition(case,answer):
 with pytest.raises(ValueError,match='unsupported_delivery_exception_personal_window'):
  check(answer,case)

@pytest.mark.parametrize('answer',[
 'The current return window is 11 days from delivery.',
 'Portable devices have an 11-day return window under the current rule.',
 'Your delivery date is unknown. The current general return window is 11 days.',
 'The current return window for your category is 11 days.',
 'If your item was delivered on or after 13 June 2033, you have 11 days to return it.',
 'You have 11 days to return it if your item was delivered after 13 June 2033.',
 'For products delivered after the cutoff, your return window is 11 days.',
 'If delivered after 2033-06-13, the deadline for returning your purchase is 11 days.',
 'I cannot confirm your return window is 11 days.',
 'Is your return window 11 days?',
 'Your return window is unknown, and the current general policy has 11 days.',
 'For your item, the return window is unknown; the current general policy has 11 days.',
 'The current return window is 11 days. Items delivered before 13 June 2033 retain the earlier window.',
])
def test_generic_rules_uncertainty_and_locally_bound_conditions_remain_allowed(case,answer):
 check(answer,case)

@pytest.mark.parametrize('record',['public_context','verified_order'])
def test_actual_delivery_input_retains_existing_known_date_path(case,record):
 facts,sources=case;facts[record]={'delivered_on':'2033-06-15'}
 check('Your return window is 11 days.',case)


def test_actual_earlier_delivery_retains_historical_path(case):
 facts,sources=case;facts['public_context']={'delivered_on':'2033-06-12'}
 check('You have 17 days to return it.',case)


def test_equal_source_windows_do_not_create_a_missing_date_obligation(case):
 facts,sources=case;sources[1]['text']=sources[1]['text'].replace('17-day','11-day');facts['return_policy']['historical_exception']['window_calendar_days']=11
 check('Your return window is 11 days.',case)


def test_changed_source_current_quantity_is_used_instead_of_static_value(case):
 facts,sources=case;sources[0]['text']=sources[0]['text'].replace('11 days','23 days');sources[1]['text']=sources[1]['text'].replace('11 days','23 days');facts['return_policy']['window_calendar_days']=23
 with pytest.raises(ValueError,match='unsupported_delivery_exception_personal_window'):check('Your return window is 23 days.',case)
 check('The current general return window is 23 days.',case)


def test_changed_source_cutoff_requires_the_changed_date(case):
 facts,sources=case;sources[1]['text']=sources[1]['text'].replace('13 June 2033','20 June 2033');facts['return_policy']['historical_exception']['delivery_before']='2033-06-20'
 with pytest.raises(ValueError,match='unsupported_delivery_exception_personal_window'):check('If your item was delivered after 13 June 2033, your return window is 11 days.',case)
 check('If your item was delivered after 20 June 2033, your return window is 11 days.',case)


def test_actual_ninth_pilot_answer_with_unbound_date_is_rejected():
 from src.kb import KnowledgeBase
 from src.data import Data
 from src.document_context import build_context
 sources=[c.public() for c in KnowledgeBase().require('RET-2','RET-3')]
 facts=build_context('What is the deadline for returning my purchase?',sources,Data(),public_context={'category':'electronics'})
 answer='The deadline for returning your electronics purchase is 7 days from the delivery date, as per the standard return window for Electronics and accessories, which applies from 1 August 2026 onwards.'
 with pytest.raises(ValueError,match='unsupported_delivery_exception_personal_window'):
  check(answer,(facts,sources))
