import json
import pytest
from src.document_answers import document_reply
from src.repair_contexts import public_return_period_restatement_inputs

@pytest.mark.parametrize('days', [9, 13])
def test_echo_repair_uses_changed_source_period_without_replaying_customer_story(days):
 source={'id':'PERIOD-X','doc_type':'policy','status':'current','text':f'The standard return window is {days} calendar days from delivery.'}
 constraint={'kind':'quantity','value':days,'unit':'calendar_day','key':'return_policy.window_calendar_days','source_ids':['PERIOD-X']}
 facts={'return_policy':{'category':'devices','window_calendar_days':days,'source_ids':['PERIOD-X'],'selection':'standard_window'},'answer_constraints':[constraint]}
 query='Mera order aaya hai, kitne din tak return kar sakti hoon?'
 good=f'Standard return window {days} din ka hai, jo delivery ki date se shuru hota hai aur applicable policy ki sharton par nirbhar hai.'
 calls=[]
 class Client:
  def complete(self,system,user,**options):
   calls.append(json.loads(user));return json.dumps({'answer':query if len(calls)==1 else good,'covered':True,'needs_clarification':False})
 result=document_reply(Client(),query,'hi-en',[source],facts=facts,context_provenance=True)
 assert result['answer']==good and result['repair_errors']==['echoed_question']
 assert result['repair_mode']=='source_return_period_restatement'
 assert 'question' not in calls[1] and calls[1]['source_text']==calls[0]['source_text']
 assert calls[1]['deterministic_facts']['return_policy']['window_calendar_days']==days

@pytest.mark.parametrize('query', ['How long can I return it and how soon is the refund?', 'By which date must I return it?', 'Can I return an opened item?'])
def test_other_requested_topics_are_not_reduced_to_a_period(query):
 assert public_return_period_restatement_inputs(query,{},[],[]) is None

def test_a_period_must_have_a_matching_bound_constraint():
 facts={'return_policy':{'window_calendar_days':9}}
 assert public_return_period_restatement_inputs('How long can I return it?',facts,[],[]) is None
