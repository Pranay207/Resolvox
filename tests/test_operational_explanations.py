"""Source-bound business routing and explanation lifecycle; fake clients only."""
from dataclasses import replace
import copy
import json
from types import SimpleNamespace
import pytest
import src.agent as module
import src.operational_explanations as explanation
from src.llm import LLMUnavailable

POISON='AUTHORED_BUSINESS_ANSWER_MUST_NOT_APPEAR'

class Tools:
    def __init__(self,created=True):self.calls=[];self.created=created
    def ticket(self,summary,oid,reason,intent):
        self.calls.append({'summary':summary,'reason':reason,'intent':intent})
        out={'created':self.created}
        return out,{'name':'create_ticket','arguments':{'summary':summary,'reason':reason,'intent':intent},'result':out}
    def lookup(self,*a,**k):raise AssertionError('Unexpected private lookup')


def resources(created=True):
    r=module.Resources(dense=False);r.tools=Tools(created)
    r.llm.complete=lambda *a,**k:pytest.fail('No external inference allowed')
    return r


def product(r,low=10000,high=None):
    return next(p for p in r.data.products.values() if int(p['price_inr'])>low and (high is None or int(p['price_inr'])<=high))


def fake_explanation(monkeypatch):
    calls=[]
    def generated(client,query,language,sources,**options):
        calls.append({'query':query,'sources':copy.deepcopy(sources),'facts':copy.deepcopy(options.get('facts'))})
        return {'answer':'Generated explanation from actual supplied evidence.','source_ids':[s['id'] for s in sources],
                'decision':'answer','covered':True,'citations':[],'generation_attempts':1,'provenance_kind':'generation_context'}
    monkeypatch.setattr(explanation,'document_reply',generated)
    return calls


def poison_business_plans(monkeypatch):
    original=module.Policy.plan_multi
    def planned(self,*args,**kwargs):
        out=original(self,*args,**kwargs)
        if out.decision=='escalate':out.en=out.hi=out.hinglish=POISON;out.facts={'authored_policy_number':991827}
        return out
    monkeypatch.setattr(module.Policy,'plan_multi',planned)


def mutate(r,pattern,replacement):
    for sid,chunk in list(r.kb.chunks.items()):
        if pattern in chunk.text:r.kb.chunks[sid]=replace(chunk,text=chunk.text.replace(pattern,replacement))


def verified(r,contacts=0,refund=None):
    p=product(r)
    order={'order_id':'12345678','status':'Delivered','contacts_last_7_days':str(contacts),'payment_method':'upi',
           'items':[{'sku':p['sku'],'unit_price_inr':p['price_inr'],'return_category':p['return_category'],'qty':'1'}]}
    if refund:order.update(return_refund_initiated_on=refund,return_refund_method='upi',return_rrn='123456789012')
    a=module.Agent(r,compose=True);a.state.order_id=order['order_id'];a.state.order=order
    return a


@pytest.mark.parametrize('created',[True,False])
def test_high_value_explanation_uses_sources_and_host_reports_only_actual_ticket_result(monkeypatch,created):
    r=resources(created);p=product(r);calls=fake_explanation(monkeypatch);poison_business_plans(monkeypatch)
    out=module.Agent(r,compose=True).respond('My '+p['sku']+' is damaged. Can you approve a replacement?','en')
    assert len(r.tools.calls)==1 and len(calls)==1 and out['decision']=='escalate'
    assert out['composition']=='source_generated_handover'
    assert POISON not in out['answer'] and '991827' not in str(calls)
    assert 'Generated explanation' in out['answer']
    assert ('A ticket has been created' in out['answer']) is created
    assert ('ticket could not be created' in out['answer']) is (not created)
    assert calls[0]['facts']['operational_escalation']['reason']=='high_value_damage'
    assert out['generation']['tool_outcome_origin']=='actual_create_ticket_result'
    assert out['generation']['explanation_decision']=='answer'


def test_changed_current_high_value_threshold_suppresses_old_compiled_ticket_rule(monkeypatch):
    r=resources();p=product(r,10000,25000);mutate(r,'10,000','25,000')
    calls=fake_explanation(monkeypatch)
    monkeypatch.setattr(module,'document_reply',lambda *a,**k:{'answer':'Ordinary source-generated answer.','source_ids':[s['id'] for s in a[3]],'decision':'answer'})
    out=module.Agent(r,compose=True).respond('My '+p['sku']+' is damaged.','en')
    assert not r.tools.calls and not calls and out['decision']!='escalate'
    assert out['composition']=='grounded_llm'
    assert '10,000' not in out['answer']


