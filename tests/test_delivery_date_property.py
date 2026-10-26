"""Pure date-property scope controls with synthetic source-bound policies."""
import copy
import json
import socket
import pytest
import requests
from src.placement_conditions import check_placement_exception_answer, delivery_exception_status
from src.document_answers import document_reply, _constraint_text


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*a, **k): pytest.fail('No network permitted')
    monkeypatch.setattr(socket, 'create_connection', denied)
    monkeypatch.setattr(requests.sessions.Session, 'request', denied)


@pytest.fixture
def case():
    sources = [
        {'id': 'SYNTHETIC-TABLE', 'text': '| Portable devices and accessories | 11 days | device_x |',
         'doc_type': 'policy', 'status': 'current', 'effective_from': '2032-01-01'},
        {'id': 'SYNTHETIC-HISTORY', 'text': 'Portable devices delivered before 13 June 2033 keep the earlier 17-day window.',
         'doc_type': 'policy', 'status': 'current', 'effective_from': '2032-01-01'},
        {'id': 'SYNTHETIC-CATALOG', 'text': json.dumps({'sku': 'DEVICE-Q9', 'title': 'Sample device', 'return_category': 'device_x'}),
         'doc_type': 'catalog', 'status': 'current'},
    ]
    facts = {'reference_date': '2033-08-04', 'public_context': {'sku': 'DEVICE-Q9'},
             'return_policy': {'category': 'device_x', 'window_calendar_days': 11, 'source_ids': ['SYNTHETIC-TABLE'],
                               'selection': 'standard_window', 'historical_exception': {'delivery_before': '2033-06-13',
                               'window_calendar_days': 17, 'source_ids': ['SYNTHETIC-HISTORY']}}}
    return facts, sources


def check(text, case):
    return check_placement_exception_answer(text, *case, normalizer=_constraint_text)


@pytest.mark.parametrize('text', [
    'Since the delivery date of DEVICE-Q9 is after 13 June 2033, the current window applies.',
    'The delivery date for DEVICE-Q9 was before 13 June 2033.',
    "DEVICE-Q9's delivery date is on 12 June 2033.",
    'The delivery date of SKU DEVICE-Q9 falls on or after that date.',
    'The delivery date of `DEVICE-Q9` is not before the cutoff.',
    'The delivery date of DEVICE-Q9 is after yesterday.',
    'If it is unused, since the delivery date of DEVICE-Q9 is after 13 June 2033, the current rule applies.',
    'We cannot confirm the receipt date, but the delivery date of DEVICE-Q9 is after 13 June 2033.',
])
def test_unknown_actual_identifier_date_property_is_not_factual(case, text):
    with pytest.raises(ValueError, match='invented_delivery_premise'): check(text, case)


@pytest.mark.parametrize('text', [
    'If the delivery date of DEVICE-Q9 is after 13 June 2033, the current rule applies.',
    'The rule depends on whether the delivery date of DEVICE-Q9 is before that date.',
    'I cannot confirm the delivery date of DEVICE-Q9 is after the cutoff.',
    'Is the delivery date of DEVICE-Q9 after 13 June 2033?',
    'Can you confirm the delivery date of DEVICE-Q9 is after 13 June 2033?',
    'Could you check that the delivery date of DEVICE-Q9 is before 13 June 2033?',
    'Please share the actual delivery date for DEVICE-Q9.',
    'Items delivered before 13 June 2033 keep the earlier 17-day window.',
    'The current general return window for DEVICE-Q9 is 11 days.',
    'The delivery date of DEVICE-Q9 is unknown.',
    'The expected delivery date of DEVICE-Q9 is after 13 June 2033.',
    'The promised delivery date of DEVICE-Q9 is after 13 June 2033.',
    'The refund delivery date of DEVICE-Q9 is after 13 June 2033.',
    'The delivery date of DEVICE-Q9 is after the dispatch date.',
    'The delivery date of UNRELATED-X is after 13 June 2033.',
])
def test_conditional_questions_uncertainty_general_and_other_event_scopes_allow(case, text): check(text, case)


@pytest.mark.parametrize('record', ['public_context', 'verified_order'])
def test_known_delivery_date_preserves_existing_source_bound_branch(case, record):
    facts, sources = case; facts.setdefault(record, {})['delivered_on'] = '2033-06-14'
    assert delivery_exception_status(facts, sources)['applicability'] == 'not_met'
    check('The delivery date of DEVICE-Q9 is after 13 June 2033.', case)


