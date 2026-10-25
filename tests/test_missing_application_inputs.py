"""Unresolved table keys are metadata; questions remain model generated."""
import json
from types import SimpleNamespace
import pytest
from src.document_context import build_context
from src.document_answers import _validate_context, document_reply


def source(sid, text, **extra):
    return dict(id=sid, text=text, status='current', doc_type='policy', **extra)


def returns():
    return [source('RET-2', '| Group | Return window | return_category |\n'
                   '| Clothes | 23 days | `fashion` |\n'
                   '| Devices | 11 days | `electronics` |')]


def refunds():
    return [source('REF-2', '| Method | Timeline |\n| UPI | 2 to 4 business days |\n'
                   '| Credit / debit cards | 8 to 9 business days |')]


def data():
    return SimpleNamespace(products={}, holidays=set())


@pytest.mark.parametrize('query',[
    'How many days do I have to return it?',
    '\u0915\u093f\u0924\u0928\u0947 \u0926\u093f\u0928 \u092e\u0947\u0902 \u0935\u093e\u092a\u0938 \u0915\u0930\u0928\u093e \u0939\u094b\u0917\u093e?',
    'Wapas karne ke liye kitne din hain?',
])
def test_duration_without_category_requires_actual_lookup_key(query):
    context = build_context(query, returns(), data())
    item = context['required_application_inputs'][0]
    assert item['key'] == 'return_category'
    assert item['source_ids'] == ['RET-2']
    assert item['allowed_rows'] == [
        {'return_category':'fashion','return_window':'23 days'},
        {'return_category':'electronics','return_window':'11 days'}]
    assert 'question' not in json.dumps(item)


@pytest.mark.parametrize('query', [
    'Compare return windows for all categories.',
    'How are the products packed?',
    'Is returning an item possible?',
])
def test_comparison_or_non_duration_does_not_require_one_category(query):
    assert 'required_application_inputs' not in build_context(query, returns(), data())


def test_resolved_category_and_shared_variant_category_need_no_question():
    context = build_context('How many days for a return?', returns(), data(),
                            public_context={'category':'fashion'})
    assert 'required_application_inputs' not in context
    products = [source('products.csv:SKU-A', json.dumps({'sku':'SKU-A','return_category':'fashion'})),
                source('products.csv:SKU-B', json.dumps({'sku':'SKU-B','return_category':'fashion'}))]
    assert 'required_application_inputs' not in build_context('Return window?', returns()+products, data())


def test_single_row_policy_and_superseded_table_do_not_force_missing_key():
    sources = [source('RET-2','| Clothing | 23 days | `fashion` |')]
    assert 'required_application_inputs' not in build_context('Return window?',sources,data())
    sources = returns()
    sources[0]['status'] = 'superseded'
    assert 'required_application_inputs' not in build_context('Return window?',sources,data())


def test_refund_method_required_only_when_unresolved():
    context = build_context('How many days does a refund take?', refunds(), data())
    assert context['required_application_inputs'][0]['key']=='payment_method'
    assert context['required_application_inputs'][0]['allowed_rows'][1]['timeline']=='8 to 9 business days'
    assert 'required_application_inputs' not in build_context('How many days does a UPI refund take?',refunds(),data())
    assert 'required_application_inputs' not in build_context('Compare all payment methods for refund duration.',refunds(),data())


def test_existing_verified_method_does_not_ask_again():
    context=build_context('Refund kab milega?',refunds(),data(),verified_order={'payment_method':'card'})
    assert 'required_application_inputs' not in context


def test_supported_declaration_without_actual_question_is_repaired():
    facts = build_context('How long can I return it?',returns(),data())
    value={'answer':'The duration depends on the product category.','covered':True,'needs_clarification':False}
    with pytest.raises(ValueError,match='missing_required_input:return_category'):
        _validate_context(value,returns(),facts,'en')
    value={'answer':'Which product category are you asking about?','covered':False,'needs_clarification':True}
    assert _validate_context(value,returns(),facts,'en')['decision']=='clarify'


