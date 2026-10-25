"""Document calculations must track retrieved values and preserve privacy."""
from types import SimpleNamespace

from src.document_context import build_context


def source(sid, text):
    return {'id': sid, 'text': text, 'status': 'current', 'doc_type': 'policy'}


def data(holidays=(), products=None):
    return SimpleNamespace(holidays=set(holidays), products=products or {})


def calendar():
    return source('KB-00.3', 'A business day is Monday to Saturday, excluding warehouse holidays.')


def test_verified_records_drop_outer_and_nested_identity_fields():
    order = {'order_id': '00112233', 'customer_id': 'C01', 'phone': '1234567890',
             'delivery_pincode': '012345', 'email': 'secret@example.com',
             'internal_notes': 'private', 'status': 'shipped',
             'items': [{'order_id': '00112233', 'sku': 'ELE-0001', 'qty': 1,
                        'customer_id': 'C01', 'address': 'private address'}]}
    context = build_context('Where is it?', [], data(), verified_order=order)
    assert context['verified_order'] == {'status': 'shipped', 'items': [{'sku': 'ELE-0001', 'qty': 1}]}
    assert context['calculations'] == []


def test_no_private_order_reader_is_needed():
    class PublicData:
        products = {}
        holidays = set()

        def read(self, *_):
            raise AssertionError('Context must never read private CSVs')

    context = build_context('Return policy?', [], PublicData(),
                            public_context={'category': 'fashion', 'phone': 'secret'})
    assert context['public_context'] == {'category': 'fashion'}


def test_refund_dates_derive_changed_bounds_and_calendar_holidays():
    sources = [source('REF-2', '| UPI | 2 to 4 business days |'), calendar()]
    context = build_context('Refund?', sources, data(['2026-10-19']),
                            verified_order={'payment_method': 'upi',
                                            'return_refund_initiated_on': '2026-10-16'})
    calculation = context['calculations'][0]
    assert calculation['inputs']['minimum_business_days'] == 2
    assert calculation['inputs']['maximum_business_days'] == 4
    assert calculation['result']['earliest_date'] == '2026-10-20'
    assert calculation['result']['latest_date'] == '2026-10-22'
    assert calculation['source_ids'] == ['REF-2', 'KB-00.3', 'data/holidays.csv']
    assert len(context['calculation_source_sha256']['REF-2']) == 64


def test_refund_without_explicit_calendar_or_ambiguous_bounds_has_no_calculation():
    order = {'payment_method': 'upi', 'return_refund_initiated_on': '2026-10-16'}
    policy = source('REF-2', '| UPI | 2 to 4 business days |')
    assert not build_context('Refund?', [policy], data(), verified_order=order)['calculations']
    policy['text'] += '\n| UPI | 1 to 3 business days |'
    assert not build_context('Refund?', [policy, calendar()], data(), verified_order=order)['calculations']


def test_calendar_weekday_rule_is_read_from_source():
    sources = [source('REF-2', '| UPI | 1 to 2 business days |'),
               source('KB-00.3', 'A business day is Monday to Friday, excluding holidays.')]
    calculation = build_context('Refund?', sources, data(),
                                verified_order={'payment_method': 'upi',
                                                'return_refund_initiated_on': '2026-10-16'})['calculations'][0]
    assert calculation['result']['earliest_date'] == '2026-10-19'
    assert calculation['result']['latest_date'] == '2026-10-20'


def test_return_deadline_uses_changed_source_days():
    sources = [source('RET-2', '| Home items | 20 days | `home_kitchen` |')]
    calculation = build_context('Can I return?', sources, data(),
                                public_context={'category': 'home_kitchen',
                                                'delivered_on': '2026-10-20'})['calculations'][0]
    assert calculation['inputs']['calendar_days'] == 20
    assert calculation['result']['deadline'] == '2026-11-09'


def test_historical_cutoff_and_window_are_both_source_derived():
    sources = [source('RET-2', '| Electronics and accessories | 8 days | `electronics` |'),
               source('RET-3', 'Electronics delivered before 1 October 2026 keep the earlier 11-day window.')]
    calculation = build_context('Return deadline?', sources, data(),
                                public_context={'category': 'electronics',
                                                'delivered_on': '2026-09-30'})['calculations'][0]
    assert calculation['inputs']['calendar_days'] == 11
    assert calculation['result']['deadline'] == '2026-10-11'
    assert 'RET-3' in calculation['source_ids']


def test_sale_dates_and_window_are_source_derived_and_missing_date_is_unresolved():
    sources = [source('RET-2', '| Clothing | 12 days | `fashion` |'),
               source('RET-8', 'Clothing from orders placed between 08 September and 12 September 2026 can be returned within 27 days of delivery.')]
    public = {'category': 'fashion', 'delivered_on': '2026-09-18'}
    assert not build_context('Deadline?', sources, data(), public_context=public)['calculations']
    public['placed_on'] = '2026-09-10'
    calculation = build_context('Deadline?', sources, data(), public_context=public)['calculations'][0]
    assert calculation['inputs']['calendar_days'] == 27
    assert calculation['result']['deadline'] == '2026-10-15'


