"""Source-derived requirement polarity regressions, with fake generation only."""
import copy
import json
from types import SimpleNamespace

import pytest
from src.generation_diagnostics import GenerationValidationError,failure_diagnostics

@pytest.fixture(scope='module')
def staged():
    from src import return_conditions as helper
    from src import document_context as context
    from src import document_answers as answers
    return helper,context,answers


@pytest.fixture
def sources():
    return [
        {'id':'CONDITION-X','text':'Cosmetics products are returnable only if unopened with the seal intact.',
         'doc_type':'policy','status':'current','effective_from':'2020-01-01','version':'fixture'},
        {'id':'CATALOG-Y','file':'data/products.csv','text':json.dumps({'sku':'ITEM-X','title':'Aster Tint','return_category':'cosmetics_sealed'}),
         'doc_type':'catalog','status':'current'},
    ]


def facts(staged,sources,query='I opened Aster Tint. Can I return it?'):
    _,context,_=staged
    return context.build_context(query,sources,SimpleNamespace(products={},holidays=set(),pincodes={}))


@pytest.mark.parametrize('answer',[
    'No, your opened item cannot be returned. Products must be opened under the return conditions.',
    'The policy requires products to be opened.',
    'Return conditions require your item to be opened.',
    'Return conditions require that products are opened.',
    'Items should remain open.',
    'Products must not be unopened.',
    'Only opened items are returnable.',
    'Items can be returned only if opened with the seal intact.',
    '\u0930\u093f\u091f\u0930\u094d\u0928 \u0915\u0940 \u0936\u0930\u094d\u0924\u0947\u0902 \u0915\u0939\u0924\u0940 \u0939\u0948\u0902 \u0915\u093f \u0909\u0924\u094d\u092a\u093e\u0926 \u0916\u094b\u0932\u0947 \u0917\u090f \u0939\u094b\u0902 \u0914\u0930 \u092c\u0902\u0926 \u0930\u0939\u0947 \u0939\u094b\u0902\u0964',
    '\u0909\u0924\u094d\u092a\u093e\u0926 \u0916\u0941\u0932\u093e \u0939\u094b\u0928\u093e \u091a\u093e\u0939\u093f\u090f\u0964',
    'Return policy kehti hai ki products khole gaye hon.',
    'Products khule hone chahiye.',
])
def test_reversed_policy_requirement_is_rejected_even_after_correct_refusal(staged,sources,answer):
    helper,_,_=staged
    with pytest.raises(ValueError,match='contradicted_return_condition_polarity:opened'):
        helper.check_return_condition_answer(answer,facts(staged,sources),sources)


@pytest.mark.parametrize('answer',[
    'No, your product has already been opened, so it does not meet the ordinary return condition.',
    'Products must be unopened with the seal intact.',
    'Products must not be opened.',
    'The policy requires your item to remain unopened.',
    'Only unopened products are returnable.',
    'Items are returnable only if unopened with the seal intact.',
    'If products had to be opened, your item might meet that condition; that is hypothetical.',
    'If products were returnable only if opened, the rule would be different.',
    'The policy does not require products to be opened.',
    'Your item has been opened. The outer packaging must be opened for inspection.',
    'For a defective item, the product must be opened for inspection.',
    '\u0909\u0924\u094d\u092a\u093e\u0926 \u0916\u094b\u0932\u0947 \u0928\u0939\u0940\u0902 \u0917\u090f \u0939\u094b\u0928\u0947 \u091a\u093e\u0939\u093f\u090f\u0964',
    '\u0909\u0924\u094d\u092a\u093e\u0926 \u0905\u0928\u0916\u0941\u0932\u093e \u0939\u094b\u0928\u093e \u091a\u093e\u0939\u093f\u090f\u0964',
    '\u0930\u093f\u091f\u0930\u094d\u0928 \u0915\u0940 \u0936\u0930\u094d\u0924\u0947\u0902 \u0915\u0939\u0924\u0940 \u0939\u0948\u0902 \u0915\u093f \u0909\u0924\u094d\u092a\u093e\u0926 \u0928\u0939\u0940\u0902 \u0916\u094b\u0932\u0947 \u0917\u090f \u0939\u094b\u0902\u0964',
    '\u0936\u0930\u094d\u0924\u0947\u0902 \u0915\u0939\u0924\u0940 \u0939\u0948\u0902 \u0915\u093f \u0905\u0917\u0930 \u0909\u0924\u094d\u092a\u093e\u0926 \u0916\u094b\u0932\u0947 \u0917\u090f \u0939\u094b\u0902, \u0924\u094b \u0909\u0928\u094d\u0939\u0947\u0902 \u0935\u093e\u092a\u0938 \u0928\u0939\u0940\u0902 \u0915\u0930\u0924\u0947\u0964',
    'Products khule nahi hone chahiye.',
    'Return policy kehti hai ki products unopened hon.',
    'Return policy kehti hai ki agar products khole gaye hon, return possible nahi hai.',
])
def test_customer_state_correct_negation_and_conditional_explanations_are_preserved(staged,sources,answer):
    helper,_,_=staged
    helper.check_return_condition_answer(answer,facts(staged,sources),sources)


def test_policy_narration_is_checked_even_when_customer_item_state_is_unresolved(staged,sources):
    helper,_,_=staged
    value=facts(staged,sources,'Can I return Aster Tint?')
    assert value['ordinary_return_condition_check']['status']=='unresolved'
    with pytest.raises(ValueError,match='contradicted_return_condition_polarity:opened'):
        helper.check_return_condition_answer('Products must be opened.',value,sources)