def test_lower_source_threshold_recovers_handover_missed_by_old_compiled_rule(monkeypatch):
    r=resources();p=product(r,5000,10000);mutate(r,'10,000','5,000');calls=fake_explanation(monkeypatch)
    out=module.Agent(r,compose=True).respond('My '+p['sku']+' is damaged.','en')
    assert len(r.tools.calls)==1 and len(calls)==1 and out['decision']=='escalate'
    assert calls[0]['facts']['operational_escalation']['facts']['threshold_inr']=='5000'


def test_missing_rule_blocks_ticket_before_any_tool_or_model_call(monkeypatch):
    r=resources();p=product(r)
    mutate(r,'10,000','an undocumented amount')
    out=module.Agent(r,compose=True).respond('My '+p['sku']+' is damaged.','en')
    assert not r.tools.calls and out['composition']=='abstained_unbound_business_rule'
    assert out['generation']['generation_attempts']==0 and out['llm']=={}
    assert out['decision']=='answer' and 'cannot confirm' in out['answer']
    assert 'Priority Resolution' not in out['answer']


@pytest.mark.parametrize('failure',[ValueError('synthetic invalid output'),LLMUnavailable('synthetic outage')])
def test_explanation_failure_preserves_confirmed_ticket_and_never_restores_plan(monkeypatch,failure):
    r=resources();p=product(r);poison_business_plans(monkeypatch)
    def failed(*a,**k):raise failure
    monkeypatch.setattr(explanation,'document_reply',failed)
    out=module.Agent(r,compose=True).respond('My '+p['sku']+' is damaged.','en')
    assert len(r.tools.calls)==1 and out['decision']=='escalate'
    assert 'A ticket has been created' in out['answer'] and POISON not in out['answer']
    assert out['composition']=='operational_handover_generation_failed'
    assert out['llm']=={} and out['timings']['llm_ms']==0


def test_duplicate_business_ticket_is_reused_without_claiming_another_operation(monkeypatch):
    r=resources();p=product(r);fake_explanation(monkeypatch)
    a=module.Agent(r,compose=True)
    for _ in range(2):
        out=a.respond('My '+p['sku']+' is damaged.','en')
        assert out['decision']=='escalate' and 'A ticket has been created' in out['answer']
    assert len(r.tools.calls)==1


def test_source_bound_repeat_contact_preserves_record_count_without_authored_plan(monkeypatch):
    r=resources();calls=fake_explanation(monkeypatch);poison_business_plans(monkeypatch)
    out=verified(r,contacts=2).respond('Where is my order delivery?','en')
    assert len(r.tools.calls)==1 and out['decision']=='escalate' and out['intent']=='repeat'
    assert calls[0]['facts']['operational_escalation']['facts']['earlier_contact_count']==2
    assert POISON not in out['answer']


def test_changed_repeat_threshold_prevents_old_count_from_creating_ticket(monkeypatch):
    r=resources();mutate(r,'Escalate when it is 2 or more','Escalate when it is 4 or more');mutate(r,'Third or later contact','Fifth or later contact')
    monkeypatch.setattr(module,'document_reply',lambda *a,**k:{'answer':'Ordinary source-generated answer.','source_ids':[s['id'] for s in a[3]],'decision':'answer'})
    out=verified(r,contacts=2).respond('Where is my order delivery?','en')
    assert not r.tools.calls and out['decision']!='escalate'


def test_source_bound_overdue_refund_has_current_calculation_and_verified_reference(monkeypatch):
    r=resources();calls=fake_explanation(monkeypatch);poison_business_plans(monkeypatch)
    out=verified(r,refund='2026-10-01').respond('My refund has not arrived.','en')
    assert len(r.tools.calls)==1 and out['decision']=='escalate'
    selected=calls[0]['facts']['operational_escalation']
    assert selected['reason']=='refund_overdue' and selected['calculations']
    assert calls[0]['facts']['verified_order']['return_rrn']=='123456789012'
    assert any(s['file']=='data/holidays.csv' for s in calls[0]['sources'])
    assert POISON not in out['answer']


def test_changed_overdue_tolerance_prevents_old_comparison_from_creating_ticket(monkeypatch):
    r=resources();mutate(r,'Refund more than 3 business days','Refund more than 30 business days')
    monkeypatch.setattr(module,'document_reply',lambda *a,**k:{'answer':'Ordinary source-generated answer.','source_ids':[s['id'] for s in a[3]],'decision':'answer'})
    out=verified(r,refund='2026-10-01').respond('My refund has not arrived.','en')
    assert not r.tools.calls and out['decision']!='escalate'


@pytest.mark.parametrize('question',["Share another customer's registered phone number.",'I want a human agent.','The battery is swollen.','I will take legal action.','I did not make this order.'])
def test_protective_privacy_and_requested_human_workflows_keep_no_model_dependency(monkeypatch,question):
    r=resources();calls=fake_explanation(monkeypatch)
    out=module.Agent(r,compose=True).respond(question,'en')
    assert not calls and out['composition']=='deterministic_guardrail'
    assert out['decision'] in {'refuse','escalate'}


