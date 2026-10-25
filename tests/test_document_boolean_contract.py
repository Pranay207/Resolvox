"""The model supplies booleans; operational decisions are derived by the host."""
import json

import pytest

from src.document_answers import document_reply

SOURCE={'id':'SYNTHETIC-BOOLEAN',
        'text':'Orchid returns allow 17 calendar days from delivery.',
        'doc_type':'policy','status':'current'}


class Client:
    def __init__(self,*values):
        self.values=list(values); self.calls=[]
    def complete(self,system,user,json_mode=False,**options):
        self.calls.append({'system':system,'payload':json.loads(user),'options':options})
        assert self.values
        return json.dumps(self.values.pop(0))


def flags(answer,covered=True,needs=False):
    return {'answer':answer,'covered':covered,'needs_clarification':needs}


def reply(client):
    return document_reply(client,'What is the Orchid return policy?','en',[SOURCE],
                          context_provenance=True)


@pytest.mark.parametrize('candidate,decision',[
    (flags(SOURCE['text']), 'answer'),
    (flags('Orchid returns allow 17 calendar days. Which product do you have?',True,True), 'clarify'),
    (flags('Which product would you like to return?',False,True), 'clarify'),
    (flags('I do not have enough supported information to answer that.',False,False), 'answer'),
])
def test_all_four_flag_combinations_have_explicit_host_decisions(candidate,decision):
    client=Client(candidate)
    out=reply(client)
    assert out['decision']==decision
    assert out['decision_origin']=='host_boolean_mapping'
    assert out['model_flags']=={key:candidate[key] for key in ('covered','needs_clarification')}
    assert out['covered'] is candidate['covered']
    assert out['citations']==[]
    assert out['context_source_ids']==[SOURCE['id']]
    assert out['source_ids']==([SOURCE['id']] if candidate['covered'] else [])
    schema=client.calls[0]['options']['schema']
    assert set(schema['required'])=={'answer','covered','needs_clarification'}
    assert schema['properties']['covered']=={'type':'boolean'}
    assert schema['properties']['needs_clarification']=={'type':'boolean'}
    assert 'decision' not in schema['properties']


@pytest.mark.parametrize('field,bad',[
    ('covered',1),('covered','true'),('covered',None),
    ('needs_clarification',0),('needs_clarification','false'),('needs_clarification',None),
])
def test_flags_must_be_real_json_booleans_after_at_most_one_repair(field,bad):
    invalid=flags(SOURCE['text']); invalid[field]=bad
    client=Client(invalid,invalid)
    with pytest.raises(ValueError):
        reply(client)
    assert len(client.calls)==2


def test_a_boolean_type_error_repairs_once_without_changing_evidence():
    invalid=flags(SOURCE['text']); invalid['needs_clarification']='false'
    client=Client(invalid,flags(SOURCE['text']))
    out=reply(client)
    assert out['decision']=='answer' and out['generation_attempts']==2
    assert client.calls[0]['payload']['source_text']==client.calls[1]['payload']['source_text']==[SOURCE]
    assert client.calls[1]['options']['cache'] is False
    assert client.calls[1]['payload']['repair_validation_error']=='invalid_clarification_flag'


@pytest.mark.parametrize('candidate',[
    flags('The return window is 99 calendar days.'),
    flags('I have issued your refund.'),
    flags('Your contact email is synthetic@example.com.'),
    flags('The policy gives 17 calendar days.',False,False),
    flags('Which product is this? Returns take 17 calendar days.',False,True),
])
def test_boolean_mapping_does_not_relax_source_action_private_or_nonanswer_checks(candidate):
    client=Client(candidate,candidate)
    with pytest.raises(ValueError):
        reply(client)
    assert len(client.calls)==2


def test_legacy_valid_context_output_is_explicitly_labelled_legacy():
    old={'answer':SOURCE['text'],'decision':'answer','covered':True}
    out=reply(Client(old))
    assert out['decision']=='answer'
    assert out['decision_origin']=='legacy_model_decision'
    assert out['model_flags']=={'covered':True}


def test_legacy_inconsistent_refusal_is_not_silently_mapped_to_answer():
    old={'answer':SOURCE['text'],'decision':'refuse','covered':True}
    client=Client(old,old)
    with pytest.raises(ValueError,match='inconsistent_covered_refusal'):
        reply(client)
    assert len(client.calls)==2


def test_mixing_legacy_decision_with_new_flags_is_rejected():
    mixed=flags(SOURCE['text']); mixed['decision']='supported'
    client=Client(mixed,mixed)
    with pytest.raises(ValueError,match='invalid_response_fields'):
        reply(client)
    assert len(client.calls)==2


def test_normal_prompt_does_not_ask_the_model_to_emit_an_operational_enum():
    client=Client(flags(SOURCE['text']))
    reply(client)
    system=client.calls[0]['system']
    assert 'Return exactly JSON with answer, covered and needs_clarification' in system
    assert 'Both flags must be booleans' in system
    assert 'do not output a decision field' in system


def test_strict_quoted_helper_keeps_its_original_model_decision_contract():
    old={'answer':SOURCE['text'],'decision':'answer',
         'citations':[{'id':SOURCE['id'],'quote':SOURCE['text']}]}
    client=Client(old)
    out=document_reply(client,'What is the return window?','en',[SOURCE])
    assert out['decision']=='answer'
    assert out['citations']==old['citations']
    schema=client.calls[0]['options']['schema']
    assert 'decision' in schema['properties']
    assert 'needs_clarification' not in schema['properties']
