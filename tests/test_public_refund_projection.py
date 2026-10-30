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



def test_repair_projection_keeps_calculated_dates_and_declines_unrequested_amount_scope():
    import copy
    from src.repair_contexts import public_refund_projection_inputs
    query='My netbanking refund started 17 October 2026; when will it arrive?'
    actual=sources();context=build_context(query,actual,SimpleNamespace(products={},holidays={'2026-10-19'}))
    before=copy.deepcopy((context,actual))
    out=public_refund_projection_inputs(query,context,actual,'2026-10-20')
    assert out['facts']['refund_projection']['earliest_expected_date']=='2026-10-22'
    assert out['facts']['refund_projection']['latest_expected_date']=='2026-10-24'
    assert out['facts']['customer_provided_refund_claim']['verified'] is False
    assert 'reference_date' not in out['facts']
    assert public_refund_projection_inputs(query+' What amount will I receive?',context,actual,'2026-10-20') is None
    assert (context,actual)==before
