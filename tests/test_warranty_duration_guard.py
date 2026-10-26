"""Source-derived warranty duration tests; all generation uses fake clients."""
import copy
import json
from types import SimpleNamespace

import pytest
from src.generation_diagnostics import GenerationValidationError,failure_diagnostics

@pytest.fixture(scope='module')
def staged():
    from src import warranty_durations as helper
    from src import document_context as context
    from src import document_answers as answers
    from src import grounding
    return helper, context, answers, grounding


@pytest.fixture
def sources():
    return [
        {'id':'CATALOG-X','file':'data/products.csv','text':json.dumps({'sku':'ITEM-X','title':'Fennel Sound Pod','brand':'Fennel','assured':'True','warranty_months':'7'}), 'doc_type':'catalog','status':'current'},
        {'id':'COVERAGE-Y','text':'Products marked `assured = true` in the catalog carry a 17-month Helio Secure warranty from the delivery date, in addition to any brand warranty. You can file claims in the app under My Orders.', 'doc_type':'policy','status':'current','effective_from':'2020-01-01','version':'fixture-current'},
        {'id':'BRAND-Z','text':"Most devices come with the manufacturer's warranty. The warranty period is listed in the `warranty_months` column of the product catalog. Brand warranty claims are made with the manufacturer service centre.", 'doc_type':'policy','status':'current','effective_from':'2020-01-01'},
    ]


def build(staged, sources, query='Does ITEM-X have Helio Secure? How do I claim?', public=None):
    _, context, _, _ = staged
    data = SimpleNamespace(products={},holidays=set(),pincodes={})
    return context.build_context(query, sources, data, public_context=public)


def test_offered_assurance_includes_only_the_source_derived_duration(staged, sources):
    facts = build(staged, sources)
    record = facts['warranty_duration']['assured']
    assert record['duration_months'] == 17 and record['benefit_name'] == 'Helio Secure'
    assert record['catalog_assured_flag'] is True and record['required_assured_flag'] is True
    assert record['sku'] == 'ITEM-X'
    assert set(record['source_ids']) == {'CATALOG-X','COVERAGE-Y'}
    assert set(record['source_sha256']) == set(record['source_ids'])
    assert facts['answer_constraints'] == [{'kind':'quantity','value':17,'unit':'month',
          'key':'warranty_duration.assured.duration_months','source_ids':record['source_ids']}]
    assert 'brand' not in facts['warranty_duration']
    assert 'verified_rule_summary' not in facts


@pytest.mark.parametrize('query',[
    'Does ITEM-X have Helio Secure? How do I claim?',
    'SKU ITEM-X pe Helio Secure hai kya? Claim kaise karein?',
    'How long is the Helio Secure warranty for ITEM-X?',
])
def test_eligibility_and_duration_questions_include_the_offered_period(staged, sources, query):
    assert build(staged,sources,query)['warranty_duration']['assured']['duration_months'] == 17


@pytest.mark.parametrize('query',[
    'Where do I file a Helio Secure claim?',
    'How do I file an Assured claim?',
    'What does Helio Secure not cover?',
    'Does ITEM-X have a brand warranty?',
    'How fast is delivery for ITEM-X?',
])
def test_route_only_exclusions_and_unrelated_questions_do_not_require_duration(staged,sources,query):
    facts=build(staged,sources,query)
    assert 'warranty_duration' not in facts
    assert not [item for item in facts['answer_constraints'] if item.get('unit') == 'month']


@pytest.mark.parametrize('flag',[False,'False',None,'yes',1])
def test_missing_ambiguous_and_nonqualifying_catalog_flags_do_not_become_positive_assurance(staged,sources,flag):
    changed=copy.deepcopy(sources)
    row=json.loads(changed[0]['text']);row['assured']=flag;changed[0]['text']=json.dumps(row)
    assert 'warranty_duration' not in build(staged,changed)


@pytest.mark.parametrize('mutation',['missing_catalog','missing_policy','superseded','future','wrong_unit','ambiguous_duration','negated_rule'])
def test_assurance_duration_needs_unambiguous_current_policy_and_catalog(staged,sources,mutation):
    changed=copy.deepcopy(sources)
    if mutation == 'missing_catalog': changed.pop(0)
    elif mutation == 'missing_policy': changed.pop(1)
    elif mutation == 'superseded': changed[1]['status']='superseded'
    elif mutation == 'future': changed[1]['effective_from']='2099-01-01'
    elif mutation == 'wrong_unit': changed[1]['text']=changed[1]['text'].replace('17-month','17-day')
    elif mutation == 'ambiguous_duration': changed.append(dict(changed[1],id='OTHER-Y',text=changed[1]['text'].replace('17-month','19-month')))
    else: changed[1]['text']=changed[1]['text'].replace('carry a','do not carry a')
    assert 'warranty_duration' not in build(staged,changed)


