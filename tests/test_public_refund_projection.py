"""Hypothetical deadlines omit an unrelated reference-date elapsed count."""
from types import SimpleNamespace
from src.document_context import build_context


def sources():
    return [{'id':'REF-2','status':'current','doc_type':'policy',
             'text':'| Net banking | 3 to 5 business days |'},
            {'id':'KB-00.3','status':'current','doc_type':'policy',
             'text':'A business day is Monday to Saturday, excluding warehouse holidays.'}]


def test_public_projection_retains_range_but_not_elapsed_reference_fact():
    data=SimpleNamespace(products={},holidays={'2026-10-19'})
    context=build_context('My netbanking refund started 17 October 2026; when will it arrive?',sources(),data)
    result=context['calculations'][0]['result']
    assert result=={'earliest_date':'2026-10-22','latest_date':'2026-10-24'}
    assert context['calculations'][0]['inputs']['reference_date']=='2026-10-20'
    assert context['customer_provided_refund_claim']['verified'] is False


def test_verified_record_keeps_separate_existing_elapsed_fact():
    data=SimpleNamespace(products={},holidays={'2026-10-19'})
    context=build_context('Refund status?',sources(),data,verified_order={
        'payment_method':'netbanking','return_refund_initiated_on':'2026-10-17'})
    assert context['calculations'][0]['result']['elapsed_business_days']==1
