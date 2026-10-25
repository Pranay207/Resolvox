"""Isolated draft tests; no original source edits, model calls or data mutations."""
import copy
import json
from types import SimpleNamespace

import pytest

@pytest.fixture(scope='module')
def staged():
    from src import return_conditions as helper
    from src import document_context as context
    from src import document_answers as answers
    return helper, context, answers

@pytest.fixture
def sources():
    return [
        {'id':'SYNTHETIC-CONDITION','text':'Cosmetics products are returnable only if unopened with the seal intact.',
         'doc_type':'policy','status':'current','effective_from':'2020-01-01','version':'fixture-one'},
        {'id':'SYNTHETIC-CATALOG','text':json.dumps({'sku':'ITEM-X','title':'Aster Tint',
             'return_category':'cosmetics_sealed'}),'doc_type':'catalog','status':'current'},
    ]


def facts(staged, sources, query='I opened Aster Tint. Can I return it?'):
    _, context, _ = staged
    data = SimpleNamespace(products={},holidays=set(),pincodes={})
    return context.build_context(query,sources,data)


def test_rule_and_customer_claim_are_typed_source_bound_and_unverified(staged,sources):
    value = facts(staged,sources)
    policy = value['return_condition_policy']
    assert policy['requirements']=={'opened':False,'seal_intact':True}
    assert set(policy['source_ids'])=={s['id'] for s in sources}
    assert value['customer_item_condition_claim']['opened'] is True
    assert value['customer_item_condition_claim']['input_status']=='customer_provided_unverified'
    assert 'verified_order' not in value
    assert value['ordinary_return_condition_check']['status']=='not_satisfied'
    assert 'eligible' not in policy


@pytest.mark.parametrize('query',[
    'I opened Aster Tint. Can I return it?',
    'मैंने Aster Tint खोल लिया है, क्या वापस कर सकती हूँ?',
    'Maine Aster Tint khol liya. Kya return kar sakti hoon?',
])
def test_explicit_item_assertions_in_primary_languages(staged,sources,query):
    value=facts(staged,sources,query)
    assert value['customer_item_condition_claim']['opened'] is True
    assert value['ordinary_return_condition_check']['status']=='not_satisfied'


@pytest.mark.parametrize('query',[
    'I have not opened Aster Tint. Can I return it?',
    "I haven't opened Aster Tint. Can I return it?",
    'मैंने Aster Tint नहीं खोला है, क्या वापस कर सकती हूँ?',
    'Maine Aster Tint khola nahi. Return possible hai?',
    'If I opened Aster Tint, could I return it?',
    'Maybe I opened Aster Tint. Can I return it?',
    'I may have opened Aster Tint. Can I return it?',
    'I opened the shipping box for Aster Tint. Can I return it?',
    'I opened Aster Tint. I have not opened Aster Tint. Can I return it?',
    'Can opened cosmetics products be returned?',
])
def test_negated_ambiguous_or_packaging_statements_do_not_create_a_denial(staged,sources,query):
    value=facts(staged,sources,query)
    assert value['ordinary_return_condition_check']['status']=='unresolved'


@pytest.mark.parametrize('query',[
    'I opened Aster Tint, but it is defective. Can I return it?',
    'I opened Aster Tint and received the wrong item. Can I return it?',
    'I opened Aster Tint. It arrived with a broken seal. Can I return it?',
    'मैंने Aster Tint खोल लिया और वह खराब है।',
])
def test_exception_scope_never_becomes_a_blanket_ordinary_return_denial(staged,sources,query):
    helper,_,_=staged
    value=facts(staged,sources,query+' Can I return it?')
    assert value['ordinary_return_condition_check']['status']=='unresolved'
    helper.check_return_condition_answer('A defective item may need a separate remedy.',value,sources)