def test_source_mutation_changes_duration_name_and_flag_requirement(staged,sources):
    changed=copy.deepcopy(sources)
    changed[1]['text']=changed[1]['text'].replace('17-month','23-month').replace('Helio Secure','Aster Protect').replace('assured = true','assured = false')
    row=json.loads(changed[0]['text']);row['assured']='False';changed[0]['text']=json.dumps(row)
    facts=build(staged,changed,'Does ITEM-X have Aster Protect?')
    record=facts['warranty_duration']['assured']
    assert record['duration_months'] == 23 and record['benefit_name'] == 'Aster Protect'
    assert record['required_assured_flag'] is False and record['catalog_assured_flag'] is False


def test_explicit_public_sku_cannot_borrow_other_catalog_record(staged,sources):
    assert 'warranty_duration' not in build(staged,sources,public={'sku':'OTHER-ITEM'})


def test_multiple_catalog_items_require_one_actual_selected_sku(staged,sources):
    changed=copy.deepcopy(sources)
    row=json.loads(changed[0]['text']);row['sku']='ITEM-Y'
    changed.append(dict(changed[0],id='CATALOG-OTHER',text=json.dumps(row)))
    assert 'warranty_duration' not in build(staged,changed,'Does my product have Helio Secure?')
    assert build(staged,changed)['warranty_duration']['assured']['sku'] == 'ITEM-X'


@pytest.mark.parametrize('query',[
    'How long is the brand warranty for ITEM-X?',
    'What is the manufacturer warranty period for ITEM-X?',
    'How many months is the warranty for ITEM-X?',
    'ITEM-X ki warranty kitne mahine hai?',
])
def test_brand_duration_comes_from_catalog_column_and_its_authorizing_source(staged,sources,query):
    facts=build(staged,sources,query)
    record=facts['warranty_duration']['brand']
    assert record['duration_months'] == 7 and record['catalog_column'] == 'warranty_months'
    assert set(record['source_ids']) == {'CATALOG-X','BRAND-Z'}
    assert 'assured' not in facts['warranty_duration']


@pytest.mark.parametrize('mutation',['missing_link','negated_link','superseded','zero','bool','invalid','missing_catalog'])
def test_brand_duration_is_not_guessed_from_assurance_or_invalid_catalog(staged,sources,mutation):
    changed=copy.deepcopy(sources)
    if mutation == 'missing_link': changed.pop(2)
    elif mutation == 'negated_link': changed[2]['text']=changed[2]['text'].replace('is listed','is not listed')
    elif mutation == 'superseded': changed[2]['status']='superseded'
    elif mutation == 'missing_catalog': changed.pop(0)
    else:
        row=json.loads(changed[0]['text']);row['warranty_months']={'zero':'0','bool':True,'invalid':'unknown'}[mutation];changed[0]['text']=json.dumps(row)
    assert 'warranty_duration' not in build(staged,changed,'How long is the brand warranty for ITEM-X?')


@pytest.mark.parametrize('tamper',['value','unit','key','source_id','record_value','record_flag','hash','source_duration','source_catalog','source_authority'])
def test_month_constraint_is_independently_rebound_to_source_entity_and_catalog(staged,sources,tamper):
    _,_,answers,_=staged
    changed=copy.deepcopy(sources);facts=build(staged,changed);item=facts['answer_constraints'][0]
    if tamper == 'value': item['value']=7
    elif tamper == 'unit': item['unit']='hour'
    elif tamper == 'key': item['key']='catalog.duration_months'
    elif tamper == 'source_id': item['source_ids']=['BRAND-Z']
    elif tamper == 'record_value': facts['warranty_duration']['assured']['duration_months']=7;item['value']=7
    elif tamper == 'record_flag': facts['warranty_duration']['assured']['catalog_assured_flag']=False
    elif tamper == 'hash': facts['warranty_duration']['assured']['source_sha256']['COVERAGE-Y']='0'*64
    elif tamper == 'source_duration': changed[1]['text']=changed[1]['text'].replace('17-month','19-month')
    elif tamper == 'source_catalog':
        row=json.loads(changed[0]['text']);row['assured']='False';changed[0]['text']=json.dumps(row)
    else: changed[1]['status']='superseded'
    with pytest.raises(ValueError,match='unbound_|unsupported_|invalid_'):
        answers._validated_constraints(facts,changed)


