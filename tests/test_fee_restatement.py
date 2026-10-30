"""Fee-only repair reads mutable fee sources and retains every host fact."""
import copy
import json
from datetime import date
import pytest
from src.repair_contexts import fee_only_restatement_inputs
from src.document_answers import document_reply

SOURCE={'id':'ORCHID-2','text':'After verification the customer gets a full refund or replacement. No reverse pickup fee applies for damaged items.','doc_type':'policy','status':'current','effective_from':'2030-01-01'}
QUERY='Is collection free if the jacket arrived torn?'

class Client:
    def __init__(self,*answers):self.answers=list(answers);self.calls=[]
    def complete(self,system,user,**options):
        self.calls.append((system,json.loads(user),options));assert self.answers
        return json.dumps({'answer':self.answers.pop(0),'covered':True,'needs_clarification':False})

@pytest.mark.parametrize('bad,error',[
    ('The customer receives a full refund.','missing_remedy_prerequisite:verification'),
    ('I have issued your refund.','unsupported_action'),
])
def test_unrequested_remedy_is_replaced_by_a_source_fee_explanation_without_relaxing_guards(monkeypatch,bad,error):
    import src.document_answers as module
    monkeypatch.setattr(module,'REFERENCE_DATE',date(2031,5,12))
    facts={'reference_date':'2031-05-12','public_context':{'category':'novel_category'}};before=copy.deepcopy(facts)
    good='The reverse pickup fee is waived for items returned because they arrived damaged.'
    client=Client(bad,good)
    out=document_reply(client,QUERY,'en',[SOURCE],facts=facts,context_provenance=True)
    assert out['answer']==good and out['repair_mode']=='source_fee_restatement'
    assert out['repair_errors']==[error]
    assert client.calls[1][2]['cache'] is False and facts==before
    assert client.calls[0][1]['deterministic_facts']==client.calls[1][1]['deterministic_facts']
    assert client.calls[0][1]['source_text']==client.calls[1][1]['source_text']==[SOURCE]
    assert 'Do not discuss refund or replacement eligibility' in client.calls[1][0]

@pytest.mark.parametrize('question',[
    'Is collection free and when does my refund arrive?',
    'How much does pickup cost and can I receive a replacement?',
    'Explain the delivery attempts.',
    'Is shipping free?',
])
def test_compound_or_noncollection_question_does_not_enter_fee_only_mode(question):
    assert fee_only_restatement_inputs(question,{},[SOURCE],'2031-05-12') is None

@pytest.mark.parametrize('change',[{'doc_type':'marketing'},{'status':'superseded'},{'effective_from':'2035-01-01'}])
def test_noncurrent_or_nonauthoritative_fee_source_is_not_selected(change):
    assert fee_only_restatement_inputs(QUERY,{},[{**SOURCE,**change}],'2031-05-12') is None

@pytest.mark.parametrize('amount',[13,29])
def test_changed_charge_is_passed_through_without_a_free_collection_constant(amount):
    source={**SOURCE,'text':f'The collection charge is {amount} rupees for damaged items.'}
    out=fee_only_restatement_inputs(QUERY,{},[source],'2031-05-12')
    assert out['sources']==[source] and str(amount) in out['sources'][0]['text']


def test_fee_focus_does_not_authorize_an_action_in_its_second_answer(monkeypatch):
    import src.document_answers as module
    monkeypatch.setattr(module,'REFERENCE_DATE',date(2031,5,12))
    with pytest.raises(ValueError,match='unsupported_action'):
        document_reply(Client('I have issued your refund.','Your collection has been scheduled.'),QUERY,'en',[SOURCE],facts={},context_provenance=True)