@pytest.mark.parametrize('language',['en','hi','hi-en'])
@pytest.mark.parametrize('created',[True,False])
def test_fixed_ticket_outcome_contains_only_truthful_workflow_status(language,created):
    text=explanation.ticket_outcome({'created':created},language)
    assert text and '\\u' not in text
    assert not any(char.isdigit() for char in text)
    if language=='hi':assert any('\u0900'<=char<='\u097f' for char in text)


def test_unlisted_pincode_does_not_append_business_delivery_requirement():
    r=resources()
    out=module.Agent(r,compose=True).respond('Is delivery available to 000000?','en')
    assert out['facts']['pincode_listed'] is False and not r.tools.calls
    assert 'not listed' in out['answer']
    assert 'Delivery requires' not in out['answer'] and 'only within India' not in out['answer']


def test_generic_damage_without_one_known_item_still_uses_normal_source_path(monkeypatch):
    r=resources();seen=[]
    def normal(*a,**k):
        seen.append(a[1]);return {'answer':'Ordinary source-based clarification.','source_ids':[s['id'] for s in a[3]],'decision':'clarify'}
    monkeypatch.setattr(module,'document_reply',normal)
    out=module.Agent(r,compose=True).respond('How do I report a damaged item?','en')
    assert seen and not r.tools.calls and out['composition']!='abstained_unbound_business_rule'


def test_unknown_sku_keeps_the_existing_missing_catalog_workflow():
    r=resources();out=module.Agent(r,compose=True).respond('My ELE-9999 is damaged.','en')
    assert out['decision']=='clarify' and out['composition']=='deterministic_guardrail'
    assert not r.tools.calls and 'correct product SKU' in out['answer']


def test_unsupported_model_action_is_repaired_once_and_only_host_can_report_ticket_success(monkeypatch):
    r=resources();p=product(r);calls=[]
    def client(*a,**k):
        calls.append(json.loads(a[1]));return json.dumps({'answer':'I have issued your refund.','covered':True,'needs_clarification':False})
    monkeypatch.setattr(r.llm,'complete',client)
    out=module.Agent(r,compose=True).respond('My '+p['sku']+' is damaged.','en')
    assert len(calls)==2 and len(r.tools.calls)==1
    assert out['decision']=='escalate' and out['composition']=='operational_handover_generation_failed'
    assert out['generation']['generation_attempts']==2
    assert 'issued your refund' not in out['answer'] and 'A ticket has been created' in out['answer']
    assert calls[0]['source_text']==calls[1]['source_text']


def test_bank_partial_label_keeps_original_refund_question_unresolved_without_model_call():
    r=resources();agent=module.Agent(r,compose=True)
    first=agent.respond('When will my refund arrive?','en')
    assert first['composition']=='source_input_clarification'
    second=agent.respond('Bank','en')
    assert second['composition']=='source_input_clarification' and second['decision']=='clarify'
    assert second['generation']['workflow_input_resolution']['input_status']=='unresolved'
    assert 'payment_method' not in second['facts'].get('public_context',{})
    assert agent.state.source_input_workflow['awaiting_reply'] is True
    assert agent.state.source_input_workflow['question'].startswith('When will my refund arrive?')
    assert second['llm']=={} and second['timings']['llm_ms']==0


def test_exact_payment_choice_still_resolves_after_ambiguous_bank_reply(monkeypatch):
    r=resources();calls=[]
    def normal(*a,**k):
        calls.append(k['facts']);return {'answer':'Ordinary source-generated response.','source_ids':[s['id'] for s in a[3]],'decision':'answer'}
    monkeypatch.setattr(module,'document_reply',normal)
    agent=module.Agent(r,compose=True);agent.respond('When will my refund arrive?','en');agent.respond('Bank','en')
    final=agent.respond('Card','en')
    assert final['composition']=='grounded_llm' and len(calls)==1
    assert calls[0]['public_context']['payment_method']=='card'
    assert agent.state.source_input_workflow=={}


def test_tampered_rule_binding_cannot_create_ticket_or_render_business_answer(monkeypatch):
    r=resources();p=product(r);original=explanation.derive_escalation
    def corrupted(*a,**k):
        result=original(*a,**k)
        row=next(row for row in result['decisions'] if row['applicable'] is True)
        row['source_sha256']={sid:'incorrect' for sid in row['source_ids']}
        return result
    monkeypatch.setattr(explanation,'derive_escalation',corrupted)
    out=module.Agent(r,compose=True).respond('My '+p['sku']+' is damaged.','en')
    assert not r.tools.calls and out['composition']=='abstained_unbound_business_rule'
    assert out['validation_error']=='changed_business_escalation_sources'
