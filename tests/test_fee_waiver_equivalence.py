"""Zero-fee wording requires the exact current source waiver and membership."""
import json
import pytest
from src.document_answers import document_reply

SOURCE={'id':'ARBITRARY-FEE','doc_type':'policy','status':'current','effective_from':'2026-01-01',
        'text':'A reverse pickup fee of 83 rupees applies to returns. The fee is waived for Orchid Premium members.'}
QUERY='I am an Orchid Premium member. Is the reverse pickup fee waived?'

class Client:
    def __init__(self,text,covered=True):self.text=text;self.covered=covered;self.calls=0
    def complete(self,*args,**kwargs):
        self.calls+=1
        return json.dumps({'answer':self.text,'covered':self.covered,'needs_clarification':False})


def reply(text,source=None,query=QUERY,**options):
    client=Client(text)
    out=document_reply(client,query,'en',[source or SOURCE],context_provenance=True,**options)
    return out,client


def test_zero_fee_is_equivalent_to_an_actual_applicable_waiver():
    text='As an Orchid Premium member, your reverse pickup fee is zero rupees.'
    out,client=reply(text)
    assert out['answer']==text and client.calls==1
    assert out['source_ids']==[SOURCE['id']]


@pytest.mark.parametrize('query,source,text',[
    ('I am not an Orchid Premium member.',SOURCE,'As an Orchid Premium member, your reverse pickup fee is zero.'),
    ('I am not currently an Orchid Premium member.',SOURCE,'As an Orchid Premium member, your reverse pickup fee is zero.'),
    ('Main Premium member nahi hoon.',SOURCE,'As an Orchid Premium member, your reverse pickup fee is zero.'),
    (QUERY,{**SOURCE,'text':'A reverse pickup fee of 83 rupees applies to every return.'},'As an Orchid Premium member, your reverse pickup fee is zero.'),
    (QUERY,{**SOURCE,'status':'superseded'},'As an Orchid Premium member, your reverse pickup fee is zero.'),
    (QUERY,{**SOURCE,'effective_from':'2027-01-01'},'As an Orchid Premium member, your reverse pickup fee is zero.'),
    (QUERY,SOURCE,'As an Orchid Premium member, your delivery fee is zero.'),
    (QUERY,SOURCE,'As an Orchid Premium member, your reverse pickup fee is 0.25 rupees.'),
    ('I am a Sun Premium member.',SOURCE,'As an Orchid Premium member, your reverse pickup fee is zero.'),
    (QUERY,SOURCE,'As a Sun Premium member, your reverse pickup fee is zero.'),
    (QUERY,SOURCE,'As an Orchid Premium member, your reverse pickup fee is zero. The warranty lasts zero months.'),
])
def test_zero_waiver_cannot_license_wrong_scope_condition_or_other_quantities(query,source,text):
    with pytest.raises(ValueError):reply(text,source,query)


def test_uncertain_numeric_draft_is_discarded_without_business_claims_or_second_call():
    client=Client('The documents do not mention a 91-day return rule for the year 2057.',covered=False)
    out=document_reply(client,'Does the new 2057 rule give 91 days?','en',[SOURCE],
                       context_provenance=True,fast_uncertainty=True)
    assert client.calls==1 and out['reply_kind']=='uncertainty'
    assert out['source_ids']==[] and not out['covered']
    assert '91' not in out['answer'] and '2057' not in out['answer']
    assert out['answer_origin']=='host_uncertainty_guardrail'
    assert out['discarded_model_draft'] is True


def test_strict_helper_and_private_records_still_require_repair_or_rejection():
    for private,fast in [(False,False),(True,True)]:
        client=Client('The documents do not mention a 91-day return rule for 2057.',covered=False)
        with pytest.raises(ValueError):
            document_reply(client,'Does the 2057 rule give 91 days?','en',[SOURCE],
                context_provenance=True,fast_uncertainty=fast,private=private)
        assert client.calls==2


def test_unqualified_tier_with_explicit_full_source_group_in_answer_is_allowed():
    text='As an Orchid Premium member, your reverse pickup fee is zero.'
    out,client=reply(text,query='I am a Premium member. Is reverse pickup free?')
    assert out['answer']==text and client.calls==1


def test_negative_fee_clause_does_not_negate_the_actual_membership_claim():
    text='Nahi, reverse pickup ki fee nahi lagegi kyunki aap Orchid Premium member hain. Aapki reverse pickup fee zero hoti hai.'
    client=Client(text)
    out=document_reply(client,'Main Premium member hoon. Reverse pickup ki fee lagegi kya?','hi-en',[SOURCE],context_provenance=True)
    assert out['answer']==text and client.calls==1