def test_explicit_customer_broken_seal_is_distinct_from_arrived_broken(staged,sources):
    value=facts(staged,sources,'I broke the seal on Aster Tint. Can I return it?')
    assert value['customer_item_condition_claim']['seal_intact'] is False
    assert value['ordinary_return_condition_check']['status']=='not_satisfied'
    value=facts(staged,sources,'I did not break the seal on Aster Tint. Can I return it?')
    assert 'seal_intact' not in value['customer_item_condition_claim']
    assert value['ordinary_return_condition_check']['status']=='unresolved'


@pytest.mark.parametrize('change',[
    'missing','superseded','future','different_category','disjunction','exception','conflicting',
])
def test_absent_or_ambiguous_rule_evidence_produces_no_condition_fact(staged,sources,change):
    changed=copy.deepcopy(sources)
    if change=='missing':changed.pop(0)
    elif change=='superseded':changed[0]['status']='superseded'
    elif change=='future':changed[0]['effective_from']='2099-01-01'
    elif change=='different_category':
        row=json.loads(changed[1]['text']);row['return_category']='books';changed[1]['text']=json.dumps(row)
    elif change=='disjunction':changed[0]['text']='Cosmetics products are returnable only if unopened or approved by the manufacturer.'
    elif change=='exception':changed[0]['text']='Cosmetics products are returnable only if unopened unless defective.'
    else:changed.append(dict(changed[0],id='OTHER-CONDITION',text='Cosmetics products are returnable only if the seal intact.'))
    assert 'return_condition_policy' not in facts(staged,changed)


def test_changed_source_recomputes_necessary_conditions_instead_of_preserving_opened_ban(staged,sources):
    helper,_,_=staged
    old=facts(staged,sources)
    changed=copy.deepcopy(sources)
    changed[0]['text']='Cosmetics products are returnable only if the seal intact.'
    new=facts(staged,changed)
    assert new['return_condition_policy']['requirements']=={'seal_intact':True}
    assert new['ordinary_return_condition_check']['status']=='unresolved'
    with pytest.raises(ValueError,match='unbound_return_condition'):
        helper.check_return_condition_answer('No, an ordinary return is unavailable.',old,changed)
    changed[0]['text']='Cosmetics products can be returned even if opened.'
    assert 'return_condition_policy' not in facts(staged,changed)


@pytest.mark.parametrize('answer',[
    'Yes, you can return it. However, opened products are not returnable.',
    'No, you can return it.',
    'You can return it because it is not damaged.',
    'You can return it, but an opened item is not eligible.',
    'Your item is eligible for return. The item must be unopened.',
    'हाँ, आप वापस कर सकती हैं। लेकिन खुला उत्पाद वापस नहीं हो सकता।',
    'आप वापस कर सकती हैं, लेकिन खुला सामान नहीं लौट सकता।',
    'Haan, aap return kar sakti hain. Opened item return nahi hota.',
])
def test_affirmative_then_negative_contradictions_are_rejected(staged,sources,answer):
    helper,_,_=staged
    with pytest.raises(ValueError,match='contradicted_return_condition'):
        helper.check_return_condition_answer(answer,facts(staged,sources),sources)


@pytest.mark.parametrize('answer',[
    'No, you cannot return the opened product for an ordinary return.',
    'Unopened sealed products can be returned; your opened product does not meet that condition.',
    'If it were unopened, you could return it; your opened product does not meet that condition.',
    'नहीं, आप खुला उत्पाद वापस नहीं कर सकती हैं। सील सही होनी चाहिए।',
    'Aap opened item return nahi kar sakti hain; seal intact chahiye.',
])
def test_safe_negative_and_counterfactual_explanations_are_preserved(staged,sources,answer):
    helper,_,_=staged
    helper.check_return_condition_answer(answer,facts(staged,sources),sources)


