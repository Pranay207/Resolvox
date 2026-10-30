"""Pending refund replies must explain the actual source initiation prerequisite."""
import copy
import pytest
from src.refund_status import pending_refund_requirement, check_pending_refund_answer
from src.inference_facts import project_inference_facts

SOURCE=dict(id='mutable-initiation-policy',doc_type='policy',status='current',effective_from='2020-01-01',
            text='The refund is initiated within 9 business days of pickup once the item passes quality check (QC).')
FACTS={'verified_order':dict(is_plus=False,return_status='picked_up',return_pickup_on='2026-10-20',
                             return_qc_passed_on=None,return_refund_initiated_on=None)}


def test_repetitive_account_filler_cannot_substitute_for_the_source_prerequisite():
    with pytest.raises(ValueError,match='missing_pending_refund_condition'):
        check_pending_refund_answer('Your refund will be in your user account. Your refund will be in your user account.',
                                    'Where is my refund?',FACTS,[SOURCE],'2026-10-20')


@pytest.mark.parametrize('answer',[
    'A quality check is required before refund initiation.',
    'रिफ़ंड शुरू होने से पहले गुणवत्ता जाँच पास होना ज़रूरी है।',
    'Refund QC pass hone ke baad initiate hota hai.',
])
def test_supported_quality_explanation_is_recognized_across_current_languages(answer):
    requirement=check_pending_refund_answer(answer,'मेरा रिफ़ंड कहाँ है?',FACTS,[SOURCE],'2026-10-20')
    assert requirement['source_ids']==['mutable-initiation-policy']


@pytest.mark.parametrize('changes',[
    {'is_plus':True},{'return_qc_passed_on':'2026-10-20'},
    {'return_refund_initiated_on':'2026-10-20'}, {'return_refund_completed_on':'2026-10-20'},
    {'return_pickup_on':None}, {'return_status':'requested'},
])
def test_other_verified_phases_do_not_gain_the_pending_condition(changes):
    facts=copy.deepcopy(FACTS);facts['verified_order'].update(changes)
    assert pending_refund_requirement('Where is my refund?',facts,[SOURCE],'2026-10-20') is None


@pytest.mark.parametrize('changes',[
    {'status':'superseded'}, {'effective_from':'2099-01-01'}, {'doc_type':'marketing'},
    {'text':'Refunds are initiated at pickup without waiting for inspection.'},
])
def test_absent_stale_or_changed_rule_cannot_force_a_quality_check(changes):
    assert pending_refund_requirement('Where is my refund?',FACTS,[dict(SOURCE,**changes)],'2026-10-20') is None


def test_audit_hash_remains_in_host_facts_but_not_in_model_projection():
    requirement=pending_refund_requirement('Where is my refund?',FACTS,[SOURCE],'2026-10-20')
    facts=dict(FACTS,pending_refund_requirement=requirement)
    projected=project_inference_facts(facts)
    assert 'source_sha256' in facts['pending_refund_requirement']
    assert 'source_sha256' not in projected['pending_refund_requirement']
    assert projected['pending_refund_requirement']['source_ids']==requirement['source_ids']
