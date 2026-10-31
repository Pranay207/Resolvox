"""A known method must retain its actual source row, clock and units."""
import copy
import json
from types import SimpleNamespace
import pytest
from src.document_context import build_context
from src.refund_timeline import refund_timeline_binding, check_refund_timeline_answer, refund_timeline_inputs
from src.document_answers import document_reply


def context(method='upi',low=23,high=37,query='When will my refund arrive?',**changes):
 source={'id':'new-refund-table','doc_type':'policy','status':'current','effective_from':'2020-01-01',
 'text':f'Refund timelines after initiation. Refunds return to the original payment method.\n| Payment method | Time |\n| --- | --- |\n| UPI | {low} to {high} business days |\n| Credit or debit card | 41 to 53 business days |\n| Net banking | 7 to 11 business days |'}
 order={'payment_method':method,'is_plus':False,'status':'delivered'};order.update(changes)
 sources=[source,{'id':'initiation-rule','doc_type':'policy','status':'current','effective_from':'2020-01-01',
                  'text':'A return refund is initiated after the item passes quality check.'}]
 return build_context(query,sources,SimpleNamespace(products={},holidays=set()),verified_order=order),sources


@pytest.mark.parametrize('method,expected',[('upi',(23,37)),('credit_card',(41,53)),('netbanking',(7,11))])
def test_method_selects_current_table_values_without_fixed_policy_numbers(method,expected):
 facts,sources=context(method)
 binding=facts['refund_arrival_policy']
 assert (binding['minimum_business_days'],binding['maximum_business_days'])==expected
 assert binding['source_ids']==['new-refund-table']
 assert binding['timing_anchor']=='after_refund_initiation'


@pytest.mark.parametrize('query',['When will my refund arrive?','Mera refund kitne din mein aayega?','और रिफ़ंड कितने दिन में आएगा?'])
def test_followup_uses_verified_method_even_without_an_initiation_date(query):
 facts,sources=context(query=query)
 assert facts['refund_arrival_policy']['payment_method']=='upi'
 assert facts['calculations']==[]


def test_source_changes_rebind_range_and_reject_stale_fact():
 facts,sources=context(); changed=copy.deepcopy(sources)
 changed[0]['text']=changed[0]['text'].replace('23 to 37','29 to 43')
 assert refund_timeline_binding('When will my refund arrive?',facts,changed,'2026-10-20')['minimum_business_days']==29
 with pytest.raises(ValueError,match='unbound_refund_arrival_policy'):
  check_refund_timeline_answer('UPI refunds take 23 to 37 business days after initiation.','When will my refund arrive?',facts,changed,'2026-10-20')


@pytest.mark.parametrize('answer',[
 'Card refunds take 41 to 53 business days after initiation.',
 'UPI refunds take 23 to 37 calendar days after initiation.',
 'UPI refunds take 37 to 23 business days after initiation.',
 'UPI refunds take 23 to 37 विज्ञान दिनों after initiation.',
 'There are 23 items and 37 days.',
])
def test_wrong_method_range_order_and_mistranslated_unit_are_rejected(answer):
 facts,sources=context()
 with pytest.raises(ValueError,match='missing_refund_arrival_range'):
  check_refund_timeline_answer(answer,'When will my refund arrive?',facts,sources,'2026-10-20')


@pytest.mark.parametrize('answer',[
 'UPI refunds take 23 to 37 business days after initiation.',
 'रिफ़ंड शुरू होने के बाद UPI के लिए 23 से 37 कार्यदिवस लगते हैं।',
 'Refund shuru hone ke baad UPI se 23 se 37 business din lagte hain.',
])
def test_supported_range_and_unit_in_each_scoped_language(answer):
 facts,sources=context()
 assert check_refund_timeline_answer(answer,'When will my refund arrive?',facts,sources,'2026-10-20')


@pytest.mark.parametrize('query',['Compare all refund payment methods.','When is my refund initiated?','When will my card refund arrive?','When will my refund arrive and what is the warranty?'])
def test_compound_initiation_only_or_conflicting_method_keeps_full_evidence(query):
 facts,sources=context(query=query)
 assert 'refund_arrival_policy' not in facts
 assert refund_timeline_inputs(query,facts,sources,'2026-10-20') is None


def test_ambiguous_current_tables_do_not_choose_a_range():
 facts,sources=context();other=copy.deepcopy(sources[0]);other['id']='conflicting-policy'
 other['text']=other['text'].replace('23 to 37','29 to 43')
 assert refund_timeline_binding('When will my refund arrive?',facts,sources+[other],'2026-10-20') is None


class Client:
 def __init__(self,*answers):self.answers=list(answers);self.calls=[]
 def complete(self,system,user,**options):
  self.calls.append((system,json.loads(user),options))
  return json.dumps(dict(answer=self.answers.pop(0),covered=True,needs_clarification=False))


def test_actual_validation_owns_one_retry_and_both_calls_keep_bound_source_row():
 facts,sources=context();good='UPI refunds take 23 to 37 business days after initiation.'
 client=Client('Card refunds take 41 to 53 business days after initiation.',good)
 result=document_reply(client,'When will my refund arrive?','en',sources,facts=facts,private=True,context_provenance=True)
 assert result['answer']==good and result['repair_mode']=='source_payment_refund_timeline'
 assert len(client.calls)==2
 for system,payload,options in client.calls:
  assert payload['deterministic_facts']['refund_arrival_policy']['minimum_business_days']==23
  assert 'source_sha256' not in payload['deterministic_facts']['refund_arrival_policy']
  assert all(row in sources for row in payload['source_text'])
 assert client.calls[-1][2]['cache'] is False


def test_input_context_trace_excludes_unseen_chunks_but_full_validation_is_preserved():
 facts,sources=context();extra={'id':'unrelated-help','doc_type':'help','status':'current','text':'Contact support for product questions.'}
 sources=sources+[extra]
 client=Client('UPI refunds take 23 to 37 business days after initiation.')
 result=document_reply(client,'When will my refund arrive?','en',sources,facts=facts,private=True,context_provenance=True)
 actual_ids=[row['id'] for row in client.calls[0][1]['source_text']]
 assert result['context_source_ids']==actual_ids
 assert result['generation_input_contexts']==[{'attempt':1,'source_ids':actual_ids}]
 assert 'unrelated-help' not in result['source_ids']
 assert 'unrelated-help' in result['validation_source_ids']
