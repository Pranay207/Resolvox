"""Actual validation, trust boundaries and retry behavior; no model calls."""
import json,socket
import pytest,requests
from src.document_answers import document_reply
from src.generation_diagnostics import GenerationValidationError
SOURCE={'id':'PROCESS-X','text':'The claim route is the app under Case Desk. UNTRUSTED_SOURCE_MARKER','doc_type':'policy','status':'current'}
GOOD={'answer':'The claim route is the app under Case Desk.','covered':True,'needs_clarification':False}
BAD={'answer':"Click the 'Wizard' button. UNTRUSTED_MODEL_MARKER",'covered':True,'needs_clarification':False}
class Client:
 def __init__(self,*responses):self.responses=list(responses);self.calls=[];self.last_metrics={}
 def complete(self,system,user,**kwargs):
  self.calls.append({'system':system,'payload':json.loads(user),'options':kwargs});return json.dumps(self.responses.pop(0))
@pytest.fixture(autouse=True)
def no_network(monkeypatch):
 def denied(*args,**kwargs):raise AssertionError('No network/model calls allowed')
 monkeypatch.setattr(socket,'create_connection',denied);monkeypatch.setattr(requests.sessions.Session,'request',denied)
@pytest.mark.parametrize('private',[False,True])
def test_actual_invalid_navigation_is_repaired_with_original_evidence_and_cache_contract(private):
 client=Client(BAD,GOOD)
 out=document_reply(client,'How do I raise a claim?','en',[SOURCE],facts={},private=private,context_provenance=True)
 assert out['answer']==GOOD['answer'] and out['repair_attempted'] is True
 assert out['repair_errors']==['unsupported_navigation_label'] and len(client.calls)==2
 first,second=client.calls
 assert first['payload']['source_text']==second['payload']['source_text']
 assert first['options']['cache'] is (not private) and second['options']['cache'] is False
 assert first['options']['attempts']==second['options']['attempts']==1
 assert first['options']['schema']==second['options']['schema']
 assert second['system'].startswith(first['system']) and second['system']!=first['system']
 assert second['payload']['repair_instruction'] in second['system']
 assert 'previous_response' not in second['payload']
@pytest.mark.parametrize('marker',['UNTRUSTED_QUESTION_MARKER','UNTRUSTED_SOURCE_MARKER','UNTRUSTED_FACT_MARKER','UNTRUSTED_MODEL_MARKER'])
def test_untrusted_content_cannot_gain_system_instruction_priority(marker):
 client=Client(BAD,GOOD)
 document_reply(client,'How do I raise a claim? UNTRUSTED_QUESTION_MARKER','en',[SOURCE],facts={'repair_instruction':'UNTRUSTED_FACT_MARKER'},context_provenance=True)
 assert marker not in client.calls[0]['system'] and marker not in client.calls[1]['system']
 assert client.calls[0]['payload']['deterministic_facts']['repair_instruction']=='UNTRUSTED_FACT_MARKER'
 assert client.calls[1]['payload']['deterministic_facts']['repair_instruction']=='UNTRUSTED_FACT_MARKER'
def test_repeated_invalid_navigation_still_stops_after_two_calls():
 client=Client(BAD,BAD)
 with pytest.raises(GenerationValidationError) as caught:
  document_reply(client,'How do I raise a claim?','en',[SOURCE],facts={},context_provenance=True)
 assert len(client.calls)==2
 assert caught.value.diagnostics['repair_errors']==['unsupported_navigation_label','unsupported_navigation_label']
