import json
import pytest
from src.catalog_events import check_catalog_fulfillment_claim
from src.document_answers import document_reply
FACTS = {'catalog': [{'sku': 'SYN-X', 'fulfilled_by': 'Example Seller'}], 'public_context': {'sku': 'SYN-X'}}

@pytest.mark.parametrize('answer', [
 'The product SYN-X was shipped from a marketplace seller and delivered after the change date.',
 'Your item has been delivered.', 'The parcel was not delivered.', 'It was shipped yesterday.',
 'The product is already delivered.', 'यह सामान डिलीवर हो गया है।', 'Product deliver ho chuka hai.',
 'I cannot confirm its date, but the product was delivered after the cutoff.',
 'I checked whether it was delivered, and the product was delivered yesterday.'
])
def test_catalog_does_not_establish_completed_fulfillment(answer):
 with pytest.raises(ValueError, match='^unverified_catalog_fulfillment_event$'):
  check_catalog_fulfillment_claim(answer, 'What return rule applies to this product?', FACTS)

@pytest.mark.parametrize('answer', [
 'The product ships from a marketplace seller.', 'The item is fulfilled by Example Seller.',
 'If the item was delivered before the change date, the earlier window applies.',
 'The window starts after the item has been delivered.',
 'Products that were delivered before the change follow the historical rule.',
 'I cannot confirm whether it was delivered.',
 'अगर सामान डिलीवर हो गया है तो लागू अवधि देखें।',
 'Agar product deliver ho chuka hai, applicable window dekhein.',
 'This applies regardless of whether the item was delivered by the retailer or a seller.',
 'Chahe product deliver ho chuka hai, condition ki jaanch zaroori hai.'
])
def test_catalog_attributes_conditional_policy_and_uncertainty_are_preserved(answer):
 check_catalog_fulfillment_claim(answer, 'What return rule applies to this product?', FACTS)

@pytest.mark.parametrize('facts,query', [
 ({**FACTS, 'verified_order': {'delivered_on': '2026-07-20'}}, 'What is my return window?'),
 ({**FACTS, 'public_context': {'sku': 'SYN-X', 'delivered_on': '2026-07-20'}}, 'What is my return window?'),
 (FACTS, 'My product was delivered last July. What window applies?'),
 ({}, 'What is the delivery policy?')
])
def test_actual_record_or_customer_premise_remains_a_separate_validation_scope(facts,query):
 check_catalog_fulfillment_claim('The item was delivered in July.',query,facts)

def test_source_generation_repairs_event_without_injecting_a_policy_answer():
 sources=[{'id':'RULE-NEW','doc_type':'policy','status':'current','text':'The general return window is 9 calendar days from delivery. Items delivered before 1 August 2026 have the earlier 14-day window.'}]
 good='The general return window is 9 calendar days from delivery. Items delivered before 1 August 2026 follow the earlier 14-day window.'
 answers=iter(['The product was shipped from a marketplace seller and delivered after the change date.',good]);calls=[]
 class Client:
  def complete(self,system,user,**options):
   calls.append(json.loads(user));return json.dumps({'answer':next(answers),'covered':True,'needs_clarification':False})
 result=document_reply(Client(),'Is the window still fourteen days?','en',sources,facts=FACTS,context_provenance=True)
 assert result['answer']==good and result['generation_attempts']==2
 assert result['repair_errors']==['unverified_catalog_fulfillment_event']
 assert calls[0]['source_text']==calls[1]['source_text']
