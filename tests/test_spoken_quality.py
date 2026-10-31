import pytest
from src.spoken_quality import check_spoken_quality
from src.refund_timeline import check_refund_timeline_answer
from test_refund_payment_timeline import context

@pytest.mark.parametrize('field',['return_deadline','standard_fee_inr','minimum_business_days','maximum_business_days','refund_arrival_policy','timing_anchor'])
def test_internal_host_labels_do_not_enter_spoken_answer(field):
 with pytest.raises(ValueError,match='internal_metadata_in_answer'):check_spoken_quality('The calculated '+field+' is shown here.')

@pytest.mark.parametrize('sentence',['The refund goes back to the original payment method.','रिफंड शुरू होने के बाद भुगतान विधि की समयसीमा लागू होती है।'])
def test_duplicate_complete_sentence_is_rejected_without_rewriting(sentence):
 with pytest.raises(ValueError,match='repeated_answer_sentence'):check_spoken_quality(sentence+' '+sentence)

def test_distinct_conditions_with_shared_words_are_preserved():
 check_spoken_quality('The refund is not recorded as initiated. After initiation, the refund follows the original payment method timeline.')

@pytest.mark.parametrize('answer',[
 'The return announcement gives UPI refunds in 23 to 37 business days after the request.',
 'वापसी की घोषणा के बाद UPI पर 23 से 37 कार्यदिवस लगते हैं।',
 'UPI refunds take 23 to 37 business days before initiation.',
])
def test_arrival_clock_cannot_be_anchored_to_a_return_announcement_or_before_initiation(answer):
 facts,sources=context()
 with pytest.raises(ValueError,match='missing_refund_initiation_anchor'):
  check_refund_timeline_answer(answer,'When will my refund arrive?',facts,sources,'2026-10-20')