@pytest.mark.parametrize('answer',[
    'ITEM-X has Helio Secure. You can file claims in the app under My Orders.',
    'Helio Secure lasts 17 days.',
    'Helio Secure lasts 17 hours.',
    'The brand warranty lasts 17 months. Helio Secure is available.',
    'Fennel warranty lasts 17 months. Helio Secure is available.',
    'Helio Secure is not 17 months.',
])
def test_missing_wrong_unit_or_other_entity_duration_does_not_satisfy_assurance(staged,sources,answer):
    _,_,answers,_=staged
    facts=build(staged,sources)
    with pytest.raises(ValueError,match='answer_constraint_missing:warranty_duration.assured.duration_months'):
        answers._check_answer_constraints(answer,facts,sources)


@pytest.mark.parametrize('answer',[
    'Helio Secure lasts 17 months. You can file claims in the app under My Orders.',
    'ITEM-X has a 17-month Helio Secure warranty.',
    'Helio Secure ki warranty 17 mahine hai.',
    'Helio Secure 17 \u092e\u0939\u0940\u0928\u0947 \u0915\u0940 \u0935\u093e\u0930\u0902\u091f\u0940 \u0939\u0948\u0964',
])
def test_supported_month_wording_in_primary_languages_satisfies_constraint(staged,sources,answer):
    _,_,answers,_=staged
    answers._check_answer_constraints(answer,build(staged,sources),sources)


def test_both_warranties_keep_separate_source_derived_durations(staged,sources):
    _,_,answers,_=staged
    facts=build(staged,sources,'How long are Helio Secure and the brand warranty for ITEM-X?')
    assert set(facts['warranty_duration']) == {'assured','brand'}
    answers._check_answer_constraints('Helio Secure lasts 17 months. The brand warranty lasts 7 months.',facts,sources)
    for answer in ('The brand warranty lasts 17 months. Helio Secure lasts 7 months.',
                   'Helio Secure and the brand warranty last 17 months.',
                   'Both warranties last 7 months.'):
        with pytest.raises(ValueError,match='answer_constraint_missing'):
            answers._check_answer_constraints(answer,facts,sources)


def test_same_number_under_other_month_entity_cannot_satisfy_both(staged,sources):
    _,_,answers,_=staged
    changed=copy.deepcopy(sources);row=json.loads(changed[0]['text']);row['warranty_months']='17';changed[0]['text']=json.dumps(row)
    facts=build(staged,changed,'How long are Helio Secure and the brand warranty for ITEM-X?')
    with pytest.raises(ValueError,match='answer_constraint_missing'):
        answers._check_answer_constraints('The brand warranty lasts 17 months. Helio Secure is available.',facts,changed)


def test_month_units_stay_distinct_from_days_and_roman_hinglish_is_measured(staged):
    _,_,_,grounding=staged
    assert ('17','month') in grounding._quantities('17 mahine')
    assert ('17','month') in grounding._quantities('17 mahina')
    assert ('17','day') in grounding._quantities('17 days')
    assert not grounding._quantity_supported(('17','month'), {('17','day')})


class ScriptedClient:
    def __init__(self,*answers):self.answers=list(answers);self.calls=[];self.last_metrics={}
    def complete(self,system,user,*args,**options):
        self.calls.append((json.loads(user),options))
        answer=self.answers.pop(0)
        if isinstance(answer,Exception):raise answer
        return json.dumps({'answer':answer,'covered':True,'needs_clarification':False})


def test_generation_repairs_duration_omission_once_with_same_actual_context(staged,sources):
    _,_,answers,_=staged
    client=ScriptedClient('Helio Secure is available. You can file claims in the app under My Orders.',
                          'Helio Secure lasts 17 months. You can file claims in the app under My Orders.')
    facts=build(staged,sources)
    out=answers.document_reply(client,'Does ITEM-X have Helio Secure? How do I claim?','en',sources,
                               facts=facts,context_provenance=True)
    assert out['generation_attempts'] == 2 and out['repair_attempted'] is True
    assert out['repair_errors'] == ['answer_constraint_missing:warranty_duration.assured.duration_months']
    assert out['citations'] == [] and out['provenance_kind'] == 'generation_context'
    assert client.calls[0][0]['source_text'] == client.calls[1][0]['source_text']
    assert client.calls[0][0]['deterministic_facts'] == client.calls[1][0]['deterministic_facts']
    assert 'verified_rule_summary' not in client.calls[1][0]


