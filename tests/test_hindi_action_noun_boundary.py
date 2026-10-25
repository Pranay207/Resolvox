"""Exclude an eligibility adjective, retaining actual operation nouns."""
import pytest
from src.grounding import _completed_action


def test_policy_applies_to_nonreturnable_items_is_not_a_completed_return():
    answer='\u0907\u0938 \u0928\u093f\u092f\u092e \u0915\u094b \u0905\u0928\u094d\u092f \u0928\u0949\u0928-\u0930\u093f\u091f\u0930\u094d\u0928\u0947\u092c\u0932 \u0935\u0938\u094d\u0924\u0941\u0913\u0902 \u0915\u0947 \u0932\u093f\u090f \u092d\u0940 \u0932\u093e\u0917\u0942 \u0915\u093f\u092f\u093e \u0917\u092f\u093e \u0939\u0948\u0964'
    assert not _completed_action(answer)


@pytest.mark.parametrize('answer',[
    '\u0906\u092a\u0915\u093e \u0930\u093f\u091f\u0930\u094d\u0928 \u0915\u093f\u092f\u093e \u0917\u092f\u093e \u0939\u0948\u0964',
    '\u0906\u092a\u0915\u093e \u0930\u093f\u092b\u0902\u0921 \u0915\u0930 \u0926\u093f\u092f\u093e \u0939\u0948\u0964',
    '\u0906\u092a\u0915\u093e \u0911\u0930\u094d\u0921\u0930 \u0930\u0926\u094d\u0926 \u0915\u093f\u092f\u093e \u0917\u092f\u093e \u0939\u0948\u0964',
])
def test_hindi_real_completed_action_claims_still_rejected(answer):
    assert _completed_action(answer)
