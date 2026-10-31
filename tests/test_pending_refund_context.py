import copy,json
import pytest
from src.pending_refund_context import pending_status_inputs,check_pending_record_claims
from src.document_answers import document_reply
from test_pending_refund_status import SOURCE,FACTS
from test_refund_payment_timeline import Client

@pytest.mark.parametrize('answer',[
 'The quality check has failed.',
 'The record shows that the quality check has failed.',
 'आपकी गुणवत्ता जांच (QC) पास नहीं हुई है।',
 'Your refund has not started yet.',
 'Use the RRN to trace it with your bank.',
 'आपके बैंक को रिफंड रिफरेंस नंबर (RRN) के साथ जानकारी देने के लिए इसका उपयोग करें।',
])
def test_missing_record_fields_do_not_authorize_failure_or_reference_advice(answer):
 with pytest.raises(ValueError,match='unrecorded_refund_'):
  check_pending_record_claims(answer,'Where is my refund?',FACTS,[SOURCE],'2026-10-20')

@pytest.mark.parametrize('answer',[
 'The record does not show a quality-check pass or refund initiation. After the item passes QC, the source initiation timeline applies.',
 'रिकॉर्ड में गुणवत्ता जांच पास होने और रिफंड शुरू होने की तारीख दर्ज नहीं है। QC पास होने पर नीति की समयसीमा लागू होगी।',
 'A quality check is required before refund initiation.',
])
def test_unknown_records_and_conditional_policy_prerequisites_remain_allowed(answer):
 check_pending_record_claims(answer,'Where is my refund?',FACTS,[SOURCE],'2026-10-20')


def test_simple_status_prompt_omits_inapplicable_reference_policy_and_unrelated_record_fields():
 facts=copy.deepcopy(FACTS);facts['verified_order']['items']=[{'title':'Unrelated item'}]
 extra={'id':'reference-rule','doc_type':'policy','status':'current','text':'Every initiated refund has an RRN the bank can trace.'}
 view=pending_status_inputs('Where is my refund?',facts,[SOURCE,extra],'2026-10-20')
 assert view['sources']==[SOURCE]
 assert 'items' not in view['facts']['verified_order']
 assert 'source_sha256' not in view['facts']['pending_refund_requirement']


def test_compound_coupon_question_keeps_original_context():
 assert pending_status_inputs('Where is my refund and how does my coupon affect the amount?',FACTS,[SOURCE],'2026-10-20') is None


def test_actual_generation_uses_bound_status_view_with_all_original_validators():
 answer='The record does not show a quality-check pass or refund initiation. After the item passes QC, the policy allows initiation within 9 business days of pickup.'
 client=Client(answer)
 result=document_reply(client,'Where is my refund?','en',[SOURCE],facts=FACTS,private=True,context_provenance=True)
 assert result['answer']==answer and result['repair_mode']=='source_pending_refund_status'
 assert client.calls[0][1]['source_text']==[SOURCE]
