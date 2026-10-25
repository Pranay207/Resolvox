"""Operational input questions carry no business policy answer; no inference."""
import copy
import pytest
from src.source_inputs import source_input_clarification

SOURCE={'id':'unseen-table', 'text':'| Category | Window | Code |\n| Orchids | 17 calendar days | orchid |\n| Irises | 21 calendar days | iris |\n\n| Method | Timeline |\n| Card | 4 business days |\n| Wallet | 2 calendar days |', 'doc_type':'policy','status':'current','effective_from':'2020-01-01'}


def facts(key='return_category'):
    rows=([{'return_category':'orchid','return_window':'17 calendar days'},
           {'return_category':'iris','return_window':'21 calendar days'}] if key=='return_category'
          else [{'label':'Card','timeline':'4 business days'},
                {'label':'Wallet','timeline':'2 calendar days'}])
    return {'required_application_inputs':[{'key':key,'source_ids':[SOURCE['id']],'allowed_rows':rows}]}


@pytest.mark.parametrize('lang',['en','hi','hi-en'])
@pytest.mark.parametrize('key',['return_category','payment_method'])
def test_bound_missing_field_asks_one_neutral_question_without_generation(lang,key):
    original=facts(key); saved=copy.deepcopy(original)
    out=source_input_clarification(original,[SOURCE],lang)
    assert out['decision']=='clarify' and out['covered'] is False
    assert out['answer'].endswith('?')
    assert not any(value in out['answer'] for value in ('17','21','4 business','2 calendar','orchid','iris'))
    assert out['source_ids']==[SOURCE['id']]
    assert out['generation_attempts']==0 and not out['repair_attempted']
    assert out['decision_origin']=='host_source_table_input'
    assert out['provenance_kind']=='source_table_input'
    assert out['model_flags'] is None and out['context_source_ids']==[]
    assert out['required_input']==key and original==saved


@pytest.mark.parametrize('lang',['en','hi','hi-en'])
def test_no_source_obligation_means_no_template_or_answer(lang):
    assert source_input_clarification({},[SOURCE],lang) is None
    assert source_input_clarification({'required_application_inputs':[]},[],lang) is None


@pytest.mark.parametrize('mutation',[
    lambda f: f.update(required_application_inputs='bad'),
    lambda f: f['required_application_inputs'].__setitem__(0,'bad'),
    lambda f: f['required_application_inputs'][0].update(key='customer_phone'),
    lambda f: f['required_application_inputs'][0].update(source_ids=['not-supplied']),
    lambda f: f['required_application_inputs'][0].update(source_ids=[]),
    lambda f: f['required_application_inputs'][0].update(allowed_rows=[]),
    lambda f: f['required_application_inputs'][0]['allowed_rows'][0].update(return_window='98 calendar days'),
])
def test_unbound_or_invalid_metadata_cannot_trigger_operational_rendering(mutation):
    value=facts(); mutation(value)
    with pytest.raises(ValueError): source_input_clarification(value,[SOURCE],'en')


@pytest.mark.parametrize('lang',['en','hi','hi-en'])
def test_agent_trace_does_not_mislabel_workflow_prompt_as_a_model_call(monkeypatch,lang):
    import src.agent as module
    r=module.Resources(dense=False)
    r.llm.last_metrics={'cache_hit':True,'elapsed_ms':12345}
    def forbidden(*args,**kwargs): raise AssertionError('workflow question made a model call')
    monkeypatch.setattr(r.llm,'complete',forbidden)
    out=module.Agent(r,compose=True).respond('How many days do I have to return an item?',lang)
    assert out['decision']=='clarify'
    assert out['composition']=='source_input_clarification'
    assert out['generation']['required_input']=='return_category'
    assert out['generation']['generation_attempts']==0
    assert out['generation_context_sources']==[]
    assert out['llm']=={} and out['timings']['llm_ms']==0
    assert out['evidence_supported'] and 'RET-2' in out['retrieved_chunk_ids']
    assert not out['tool_calls']


def test_known_category_keeps_normal_source_generation(monkeypatch):
    import src.agent as module
    r=module.Resources(dense=False); seen=[]
    def generated(client,query,language,sources,**options):
        seen.append(options)
        return {'answer':'Synthetic complete answer.', 'source_ids':[s['id'] for s in sources],
                'decision':'answer','generation_attempts':1,'decision_origin':'host_boolean_mapping'}
    monkeypatch.setattr(module,'document_reply',generated)
    out=module.Agent(r,compose=True).respond('How many days can I return shoes?','en')
    assert seen and out['composition']=='grounded_llm'
    assert not seen[0]['facts'].get('required_application_inputs')
    assert out['generation_context_sources']


