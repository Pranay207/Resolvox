"""Focused refund inputs must preserve compound questions and recorded completion."""
from types import SimpleNamespace
import pytest
from src.document_context import build_context
from src.document_answers import document_reply
from src.refund_timeline import refund_timeline_binding, refund_timeline_inputs
from test_refund_payment_timeline import context, Client


def coupon_context(query):
 facts,sources=context(query=query)
 sources.append({'id':'coupon-rule','doc_type':'policy','status':'current',
                 'text':'A partial refund is the price paid for that item after its share of any coupon discount.'})
 facts=build_context(query,sources,SimpleNamespace(products={},holidays=set()),verified_order=facts['verified_order'])
 return facts,sources


@pytest.mark.parametrize('query',[
 'When will my refund arrive, and how will my coupon discount affect a partial refund?',
 'When will my refund arrive and how much money will I get?',
 'Mera refund kitne din mein aayega aur coupon discount ka kya hoga?',
 'रिफंड कितने दिन में आएगा और कूपन की छूट कितनी कटेगी?',
 'रिफंड कितने दिन में आएगा और कितनी राशि वापस मिलेगी?',
])
def test_amount_or_coupon_facets_keep_the_full_generation_context(query):
 facts,sources=coupon_context(query)
 assert refund_timeline_inputs(query,facts,sources,'2026-10-20') is None


def test_compound_reply_reaches_model_with_original_coupon_rule_and_verified_fields():
 query='When will my refund arrive, and how will my coupon discount affect a partial refund?'
 facts,sources=coupon_context(query)
 client=Client('UPI refunds take 23 to 37 business days after initiation. A partial refund uses the item price after its coupon discount.')
 result=document_reply(client,query,'en',sources,facts=facts,private=True,context_provenance=True)
 assert len(client.calls)==1 and result['decision']=='answer'
 payload=client.calls[0][1]
 assert {row['id']:row for row in payload['source_text']}=={row['id']:row for row in sources}
 assert len(payload['source_text'])==len(sources)
 assert payload['deterministic_facts']['verified_order']==facts['verified_order']
 assert any(row['id']=='coupon-rule' for row in payload['source_text'])


@pytest.mark.parametrize('query',[
 'When was my refund completed?',
 'When will my refund arrive?',
 'मेरा रिफंड कब पूरा हुआ?',
 'Mera refund kab complete hua?',
])
def test_recorded_completion_disables_future_arrival_projection(query):
 facts,sources=context(query=query,return_status='refunded',return_refund_initiated_on='2026-10-15',
                       return_refund_completed_on='2026-10-17',return_refund_method='upi')
 assert 'refund_arrival_policy' not in facts
 assert refund_timeline_binding(query,facts,sources,'2026-10-20') is None
 assert refund_timeline_inputs(query,facts,sources,'2026-10-20') is None


@pytest.mark.parametrize('query',[
 'When was my refund completed?',
 'When did my refund arrive?',
 'मेरा रिफंड कब पूरा हुआ?',
 'Mera refund kab complete hua?',
])
def test_historical_completion_question_without_a_date_does_not_force_future_range(query):
 facts,sources=context(query=query)
 assert 'refund_arrival_policy' not in facts
 assert refund_timeline_inputs(query,facts,sources,'2026-10-20') is None


def test_recorded_date_is_supplied_to_model_and_valid_answer_passes_existing_guards():
 query='When was my refund completed?'
 facts,sources=context(query=query,return_status='refunded',return_refund_completed_on='2026-10-17')
 answer='The order record lists refund completed on 17 October 2026.'
 client=Client(answer)
 result=document_reply(client,query,'en',sources,facts=facts,private=True,context_provenance=True)
 assert result['answer']==answer and len(client.calls)==1
 assert client.calls[0][1]['deterministic_facts']['verified_order']['return_refund_completed_on']=='2026-10-17'


def test_invented_completion_date_is_still_rejected():
 query='When was my refund completed?'
 facts,sources=context(query=query,return_status='refunded',return_refund_completed_on='2026-10-17')
 bad='The order record lists refund completed on 18 October 2026.'
 with pytest.raises(ValueError,match='unverified_record_completion'):
  document_reply(Client(bad,bad),query,'en',sources,facts=facts,private=True,context_provenance=True)


def test_uncompleted_simple_arrival_still_uses_bound_payment_range():
 facts,sources=context(return_refund_completed_on=None)
 view=refund_timeline_inputs('When will my refund arrive?',facts,sources,'2026-10-20')
 assert view['facts']['refund_arrival_policy']['minimum_business_days']==23
 assert view['facts']['refund_arrival_policy']['maximum_business_days']==37


def test_coupon_policy_survives_the_existing_range_repair_too():
 query='When will my refund arrive and how does my coupon affect a partial refund?'
 facts,sources=coupon_context(query)
 good='UPI refunds take 23 to 37 business days after initiation. A partial refund uses the item price after its coupon discount.'
 client=Client('UPI refunds take 41 to 53 business days after initiation.',good)
 result=document_reply(client,query,'en',sources,facts=facts,private=True,context_provenance=True)
 assert result['answer']==good and len(client.calls)==2
 assert all({row['id']:row for row in call[1]['source_text']}=={row['id']:row for row in sources}
            and len(call[1]['source_text'])==len(sources) for call in client.calls)