def test_catalog_and_explicit_identifier_sources_are_independent_not_inferred_from_fact_catalog(case):
    facts, sources = copy.deepcopy(case)
    del facts['public_context']
    with pytest.raises(ValueError, match='invented_delivery_premise'):
        check('The delivery date of DEVICE-Q9 is after the cutoff.', (facts, sources))
    sources.pop()
    facts['catalog'] = [{'sku': 'STALE-X', 'return_category': 'device_x'}]
    check('The delivery date of STALE-X is after the cutoff.', (facts, sources))
    facts['public_context'] = {'sku': 'EXPLICIT-P9'}
    with pytest.raises(ValueError, match='invented_delivery_premise'):
        check('The delivery date of EXPLICIT-P9 is after the cutoff.', (facts, sources))


def test_counterfactual_identifiers_dates_durations_and_reference_do_not_supply_delivery_input(case):
    facts, sources = case
    facts['public_context']['sku'] = 'ZED_42'
    sources[2]['text'] = json.dumps({'sku': 'ZED_42', 'return_category': 'device_x'})
    sources[0]['text'] = sources[0]['text'].replace('11 days', '23 days')
    sources[1]['text'] = sources[1]['text'].replace('13 June 2033', '20 July 2034').replace('17-day', '29-day')
    facts['reference_date'] = '2035-01-02';facts['return_policy']['window_calendar_days'] = 23
    facts['return_policy']['historical_exception'].update(delivery_before='2034-07-20', window_calendar_days=29)
    status = delivery_exception_status(facts, sources)
    assert status['input_origin'] == 'missing' and status['delivery_date'] is None
    with pytest.raises(ValueError, match='invented_delivery_premise'):
        check('Since the delivery date of ZED_42 is after 20 July 2034, the current 23-day rule applies.', case)
    check('If the delivery date of ZED_42 is after 20 July 2034, the current 23-day rule applies.', case)


def test_stale_actual_policy_change_is_rebound_before_property_guard(case):
    facts, sources = case
    sources[1]['text'] = sources[1]['text'].replace('17-day', '19-day')
    with pytest.raises(ValueError, match='unbound_delivery_exception'):
        check('The delivery date of DEVICE-Q9 is after the cutoff.', case)


def test_generation_repairs_once_using_original_sources_and_facts(case):
    facts, sources = case; original = copy.deepcopy(case)
    bad = 'Since the delivery date of DEVICE-Q9 is after 13 June 2033, the current 11-day window applies.'
    good = 'The current general return window is 11 days. Items delivered before 13 June 2033 keep the earlier 17-day window.'
    class Client:
        last_metrics = {}
        def __init__(self): self.calls = []
        def complete(self, system, user, **options):
            self.calls.append((json.loads(user), options));assert len(self.calls) <= 2
            text = bad if len(self.calls) == 1 else good
            return json.dumps({'answer': text, 'covered': True, 'needs_clarification': False})
    client = Client()
    result = document_reply(client, 'What is the return window?', 'en', sources, facts=facts, context_provenance=True)
    assert result['answer'] == good and result['repair_errors'] == ['invented_delivery_premise']
    assert len(client.calls) == 2 and client.calls[1][1]['cache'] is False and case == original


def test_new_property_condition_does_not_expand_existing_entitlement_exemption(case):
    text = 'If the delivery date of DEVICE-Q9 is before the cutoff, but you have 17 days regardless.'
    with pytest.raises(ValueError, match='unsupported_delivery_exception_entitlement'): check(text, case)


@pytest.mark.parametrize('prefix', ['Can you please confirm that ', 'Could you please check that ', 'Please confirm that '])
def test_polite_focused_date_requests_are_not_factual_claims(case, prefix):
    check(prefix + 'the delivery date of DEVICE-Q9 is after 13 June 2033?', case)


@pytest.mark.parametrize('text', [
    'Please confirm the receipt date, since the delivery date of DEVICE-Q9 is after 13 June 2033.',
    'Could you please check the receipt date, but the delivery date of DEVICE-Q9 is after the cutoff?',
])
def test_request_or_question_mark_does_not_exempt_neighbor_assertion(case, text):
    with pytest.raises(ValueError, match='invented_delivery_premise'): check(text, case)
