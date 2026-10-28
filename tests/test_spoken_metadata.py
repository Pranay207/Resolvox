import json,pytest
from src.document_answers import document_reply
from src.generation_diagnostics import GenerationValidationError
SOURCE={'id':'route-new','text':'Claims are raised in the app under Service Requests.','doc_type':'policy','status':'current','effective_from':'2020-01-01'}
class Client:
 def __init__(self,*answers):self.answers=list(answers)
 def complete(self,*a,**kw):return json.dumps({'answer':self.answers.pop(0),'covered':True,'needs_clarification':False})
@pytest.mark.parametrize('bad',['covered=true reason: Claims are in the app.','has_document_support=true reason: Claims are in the app.','needs_clarification: false.','ordinary_return_condition_check is not satisfied.'])
def test_machine_metadata_is_rejected_as_spoken_text(bad):
 with pytest.raises(GenerationValidationError):document_reply(Client(bad,bad),'Where are claims raised?','en',[SOURCE],context_provenance=True)
def test_metadata_leak_gets_one_source_based_repair():
 good='Claims are in the app under Service Requests.'
 result=document_reply(Client('covered=true reason: Claims are in the app.',good),'Where are claims raised?','en',[SOURCE],context_provenance=True)
 assert result['answer']==good and result['repair_errors']==['internal_metadata_in_answer']
