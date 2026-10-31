import pytest
from test_refund_payment_timeline import context
from src.document_answers import _validate_context

@pytest.mark.parametrize('suffix',['',' For a partial refund, the refund is the price paid after its share of any coupon discount.'])
def test_source_clock_conditional_pronoun_is_not_a_performed_action(suffix):
 facts,sources=context()
 sources.append({'id':'coupon-rule','doc_type':'policy','status':'current','effective_from':'2020-01-01','text':'For a partial refund, the refund is the price paid after its share of any coupon discount.'})
 answer='Your refund will arrive in 23 to 37 business days after it is initiated.'+suffix
 result=_validate_context({'answer':answer,'covered':True,'needs_clarification':False},sources,facts,'en',private=True,query='When will my refund arrive?')
 assert result['answer']==answer

@pytest.mark.parametrize('extra',[' I have initiated your refund.',' Your refund has been initiated.',' We processed your refund.'])
def test_neighboring_actual_action_claim_is_still_rejected(extra):
 facts,sources=context();answer='Your refund will arrive in 23 to 37 business days after it is initiated.'+extra
 with pytest.raises(ValueError,match='unsupported_action|unverified_record'):
  _validate_context({'answer':answer,'covered':True,'needs_clarification':False},sources,facts,'en',private=True,query='When will my refund arrive?')

def test_inactive_policy_does_not_license_pronoun_masking():
 from src.document_answers import _source_generic_initiation_validation_text
 _,sources=context();sources[0]['status']='archived';answer='Your refund arrives after it is initiated.'
 assert _source_generic_initiation_validation_text(answer,sources)==answer