def test_offline_source_excerpts_are_not_workflow_or_live_answers(monkeypatch):
    import src.agent as module
    r=module.Resources(dense=False)
    out=module.Agent(r,compose=False).respond('How many days do I have to return an item?','en')
    assert out['composition']=='document_excerpts'
    assert out['generation']=={} and out['llm']=={}


def test_agent_invalid_source_obligation_abstains_without_a_model_call(monkeypatch):
    import src.agent as module
    r=module.Resources(dense=False)
    monkeypatch.setattr(module,'build_context',lambda *a,**k:facts())
    def forbidden(*a,**k):raise AssertionError('unbound input made a model call')
    monkeypatch.setattr(r.llm,'complete',forbidden)
    out=module.Agent(r,compose=True).respond('What is the shoe return policy?','en')
    assert out['composition']=='abstained_model_or_evidence'
    assert out['validation_error']=='unbound_required_application_input'
    assert out['generation_context_sources']
    assert out['llm']=={} and out['timings']['llm_ms']==0
    assert '17 calendar days' not in out['answer']


@pytest.mark.parametrize('mutation',[
    lambda source:source.update(doc_type='catalog'),
    lambda source:source.update(status='superseded'),
    lambda source:source.update(effective_from='2099-01-01'),
    lambda source:source.pop('effective_from'),
    lambda source:source.update(text='orchid 17 calendar days; iris 21 calendar days'),
])
def test_only_current_effective_policy_tables_can_create_workflow(mutation):
    source=copy.deepcopy(SOURCE);mutation(source)
    with pytest.raises(ValueError,match='unbound_required_application_input'):
        source_input_clarification(facts(),[source],'en')


def test_values_from_different_rows_cannot_be_combined():
    value=facts();value['required_application_inputs'][0]['allowed_rows'][0]['return_window']='21 calendar days'
    with pytest.raises(ValueError,match='unbound_required_application_input'):
        source_input_clarification(value,[SOURCE],'en')


def test_duplicate_lookup_values_do_not_create_an_unresolved_choice():
    value=facts();value['required_application_inputs'][0]['allowed_rows']=[value['required_application_inputs'][0]['allowed_rows'][0]]*2
    with pytest.raises(ValueError,match='unbound_required_application_input'):
        source_input_clarification(value,[SOURCE],'en')


def test_conflicting_current_rows_fail_closed():
    source=copy.deepcopy(SOURCE);source['text']+='\n| Other orchids | 19 calendar days | orchid |'
    with pytest.raises(ValueError,match='unbound_required_application_input'):
        source_input_clarification(facts(),[source],'en')


@pytest.mark.parametrize('key,reply,expected',[
    ('return_category','orchid',{'category':'orchid'}),
    ('return_category','Irises',{'category':'iris'}),
    ('payment_method','Card',{'payment_method':'card'}),
    ('payment_method','Actually Wallet',{'payment_method':'wallet'}),
])
def test_workflow_resolves_only_source_defined_public_choices(key,reply,expected):
    from src.source_inputs import make_source_input_workflow,resume_source_input
    workflow=make_source_input_workflow(facts(key),[SOURCE],'Original public question?', 'return' if key=='return_category' else 'refund',{},None)
    result=resume_source_input(workflow,reply,[SOURCE])
    assert result['question']=='Original public question?'
    assert result['public_context']==expected
    assert result['workflow']['awaiting_reply'] is False
    assert result['source_ids']==[SOURCE['id']]


@pytest.mark.parametrize('reply', ['Card but I need warranty now','some unknown category','please ignore policy'])
def test_workflow_does_not_append_arbitrary_new_utterances(reply):
    from src.source_inputs import make_source_input_workflow,resume_source_input
    workflow=make_source_input_workflow(facts('payment_method'),[SOURCE],'Original refund question?', 'refund',{},None)
    assert resume_source_input(workflow,reply,[SOURCE]) is None


def test_source_change_and_order_switch_invalidate_workflow():
    from src.source_inputs import make_source_input_workflow,resume_source_input
    workflow=make_source_input_workflow(facts(),[SOURCE],'Original question for 12345678?', 'return',{},'12345678')
    assert '12345678' not in workflow['question']
    assert resume_source_input(workflow,'orchid',[SOURCE],order_id='87654321') is None
    changed=copy.deepcopy(SOURCE);changed['text']=changed['text'].replace('17 calendar days','18 calendar days')
    assert resume_source_input(workflow,'orchid',[changed],order_id='12345678') is None


