"""Finite changed-source remedy-condition tests, with no inference."""
import copy,importlib.util
from pathlib import Path
import pytest

from src import remedy_prerequisites as helper
SOURCE={'id':'Fictional-Remedy','doc_type':'policy','status':'current',
 'text':'After verification the customer gets a free replacement or a full refund, including delivery fees. No reverse pickup fee applies.'}


def check(answer,*,source=None,facts=None,query='The jacket arrived torn; is collection free?'):
 return helper.check_remedy_prerequisites(answer,query,[SOURCE if source is None else source],facts=facts,reference_date='2031-05-12')


@pytest.mark.parametrize('answer',[
 'You will get a free replacement or full refund.',
 'The customer receives a free replacement or full refund including delivery fees.',
 'If the jacket arrived torn, you get a full refund.',
 'If it was reported in time, the customer gets a replacement.',
 'आपको मुफ्त रिप्लेसमेंट या पूरा रिफंड मिलेगा।',
 'ग्राहक को पूरा रिफंड मिलता है।',
 'Aapko free replacement ya full refund milega.',
 'Customer ko full refund milta hai.',
])
def test_definite_remedy_needs_its_own_source_prerequisite(answer):
 with pytest.raises(ValueError,match='missing_remedy_prerequisite:verification'):check(answer)


@pytest.mark.parametrize('answer',[
 'Collection is free; no reverse pickup fee applies.',
 'The policy lists replacement and refund options.',
 'You may receive a refund or replacement.',
 'Could the customer receive a replacement?',
 'You are not eligible for a refund.',
 'After verification, you get a replacement or full refund.',
 'Once verification is completed, the customer receives a full refund.',
 'You get a replacement after verification.',
 'सत्यापन के बाद आपको पूरा रिफंड मिलेगा।',
 'Verification ke baad aapko full refund milega.',
])
def test_fee_only_generic_tentative_negative_and_proper_conditional_pass(answer):check(answer)


@pytest.mark.parametrize('facts',[
 {'verified_order':{'status':'Delivered'}},
 {'verified_order':{'damage_status':'Verified','damage_photos_attached':True}},
 {'public_context':{'verified':True}},
 {'claim_verified':True},
])
def test_authentication_photos_or_unmapped_status_do_not_prove_unspecified_verification(facts):
 with pytest.raises(ValueError):check('You receive a full refund.',facts=facts)


def test_explicit_identity_condition_only_accepts_actual_authenticated_identity_boundary():
 source=dict(SOURCE,text='After identity verification the customer gets a replacement.')
 check('You receive a replacement.',source=source,facts={'verified_order':{'status':'Delivered'}})
 with pytest.raises(ValueError):check('You receive a replacement.',source=source,facts={'public_context':{'verified':True}})


@pytest.mark.parametrize('condition',['claim verification','inspection','approval'])
def test_other_condition_roles_do_not_accept_identity_proof(condition):
 source=dict(SOURCE,text='After '+condition+' the customer gets a replacement.')
 with pytest.raises(ValueError):check('You receive a replacement.',source=source,facts={'verified_order':{'status':'Delivered'}})


@pytest.mark.parametrize('condition',['inspection','approval','claim verification'])
def test_source_condition_mutation_changes_required_qualification(condition):
 source=dict(SOURCE,text='After '+condition+' the customer gets a replacement.')
 check('After '+condition+', you receive a replacement.',source=source)
 with pytest.raises(ValueError):check('After identity verification, you receive a replacement.',source=source)


def test_condition_removed_from_actual_source_is_not_imposed():
 check('The customer receives a replacement.',source=dict(SOURCE,text='The customer gets a replacement.'))


def test_unrelated_policy_condition_does_not_leak_to_a_different_refund_path():
 source=dict(SOURCE,file='pol_damaged_wrong_missing.md')
 check('You receive a full refund.',source=source,query='Explain a prepaid cancellation refund.')
 with pytest.raises(ValueError):check('You receive a full refund.',source=source,query='The parcel arrived torn.')


def test_an_earlier_qualified_remedy_does_not_rescue_a_later_independent_entitlement():
 with pytest.raises(ValueError):check('After verification you get a replacement, but you get a full refund automatically.')


def test_unrelated_action_after_verification_does_not_rescue_remedy_entitlement():
 with pytest.raises(ValueError):check('After verification contact support, and you get a full refund.')


def test_wrong_role_cannot_be_silently_substituted():
 with pytest.raises(ValueError):check('After identity verification you get a full refund.')


@pytest.mark.parametrize('change',[{'status':'superseded'},{'doc_type':'marketing'},{'doc_type':''},{'effective_from':'2040-01-01'}])
def test_unbound_authority_or_future_condition_is_not_applied(change):
 check('You receive a full refund.',source=dict(SOURCE,**change))


def test_actual_source_hashes_mutate_and_inputs_are_not_changed():
 before=copy.deepcopy(SOURCE)
 first=helper.derive_remedy_prerequisites([SOURCE])
 second=helper.derive_remedy_prerequisites([dict(SOURCE,text=SOURCE['text'].replace('verification','inspection'))])
 assert first[0]['source_ids']==[SOURCE['id']]
 assert first[0]['source_sha256']!=second[0]['source_sha256']
 assert SOURCE==before


@pytest.mark.parametrize('answer',[
 'I cannot confirm whether you receive a refund.',
 "You won't receive a refund.",
 'Aapko refund mil sakta hai.',
])
def test_genuine_uncertainty_negative_and_hypothetical_is_preserved(answer):check(answer)


def test_an_earlier_uncertainty_does_not_rescue_a_definite_remedy():
 with pytest.raises(ValueError):check('I cannot confirm it, but you receive a full refund.')
