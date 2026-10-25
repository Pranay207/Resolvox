"""Local predicate-scope checks; no model, policy IDs, or gold answer imports."""
import json
import pytest

@pytest.fixture(scope='module')
def helper():
    from src import return_conditions
    return return_conditions


def source_facts(helper,*,opened=False):
    state='opened' if opened else 'unopened'
    sources=[{'id':'dynamic-rule','text':f'Cosmetics products are returnable only if {state} with the seal intact.',
              'doc_type':'policy','status':'current','effective_from':'2020-01-01'},
             {'id':'dynamic-item','text':json.dumps({'sku':'CASE-X','title':'Aster Tint','return_category':'cosmetics_sealed'}),
              'doc_type':'catalog','status':'current'}]
    facts=helper.return_condition_context('I opened Aster Tint. Can I return it?',sources,reference_date='2026-10-20')
    facts['reference_date']='2026-10-20'
    return sources,facts

@pytest.mark.parametrize('answer',[
    'If you contact support, the product must be opened for an ordinary return.',
    'If you contact support the product must be opened.',
    'If the courier is late, products must be opened.',
    'When you have a receipt, the product must be opened.',
    'This is not a damaged product, so the product must be opened.',
    'There are rules about damaged products, but this product must be opened.',
    'For a damaged product, the product must be opened for an ordinary return.',
    'For a defective item, the product must be opened for an ordinary return and for inspection.',
    'For a damaged item, products must be opened.',
    'For a not damaged item, the product must be opened for inspection.',
    'If the product is not damaged, the product must be opened for inspection.',
    'If products are unopened, the product must be opened.',
    'If products must be unopened, the product must be opened.',
    'Return policy kehti hai ki agar aap phone karein, products khole gaye hon.',
    '\u0936\u0930\u094d\u0924\u0947\u0902 \u0915\u0939\u0924\u0940 \u0939\u0948\u0902 \u0915\u093f \u0905\u0917\u0930 \u0906\u092a \u092b\u094b\u0928 \u0915\u0930\u0947\u0902, \u0909\u0924\u094d\u092a\u093e\u0926 \u0916\u0941\u0932\u0947 \u0939\u094b\u0902\u0964',
    'For a defective item, the product must be opened for inspection, but the product must be opened.',
])
def test_unrelated_or_negative_exception_cannot_hide_required_state_reversal(helper,answer):
    sources,facts=source_facts(helper)
    with pytest.raises(ValueError,match='contradicted_return_condition_polarity:opened'):
        helper.check_return_condition_answer(answer,facts,sources)

@pytest.mark.parametrize('answer',[
    'Products must be unopened with the seal intact.',
    'If you contact support, products must remain unopened.',
    'If products must be opened, that would be a different rule.',
    'If products were returnable only if opened, the rule would be different.',
    'If products had to be opened, your item might meet that condition; that is hypothetical.',
    'If only opened items are returnable, that is a hypothetical rule.',
    'For a defective item, the product must be opened for inspection.',
    'For a defective item, the product must be opened for inspection, but ordinary products must remain unopened.',
    'Return policy kehti hai ki agar products khole gaye hon, return possible nahi hai.',
    'If the product is defective, the product must be opened for inspection.',
    'For a damaged item, the product must be opened for assessment.',
    'Your product was opened. The outer packaging must be opened for inspection.',
    'The product does not have to be opened; it must remain unopened.',
    'Return policy kehti hai ki agar products khole gaye hon, return possible nahi hai.',
])
def test_real_item_condition_and_scoped_inspection_remain_distinct(helper,answer):
    sources,facts=source_facts(helper)
    helper.check_return_condition_answer(answer,facts,sources)


def test_dynamic_source_requirement_flips_without_fixed_policy_answer(helper):
    sources,facts=source_facts(helper,opened=True)
    helper.check_return_condition_answer('If you contact support, the product must be opened.',facts,sources)
    with pytest.raises(ValueError,match='contradicted_return_condition_polarity:opened'):
        helper.check_return_condition_answer('If you contact support, the product must be unopened.',facts,sources)


def test_changed_authority_and_source_text_still_fail_binding(helper):
    sources,facts=source_facts(helper)
    sources[0]={**sources[0],'status':'superseded'}
    with pytest.raises(ValueError,match='unbound_return_condition'):
        helper.check_return_condition_answer('Products must be unopened.',facts,sources)
