"""Personal monetary-role grounding tests; no inference or organizer scoring."""
import copy,hashlib,json
import pytest
from src.personal_money import derive_personal_money_bindings,validate_personal_money


def source(value='37'):
 return {'id':'FEES-X','text':'A cash-on-delivery fee of INR '+value+' applies. Refunds take the documented method timeline.','doc_type':'policy','status':'current','effective_from':'2020-01-01'}

@pytest.mark.parametrize('answer',[
 'Your refund is INR 37.',
 'INR 37 ka credit card wala refund shuru hua tha.',
 'Your card refund of 37 rupees should arrive by the recorded deadline.',
 'You paid INR 37 for your order.',
 'Aapka 37 rupaye ka refund process mein hai.',
 '\u0906\u092a\u0915\u093e \u0930\u093f\u092b\u0902\u0921 37 \u0930\u0941\u092a\u092f\u0947 \u0915\u093e \u0939\u0948\u0964',
])
def test_source_fee_cannot_become_an_unknown_personal_amount(answer):
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money(answer,'My card refund started on the stated date.',{},[source()])

@pytest.mark.parametrize('answer',[
 'The COD fee is INR 37.',
 'A cash-on-delivery fee of INR 37 is refunded under the stated conditions.',
 'Your refund timeline follows the source. The COD fee is INR 37.',
 'If your refund were INR 37, its method timeline would still apply.',
 'For a INR 37 refund, the documented method timeline applies.',
 'For example, your refund of INR 37 follows the method timeline.',
 'Suppose your refund were INR 37; the timeline is independent of that amount.',
 'Agar aapka refund INR 37 ho, timeline method par depend karegi.',
 'Refunds between INR 37 and INR 90 follow their payment-method rules.',
 'Customers pay INR 37 as the specified fee.',
 'Your refund is not INR 37.',
])
def test_generic_fees_ranges_and_scoped_hypothetical_examples_remain_allowed(answer):
 validate_personal_money(answer,'What is the documented refund timeline?',{},[source()])

@pytest.mark.parametrize('amount',['731','1449.50','12000'])
@pytest.mark.parametrize('style',['INR {value}','Rs. {value}','{value} rupees','\u20b9{value}'])
def test_explicit_customer_refund_amount_is_bound_without_policy_constant(amount,style):
 money=style.format(value=amount)
 query='My card refund of '+money+' started on the stated date. When should it arrive?'
 out=validate_personal_money('Your card refund is '+money+'.',query,{},[source()])
 assert out['amount_bindings'][0]['role']=='refund_amount'
 assert out['amount_bindings'][0]['origin']=='customer_provided_unverified'


def test_customer_paid_amount_does_not_automatically_authorize_a_refund_amount():
 query='I paid INR 731 for the order. When will my refund arrive?'
 validate_personal_money('You paid INR 731 for the order.',query,{},[source()])
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money('Your refund is INR 731.',query,{},[source()])


def test_customer_fee_premise_does_not_authorize_the_card_refund_amount():
 query='The COD fee is INR 37. My card refund started yesterday.'
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money('Your card refund is INR 37.',query,{},[source()])


def test_an_amount_question_is_not_a_confirmed_amount_premise():
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money('Your refund is INR 731.','Will my refund be INR 731?',{},[source()])

@pytest.mark.parametrize('field',['return_refund_amount_inr','cancellation_refund_amount_inr','rto_refund_amount_inr'])
def test_actual_safe_verified_refund_field_authorizes_its_changed_value(field):
 facts={'verified_order':{field:'731','order_id':'must-not-be-copied','phone':'must-not-be-copied'}}
 out=validate_personal_money('Your refund is INR 731.','What is the recorded refund amount?',facts,[source()],private=True)
 assert out['amount_bindings']==[{'amount':'731','currency':'INR','role':'refund_amount','event':field.split('_refund_',1)[0],'origin':'verified_record','path':'verified_order.'+field}]
 assert 'must-not-be-copied' not in str(out)


def test_unverified_record_dictionary_does_not_authorize_personal_amount():
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money('Your refund is INR 731.','My refund is pending.',{'verified_order':{'return_refund_amount_inr':'731'}},[source()],private=False)


def test_verified_field_outranks_inconsistent_customer_amount():
 facts={'verified_order':{'return_refund_amount_inr':'731'}}
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money('Your return refund is INR 37.','My return refund is INR 37.',facts,[source()],private=True)
 validate_personal_money('Your return refund is INR 731.','My return refund is INR 37.',facts,[source()],private=True)


def test_order_total_cannot_become_refund_or_prove_payment_completion():
 facts={'verified_order':{'total_inr':'731'}}
 for answer in ('Your refund is INR 731.','You paid INR 731.'):
  with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
   validate_personal_money(answer,'What is the amount?',facts,[source()],private=True)


def test_ambiguous_refund_events_do_not_choose_an_amount_without_subject():
 facts={'verified_order':{'return_refund_amount_inr':'731','cancellation_refund_amount_inr':'844'}}
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money('Your refund is INR 731.','What is my refund amount?',facts,[source()],private=True)
 validate_personal_money('Your return refund is INR 731.','What is my return refund amount?',facts,[source()],private=True)
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money('Your cancellation refund is INR 731.','What is my cancellation refund amount?',facts,[source()],private=True)


