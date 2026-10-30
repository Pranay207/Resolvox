"""Check source-bound separation of membership initiation and settlement."""
import pytest
from src.source_semantics import derive_source_constraints, validate_source_semantics


def policy(name='Orchid Gold', **changes):
    return dict(id='mutated-benefit', doc_type='policy', status='current',
                text=f'{name} does **not** change return windows, return eligibility or refund timelines after initiation.', **changes)


@pytest.mark.parametrize('answer', [
    'Orchid Gold member hai, isliye wallet se instant refund milta hai.',
    'Because you are an Orchid Gold member, your refund arrives instantly.',
    'Your refund is faster because you are an Orchid Gold member.',
    'Orchid Gold सदस्य हैं इसलिए रिफंड तुरंत मिलता है।',
])
def test_membership_cannot_be_the_reason_for_faster_arrival(answer):
    with pytest.raises(ValueError, match='source_membership_refund_speed'):
        validate_source_semantics(answer, [policy()])


@pytest.mark.parametrize('answer', [
    'For Orchid Gold, refunds are initiated at pickup. Wallet refunds are instant after initiation.',
    'Orchid Gold members initiate at pickup, so the refund starts immediately.',
    'Wallet se payment kiya tha, isliye refund instant milta hai. Orchid Gold se initiation pickup par hota hai.',
    'Orchid Gold does not make refunds arrive faster.',
    'Wallet refunds are instant; Orchid Gold does not change that timeline.',
    'Orchid Gold membership changes initiation, not refund arrival speed.',
    'An Orchid Gold member gets a refund according to the original payment method.',
])
def test_distinct_initiation_and_payment_method_clauses_remain_valid(answer):
    validate_source_semantics(answer, [policy()])


def test_membership_name_and_source_identity_are_read_from_changed_policy():
    old='Orchid Gold member hai, isliye wallet se instant refund milta hai.'
    changed=policy('Cobalt Pearl')
    validate_source_semantics(old, [changed])
    with pytest.raises(ValueError, match='source_membership_refund_speed'):
        validate_source_semantics(old.replace('Orchid Gold','Cobalt Pearl'), [changed])
    item=derive_source_constraints([changed])[0]
    assert item['membership_label']=='Cobalt Pearl'
    assert item['source_ids']==['mutated-benefit']
    assert item['source_sha256']['mutated-benefit']


@pytest.mark.parametrize('change', [
    {'status':'archived'}, {'status':'draft'}, {'doc_type':'faq'},
    {'effective_from':'2099-01-01'},
    {'text':'Orchid Gold refunds are faster after initiation.'},
    {'text':'Orchid Gold does not change return windows.'},
])
def test_no_exclusion_is_invented_without_a_current_policy_rule(change):
    p=policy();p.update(change)
    assert not any(c['kind']=='membership_refund_timing_exclusion' for c in derive_source_constraints([p]))


def test_actual_saved_answer_is_detected_without_its_question_or_case_id():
    sources=[dict(policy('ZentroMart Plus'), id='arbitrary-new-id')]
    with pytest.raises(ValueError, match='source_membership_refund_speed'):
        validate_source_semantics('ZentroMart Plus member hai, isliye wallet se instant refund milta hai.',sources)


class ScriptedClient:
    def __init__(self, *answers):
        self.answers=list(answers)
        self.calls=[]

    def complete(self, system, user, **options):
        import json
        self.calls.append((system,json.loads(user),options))
        assert self.answers, 'Unexpected extra model request'
        return json.dumps({'answer':self.answers.pop(0),'covered':True,'needs_clarification':False})


def test_existing_model_repair_uses_original_evidence_and_rechecks_the_causal_rule():
    from src.document_answers import document_reply
    sources=[policy(), dict(id='payment-rule',doc_type='policy',status='current',
                            text='Wallet refunds are instant after initiation.')]
    bad='Your refund arrives instantly because you are an Orchid Gold member.'
    good='Wallet refunds are instant after initiation. Membership does not change arrival timing.'
    client=ScriptedClient(bad,good)
    result=document_reply(client,'How long does a wallet refund take?','en',sources,
                          facts={'source_semantic_constraints':[]},context_provenance=True)
    assert result['answer']==good
    assert result['generation_attempts']==2
    assert client.calls[1][1]['repair_validation_error']=='source_membership_refund_speed'
    assert client.calls[1][1]['repair_source_constraints']==derive_source_constraints(sources)
    assert client.calls[0][1]['source_text']==client.calls[1][1]['source_text']
    assert client.calls[1][2]['cache'] is False


def test_a_second_unsupported_model_reply_is_rejected_not_replaced_by_an_authored_answer():
    from src.document_answers import document_reply
    bad='Your refund arrives instantly because you are an Orchid Gold member.'
    client=ScriptedClient(bad,bad)
    with pytest.raises(ValueError,match='source_membership_refund_speed'):
        document_reply(client,'Does membership accelerate refunds?','en',[policy()],context_provenance=True)
    assert len(client.calls)==2
