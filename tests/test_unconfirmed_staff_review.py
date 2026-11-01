"""Queued handover does not establish active staff review; no network/model calls."""
import pytest
from src.pending_refund_context import check_unconfirmed_staff_review

FACTS={'operational_escalation':{'reason':'refund_overdue'}}

@pytest.mark.parametrize('text',[
 'Your case is being reviewed by our team.',
 'Your refund is currently under review.',
 'Our support team is actively reviewing your case.',
 'Aapka refund review kiya ja raha hai.',
 'Aapka case review ho raha hai.',
 'आपके मामले की समीक्षा की जा रही है।',
 'आपका मामला समीक्षाधीन है।',
 'We cannot confirm receipt, but your case is being reviewed.',
 'If needed, we can escalate; your case is under review.',
 'We cannot confirm receipt and your case is under review.',
 'Your case is under review and I cannot confirm receipt.',
])
def test_queued_handover_cannot_claim_active_staff_review(text):
 with pytest.raises(ValueError,match='unconfirmed_active_staff_review'):
  check_unconfirmed_staff_review(text,FACTS)

@pytest.mark.parametrize('text',[
 'Your case needs review.',
 'Your case will be reviewed after handover.',
 'A ticket has been created for review.',
 'I cannot confirm that your case is being reviewed.',
 'It is unknown whether your case is under review.',
 'If your case is under review, please wait for the response.',
 'Mujhe nahi pata ki aapka case review ho raha hai.',
 'Aapka case review ho raha hai ya nahi, pata nahi.',
 'Aapka case review ho raha nahi hai.',
 'Agar case review ho raha hai, response ka wait karein.',
 'मुझे पता नहीं कि आपके मामले की समीक्षा की जा रही है।',
 'यदि मामले की समीक्षा की जा रही है, उत्तर की प्रतीक्षा करें।',
])
def test_future_needed_conditional_or_uncertain_review_is_not_active_claim(text):
 check_unconfirmed_staff_review(text,FACTS)

def test_non_escalation_reply_is_outside_guard_scope():
 check_unconfirmed_staff_review('The product is under review.',{})