def test_repeated_omission_raises_without_authored_policy_fallback(staged,sources):
    _,_,answers,_=staged
    client=ScriptedClient(*['Helio Secure is available. You can file claims in the app under My Orders.']*2)
    with pytest.raises(GenerationValidationError,match='^document_generation_failed:answer_constraint_missing$') as failure:
        answers.document_reply(client,'Does ITEM-X have Helio Secure? How do I claim?','en',sources,
                               facts=build(staged,sources),context_provenance=True)
    assert len(client.calls) == 2

    diagnostics=failure_diagnostics(failure.value)
    assert diagnostics['repair_errors']==['answer_constraint_missing', 'answer_constraint_missing']
    assert diagnostics['validation_error']=='answer_constraint_missing'
    assert diagnostics['generation_attempts']==len(client.calls)==2
    assert diagnostics['repair_attempted'] is True and len(diagnostics['attempt_metrics'])==2
    assert client.calls[1][0]['repair_validation_error']=='answer_constraint_missing:warranty_duration.assured.duration_months'


def test_provider_failure_does_not_render_a_warranty_template(staged,sources):
    from src.llm import LLMUnavailable
    _,_,answers,_=staged
    client=ScriptedClient(LLMUnavailable('synthetic outage'))
    with pytest.raises(LLMUnavailable):
        answers.document_reply(client,'Does ITEM-X have Helio Secure? How do I claim?','en',sources,
                               facts=build(staged,sources),context_provenance=True)
    assert len(client.calls) == 1


@pytest.mark.parametrize('answer', [
    'Helio Secure lasts 7 months.',
    'Pickup takes 7 months.',
    'Helio Secure is available. It lasts 7 months.',
])
def test_brand_constraint_cannot_borrow_assurance_or_unrelated_month_quantity(staged,sources,answer):
    _,_,answers,_=staged
    facts=build(staged,sources,'How long is the brand warranty for ITEM-X?')
    with pytest.raises(ValueError,match='answer_constraint_missing:warranty_duration.brand.duration_months'):
        answers._check_answer_constraints(answer,facts,sources)


def test_assurance_pronoun_cannot_borrow_a_preceding_brand_subject(staged,sources):
    _,_,answers,_=staged
    facts=build(staged,sources)
    with pytest.raises(ValueError,match='answer_constraint_missing:warranty_duration.assured.duration_months'):
        answers._check_answer_constraints('The brand warranty is available. It lasts 17 months.',facts,sources)


@pytest.mark.parametrize('query', [
    'Assured claim kaise karna hai?',
    'Helio Secure claim file karna hai kya?',
    'Helio Secure claim kahan karna hai?',
    'Helio Secure \u0915\u094d\u0932\u0947\u092e \u0915\u0948\u0938\u0947 \u0915\u0930\u0928\u093e \u0939\u0948?',
    'Helio Secure \u0926\u093e\u0935\u093e \u0915\u0939\u093e\u0901 \u0915\u0930\u0928\u093e \u0939\u0948?',
])
def test_copula_in_pure_claim_route_does_not_create_duration_obligation(staged,sources,query):
    assert 'warranty_duration' not in build(staged,sources,query)


@pytest.mark.parametrize('months,wording', [(12,'one-year'), (24,'2 years'), (6,'0.5 years')])
def test_exact_year_equivalents_preserve_source_derived_month_duration(staged,sources,months,wording):
    _,_,answers,_=staged
    changed=copy.deepcopy(sources)
    changed[1]['text']=changed[1]['text'].replace('17-month',str(months)+'-month')
    facts=build(staged,changed)
    answer='Helio Secure is a '+wording+' warranty. You can file claims in the app under My Orders.'
    answers._check_answer_constraints(answer,facts,changed)
    client=ScriptedClient(answer)
    out=answers.document_reply(client,'Does ITEM-X have Helio Secure? How do I claim?','en',changed,
                               facts=facts,context_provenance=True)
    assert out['answer']==answer and len(client.calls)==1


def test_year_conversion_does_not_authorize_day_or_unrelated_number_claims(staged,sources):
    _,_,answers,grounding=staged
    assert not grounding._quantity_supported(('1','year'),{('12','day')})
    assert not grounding._quantity_supported(('12','month'),{('1','day')})
    changed=copy.deepcopy(sources)
    changed[1]['text']=changed[1]['text'].replace('17-month','12-month')
    facts=build(staged,changed)
    client=ScriptedClient(*['Helio Secure lasts 1 year. Pickup takes 99 days.']*2)
    with pytest.raises(ValueError,match='unsupported_number|unsupported_quantity_unit'):
        answers.document_reply(client,'Does ITEM-X have Helio Secure? How do I claim?','en',changed,
                               facts=facts,context_provenance=True)
    assert len(client.calls)==2