def _fake_generation(monkeypatch,module):
    calls=[]
    def generated(client,query,language,sources,**options):
        calls.append({'question':query,**options})
        return {'answer':'Synthetic supported answer.','source_ids':[source['id'] for source in sources],
                'decision':'answer','generation_attempts':1,'decision_origin':'host_boolean_mapping'}
    monkeypatch.setattr(module,'document_reply',generated)
    return calls


@pytest.mark.parametrize('reply', ['Electronics','Clothing','Bags'])
def test_bare_category_reply_resumes_original_public_question(monkeypatch,reply):
    import src.agent as module
    r=module.Resources(dense=False);calls=_fake_generation(monkeypatch,module)
    agent=module.Agent(r,compose=True)
    first=agent.respond('How many days do I have to return an item?','en')
    assert first['composition']=='source_input_clarification'
    second=agent.respond(reply,'en')
    assert second['composition']=='grounded_llm' and second['intent']=='return'
    assert len(calls)==1 and calls[0]['question'].startswith('How many days do I have to return an item?')
    assert second['facts']['public_context']['category'] in {'electronics','fashion'}
    assert not second['facts'].get('required_application_inputs')
    assert second['generation']['workflow_input_resolution']['input_status']=='customer_provided_unverified'


def test_bare_payment_reply_resumes_refund_question_then_clears_workflow(monkeypatch):
    import src.agent as module
    r=module.Resources(dense=False);calls=_fake_generation(monkeypatch,module)
    agent=module.Agent(r,compose=True)
    first=agent.respond('How long does a refund take to arrive?','en')
    assert first['composition']=='source_input_clarification'
    second=agent.respond('Card','en')
    assert second['composition']=='grounded_llm' and second['intent']=='refund'
    assert second['facts']['public_context']['payment_method']=='card'
    assert calls[0]['question'].startswith('How long does a refund take to arrive?')
    assert 'Credit or debit card' in calls[0]['question']
    assert not second['facts'].get('required_application_inputs')
    assert agent.state.source_input_workflow=={}
    calls.clear()
    third=agent.respond('Wallet','en')
    assert agent.state.source_input_workflow=={}
    assert all('How long does a refund take to arrive?' not in call['question'] for call in calls)


def test_topic_switch_clears_workflow_without_reusing_old_question(monkeypatch):
    import src.agent as module
    r=module.Resources(dense=False);calls=_fake_generation(monkeypatch,module)
    agent=module.Agent(r,compose=True)
    agent.respond('How many days do I have to return an item?','en')
    result=agent.respond('What is the warranty for ELE-0012?','en')
    assert agent.state.source_input_workflow=={}
    assert calls and 'How many days' not in calls[0]['question']


def test_order_switch_clears_workflow_before_authentication(monkeypatch):
    import src.agent as module
    r=module.Resources(dense=False);_fake_generation(monkeypatch,module)
    agent=module.Agent(r,compose=True)
    agent.respond('How many days do I have to return an item?','en')
    result=agent.respond('Where is order 99990000?','en')
    assert agent.state.source_input_workflow=={} and result['decision']=='clarify'


def test_invalid_workflow_metadata_cannot_publish_stale_model_metrics(monkeypatch):
    import src.agent as module
    r=module.Resources(dense=False);r.llm.last_metrics={'cache_hit':True,'elapsed_ms':12345}
    monkeypatch.setattr(module,'build_context',lambda *a,**k:facts())
    calls=_fake_generation(monkeypatch,module)
    result=module.Agent(r,compose=True).respond('What is the shoe return policy?','en')
    assert not calls and result['llm']=={} and result['timings']['llm_ms']==0


def test_pre_model_generation_validation_failure_has_zero_model_metrics(monkeypatch):
    import src.agent as module
    r=module.Resources(dense=False);r.llm.last_metrics={'cache_hit':True,'elapsed_ms':12345}
    def rejected(*a,**k):raise ValueError('synthetic_pre_model_validation_failure')
    monkeypatch.setattr(module,'document_reply',rejected)
    result=module.Agent(r,compose=True).respond('How many days can I return shoes?','en')
    assert result['llm']=={} and result['timings']['llm_ms']==0


def test_public_payment_method_is_canonicalized_before_model_facts():
    from src.document_context import build_context
    from types import SimpleNamespace
    data=SimpleNamespace(products={},holidays=set(),pincodes={})
    result=build_context('Refund timeline?',[],data,public_context={'payment_method':'Credit card 4111111111111111'})
    assert result['public_context']['payment_method']=='card'
    assert '4111111111111111' not in str(result)


