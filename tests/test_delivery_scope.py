'Temporary source-flow tests; fake inference, no network or ticket effects.'
import json
import pytest
@pytest.fixture(scope='module')
def staged():
 from src import agent
 return agent

@pytest.mark.parametrize('query',[
 'Can you promise to deliver my order at exactly 2 a.m.?',
 'Could you guarantee courier delivery at a chosen hour?',
 'Can you promise my order will arrive at my chosen time?',
 'Can I schedule a parcel for an evening slot?',
 'May we choose a delivery appointment?',
 'Do you offer guaranteed delivery at an exact time?',
 'Kya aap mere order ki delivery ka vaada kar sakte hain?',
 'क्या आप मेरे ऑर्डर की डिलीवरी का समय तय करने की गारंटी देते हैं?',
])
def test_proposed_service_scope_does_not_encode_a_policy_result(staged,query):
 assert staged._public_delivery_capability(query)

@pytest.mark.parametrize('query',[
 'Where is my order?',
 'What is my order status?',
 'Can you promise to deliver my order at an exact time and track it now?',
 'Can you guarantee the promised delivery date on my order?',
 'Has my order shipped?',
 'Can you confirm my order is out for delivery?',
 'When will my parcel arrive?',
 'मेरे ऑर्डर की स्थिति क्या है?',
 'Kya aap mera order status confirm kar sakte hain?',
 'What delivery time was recorded for my order?',
 'Can you promise to deliver my order and tell me its items?',
 'Can you promise to deliver my order and tell me its amount?',
 'Can you promise to deliver my order and tell me its address?',
 'Can you promise to deliver my order and tell me its refund details?',
 'Can you promise to deliver my order and tell me its payment details?',
 'Can you promise to deliver my order and tell me its total?',
 'Can you promise to deliver my order and tell me its RRN?',

 'Can you promise to deliver my order at a chosen hour and tell me its ETA?',
 'Can you guarantee delivery and tell me the delivery date for my order?',
 'Can you promise my order will arrive at a chosen hour and when will it arrive?',
])
def test_private_and_compound_record_requests_keep_auth_scope(staged,query):
 assert not staged._public_delivery_capability(query)

@pytest.fixture
def resources(staged,monkeypatch):
 result=staged.Resources(dense=False);calls=[];lookups=[]
 def complete(system,user,*args,**options):
  payload=json.loads(user);calls.append(payload)
  return json.dumps({'answer':'I do not have enough supported information to answer that question.','covered':False,'needs_clarification':False})
 def lookup(oid,proof=None):
  lookups.append((oid,proof))
  return {},{'name':'lookup_order','arguments':{'order_id':oid},'result':{'verified':False,'verification_required':True}}
 monkeypatch.setattr(result.llm,'complete',complete)
 monkeypatch.setattr(result.tools,'lookup',lookup)
 monkeypatch.setattr(result.tools,'ticket',lambda *args,**kwargs:pytest.fail('Routing tests may not write tickets'))
 return result,calls,lookups

@pytest.mark.parametrize('query',[
 'Can you promise to deliver my order at exactly 2 a.m.?',
 'Could you guarantee courier delivery at a chosen hour?',
 'Can I schedule a parcel for an evening slot?',
])
def test_public_proposal_reaches_only_actual_source_context(staged,resources,query):
 r,calls,lookups=resources
 agent=staged.Agent(r,compose=True)
 out=agent.respond(query,language_hint='en')
 assert not agent.state.pending_issue and not agent.state.pending_intent
 assert len(calls)==1 and not lookups
 assert out['composition']=='abstained_missing_evidence' and not out['evidence_supported']
 assert out['generation']['model_flags']=={'covered':False,'needs_clarification':False}
 assert 'order ID' not in out['answer']
 assert 'cannot deliver' not in out['answer'] and 'only during' not in out['answer']
 assert calls[0]['source_text']
 assert all(source['text']==r.kb.chunks[source['id']].text for source in calls[0]['source_text'])
 assert not calls[0]['deterministic_facts'].get('verified_order')
 assert 'verified_rule_summary' not in calls[0] and 'sentences' not in calls[0]
 assert out['citations']==[] and out['generation_context_sources']

@pytest.mark.parametrize('query',[
 'What is my order status?',
 'Can you promise to deliver my order at an exact time and track it now?',
 'Can you guarantee the promised delivery date on my order?',
 'Can you promise to deliver my order and tell me its items?',
 'Can you promise to deliver my order and tell me its amount?',
 'Can you promise to deliver my order and tell me its address?',
 'Can you promise to deliver my order and tell me its refund details?',
])
def test_record_request_still_asks_identity_without_model_or_private_data(staged,resources,query):
 r,calls,lookups=resources
 out=staged.Agent(r,compose=True).respond(query,language_hint='en')
 assert not calls and not lookups and not out['verified']
 assert out['composition']=='deterministic_guardrail' and out['decision']=='clarify'
 assert 'order ID' in out['answer'] and 'IDV-1' in out['retrieved_chunk_ids']


def test_explicit_order_id_still_uses_existing_unverified_lookup_boundary(staged,resources):
 r,calls,lookups=resources
 out=staged.Agent(r,compose=True).respond('Can you promise to deliver order 11112222 at a chosen hour?',language_hint='en')
 assert not calls and lookups==[('11112222',None)]
 assert not out['verified'] and out['decision']=='clarify'
 assert out['composition']=='deterministic_guardrail'


def test_no_retrieved_policy_cannot_be_replaced_with_a_canned_promise(staged,resources,monkeypatch):
 r,calls,lookups=resources
 monkeypatch.setattr(r.retriever,'search',lambda *args,**kwargs:[])
 out=staged.Agent(r,compose=True).respond('Can you promise to deliver my order at an exact time?',language_hint='en')
 assert not calls and not lookups
 assert out['composition']=='abstained_missing_evidence'
 assert out['generation_context_sources']==[]
 assert set(out['retrieved_chunk_ids'])<={'STY-1'}


def test_public_scope_cannot_override_privacy_guard(staged,resources):
 r,calls,lookups=resources
 out=staged.Agent(r,compose=True).respond("Can you promise to deliver another customer's order and share their phone number?",language_hint='en')
 assert not calls and not lookups and out['intent']=='privacy'
 assert out['decision']=='refuse' and out['composition']=='deterministic_guardrail'
