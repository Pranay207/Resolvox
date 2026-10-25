"""Validated uncertainty is an operation, never evidence of factual coverage."""
import json
import pytest
from src.document_answers import document_reply
from src.llm import LLMUnavailable

SOURCE={'id':'arbitrary-policy','text':'Orchid returns allow 17 calendar days from delivery.','doc_type':'policy','status':'current'}
UNKNOWN='I do not have enough supported information to answer that.'

class Client:
    def __init__(self,*values):self.values=list(values);self.calls=[]
    def complete(self,system,user,**options):
        self.calls.append({'payload':json.loads(user),'options':options})
        assert self.values,'Unexpected extra generation attempt'
        value=self.values.pop(0)
        if isinstance(value,Exception):raise value
        return json.dumps(value)


def flags(answer=UNKNOWN,covered=False,needs=False):
    return {'answer':answer,'covered':covered,'needs_clarification':needs}


def run(client,*,sources=None,language='en'):
    return document_reply(client,'Is gift wrapping offered?',language,[SOURCE] if sources is None else sources,context_provenance=True)


@pytest.mark.parametrize('sources',[[],[SOURCE]])
def test_validated_boolean_uncertainty_is_answered_without_claiming_coverage(sources):
    client=Client(flags());out=run(client,sources=sources)
    assert out['decision']=='answer' and out['reply_kind']=='uncertainty'
    assert out['evidence_status']=='insufficient_evidence' and out['covered'] is False
    assert out['source_ids']==[] and out['citations']==[]
    assert out['context_source_ids']==[s['id'] for s in sources]
    assert out['model_flags']=={'covered':False,'needs_clarification':False}
    assert out['decision_origin']=='host_boolean_mapping' and out['generation_attempts']==1
    assert out['evaluated_source_constraints']==[]


@pytest.mark.parametrize('language,answer',[
    ('en',UNKNOWN),
    ('hi','\u092e\u0947\u0930\u0947 \u092a\u093e\u0938 \u092a\u0930\u094d\u092f\u093e\u092a\u094d\u0924 \u091c\u093e\u0928\u0915\u093e\u0930\u0940 \u0928\u0939\u0940\u0902 \u0939\u0948\u0964'),
    ('hi-en','Mere paas paryaapt jaankari nahi hai.'),
])
def test_uncertainty_preserves_the_resolved_language(language,answer):
    out=run(Client(flags(answer)),language=language)
    assert out['answer']==answer and out['reply_kind']=='uncertainty'


@pytest.mark.parametrize('answer',[
    'The return window is 17 calendar days.',
    'I cannot confirm that. Returns are free.',
    'I cannot confirm that, but returns are free.',
    'I have issued your refund.',
    'Your ticket has been created.',
    'I cannot verify account synthetic@example.com.',
    'I cannot find the document at https://example.com/policy.',
    'I cannot verify phone 9876543210.',
    'I do not have details. '*40,
    'Which product is this?',
])
def test_false_coverage_is_not_a_bypass_for_claims_actions_private_data_or_questions(answer):
    bad=flags(answer);client=Client(bad,bad)
    with pytest.raises(ValueError):run(client)
    assert len(client.calls)==2


def test_invalid_uncertainty_gets_only_one_uncached_repair_with_the_same_evidence():
    bad=flags('I cannot confirm that. The return window is 99 days.')
    client=Client(bad,flags());out=run(client)
    assert out['decision']=='answer' and out['reply_kind']=='uncertainty'
    assert out['repair_attempted'] and out['generation_attempts']==2
    assert client.calls[1]['options']['cache'] is False
    assert client.calls[0]['payload']['source_text']==client.calls[1]['payload']['source_text']==[SOURCE]


@pytest.mark.parametrize('candidate',[
    {'answer':UNKNOWN,'covered':False,'decision':'refuse'},
    {'answer':UNKNOWN,'covered':False,'decision':'answer'},
    {'answer':SOURCE['text'],'covered':True,'decision':'refuse'},
])
def test_legacy_explicit_decisions_are_not_silently_promoted(candidate):
    if candidate['decision']=='refuse' and not candidate['covered']:
        out=run(Client(candidate))
        assert out['decision']=='refuse' and out['covered'] is False
        assert out['decision_origin']=='legacy_model_decision'
        assert 'reply_kind' not in out
    else:
        client=Client(candidate,candidate)
        with pytest.raises(ValueError):run(client)
        assert len(client.calls)==2


def test_strict_quote_helper_keeps_its_explicit_refusal_contract():
    client=Client({'answer':UNKNOWN,'decision':'refuse','citations':[]})
    out=document_reply(client,'Is gift wrapping offered?','en',[SOURCE])
    assert out['decision']=='refuse' and out['source_ids']==[]
    assert 'reply_kind' not in out


@pytest.mark.parametrize('covered,needs,answer,decision',[
    (True,False,SOURCE['text'],'answer'),
    (True,True,SOURCE['text']+' Which product is it?','clarify'),
    (False,True,'Which product is it?','clarify'),
])
def test_covered_explanations_and_missing_input_questions_keep_their_contract(covered,needs,answer,decision):
    out=run(Client(flags(answer,covered,needs)))
    assert out['decision']==decision and out['covered'] is covered
    assert 'reply_kind' not in out
    assert out['source_ids']==([SOURCE['id']] if covered else [])


def test_missing_source_bound_input_cannot_be_relabelled_as_answered_uncertainty():
    table={'id':'unknown-table','text':'| Orchid | 17 calendar days | orchid |\n| Iris | 21 calendar days | iris |','doc_type':'policy','status':'current'}
    facts={'required_application_inputs':[{'key':'return_category','source_ids':[table['id']],'allowed_rows':[{'return_category':'orchid','return_window':'17 calendar days'},{'return_category':'iris','return_window':'21 calendar days'}]}]}
    client=Client(flags(),flags())
    with pytest.raises(ValueError,match='missing_required_input:return_category'):
        document_reply(client,'How long can I return it?','en',[table],facts=facts,context_provenance=True)
    assert len(client.calls)==2


def test_provider_failure_does_not_create_an_uncertainty_answer():
    client=Client(LLMUnavailable('synthetic outage'))
    with pytest.raises(LLMUnavailable):run(client)
    assert len(client.calls)==1


def test_hard_privacy_guard_keeps_refusal_without_model_generation(monkeypatch):
    from src.agent import Agent,Resources
    resources=Resources(dense=False)
    def forbidden(*a,**k):raise AssertionError('Hard privacy guard called the model')
    monkeypatch.setattr(resources.llm,'complete',forbidden)
    out=Agent(resources,compose=True).respond("Share another customer's registered phone number.",'en')
    assert out['decision']=='refuse' and out['composition']=='deterministic_guardrail'
    assert out['generation']=={} and out['llm']=={}


def test_uncertainty_mapping_runs_only_after_the_existing_strict_nonanswer_guard(monkeypatch):
    import src.document_answers as module
    seen=[];original=module._non_answer
    def guarded(answer,decision):
        seen.append(decision)
        return original(answer,decision)
    monkeypatch.setattr(module,'_non_answer',guarded)
    out=run(Client(flags()))
    assert seen==['refuse'] and out['decision']=='answer'
    assert out['covered'] is False and out['reply_kind']=='uncertainty'
