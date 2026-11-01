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


@pytest.mark.parametrize('term',['क्वालिटी चेक','क्वालिटी जांच','गुणवत्ता जाँच','QC'])
def test_native_quality_check_terms_preserve_the_source_prerequisite(term):
 from src.refund_status import check_pending_refund_answer
 text=f'रिकॉर्ड में {term} पास होने की तारीख दर्ज नहीं है। यदि {term} पास हो तो स्रोत की रिफंड समयसीमा लागू होगी।'
 check_pending_refund_answer(text,'Where is my refund?',FACTS,[SOURCE],'2026-10-20')
 with pytest.raises(ValueError,match='missing_pending_refund_condition'):
  check_pending_refund_answer('रिफंड समयसीमा लागू होगी।','Where is my refund?',FACTS,[SOURCE],'2026-10-20')


@pytest.mark.parametrize('days',[9,13])
def test_qc_prerequisite_does_not_replace_source_pickup_clock(days):
 from src.refund_status import check_pending_refund_answer
 source=dict(SOURCE,text=SOURCE['text'].replace('9 business days',str(days)+' business days'))
 bad=f'QC पास होने के {days} कार्यदिवस के भीतर रिफंड शुरू होगा।'
 with pytest.raises(ValueError,match='missing_refund_initiation_anchor'):
  check_pending_refund_answer(bad,'Where is my refund?',FACTS,[source],'2026-10-20')
 good=f'QC पास होने पर पिकअप के {days} कार्यदिवस के भीतर रिफंड शुरू होगा।'
 requirement=check_pending_refund_answer(good,'Where is my refund?',FACTS,[source],'2026-10-20')
 assert requirement['initiation_clocks'][0]['business_days']==days


@pytest.mark.parametrize('answer',[
 'Therefore the refund requirements have not been met.',
 'इसलिए रिफंड शुरू होने की शर्तें पूरी नहीं हुई हैं।',
 'Refund ki shartein puri nahi hui hain.',
])
def test_missing_dates_do_not_establish_unfulfilled_refund_prerequisites(answer):
 with pytest.raises(ValueError,match='unrecorded_refund_quality_claim'):
  check_pending_record_claims(answer,'Where is my refund?',FACTS,[SOURCE],'2026-10-20')
 view=pending_status_inputs('Where is my refund?',FACTS,[SOURCE],'2026-10-20')
 assert view['facts']['record_evidence']['prerequisite_satisfaction']=='unknown'



def test_unknown_return_reason_is_not_an_asserted_change_of_mind():
 from src.pending_refund_context import check_unverified_return_reason
 facts={'return_pickup_policy':{'personal_charge_confirmed':False},'verified_order':{'return_reason':None}}
 with pytest.raises(ValueError,match='unverified_return_reason'):
  check_unverified_return_reason('यह मन बदलने के कारण का रिटर्न है।','Can I return this?',facts)
 check_unverified_return_reason('यदि यह मन बदलने के कारण का रिटर्न है तो शुल्क लागू है।','Can I return this?',facts)
 check_unverified_return_reason('यह मन बदलने के कारण का रिटर्न है।','मेरा मन बदल गया।',facts)
