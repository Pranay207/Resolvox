"""Tmp-only mutation tests for the finite semantic guard prototype."""
import pytest

from src.source_semantics import (
    derive_source_constraints, validate_source_semantics)


def source(text, key='changed-source'):
    return {'id': key, 'text': text, 'doc_type': 'policy', 'status': 'current'}


PERMISSION = source('A shipped order cannot be cancelled. The customer can:\n'
                    '- refuse the parcel at the door; or\n'
                    '- accept delivery and return an eligible item.')


@pytest.mark.parametrize('answer', [
    'You cannot refuse the parcel at the door.',
    'You may not decline the parcel.',
    'दरवाजे पर पैकेट को रिफस नहीं कर सकते हैं।',
    'Aap parcel ko refuse nahi kar sakte hain.',
])
def test_explicit_source_permission_cannot_be_reversed(answer):
    with pytest.raises(ValueError, match='source_permission_reversed'):
        validate_source_semantics(answer, [PERMISSION])


@pytest.mark.parametrize('answer', [
    'You cannot cancel the shipped order, but you can refuse the parcel at the door.',
    'Aap shipped order cancel nahi kar sakte hain, lekin parcel refuse kar sakte hain.',
    'ऑर्डर कैंसिल नहीं कर सकते हैं, लेकिन दरवाजे पर पैकेट को रिफस कर सकते हैं।',
])
def test_negative_cancellation_clause_does_not_reverse_an_affirmative_alternative(answer):
    validate_source_semantics(answer, [PERMISSION])


def test_mutated_source_permission_changes_the_constraint_without_a_source_id_rule():
    changed = source(PERMISSION['text'].replace('The customer can:\n- refuse',
                                              'The customer cannot refuse'),
                     key='a-different-policy')
    constraints = derive_source_constraints([changed])
    assert not any(item['kind'] == 'explicit_permission' for item in constraints)
    validate_source_semantics('You cannot refuse the parcel.', [changed])


def test_constraints_are_bound_to_actual_source_identity_and_hash():
    a = derive_source_constraints([PERMISSION])[0]
    changed = source(PERMISSION['text'] + '\nKeep the parcel sealed.', 'other-source')
    b = derive_source_constraints([changed])[0]
    assert a['source_ids'] == [PERMISSION['id']]
    assert b['source_ids'] == ['other-source']
    assert list(b['source_sha256']) == ['other-source']
    assert a['source_sha256'][PERMISSION['id']] != b['source_sha256']['other-source']


BRAND = source("The manufacturer's warranty period is listed in the catalog. "
               "Brand warranty claims go to the manufacturer's service centre.",
               'brand-info')
ASSURED = source('Marked items carry an additional store warranty from the delivery date, '
                 'in addition to any brand warranty.', 'store-info')
EXCLUSIONS = source('Physical damage and normal wear are not covered.', 'exclusions')


@pytest.mark.parametrize('answer', [
    'Both warranties are valid from the delivery date.',
    "The manufacturer's warranty starts from delivery.",
    'ब्रांड वारंटी डिलीवरी से शुरू होती है।',
    'Dono warranties delivery se valid hain.',
])
def test_store_start_date_does_not_prove_the_brand_start_date(answer):
    with pytest.raises(ValueError, match='unsupported_brand_warranty_start'):
        validate_source_semantics(answer, [BRAND, ASSURED, EXCLUSIONS])


@pytest.mark.parametrize('scope', ['battery defects', 'motor defects', 'manufacturing defects'])
def test_positive_brand_coverage_must_come_from_a_positive_source_claim(scope):
    answer = 'The brand warranty covers ' + scope + '.'
    with pytest.raises(ValueError, match='unsupported_brand_warranty_coverage'):
        validate_source_semantics(answer, [BRAND, ASSURED, EXCLUSIONS])
    updated = source('The brand warranty covers ' + scope + '.', 'new-coverage')
    validate_source_semantics(answer, [BRAND, ASSURED, EXCLUSIONS, updated])


def test_changed_positive_scope_does_not_support_a_different_scope():
    documented = source('The brand warranty covers motor defects.', 'positive-scope')
    with pytest.raises(ValueError, match='unsupported_brand_warranty_coverage'):
        validate_source_semantics('The brand warranty covers battery defects.', [BRAND, documented])


@pytest.mark.parametrize('event', ['purchase', 'invoice', 'activation', 'delivery'])
def test_documented_brand_start_event_is_dynamic(event):
    changed = source('The brand warranty begins from the ' + event + ' date.', 'brand-start')
    validate_source_semantics('Both warranties are valid from ' + event + '.', [BRAND, changed])


def test_a_documented_start_event_does_not_authorize_a_different_event():
    changed = source('The brand warranty begins from the invoice date.', 'brand-start')
    with pytest.raises(ValueError, match='unsupported_brand_warranty_start'):
        validate_source_semantics('The brand warranty is valid from delivery.', [BRAND, changed])


def test_negative_exclusions_and_store_scoped_start_are_not_invented_brand_terms():
    validate_source_semantics(
        'The store warranty starts from delivery. Both warranties do not cover physical damage.',
        [BRAND, ASSURED, EXCLUSIONS])


