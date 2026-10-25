"""Definite customer-state assertions remain distinct from source requirements."""
import copy,json
import pytest
from src import return_conditions as helper
from src.document_answers import document_reply,CONTEXT_SYSTEM,CONTEXT_LANGUAGE

SOURCES=[{'id':'novel-rule','text':'Cosmetics products are returnable only if unopened with the seal intact.','doc_type':'policy','status':'current','effective_from':'2020-01-01'},
         {'id':'novel-catalog','text':json.dumps({'sku':'ASTER-X','title':'Aster Tint','return_category':'cosmetics_sealed'}),'doc_type':'catalog','status':'current'}]
QUERY='I opened Aster Tint. Can I return it?'
def facts(query=QUERY,sources=SOURCES):return {'reference_date':'2026-10-20',**helper.return_condition_context(query,sources,reference_date='2026-10-20')}
def check(answer,query=QUERY,sources=SOURCES):return helper.check_return_condition_answer(answer,facts(query,sources),sources)

@pytest.mark.parametrize('answer',[
    'No, you cannot return it because it is unopened. You opened the product.',
    'Your item is unopened, but the policy requires unopened products.',
    'The product was unopened.',
    'Aster Tint is unopened.',
    'It remains unopened.',
    'If you contact support, it is unopened.',
    'I cannot confirm other details, but it is unopened.',
    'It is not opened.',
    'It unopened hai.',
    '\u092f\u0939 \u0905\u0928\u0916\u0941\u0932\u093e \u0939\u0948\u0964',
])
def test_a_required_state_cannot_be_asserted_as_the_opposite_customer_state(answer):
    with pytest.raises(ValueError,match='contradicted_customer_item_premise:opened'):check(answer)

@pytest.mark.parametrize('answer',[
    'No, you said you opened the product; the policy requires it to remain unopened.',
    'Your item is opened. The ordinary return condition requires unopened products.',
    'The product must remain unopened for an ordinary return.',
    'If it is unopened, it meets that necessary condition.',
    'If your item is unopened, that satisfies the unopened condition.',
    'Assuming Aster Tint is unopened, that condition is satisfied.',
    'I cannot confirm whether it is unopened.',
    'I cannot verify that it is unopened.',
    'The policy requires that it is unopened.',
    'The box is unopened; you said you opened the product.',
    'Another product is unopened.',
    'Your product may be unopened.',
    'It is opened.',
    '\u092f\u0939 \u0916\u0941\u0932\u093e \u0939\u0948\u0964',
])
def test_requirements_conditions_uncertainty_and_unrelated_states_are_preserved(answer):check(answer)

def test_customer_stated_unopened_cannot_be_rewritten_as_opened():
    with pytest.raises(ValueError,match='contradicted_customer_item_premise:opened'):
        check('Your product is opened.','I have not opened Aster Tint. Can I return it?')

def test_only_explicit_seal_state_is_compared_without_inference_from_opening():
    check('Its seal is intact.') # Opening is explicit; a broken seal was not claimed.
    with pytest.raises(ValueError,match='contradicted_customer_item_premise:seal_intact'):
        check('Its seal is intact.','I opened Aster Tint and broke the seal. Can I return it?')
    with pytest.raises(ValueError,match='contradicted_customer_item_premise:seal_intact'):
        check('Your seal is broken.','I have Aster Tint. The seal is intact. Can I return it?')

def test_unknown_or_ambiguous_customer_state_stays_unresolved():
    check('It is unopened.','Can I return Aster Tint?')
    check('It is unopened.','I might have opened Aster Tint. Can I return it?')

def test_no_state_claim_is_promoted_to_verification():
    value=facts();assert value['customer_item_condition_claim']['input_status']=='customer_provided_unverified'
    before=copy.deepcopy(value);helper.check_return_condition_answer('It is opened.',value,SOURCES)
    assert value==before

def test_changed_policy_and_catalog_are_rebound_instead_of_using_an_opened_ban():
    changed=copy.deepcopy(SOURCES);changed[0]['text']=changed[0]['text'].replace('unopened','opened')
    check('It is opened.',sources=changed)
    with pytest.raises(ValueError,match='contradicted_customer_item_premise:opened'):
        check('It is unopened.',sources=changed)
    with pytest.raises(ValueError,match='unbound_return_condition'):
        helper.check_return_condition_answer('It is opened.',facts(),changed)

class Client:
    def __init__(self,*answers):self.answers=list(answers);self.calls=[]
    def complete(self,system,user,**options):
        self.calls.append((system,json.loads(user),options));assert self.answers
        return json.dumps({'answer':self.answers.pop(0),'covered':True,'needs_clarification':False})

def test_one_repair_uses_only_original_inputs_with_unchanged_primary_prompt():
    client=Client('No, because it is unopened.','No, your statement that you opened it conflicts with the unopened condition.')
    out=document_reply(client,QUERY,'en',SOURCES,facts=facts(),context_provenance=True)
    assert out['generation_attempts']==2 and out['repair_errors']==['contradicted_customer_item_premise:opened']
    first,second=client.calls
    assert first[0]==second[0]==CONTEXT_SYSTEM+'\n'+CONTEXT_LANGUAGE['en']
    assert set(first[1])=={'source_text','deterministic_facts','reference_date','language','question'}
    assert first[1]['source_text']==second[1]['source_text']
    assert first[1]['deterministic_facts']==second[1]['deterministic_facts']
    assert 'unverified' in second[1]['repair_instruction']
    assert first[2]['cache'] is True and second[2]['cache'] is False

def test_repeated_wrong_premise_fails_after_exactly_two_calls():
    client=Client('It is unopened.','It is unopened.')
    with pytest.raises(ValueError,match='contradicted_customer_item_premise:opened'):
        document_reply(client,QUERY,'en',SOURCES,facts=facts(),context_provenance=True)
    assert len(client.calls)==2
