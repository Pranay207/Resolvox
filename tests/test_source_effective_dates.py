"""Exact metadata dates do not grant permission for their component digits."""
import pytest
from src.document_answers import _validate_context, _source_effective_date_validation_text


def sources():
    return [{'id':'DEL-test','text':'ZentroMart delivers within India only.',
             'doc_type':'policy','status':'current','effective_from':'2026-04-01'}]


def validate(answer, source_rows=None):
    return _validate_context({'answer':answer,'covered':True,'needs_clarification':False},
                             source_rows or sources(), {}, 'en')


@pytest.mark.parametrize('date',['2026-04-01','1 April 2026','April 1, 2026'])
def test_exact_effective_metadata_date_is_allowed_as_a_whole(date):
    answer='ZentroMart delivers within India only; the policy is effective from '+date+'.'
    assert validate(answer)['answer']==answer


@pytest.mark.parametrize('answer',[
    'ZentroMart delivers within India only; the policy is effective from 2026-04-02.',
    'Delivery takes 4 days.',
    'The fee is 2026 rupees.',
    'The policy is effective from 2026-04-01 and delivery takes 4 days.',
    'The delivery window is 2026-04-01 days.',
    'The fee is INR 2026-04-01.',
])
def test_other_dates_and_numeric_claims_are_not_authorized(answer):
    with pytest.raises(ValueError,match='unsupported_number|unsupported_quantity_unit'):
        validate(answer)


def test_missing_or_invalid_metadata_does_not_authorize_a_date():
    for value in (None,'nonsense','2026-02-31'):
        rows=sources()
        rows[0]['effective_from']=value
        with pytest.raises(ValueError,match='unsupported_number'):
            validate('The policy is effective from 2026-04-01.',rows)


def test_metadata_mask_preserves_performed_action_checks():
    with pytest.raises(ValueError,match='unsupported_action'):
        validate('I have cancelled your order under the policy effective from 2026-04-01.')



@pytest.mark.parametrize('answer',[
    'Your refund arrives on 2026-04-01.',
    'The brand warranty began on 2026-04-01.',
    'Your delivery will arrive on 1 April 2026.',
    'The policy is effective from 2026-04-01; your refund arrives on 2026-04-01.',
    'The policy is effective from 2026-04-01 and your refund arrives on 2026-04-01.',
])
def test_exact_metadata_date_cannot_fill_an_unrelated_date_role(answer):
    with pytest.raises(ValueError,match='unsupported_number'):
        validate(answer)


@pytest.mark.parametrize('answer',[
    'Policy 1 April 2026 se lagu hai.',
    '\u092f\u0939 \u0928\u0940\u0924\u093f 1 \u0905\u092a\u094d\u0930\u0948\u0932 2026 \u0938\u0947 \u0932\u093e\u0917\u0942 \u0939\u0948\u0964',
])
def test_hindi_hinglish_policy_effectivity_role_is_recognized(answer):
    text=_source_effective_date_validation_text(answer,sources())
    assert 'source effective date' in text