def test_missing_input_requires_a_question_even_if_flag_true():
    facts = build_context('How long can I return it?',returns(),data())
    value={'answer':'The duration depends on the product category.','covered':True,'needs_clarification':True}
    with pytest.raises(ValueError,match='missing_required_input:return_category'):
        _validate_context(value,returns(),facts,'en')


def test_fabricated_required_input_rows_are_rejected():
    facts=build_context('How long can I return it?',returns(),data())
    facts['required_application_inputs'][0]['allowed_rows'][0]['return_window']='888 days'
    value={'answer':'Which category?','covered':False,'needs_clarification':True}
    with pytest.raises(ValueError,match='unbound_required_application_input'):
        _validate_context(value,returns(),facts,'en')


def test_no_network_stub_exercises_one_repair_with_metadata_only():
    class Stub:
        last_metrics={}
        def __init__(self): self.calls=[]
        def complete(self,system,payload,**kwargs):
            self.calls.append((system,json.loads(payload),kwargs))
            if len(self.calls)==1:
                return json.dumps({'answer':'The period depends on category.','covered':True,'needs_clarification':False})
            return json.dumps({'answer':'Which product category do you mean?','covered':False,'needs_clarification':True})
    stub=Stub()
    facts=build_context('How long can I return it?',returns(),data())
    result=document_reply(stub,'How long can I return it?','en',returns(),facts=facts,context_provenance=True)
    assert result['decision']=='clarify' and result['generation_attempts']==2
    repair=stub.calls[1][1]
    assert repair['repair_required_inputs'][0]['key']=='return_category'
    assert stub.calls[1][2]['cache'] is False
    assert '23 days' not in repair['repair_instruction']


@pytest.mark.parametrize('query', [
    'When will my refund be initiated after pickup and QC?',
    'Pickup ke baad refund kab shuru hoga?',
    '\u092a\u093f\u0915\u0905\u092a \u0915\u0947 \u092c\u093e\u0926 \u0930\u093f\u092b\u0902\u0921 \u0915\u092c \u0936\u0941\u0930\u0942 \u0939\u094b\u0917\u093e?',
])
def test_source_wide_initiation_clock_does_not_require_payment_method(query):
    assert 'required_application_inputs' not in build_context(query, refunds(), data())


@pytest.mark.parametrize('query', [
    'Sabhi categories ke return windows batao.',
    '\u0938\u092d\u0940 \u0936\u094d\u0930\u0947\u0923\u093f\u092f\u094b\u0902 \u0915\u0947 \u0930\u093f\u091f\u0930\u094d\u0928 \u092e\u0947\u0902 \u0915\u093f\u0924\u0928\u0947 \u0926\u093f\u0928 \u0939\u0948\u0902?',
])
def test_hindi_hinglish_whole_table_requests_remain_exempt(query):
    assert 'required_application_inputs' not in build_context(query, returns(), data())


def test_explicit_started_date_without_method_still_needs_arrival_lookup():
    context=build_context('My refund started 17 October 2026; by when will I get it?', refunds(), data())
    assert context['required_application_inputs'][0]['key']=='payment_method'



def cod_sources():
    return [source('REF-2','| UPI | 2 to 4 business days |\n'
                   '| Bank transfer (NEFT) for cash-on-delivery orders | 5 to 7 business days |\n'
                   '| ZentroMart Wallet for cash-on-delivery orders | Instant, within 2 hours |')]


@pytest.mark.parametrize('query', [
    'I paid cash on delivery and returned the item. How do I get my money back?',
    'COD refund kitne din mein milega?',
    'How long does a cash-on-delivery refund take?',
])
def test_cod_public_option_overview_does_not_force_a_destination(query):
    assert 'required_application_inputs' not in build_context(query,cod_sources(),data())


def test_cod_dated_individual_arrival_application_asks_only_actual_cod_destinations():
    context=build_context('My COD refund started 17 October 2026; by when will I get it?',cod_sources(),data())
    item=context['required_application_inputs'][0]
    assert item['key']=='payment_method'
    assert {r['payment_method'] for r in item['allowed_rows']}=={'cod_bank','cod_wallet'}
