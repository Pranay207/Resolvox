"""Action classification tests, not a proof of complete policy conditions."""
import pytest
from src.grounding import _completed_action


@pytest.mark.parametrize('answer', [
    'If a delivery attempt fails, a refund is initiated under the policy.',
    'When delivery attempts fail, the parcel returns and a refund is initiated.',
])
def test_indefinite_present_conditional_is_not_a_performed_action(answer):
    assert not _completed_action(answer)


@pytest.mark.parametrize('answer', [
    'I have initiated your refund.',
    'If delivery fails, I have initiated your refund.',
    'If delivery fails, your refund has been initiated.',
    'If delivery fails, a refund was initiated.',
    'If delivery fails, a refund is initiated already.',
    'If delivery fails, a refund is initiated now.',
    'If delivery fails, a refund is initiated today.',
    'If delivery fails, a refund is initiated and a ticket is created.',
    'A refund is initiated.',
    'Your refund is initiated.',
    'If delivery fails, a refund is initiated on 20 October 2026.',
])
def test_customer_or_completed_actions_still_rejected(answer):
    assert _completed_action(answer)



def test_generic_conditional_wallet_timing_is_not_performed_operation():
    assert not _completed_action('If you choose the wallet, the refund is processed within 2 hours.')
    assert not _completed_action('If you choose the wallet, the refund is processed within two hours.')


@pytest.mark.parametrize('answer',[
    'If you choose the wallet, your refund is processed within 2 hours.',
    'If you choose the wallet, the refund has been processed within 2 hours.',
    'If you choose the wallet, the refund was processed within 2 hours.',
    'If you chose the wallet yesterday, the refund is processed within 2 hours.',
    'If you have already chosen the wallet, the refund is processed within 2 hours.',
    'If you choose the wallet, the refund is processed already within 2 hours.',
    'If you choose the wallet, the refund is processed.',
])
def test_performed_or_unscoped_timing_claims_still_rejected(answer):
    assert _completed_action(answer)
