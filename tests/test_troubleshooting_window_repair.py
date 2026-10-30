"""An unrelated personal window must not hide source-supported repair steps."""
from datetime import date
import copy
import json
import pytest
from src.document_answers import document_reply
from src.generation_diagnostics import GenerationValidationError


class Client:
    def __init__(self, *answers):self.answers=list(answers);self.calls=[]
    def complete(self, system, user, **options):
        self.calls.append({'payload':json.loads(user),'system':system,'options':options})
        return json.dumps({'answer':self.answers.pop(0),'covered':True,'needs_clarification':False})


def fixture(current=11, previous=17, charge=18, reset=6):
    sources=[
        {'id':'SYNTH-TABLE','text':f'| Portable devices and accessories | {current} days | device_x |','doc_type':'policy','status':'current','effective_from':'2032-01-01'},
        {'id':'SYNTH-HISTORY','text':f'From 13 June 2033, the return window for portable devices and accessories is {current} days. Portable devices delivered before 13 June 2033 keep the earlier {previous}-day window from version 2 of this policy.','doc_type':'policy','status':'current','effective_from':'2032-01-01'},
        {'id':'SYNTH-HELP','text':f'## Portable device not powering on\n1. Charge it for at least {charge} minutes with its supplied cable.\n2. Hold the power button for {reset} seconds to restart.\nIf the issue persists after these steps, it may be returned within its applicable window or claimed under the applicable warranty.','doc_type':'help','status':'current','effective_from':'2020-01-01'}]
    facts={'reference_date':'2033-08-04','calculations':[], 'public_context':{'category':'device_x'},'return_policy':{'category':'device_x','window_calendar_days':current,'source_ids':['SYNTH-TABLE'],'selection':'standard_window','historical_exception':{'delivery_before':'2033-06-13','window_calendar_days':previous,'source_ids':['SYNTH-HISTORY']}}}
    good=f'Charge the device for at least {charge} minutes using its supplied cable, then hold the power button for {reset} seconds to restart. If the issue persists after these steps, refer to the applicable return window or warranty.'
    bad=good+f' The item can be returned within its {current}-day return window.'
    return sources,facts,good,bad


@pytest.mark.parametrize('values',[(11,17,18,6),(4,9,22,8),(13,19,45,16)])
def test_repair_keeps_mutated_source_steps_and_does_not_guess_a_delivery_window(monkeypatch,values):
    import src.document_answers as module
    monkeypatch.setattr(module,'REFERENCE_DATE',date(2033,8,4))
    sources,facts,good,bad=fixture(*values);before=copy.deepcopy((sources,facts));client=Client(bad,good)
    result=document_reply(client,"My portable device won't power on.",'en',sources,facts=facts,context_provenance=True)
    assert result['answer']==good
    assert result['repair_errors']==['unsupported_delivery_exception_personal_window']
    assert result['generation_attempts']==2
    assert 'actual numbered troubleshooting procedure' in client.calls[1]['system']
    assert result['repair_mode']=='source_troubleshooting_restatement'
    assert client.calls[1]['payload']['source_text']==[next(row for row in sources if row['id']=='SYNTH-HELP')]
    assert client.calls[1]['payload']['deterministic_facts']=={}
    assert client.calls[1]['options']['cache'] is False
    assert (sources,facts)==before


def test_repeated_wrong_individual_window_remains_rejected(monkeypatch):
    import src.document_answers as module
    monkeypatch.setattr(module,'REFERENCE_DATE',date(2033,8,4))
    sources,facts,_,bad=fixture();client=Client(bad,bad)
    with pytest.raises(GenerationValidationError):
        document_reply(client,"My portable device won't power on.",'en',sources,facts=facts,context_provenance=True)
    assert len(client.calls)==2


def test_compound_return_question_retains_the_full_policy_and_date_requirements(monkeypatch):
    import src.document_answers as module
    monkeypatch.setattr(module,'REFERENCE_DATE',date(2033,8,4))
    sources,facts,good,bad=fixture()
    good+=' The current return window is 11 days for devices delivered on or after 13 June 2033; devices delivered before that date retain the earlier 17-day window.'
    client=Client(bad,good)
    result=document_reply(client,"My device won't power on. What steps can I try and what return windows apply?",'en',sources,facts=facts,context_provenance=True)
    assert result['answer']==good
    assert client.calls[1]['payload']['source_text']==client.calls[0]['payload']['source_text']
    assert 'If the customer actually asks about return timing' in client.calls[1]['payload']['repair_instruction']



def test_ambiguous_or_unrequested_help_view_is_not_selected():
    from src.repair_contexts import troubleshooting_restatement_inputs
    sources,facts,_,_=fixture()
    assert troubleshooting_restatement_inputs("My portable device won't power on.",facts,sources,date(2033,8,4))
    for question in ["My portable device won't power on; can I return it?", "My portable device won't power on; what warranty applies?", "It won't power on."]:
        assert troubleshooting_restatement_inputs(question,facts,sources,date(2033,8,4)) is None
    duplicate=copy.deepcopy(sources[-1]);duplicate['id']='OTHER-HELP'
    assert troubleshooting_restatement_inputs("My portable device won't power on.",facts,sources+[duplicate],date(2033,8,4)) is None


def test_focused_context_does_not_authorize_an_invented_step_duration(monkeypatch):
    import src.document_answers as module
    monkeypatch.setattr(module,'REFERENCE_DATE',date(2033,8,4))
    sources,facts,good,bad=fixture()
    client=Client(bad,good.replace('18 minutes','999 minutes'))
    with pytest.raises(GenerationValidationError) as error:
        document_reply(client,"My portable device won't power on.",'en',sources,facts=facts,context_provenance=True)
    assert error.value.diagnostics['validation_error'] in {'unsupported_number','unsupported_quantity_unit'}
