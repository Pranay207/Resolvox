import json,pytest
from test_customer_condition_premises import Client,SOURCES,QUERY,facts
from src.document_answers import document_reply
from src.generation_diagnostics import GenerationValidationError

def test_source_bound_mismatch_names_support_flag_without_changing_policy_text():
 client=Client('Your product is unopened.','You reported opening it; this does not meet the ordinary condition requiring unopened products.')
 result=document_reply(client,QUERY,'en',SOURCES,facts=facts(),context_provenance=True)
 schema=client.calls[1][2]['schema']
 assert 'covered' not in schema['properties']
 assert schema['properties']['has_document_support']=={'type':'boolean'}
 assert schema['properties']['needs_clarification']=={'type':'boolean'}
 assert result['coverage_contract']['customer_report_status']=='unverified'
 assert result['coverage_contract']['scope']=='ordinary necessary-condition explanation only'
 assert result['answer']=='You reported opening it; this does not meet the ordinary condition requiring unopened products.'

def test_constrained_flag_cannot_launder_a_reversed_rule():
 client=Client('Your product is unopened.','The policy requires the product to be opened.')
 with pytest.raises(GenerationValidationError):document_reply(client,QUERY,'en',SOURCES,facts=facts(),context_provenance=True)

def test_constrained_flag_cannot_launder_an_uncertainty_answer():
 client=Client('Your product is unopened.','I cannot confirm what the return policy requires.')
 with pytest.raises(GenerationValidationError):document_reply(client,QUERY,'en',SOURCES,facts=facts(),context_provenance=True)

def test_unresolved_state_keeps_the_normal_unconstrained_flag_contract():
 class Scripted:
  def __init__(self):self.calls=[]
  def complete(self,system,user,**options):
   self.calls.append(options)
   return json.dumps({'answer':'The policy requires products to be opened.','covered':True,'needs_clarification':False}) if len(self.calls)==1 else json.dumps({'answer':'Could you confirm whether the item is unopened?','covered':False,'needs_clarification':True})
 client=Scripted();question='Can I return Aster Tint?'
 result=document_reply(client,question,'en',SOURCES,facts=facts(question),context_provenance=True)
 assert 'coverage_contract' not in result and 'enum' not in client.calls[1]['schema']['properties']['covered']
 assert result['decision']=='clarify'

def test_explicit_support_flag_is_preserved_and_not_forced_true():
 class Scripted:
  def __init__(self,support):self.calls=0;self.support=support
  def complete(self,*args,**options):
   self.calls+=1
   if self.calls==1:return json.dumps({'answer':'Your product is unopened.','covered':True,'needs_clarification':False})
   return json.dumps({'answer':'You reported opening the product; this does not meet the policy condition requiring it to be unopened.','has_document_support':self.support,'needs_clarification':False})
 good=Scripted(True);result=document_reply(good,QUERY,'en',SOURCES,facts=facts(),context_provenance=True)
 assert result['coverage_contract']['original_model_flags']['has_document_support'] is True
 bad=Scripted(False)
 with pytest.raises(GenerationValidationError):document_reply(bad,QUERY,'en',SOURCES,facts=facts(),context_provenance=True)

def test_an_ambiguous_resolved_condition_is_not_accepted_as_a_negative_answer():
 client=Client('Your product is unopened.','इसलिए आम वापसी की शर्त निपटाई गई है।')
 with pytest.raises(GenerationValidationError):document_reply(client,QUERY,'hi',SOURCES,facts=facts(),context_provenance=True)
