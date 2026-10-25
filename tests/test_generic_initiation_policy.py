"""A generic policy clock is distinct from an executed customer action."""
import json
import pytest
from src.document_answers import document_reply,_source_generic_initiation_validation_text
from src.grounding import _completed_action

SOURCE={'id':'novel-source','text':'For Orchid Circle members, the refund is initiated at the time of collection.',
        'doc_type':'policy','status':'current','effective_from':'2020-01-01'}
ANSWER='For Orchid Circle members, the refund is initiated at collection.'

class Client:
    def __init__(self,*answers):self.answers=list(answers);self.calls=[]
    def complete(self,*args,**kwargs):
        self.calls.append((args,kwargs));assert self.answers
        return json.dumps({'answer':self.answers.pop(0),'covered':True,'needs_clarification':False})


def run(client,sources=None):
    return document_reply(client,'Explain the membership initiation clock.','en',[SOURCE] if sources is None else sources,context_provenance=True)


def test_source_supported_generic_clock_is_not_a_completed_customer_action():
    assert _completed_action(ANSWER)
    assert not _completed_action(_source_generic_initiation_validation_text(ANSWER,[SOURCE]))
    out=run(Client(ANSWER))
    assert out['answer']==ANSWER and out['generation_attempts']==1 and out['covered'] is True


@pytest.mark.parametrize('answer',[
    'For Orchid Circle members, your refund is initiated at collection.',
    'For Orchid Circle members, the refund was initiated at collection.',
    'For Orchid Circle members, the refund has been initiated at collection.',
    'For Orchid Circle members, the refund is initiated at collection today.',
    'For Orchid Circle members, the refund is initiated at collection on 3 November 2026.',
    ANSWER+' I have issued your refund.',
    ANSWER+' Your ticket has been created.',
    'I confirm that for Orchid Circle members, the refund is initiated at collection.',
])
def test_personal_completed_dated_and_separate_operational_claims_still_fail(answer):
    client=Client(answer,answer)
    with pytest.raises(ValueError):run(client)
    assert len(client.calls)==2


@pytest.mark.parametrize('change',[
    {'text':SOURCE['text'].replace('collection','dispatch')},
    {'text':SOURCE['text'].replace('Orchid Circle','Iris Circle')},
    {'text':'There is no documented initiation policy.'},
    {'text':'It is false that for Orchid Circle members, the refund is initiated at collection.'},
    {'text':'For Orchid Circle members, the refund is not initiated at collection.'},
    {'doc_type':'faq'},
    {'doc_type':'marketing'},
    {'status':'superseded'},
    {'effective_from':'2099-01-01'},
    {'effective_from':None},
])
def test_changed_missing_or_unauthorized_source_does_not_authorize_old_predicate(change):
    source={**SOURCE,**change};client=Client(ANSWER,ANSWER)
    with pytest.raises(ValueError):run(client,[source])
    assert len(client.calls)==2


def test_same_rank_conflicting_policy_clocks_decline_exemption():
    other={**SOURCE,'id':'other-source','text':SOURCE['text'].replace('collection','dispatch')}
    assert _source_generic_initiation_validation_text(ANSWER,[SOURCE,other])==ANSWER
    with pytest.raises(ValueError):run(Client(ANSWER,ANSWER),[SOURCE,other])


def test_source_mutation_changes_the_supported_clock_without_static_policy_constants():
    source={**SOURCE,'id':'random-new-id','text':SOURCE['text'].replace('Orchid Circle','Aster Guild').replace('collection','dispatch')}
    answer=ANSWER.replace('Orchid Circle','Aster Guild').replace('collection','dispatch')
    assert run(Client(answer),[source])['answer']==answer


@pytest.mark.parametrize('answer',[
    ANSWER+' Returns take 99 calendar days.',
    ANSWER+' The fee is 99 rupees.',
    ANSWER+' Your email is customer@example.com.',
])
def test_masking_a_generic_predicate_does_not_hide_quantities_or_private_claims(answer):
    with pytest.raises(ValueError):run(Client(answer,answer))


def test_a_valid_clock_quantity_keeps_its_unit_checks():
    source={**SOURCE,'text':SOURCE['text'].replace('at the time of collection','within 17 business days of collection')}
    answer=ANSWER.replace('at collection','within 17 business days of collection')
    assert run(Client(answer),[source])['answer']==answer
    wrong=answer.replace('business','calendar')
    with pytest.raises(ValueError):run(Client(wrong,wrong),[source])


def test_invalid_action_gets_one_repair_using_unchanged_source():
    client=Client('I have issued your refund.',ANSWER)
    out=run(client)
    assert out['generation_attempts']==2 and out['repair_attempted']
    first=json.loads(client.calls[0][0][1]);second=json.loads(client.calls[1][0][1])
    assert first['source_text']==second['source_text']==[SOURCE]
    assert second['repair_validation_error']=='unsupported_action'
