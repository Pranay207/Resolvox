import json
import pytest
from src.document_answers import document_reply
class Client:
 def __init__(self,*answers):self.answers=list(answers);self.calls=[]
 def complete(self,system,user,**options):
  self.calls.append((system,json.loads(user),options));return json.dumps({'answer':self.answers.pop(0),'has_document_support':True,'needs_clarification':False},ensure_ascii=False)
def sources():
 return [{'id':'report-rule','file':'damage.md','doc_type':'policy','status':'current','effective_from':'2020-01-01','text':'Report damaged items within 17 hours of delivery. Photos of the item and packaging are required.'},{'id':'claim-rule','file':'damage.md','doc_type':'policy','status':'current','effective_from':'2020-01-01','text':'After claim verification, you will get a replacement.'}]
def test_hindi_reporting_starts_with_the_actual_rule_without_eligibility_promises():
 client=Client('डिलीवरी के 17 घंटे के भीतर खराब सामान की रिपोर्ट करें। सामान और पैकेजिंग की फ़ोटो दें।')
 result=document_reply(client,'मेरा सामान खराब आया है, अब क्या करूँ?','hi',sources(),facts={},context_provenance=True)
 assert len(client.calls)==1 and result['covered'] is True and result['repair_attempted'] is False
 assert [s['id'] for s in client.calls[0][1]['source_text']]==['report-rule']
 assert 'has_document_support' in client.calls[0][2]['schema']['properties']
 assert result['reporting_support_contract']['scope']=='public_reporting_obligation_only'
def test_actual_claim_verification_is_still_required_for_a_replacement_promise():
 bad='Report the damage within 17 hours of delivery with photos. You will get a replacement.'
 with pytest.raises(ValueError):document_reply(Client(bad,bad),'My item arrived broken. What do I do now?','en',sources(),facts={},context_provenance=True)