def test_arbitrary_calculation_number_cannot_turn_source_fee_into_personal_money():
 doc=source();facts={'calculation_source_sha256':{'FEES-X':hashlib.sha256(doc['text'].encode()).hexdigest()},'calculations':[{'source_ids':['FEES-X'],'inputs':{'refund_amount_inr':'37'}}]}
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money('Your refund is INR 37.','My refund has not arrived.',facts,[doc])


def test_source_backed_calculation_input_keeps_independent_safe_amount_origin():
 doc=source();facts={'verified_order':{'return_refund_amount_inr':'731'},'calculation_source_sha256':{'FEES-X':hashlib.sha256(doc['text'].encode()).hexdigest()},'calculations':[{'source_ids':['FEES-X'],'inputs':{'refund_amount_inr':'731'}}]}
 out=validate_personal_money('Your refund is INR 731.','What is my refund amount?',facts,[doc],private=True)
 assert out['calculation_inputs'][0]['amount']=='731' and out['calculation_inputs'][0]['source_ids']==['FEES-X']


def test_conditional_date_does_not_create_a_hypothetical_amount_premise():
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money('If your refund started on the stated date its amount is INR 37.','When should my refund arrive?',{},[source()])


def test_actual_fresh_card_refund_amount_invention_rejects_without_altering_dates():
 from src.kb import KnowledgeBase
 docs=[c.public() for c in KnowledgeBase().require('REF-2','REF-5','KB-00.3')]
 query='credit card wala refund 17 October 2026 ko shuru hua, kab tak aa jaana chahiye?'
 facts={'customer_provided_refund_claim':{'initiated_on':'2026-10-17','payment_method':'card','verified':False}}
 answer='\u20b925 ka credit card wala refund 17 October 2026 ko shuru hua, 24 October 2026 se 27 October 2026 tak aa sakta hai.'
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money(answer,query,facts,docs)
 validate_personal_money('Card refund 17 October 2026 ko shuru hua; 24 October 2026 se 27 October 2026 tak aa sakta hai.',query,facts,docs)

class Client:
 def __init__(self,values):self.values=iter(values);self.calls=[];self.last_metrics={}
 def complete(self,system,user,**options):self.calls.append(json.loads(user));return json.dumps(next(self.values))

def response(text):return {'answer':text,'covered':True,'needs_clarification':False}


def test_one_repair_omits_unbound_amount_and_receives_no_primary_extra_facts():
 from src.document_answers import document_reply
 c=Client([response('Your refund is INR 37.'),response('The supplied sources do not establish the amount of your refund.')])
 # A source-backed fee supplies the same bare numeric value, exposing exactly
 # the role-transfer error that plain numeric validation alone would miss.
 result=document_reply(c,'What is my card refund amount?','en',[source()],facts={},context_provenance=True)
 assert result['repair_errors']==['unsupported_personal_money_amount'] and len(c.calls)==2
 assert 'repair_personal_money_bindings' not in c.calls[0]
 assert c.calls[1]['repair_personal_money_bindings']['amount_bindings']==[]
 assert c.calls[0]['source_text']==c.calls[1]['source_text']


def test_second_unbound_amount_is_rejected_after_one_repair():
 from src.document_answers import document_reply
 c=Client([response('Your refund is INR 37.'),response('Your refund is INR 37.')])
 with pytest.raises(ValueError,match='document_generation_failed:unsupported_personal_money_amount'):
  document_reply(c,'What is my card refund amount?','en',[source()],facts={},context_provenance=True)
 assert len(c.calls)==2


@pytest.mark.parametrize('query',[
 'Can you tell me when my refund of INR 731 arrives?',
 'When will my INR 731 refund arrive?',
 'My INR 731 refund is pending; can you check the timeline?',
])
def test_request_question_preserves_an_asserted_amount_premise(query):
 validate_personal_money('Your refund of INR 731 follows the method timeline.',query,{},[source()])


@pytest.mark.parametrize('query',['Is my refund INR 731?','Will my refund be INR 731?','Can you tell me if my refund is INR 731?','Did I pay INR 731?'])
def test_amount_question_does_not_answer_itself(query):
 role='paid' if query.startswith('Did') else 'refund'
 answer='You paid INR 731.' if role=='paid' else 'Your refund is INR 731.'
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money(answer,query,{},[source()])


@pytest.mark.parametrize('answer',[
 'You will receive a INR 37 refund.',
 'You are eligible for a INR 37 refund.',
 'Your return qualifies for a INR 37 refund.',
])
def test_indefinite_article_does_not_make_a_personal_refund_promise_hypothetical(answer):
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money(answer,'When should my refund arrive?',{},[source()])


def test_generic_present_fee_payment_is_preserved_but_actual_past_payment_needs_a_premise():
 validate_personal_money('You pay INR 37 as a COD fee.','What is the COD fee?',{},[source()])
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money('You paid INR 37 as a COD fee.','What is the COD fee?',{},[source()])
 validate_personal_money('You paid INR 37 as a COD fee.','I paid INR 37 as a COD fee.',{},[source()])


def test_fee_descriptor_near_another_paid_amount_does_not_create_a_second_payment_premise():
 query='I paid INR 731 for the order and the COD fee is INR 37.'
 validate_personal_money('You paid INR 731 for the order.',query,{},[source()])
 with pytest.raises(ValueError,match='unsupported_personal_money_amount'):
  validate_personal_money('You paid INR 37.',query,{},[source()])