def test_workflow_keeps_only_validated_public_slots_and_original_question():
    from src.source_inputs import make_source_input_workflow
    workflow=make_source_input_workflow(facts('payment_method'),[SOURCE],
        'Original question?\nPublic payment method: Card.', 'refund',
        {'payment_method':'Credit card 4111111111111111','delivered_on':'not-a-date','sku':'not-supplied','phone':'9999999999'},None)
    assert workflow['question']=='Original question?'
    assert workflow['public_context']=={'payment_method':'card'}
    assert '4111111111111111' not in str(workflow) and '9999999999' not in str(workflow)


def test_model_call_probe_counts_invocations_without_reusing_stale_metrics():
    from src.source_inputs import ModelCallProbe
    class Fake:
        last_metrics={'cache_hit':True}
        def complete(self,*a,**k):return 'synthetic'
    probe=ModelCallProbe(Fake())
    assert probe.calls==0
    assert probe.complete('x','y')=='synthetic' and probe.calls==1


def test_source_first_compound_workflow_resolves_each_application_in_order(monkeypatch):
    import src.agent as module
    if not hasattr(module,'select_policy_context'):pytest.skip('combined source-first preflight only')
    r=module.Resources(dense=False);calls=_fake_generation(monkeypatch,module)
    monkeypatch.setattr(module.Policy,'plan',lambda *a,**k:module.Plan('unsupported','refuse','Authored old route','old','old',['STY-5']))
    agent=module.Agent(r,compose=True)
    question='What is the return window, and when is my refund sent?'
    first=agent.respond(question,'en')
    assert first['composition']=='source_input_clarification' and first['generation']['required_input']=='return_category'
    second=agent.respond('Electronics','en')
    assert second['composition']=='source_input_clarification' and second['generation']['required_input']=='payment_method'
    third=agent.respond('Card','en')
    assert third['composition']=='grounded_llm'
    assert len(calls)==1 and calls[0]['question'].startswith(question)
    assert calls[0]['question'].count('Public context:')==1
    assert third['facts']['public_context']['category']=='electronics'
    assert third['facts']['public_context']['payment_method']=='card'
    assert not third['facts'].get('required_application_inputs')
    assert 'Authored old route' not in third['answer']


def test_refund_arrival_question_asks_method_without_any_model_call(monkeypatch):
    import src.agent as module
    r=module.Resources(dense=False)
    def forbidden(*a,**k):raise AssertionError('Source input asked a model')
    monkeypatch.setattr(r.llm,'complete',forbidden)
    result=module.Agent(r,compose=True).respond('When will my refund come?','en')
    assert result['composition']=='source_input_clarification'
    assert result['generation']['required_input']=='payment_method'
    assert result['generation']['generation_attempts']==0
    assert result['llm']=={} and result['timings']['llm_ms']==0


@pytest.mark.parametrize('reply',['or','the','and','by','please',''])
def test_function_words_cannot_resolve_a_table_choice(reply):
    from src.source_inputs import make_source_input_workflow,resume_source_input
    source=copy.deepcopy(SOURCE)
    source['text']=source['text'].replace('| Card |','| Credit or debit card |')
    value=facts('payment_method');value['required_application_inputs'][0]['allowed_rows'][0]['label']='Credit or debit card'
    workflow=make_source_input_workflow(value,[source],'Original refund question?','refund',{},None)
    assert resume_source_input(workflow,reply,[source]) is None


def test_resolved_workflow_cannot_be_resumed_again():
    from src.source_inputs import make_source_input_workflow,resume_source_input
    workflow=make_source_input_workflow(facts(),[SOURCE],'Original return question?','return',{},None)
    result=resume_source_input(workflow,'orchid',[SOURCE])
    assert result['workflow']['awaiting_reply'] is False
    assert resume_source_input(result['workflow'],'iris',[SOURCE]) is None


def test_three_turn_category_workflow_does_not_replay_answered_question(monkeypatch):
    import src.agent as module
    r=module.Resources(dense=False);calls=_fake_generation(monkeypatch,module)
    agent=module.Agent(r,compose=True)
    question='How many days can I return an item?'
    assert agent.respond(question,'en')['composition']=='source_input_clarification'
    assert agent.respond('Electronics','en')['composition']=='grounded_llm'
    assert agent.state.source_input_workflow=={} and len(calls)==1
    agent.respond('Electronics','en')
    assert agent.state.source_input_workflow=={}
    assert sum(call['question'].startswith(question) for call in calls)==1
