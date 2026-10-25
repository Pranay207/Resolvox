"""Public refund dates are projections from unverified customer statements."""
import json
from types import SimpleNamespace

from src.document_context import build_context


def source(sid, text):
    return {'id': sid, 'text': text, 'status': 'current', 'doc_type': 'policy'}


def sources(card='5 to 7', net='3 to 5'):
    return [source('REF-2', '| Credit or debit card | ' + card + ' business days |\n'
                   '| Net banking | ' + net + ' business days |\n| UPI | 1 to 3 business days |'),
            source('KB-00.3', 'A business day is Monday to Saturday, excluding warehouse holidays.')]


def public_data():
    return SimpleNamespace(products={}, holidays={'2026-10-19'})


def test_public_card_date_projection_is_not_a_verified_order():
    context = build_context('credit card wala refund 17 October 2026 ko shuru hua, kab tak?',
                            sources(), public_data())
    claim = context['customer_provided_refund_claim']
    assert claim == {'initiated_on': '2026-10-17', 'payment_method': 'card',
                     'verified': False, 'origin': 'customer_provided',
                     'transaction_status_confirmed': False}
    assert 'verified_order' not in context
    calculation = context['calculations'][0]
    assert calculation['result']['earliest_date'] == '2026-10-24'
    assert calculation['result']['latest_date'] == '2026-10-27'
    assert calculation['input_status'] == 'customer_provided_unverified'
    assert calculation['inputs']['customer_statement_verified'] is False
    assert calculation['source_ids'] == ['REF-2', 'KB-00.3', 'data/holidays.csv']
    assert context['date_labels']['2026-10-27'] == '27 October 2026'


def test_public_netbanking_projection_and_changed_policy_bounds():
    query = 'My refund to net banking was started on 14 October 2026. By which date should I have it?'
    context = build_context(query, sources(), public_data())
    assert context['calculations'][0]['result']['latest_date'] == '2026-10-21'
    changed = build_context(query, sources(net='1 to 2'), public_data())
    assert changed['calculations'][0]['result']['earliest_date'] == '2026-10-15'
    assert changed['calculations'][0]['result']['latest_date'] == '2026-10-16'


def test_public_projection_needs_source_calendar_and_bounds():
    query = 'My card refund was initiated on 2026-10-17.'
    for selected in ([], sources()[:1], sources()[1:]):
        context = build_context(query, selected, public_data())
        assert context['calculations'] == []
        assert 'verified_order' not in context


def test_ambiguous_or_undated_refund_claims_are_not_calculated():
    queries = [
        'My card refund started on 17 October 2026 or 18 October 2026.',
        'My UPI or card refund started on 17 October 2026.',
        'My refund started on 17 October 2026.',
        'My card refund started on 17 October.',
        'My card refund started recently.',
        'My card refund started on 31 February 2026.',
        'My card order was delivered on 17 October 2026. Refund started today.',
    ]
    for query in queries:
        context = build_context(query, sources(), public_data())
        assert context['calculations'] == [], query
        assert 'customer_provided_refund_claim' not in context, query


def test_negated_or_unrelated_events_do_not_become_refund_initiation():
    for query in [
        'My card refund was not started on 17 October 2026.',
        'Mera card refund 17 October 2026 ko shuru nahi hua.',
        'My card delivery started on 17 October 2026.',
        'My card refund was completed on 17 October 2026.',
    ]:
        context = build_context(query, sources(), public_data())
        assert 'customer_provided_refund_claim' not in context, query
        assert not context['calculations'], query


def test_public_statement_never_overrides_actual_verified_record():
    context = build_context('My card refund started on 17 October 2026.', sources(), public_data(),
                            verified_order={'payment_method': 'card',
                                            'return_refund_initiated_on': '2026-10-14'})
    assert 'customer_provided_refund_claim' not in context
    assert context['calculations'][0]['inputs']['initiated_on'] == '2026-10-14'


def test_claim_context_retains_no_raw_text_identity_or_contact_fields():
    class SafeData:
        products = {}
        holidays = {'2026-10-19'}

        def read(self, *_):
            raise AssertionError('No private order reader is permitted')

    context = build_context('My card refund was started on 17 October 2026. Phone 9876543210, email secret@example.com.',
                            sources(), SafeData())
    serialized = json.dumps(context)
    assert 'secret@example.com' not in serialized and '9876543210' not in serialized
    assert context['customer_provided_refund_claim']['verified'] is False


def test_hindi_customer_statement_has_a_labeled_public_projection():
    query = '\u092e\u0947\u0930\u093e \u0915\u093e\u0930\u094d\u0921 \u0930\u093f\u092b\u0902\u0921 17 \u0905\u0915\u094d\u091f\u0942\u092c\u0930 2026 \u0915\u094b \u0936\u0941\u0930\u0942 \u0939\u0941\u0906'
    context = build_context(query, sources(), public_data())
    assert context['customer_provided_refund_claim']['payment_method'] == 'card'
    assert context['calculations'][0]['result']['latest_date'] == '2026-10-27'