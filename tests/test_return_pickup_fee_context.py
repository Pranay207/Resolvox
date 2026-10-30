"""Verified return explanations preserve the source conditional pickup charge."""
from types import SimpleNamespace
import copy
import pytest
from src.document_context import build_context
from src.document_answers import _validate_context


def source(key,text,**extra):
    return dict(id=key,text=text,doc_type='policy',status='current',effective_from='2020-01-01',**extra)


def context(query='Can I return this jacket?',amount=23,**order_changes):
    sources=[source('RET-2','The return window starts on the delivery date.\n| Clothing, footwear and bags | 17 days | fashion |'),
             source('changing-fee',f'A reverse pickup fee of ₹{amount} applies to change-of-mind returns of clothing, footwear and bags. The fee is waived for Orchid members and for damaged items.')]
    order=dict(is_plus=False,delivered_on='2026-10-14',items=[dict(sku='J1',title='Novel Jacket',return_category='fashion')]);order.update(order_changes)
    data=SimpleNamespace(products={},holidays=set())
    return build_context(query,sources,data,verified_order=order),sources


@pytest.mark.parametrize('query',['Can I return this jacket?','Kya main jacket wapas kar sakti hoon?','क्या मैं जैकेट वापस कर सकती हूँ?'])
@pytest.mark.parametrize('amount',[23,71])
def test_fee_value_is_source_bound_for_verified_ordinary_return_explanations(query,amount):
    facts,sources=context(query,amount)
    fee=facts['return_pickup_policy']
    assert fee['standard_fee_inr']==amount and fee['personal_charge_confirmed'] is False
    assert fee['source_ids']==['changing-fee']
    constraint=next(r for r in facts['answer_constraints'] if r['key']=='return_pickup_policy.standard_fee_inr')
    assert constraint['value']==amount
    assert 'changing-fee' in facts['calculation_source_sha256']


@pytest.mark.parametrize('changes',[{'is_plus':True},{'is_plus':None},{'return_reason':'damaged'},{'return_reason':'wrong_item'}])
def test_waived_or_unknown_cases_do_not_gain_a_standard_charge_requirement(changes):
    facts,_=context(**changes)
    assert 'return_pickup_policy' not in facts


@pytest.mark.parametrize('query',['How long is the return window?','When does my refund arrive?','My jacket arrived damaged; can I return it?'])
def test_duration_refund_or_damage_questions_do_not_gain_this_eligibility_requirement(query):
    facts,_=context(query)
    assert 'return_pickup_policy' not in facts


def test_omitting_source_cost_is_rejected_and_conditional_complete_answer_passes():
    query='Can I return this jacket?';facts,sources=context(query)
    value=dict(answer='You may request a return within the applicable window.',covered=True,needs_clarification=False)
    with pytest.raises(ValueError,match='answer_constraint_missing:return_pickup_policy.standard_fee_inr'):
        _validate_context(value,sources,facts,'en',private=True,query=query)
    value['answer']='A change-of-mind return has a reverse pickup fee of 23 rupees, unless a documented waiver applies.'
    _validate_context(value,sources,facts,'en',private=True,query=query)


def test_expired_verified_return_does_not_require_an_inapplicable_charge():
    facts,_=context(delivered_on='2026-09-01')
    assert 'return_pickup_policy' not in facts