def credit_source(label='Orchid Club', amount=137):
    return source(
        'If an Express order is late, the ' + str(amount) +
        ' express fee the customer paid is credited to the wallet. ' +
        label + ' members, who pay no express fee, get no credit. '
        'There is no compensation for late Standard deliveries.', 'conditional-credit')


@pytest.mark.parametrize('label,amount', [('Orchid Club', 137), ('Aster Elite', 263)])
def test_amount_and_membership_values_are_read_from_changed_source(label, amount):
    evidence = credit_source(label, amount)
    constraints = derive_source_constraints([evidence])
    assert constraints[0]['excluded_membership'] == label
    answer = ('The ' + str(amount) + ' Express fee you paid is credited if delivery is late. '
              + label + ' members pay no fee and get no credit.')
    validate_source_semantics(answer, [evidence])


def test_unconditional_credit_without_paid_fee_condition_is_rejected():
    with pytest.raises(ValueError, match='source_credit_paid_fee_condition_missing'):
        validate_source_semantics('Yes, you get a credit to your wallet.', [credit_source()])


def test_fee_paid_description_still_preserves_the_source_membership_exclusion():
    with pytest.raises(ValueError, match='source_credit_membership_exclusion_missing'):
        validate_source_semantics('The Express fee you paid is credited to your wallet.',
                                  [credit_source()])


def test_changing_membership_does_not_accept_the_old_group_as_the_exclusion():
    answer = ('The Express fee you paid is credited. Orchid Club members get no credit.')
    with pytest.raises(ValueError, match='source_credit_membership_exclusion_missing'):
        validate_source_semantics(answer, [credit_source('Aster Elite')])


def test_no_credit_explanation_or_unrelated_reply_does_not_trigger_benefit_conditions():
    validate_source_semantics('No credit applies to late Standard deliveries.', [credit_source()])
    validate_source_semantics('Charge the device using its original cable.', [credit_source()])


def test_source_without_this_conditional_benefit_does_not_create_the_obligation():
    unrelated = source('Late orders are monitored by the logistics team.')
    assert not derive_source_constraints([unrelated])
    validate_source_semantics('Your order can be tracked in the app.', [unrelated])


def test_negation_of_cancellation_does_not_scope_over_an_affirmative_refusal():
    validate_source_semantics('You cannot cancel and you can refuse the parcel.', [PERMISSION])


def test_unrelated_refusal_is_not_a_delivery_permission_reversal():
    validate_source_semantics('You cannot refuse the refund method.', [PERMISSION])


def test_source_hash_is_of_actual_text_including_markdown():
    import hashlib
    changed = source('The customer can **refuse the parcel** at the door.', 'markdown-source')
    item = derive_source_constraints([changed])[0]
    assert item['source_sha256']['markdown-source'] == hashlib.sha256(changed['text'].encode('utf-8')).hexdigest()


@pytest.mark.parametrize('joiner', [', ', ' '])
def test_later_brand_reference_never_inherits_earlier_store_start_or_scope(joiner):
    store = source(
        'Marked items carry a store warranty from delivery that covers battery defects'
        + joiner + 'in addition to any brand warranty.', 'store-scope')
    with pytest.raises(ValueError, match='unsupported_brand_warranty_start'):
        validate_source_semantics('The brand warranty starts from delivery.', [BRAND, store])
    with pytest.raises(ValueError, match='unsupported_brand_warranty_coverage'):
        validate_source_semantics('The brand warranty covers battery defects.', [BRAND, store])


@pytest.mark.parametrize('answer', [
    'The brand warranty covers material defects.',
    'The brand warranty covers workmanship faults.',
    'Material defects are covered by the brand warranty.',
])
def test_safe_scope_subsets_reordering_and_fault_paraphrase_are_supported(answer):
    updated = source('The brand warranty covers defects in materials and workmanship.',
                     'positive-scope')
    validate_source_semantics(answer, [BRAND, updated])


def test_a_generic_defects_claim_does_not_broaden_a_component_limited_scope():
    updated = source('The brand warranty covers battery defects.', 'positive-scope')
    with pytest.raises(ValueError, match='unsupported_brand_warranty_coverage'):
        validate_source_semantics('The brand warranty covers defects.', [BRAND, updated])


@pytest.mark.parametrize('paid_sentence', [
    'Any Express charges paid are credited if the order is late.',
    'The Express fee charged is credited if the order is late.',
    'The Express delivery charges collected are credited if the order is late.',
    'आपने एक्सप्रेस फ़ीस चुकाई है तो वॉलेट में क्रेडिट मिलेगा।',
    'आपसे लिया गया एक्सप्रेस शुल्क वॉलेट में क्रेडिट होता है।',
    'Express fee aapne pay kiya hai to wallet credit milta hai.',
])
def test_ordinary_paid_fee_paraphrases_preserve_the_eligibility_condition(paid_sentence):
    validate_source_semantics(
        paid_sentence + ' Orchid Club members get no credit.', [credit_source()])


def test_no_fee_charged_exclusion_is_not_itself_proof_that_a_fee_was_paid():
    with pytest.raises(ValueError, match='source_credit_paid_fee_condition_missing'):
        validate_source_semantics(
            'You get a wallet credit. Orchid Club members have no fee charged and get no credit.',
            [credit_source()])