def test_changed_source_flips_required_state_instead_of_preserving_an_opened_ban(staged,sources):
    helper,_,_=staged
    changed=copy.deepcopy(sources);changed[0]['text']=changed[0]['text'].replace('unopened','opened')
    old=facts(staged,sources);new=facts(staged,changed)
    assert new['return_condition_policy']['requirements']['opened'] is True
    helper.check_return_condition_answer('Products must be opened.',new,changed)
    with pytest.raises(ValueError,match='contradicted_return_condition_polarity:opened'):
        helper.check_return_condition_answer('Products must be unopened.',new,changed)
    with pytest.raises(ValueError,match='unbound_return_condition'):
        helper.check_return_condition_answer('Products must be unopened.',old,changed)


def test_removed_opening_condition_removes_this_specific_polarity_constraint(staged,sources):
    helper,_,_=staged
    changed=copy.deepcopy(sources);changed[0]['text']='Cosmetics products are returnable only if the seal intact.'
    value=facts(staged,changed)
    assert 'opened' not in value['return_condition_policy']['requirements']
    helper.check_return_condition_answer('Products must be opened.',value,changed)


@pytest.mark.parametrize('change',['missing','superseded','future','category','claim_type'])
def test_source_authority_and_claim_type_checks_are_not_weakened(staged,sources,change):
    helper,_,_=staged
    value=facts(staged,sources);changed=copy.deepcopy(sources)
    if change=='missing':changed.pop(0)
    elif change=='superseded':changed[0]['status']='superseded'
    elif change=='future':changed[0]['effective_from']='2099-01-01'
    elif change=='category':
        row=json.loads(changed[1]['text']);row['return_category']='books';changed[1]['text']=json.dumps(row)
    else:value['customer_item_condition_claim']['opened']='true'
    with pytest.raises(ValueError,match='unbound_return_condition'):
        helper.check_return_condition_answer('Products must be unopened.',value,changed)


class ScriptedClient:
    def __init__(self,*answers):self.answers=list(answers);self.calls=[];self.last_metrics={}
    def complete(self,system,user,*args,**options):
        self.calls.append((json.loads(user),options));answer=self.answers.pop(0)
        if isinstance(answer,Exception):raise answer
        return json.dumps({'answer':answer,'covered':True,'needs_clarification':False})


def test_generation_repairs_requirement_polarity_once_without_policy_template(staged,sources):
    _,_,answers=staged
    client=ScriptedClient('No, your opened item cannot be returned. Products must be opened.',
                          'No, your opened item cannot be returned. Products must be unopened with the seal intact.')
    out=answers.document_reply(client,'I opened Aster Tint. Can I return it?','en',sources,
                               facts=facts(staged,sources),context_provenance=True)
    assert out['repair_attempted'] is True and len(client.calls)==2
    assert out['repair_errors']==['contradicted_return_condition_polarity:opened']
    assert client.calls[0][0]['source_text']==client.calls[1][0]['source_text']
    keys=('return_condition_policy','customer_item_condition_claim','ordinary_return_condition_check')
    assert client.calls[1][0]['deterministic_facts']=={key:client.calls[0][0]['deterministic_facts'][key] for key in keys}
    assert out['repair_mode']=='source_condition_application'
    assert 'verified_rule_summary' not in client.calls[1][0]
    assert out['citations']==[]


def test_repeated_wrong_requirement_fails_without_authored_fallback(staged,sources):
    _,_,answers=staged
    client=ScriptedClient(*['No, your opened item cannot be returned. Products must be opened.']*2)
    with pytest.raises(GenerationValidationError,match='^document_generation_failed:contradicted_return_condition_polarity$') as failure:
        answers.document_reply(client,'I opened Aster Tint. Can I return it?','en',sources,
                               facts=facts(staged,sources),context_provenance=True)
    assert len(client.calls)==2

    diagnostics=failure_diagnostics(failure.value)
    assert diagnostics['repair_errors']==['contradicted_return_condition_polarity', 'contradicted_return_condition_polarity']
    assert diagnostics['validation_error']=='contradicted_return_condition_polarity'
    assert diagnostics['generation_attempts']==len(client.calls)==2
    assert diagnostics['repair_attempted'] is True and len(diagnostics['attempt_metrics'])==2
    assert client.calls[1][0]['repair_validation_error']=='contradicted_return_condition_polarity:opened'


@pytest.mark.parametrize('answer',[
    'The product does not have to be opened; it must remain unopened.',
    'The product should not need to be opened; it must stay unopened.',
    "The product doesn't have to be opened. It must remain unopened.",
])
def test_negated_obligation_is_not_an_affirmative_opened_requirement(staged,sources,answer):
    helper,_,_=staged
    helper.check_return_condition_answer(answer,facts(staged,sources),sources)


@pytest.mark.parametrize('answer',[
    'The product does not have to be opened, but it must be opened.',
    'The policy does not require products to be opened, but the product must be opened.',
])
def test_negated_earlier_obligation_cannot_rescue_later_wrong_requirement(staged,sources,answer):
    helper,_,_=staged
    with pytest.raises(ValueError,match='contradicted_return_condition_polarity:opened'):
        helper.check_return_condition_answer(answer,facts(staged,sources),sources)
