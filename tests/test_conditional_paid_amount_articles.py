"""Conditional fee premises do not assert a personal payment took place."""
import pytest
from src.personal_money import validate_personal_money,_mentions
from src.document_answers import document_reply
from src.generation_diagnostics import GenerationValidationError

@pytest.mark.parametrize('article',['the','a','an'])
@pytest.mark.parametrize('subject',['you paid','you have paid','I paid','we paid'])
def test_article_in_a_direct_payment_condition_remains_hypothetical(article,subject):
 text=f'If {subject} {article} ₹137 service fee, the policy condition may apply.'
 mentions=_mentions(text)
 assert len(mentions)==1 and mentions[0]['role']=='paid_amount' and mentions[0]['conditional'] is True
 validate_personal_money(text,'Is there a benefit for a late shipment?',{},[],private=False)

@pytest.mark.parametrize('text',[
 'You paid the ₹137 service fee.',
 'If delivery was late then you paid the ₹137 service fee.',
 'If delivery was late then you paid ₹137.',
 'If delivery was late, you paid the ₹137 service fee.',
 'If you paid the ₹137 fee, your refund is ₹999.',
])
def test_unrelated_conditions_and_later_amount_assertions_still_require_payment_evidence(text):
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money(text,'Is there a benefit for a late shipment?',{},[],private=False)

def test_hypothetical_payment_does_not_authorize_a_new_source_quantity():
 import json
 class Client:
  def complete(self,*a,**kw):return json.dumps({'answer':'If you paid the ₹999 service fee, a condition may apply.','covered':True,'needs_clarification':False})
 sources=[{'id':'fee-novel','text':'A service fee is ₹137.','doc_type':'policy','status':'current','effective_from':'2020-01-01'}]
 with pytest.raises(GenerationValidationError):document_reply(Client(),'What is the service fee?','en',sources,context_provenance=True)
