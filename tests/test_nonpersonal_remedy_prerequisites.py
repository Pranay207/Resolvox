"""An item/report entitlement retains the same source-bound prerequisite."""
import pytest
from src.remedy_prerequisites import check_remedy_prerequisites

SOURCE = {'id': 'violet-resolution', 'text': 'After verification the customer gets a replacement or full refund. No reverse pickup fee applies.', 'doc_type': 'policy', 'status': 'current', 'file': 'damage_policy.md'}

def check(answer, source=SOURCE, query='The parcel arrived broken; is collection free?'):
    return check_remedy_prerequisites(answer, query, [source], reference_date='2031-05-12')

@pytest.mark.parametrize('subject', ['it', 'the item', 'your product', 'the order', 'the claim', 'the report', 'this request', 'the case'])
def test_nonpersonal_entitlement_cannot_drop_verification(subject):
    with pytest.raises(ValueError, match='missing_remedy_prerequisite:verification'):
        check(f'{subject} qualifies for a free replacement or full refund.')

@pytest.mark.parametrize('subject', ['it', 'the item', 'your product', 'the order', 'the claim', 'the report', 'this request', 'the case'])
def test_qualification_stays_attached_to_nonpersonal_entitlement(subject):
    check(f'After verification, {subject} qualifies for a replacement or refund.')

@pytest.mark.parametrize('answer', [
    'The report must be made within the reporting window and qualifies for a free replacement or full refund.',
    'The item is eligible for a refund because it arrived broken.',
    'Your claim qualifies for a refund after identity verification.',
])
def test_customer_assertions_reporting_window_and_identity_are_not_claim_verification(answer):
    with pytest.raises(ValueError, match='missing_remedy_prerequisite:verification'):
        check(answer)

@pytest.mark.parametrize('answer', [
    'Collection of the item is free; no reverse pickup fee applies.',
    'The report can be submitted in the app.',
    'The policy lists refund and replacement options.',
    'The claim might qualify for a refund.',
    'The item is not eligible for a refund.',
    'Does the report qualify for a refund?',
    'You receive a refund after verification.',
])
def test_fee_only_neutral_tentative_negative_questions_and_qualified_replies_stay_valid(answer):
    check(answer)

@pytest.mark.parametrize('condition', ['inspection', 'approval', 'claim verification'])
def test_mutated_source_condition_governs_nonpersonal_entitlement(condition):
    source = {**SOURCE, 'text': f'After {condition} the customer gets a refund.'}
    check(f'After {condition}, the item qualifies for a refund.', source)
    with pytest.raises(ValueError):
        check('The item qualifies for a refund after identity verification.', source)


def test_unrelated_remedy_path_is_not_bound_to_damage_prerequisite():
    check('The order qualifies for a refund.', query='Explain a prepaid cancellation refund.')


def test_source_without_condition_does_not_impose_one():
    check('The item qualifies for a refund.', source={**SOURCE, 'text': 'The customer gets a refund.'})