def test_superseded_or_missing_numeric_policy_cannot_supply_deadline():
    policy = source('RET-2', '| Electronics | 8 days | `electronics` |')
    policy['status'] = 'superseded'
    assert not build_context('Deadline?', [policy], data(),
                             public_context={'category': 'electronics',
                                             'delivered_on': '2026-10-20'})['calculations']

def test_date_labels_derive_from_included_actual_dates():
    context = build_context('Status?', [], data(),
                            verified_order={'shipped_on': '2026-10-13'})
    assert context['date_labels']['2026-10-13'] == '13 October 2026'
    assert context['date_labels'][context['reference_date']]


def postal_source(pin='560034', **values):
    import json
    row = {'pincode': pin, 'city': 'Bengaluru', 'serviceable': 'True',
           'cod_available': 'True', 'express_available': 'False'}
    row.update(values)
    return source('pincodes.csv:' + pin, json.dumps(row))


def test_public_postal_facts_use_retrieved_row_and_only_requested_services():
    sources = [postal_source(phone='do-not-copy', customer_id='private')]
    context = build_context('Can Standard delivery reach pincode 560034?', sources, data())
    assert context['pincode_listed'] is True and context['serviceable'] is True
    assert 'cod_available' not in context and 'express_available' not in context
    record = context['public_serviceability']['record']
    assert record['pincode'] == '560034'
    assert 'phone' not in record and 'customer_id' not in record
    context = build_context('Is Express available at pincode 560034?', sources, data())
    assert context['express_available'] is False and 'cod_available' not in context


def test_cod_amount_uses_changed_policy_cap_and_excludes_pincode_from_price():
    sources = [postal_source(), source('PAY-2', 'COD is available on orders up to Rs 12,345, only on enabled pincodes.')]
    query = 'Can I pay COD for 15000 rupees at pincode 560034?'
    context = build_context(query, sources, data())
    assert context['cod_available'] is True and context['cod_eligible'] is False
    calculation = context['calculations'][0]
    assert calculation['inputs']['maximum_order_inr'] == 12345
    assert calculation['inputs']['order_amount_inr'] == 15000
    assert calculation['source_ids'] == ['pincodes.csv:560034', 'PAY-2']
    sources[1]['text'] = 'COD is available on orders up to INR 20,000, only on enabled pincodes.'
    assert build_context(query, sources, data())['cod_eligible'] is True


def test_cod_requires_explicit_unambiguous_amount_and_retrieved_limit():
    row = postal_source()
    assert 'cod_eligible' not in build_context('COD for 15000 rupees at pincode 560034?', [row], data())
    sources = [row, source('PAY-2', 'COD is available on orders up to Rs 12000.')]
    assert 'cod_eligible' not in build_context('COD at pincode 560034?', sources, data())
    assert 'cod_eligible' not in build_context('Compare COD for 11000 rupees and 13000 rupees at pincode 560034.', sources, data())


def test_unserviceable_postal_row_cannot_enable_cod_or_express():
    sources = [postal_source(serviceable='False', express_available='True'),
               source('PAY-2', 'COD is available on orders up to Rs 12000.')]
    context = build_context('COD and Express for 100 rupees at pincode 560034?', sources, data())
    assert context['serviceable'] is False
    assert context['cod_available'] is False and context['cod_eligible'] is False
    assert context['express_available'] is False


def test_unlisted_public_pincode_is_not_an_identity_lookup():
    public_data = data()
    public_data.pincodes = {'560034': {'pincode': '560034'}}
    context = build_context('Can delivery reach pincode 999999?', [], public_data)
    assert context['pincode_listed'] is False and 'verified_order' not in context
    assert 'serviceable' not in context


def test_incidental_pincode_does_not_create_serviceability_facts():
    context = build_context('My pincode is 560034. What is the return period for ELE-0002?', [postal_source()], data())
    assert 'serviceable' not in context and 'public_serviceability' not in context


def test_six_digit_price_is_not_mistaken_for_the_explicit_public_pincode():
    sources = [postal_source(), source('PAY-2', 'COD is available on orders up to Rs 12000.')]
    context = build_context('COD for 150000 rupees at pincode 560034?', sources, data())
    assert context['cod_eligible'] is False
    assert context['calculations'][0]['inputs']['order_amount_inr'] == 150000
    public_data = data()
    public_data.pincodes = {}
    assert 'pincode_listed' not in build_context('COD for 150000 rupees?', [], public_data)
