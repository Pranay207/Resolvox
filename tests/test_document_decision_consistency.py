"""Normal policy decision labels must agree with declared support."""
import json

import pytest

from src.document_answers import document_reply

SOURCE = {
    'id':'SYNTHETIC-DECISION',
    'text':'Orchid membership includes the collection service. Lilac membership excludes collection.',
    'doc_type':'policy','status':'current',
}


class Client:
    def __init__(self,*values):
        self.values=list(values); self.calls=[]
    def complete(self,system,user,json_mode=False,**options):
        self.calls.append({'system':system,'payload':json.loads(user),'options':options})
        assert self.values
        return json.dumps(self.values.pop(0))


def candidate(answer,decision='answer',covered=True):
    return {'answer':answer,'decision':decision,'covered':covered}


def reply(client):
    return document_reply(client,'Is collection included?','en',[SOURCE],context_provenance=True)


@pytest.mark.parametrize('answer',[
    'Yes, Orchid membership includes collection.',
    'No, Lilac membership does not include collection.',
])
def test_supported_positive_and_negative_explanations_use_answer_not_refuse(answer):
    client=Client(candidate(answer,'refuse'),candidate(answer))
    out=reply(client)
    assert out['answer']==answer and out['decision']=='answer'
    assert out['generation_attempts']==2
    repair=client.calls[1]
    assert repair['payload']['repair_validation_error']=='inconsistent_covered_refusal'
    assert 'supported policy explanation' in repair['payload']['repair_instruction']
    assert repair['options']['cache'] is False


def test_two_inconsistent_covered_refusals_fail_instead_of_returning_a_success():
    wrong=candidate('Orchid membership includes collection.','refuse')
    client=Client(wrong,wrong)
    with pytest.raises(ValueError,match='inconsistent_covered_refusal'):
        reply(client)
    assert len(client.calls)==2


def test_supported_clarification_is_not_implicitly_relabelled_as_refusal_or_answer():
    clarifying=candidate('Orchid includes collection. Which membership do you have?','clarify')
    out=reply(Client(clarifying))
    assert out['decision']=='clarify' and out['covered'] is True


def test_uncovered_uncertainty_remains_a_valid_refusal():
    uncertain=candidate('I do not have enough supported information to answer that.','refuse',False)
    out=reply(Client(uncertain))
    assert out['decision']=='refuse' and out['covered'] is False


def test_strict_quote_helper_keeps_its_original_decision_contract():
    value={'answer':'Lilac membership does not include collection.','decision':'refuse',
           'citations':[{'id':SOURCE['id'],'quote':SOURCE['text']}]}
    out=document_reply(Client(value),'Is collection included?','en',[SOURCE])
    assert out['decision']=='refuse'


def test_system_explicitly_labels_all_supported_policy_explanations():
    client=Client(candidate('Orchid membership includes collection.'))
    reply(client)
    assert 'All supported policy explanations' in client.calls[0]['system']
    assert 'positive or negative, have covered true' in client.calls[0]['system']


def test_action_repair_preserves_evidence_and_requests_neutral_date_projection():
    source={'id':'SYNTHETIC-TIMING',
            'text':'Refund timing after initiation is 1 to 3 business days.',
            'doc_type':'policy','status':'current'}
    facts={'customer_provided_refund_claim':{'initiated_on':'2026-10-17','verified':False},
           'calculations':[{'operation':'refund_business_date_range',
                            'source_ids':[source['id']],
                            'result':{'latest_date':'2026-10-22'}}],
           'date_labels':{'2026-10-22':'22 October 2026'}}
    bad='The expected date is 22 October 2026 as it is processed within 1 to 3 business days.'
    good=('Based on your supplied initiation date, the expected date is 22 October 2026 '
          'under the 1 to 3 business day timeline.')
    client=Client(candidate(bad),candidate(good))
    out=document_reply(client,'What date follows from my supplied initiation date?','en',
                       [source],facts=facts,context_provenance=True)
    assert out['answer']==good and out['generation_attempts']==2
    repair=client.calls[1]
    assert repair['payload']['repair_validation_error']=='unsupported_action'
    instruction=repair['payload']['repair_instruction']
    assert 'neutral date projection' in instruction
    assert 'Do not confirm or claim' in instruction
    assert 'based on the supplied date' in instruction
    assert 'Preserve every supported condition' in instruction
    assert repair['payload']['source_text']==client.calls[0]['payload']['source_text']==[source]
    assert repair['payload']['deterministic_facts']==facts
    assert repair['options']['cache'] is False