@pytest.mark.parametrize('tamper',['rule','hash','source_id','category','claim_type'])
def test_condition_facts_cannot_be_detached_from_actual_source_and_category(staged,sources,tamper):
    helper,_,_=staged
    value=copy.deepcopy(facts(staged,sources))
    if tamper=='rule':value['return_condition_policy']['requirements']['opened']=True
    elif tamper=='hash':value['return_condition_policy']['source_sha256']['SYNTHETIC-CONDITION']='0'*64
    elif tamper=='source_id':value['return_condition_policy']['source_ids']=['INVENTED']
    elif tamper=='category':value['return_condition_policy']['category']='books'
    else:value['customer_item_condition_claim']['opened']='true'
    with pytest.raises(ValueError,match='unbound_return_condition'):
        helper.check_return_condition_answer('No, the condition is not met.',value,sources)


class ScriptedClient:
    def __init__(self,*answers):self.answers=list(answers);self.calls=[];self.last_metrics={}
    def complete(self,system,user,*args,**options):
        self.calls.append((json.loads(user),options))
        value=self.answers.pop(0)
        if isinstance(value,Exception):raise value
        return json.dumps({'answer':value,'covered':True,'needs_clarification':False})


def test_normal_generation_repairs_a_contradiction_once_using_same_evidence(staged,sources):
    _,_,answers=staged
    client=ScriptedClient('Yes, you can return it. Opened items are not returnable.',
                          'No, the opened product does not meet the unopened and intact-seal conditions for an ordinary return.')
    value=facts(staged,sources)
    out=answers.document_reply(client,'I opened Aster Tint. Can I return it?','en',sources,
                              facts=value,context_provenance=True)
    assert len(client.calls)==2 and out['repair_attempted'] is True
    assert out['repair_errors']==['contradicted_return_condition']
    assert out['citations']==[] and out['provenance_kind']=='generation_context'
    assert client.calls[0][0]['source_text']==client.calls[1][0]['source_text']
    assert 'verified_rule_summary' not in client.calls[1][0]


def test_repeated_contradiction_never_returns_an_authored_policy_fallback(staged,sources):
    _,_,answers=staged
    client=ScriptedClient('Yes, you can return it.','Yes, you can return it.')
    with pytest.raises(ValueError,match='contradicted_return_condition'):
        answers.document_reply(client,'I opened Aster Tint. Can I return it?','en',sources,
                               facts=facts(staged,sources),context_provenance=True)
    assert len(client.calls)==2


def test_provider_failure_does_not_create_a_policy_answer(staged,sources):
    from src.llm import LLMUnavailable
    _,_,answers=staged
    client=ScriptedClient(LLMUnavailable('synthetic outage'))
    with pytest.raises(LLMUnavailable):
        answers.document_reply(client,'I opened Aster Tint. Can I return it?','en',sources,
                               facts=facts(staged,sources),context_provenance=True)
    assert len(client.calls)==1


@pytest.mark.parametrize('text',[
    'Cosmetics products are returnable only if not unopened with the seal intact.',
    'Cosmetics products are not returnable only if unopened with the seal intact.',
])
def test_negated_rule_grammar_is_left_unresolved(staged,sources,text):
    changed=copy.deepcopy(sources);changed[0]['text']=text
    assert 'return_condition_policy' not in facts(staged,changed)


@pytest.mark.parametrize('query',[
    'I opened Aster Tint. It is not damaged. Can I return it?',
    'I opened Aster Tint. It is not defective. Can I return it?',
    'Maine Aster Tint khol liya. Yeh kharab nahi hai. Can I return it?',
])
def test_explicitly_negated_damage_does_not_bypass_ordinary_condition(staged,sources,query):
    value=facts(staged,sources,query)
    assert value['ordinary_return_condition_check']['status']=='not_satisfied'


def test_unrelated_warranty_question_does_not_receive_a_return_constraint(staged,sources):
    assert 'return_condition_policy' not in facts(staged,sources,'I opened Aster Tint. Does the warranty cover repair?')


def test_service_affirmation_is_not_mistaken_for_eligibility(staged,sources):
    helper,_,_=staged
    helper.check_return_condition_answer('Yes, I can explain the policy. Your opened product does not meet the ordinary return condition.',facts(staged,sources),sources)
