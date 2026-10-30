"""Public date estimates cannot certify future settlement or negate late dates."""
import copy
import json
from types import SimpleNamespace

import pytest

from src.document_answers import document_reply
from src.document_context import build_context
from src.generation_diagnostics import validation_code
from src.refund_arrival_claims import check_public_refund_timeliness


def context():
    sources = [
        {'id': 'REF-2', 'status': 'current', 'doc_type': 'policy',
         'text': '| UPI | 2 to 4 business days |'},
        {'id': 'KB-00.3', 'status': 'current', 'doc_type': 'policy',
         'text': 'A business day is Monday to Saturday, excluding warehouse holidays.'}]
    query = 'My UPI refund was started on 6 October 2026; by when should it arrive?'
    facts = build_context(query, sources, SimpleNamespace(products={}, holidays=set()))
    assert facts['calculations'][0]['result']['latest_date'] == '2026-10-10'
    return query, sources, facts


@pytest.mark.parametrize('text', [
    'There will be no delay.', 'No additional delays will occur.',
    "It won't be late.", "Your refund won't be overdue.",
    'Your refund will not be delayed.', "You won't experience any delays.",
    'Koi delay nahi hoga.', '20 October tak usse pahle koi delay nahi hoga.',
    'Deri nahin hogi.', 'कोई देरी नहीं होगी।', 'विलंब नहीं होगा।',
    'The refund is not overdue.', 'The refund is not yet delayed.',
    'The refund remains on time.', 'Abhi delay nahi hai.', 'देरी नहीं है।'])
def test_unverified_projection_does_not_prove_timely_settlement(text):
    _, _, facts = context()
    with pytest.raises(ValueError, match='^unverified_refund_timeliness$'):
        check_public_refund_timeliness(text, facts)


@pytest.mark.parametrize('text', [
    'The expected latest date is 10 October 2026, based on the supplied initiation date.',
    'If it has not arrived after the expected window, ask support to review it.',
    'There may be a delay.', 'It may not be delayed.',
    'I cannot guarantee that there will be no delay.',
    'The policy does not guarantee that there will be no delay.',
    'There is no guarantee that there will be no delay.',
    'There is no guarantee that your refund will not be delayed.',
    'I cannot confirm that the refund is not overdue.',
    'I cannot confirm that your refund will not be delayed.',
    'There will be no delay is not guaranteed.',
    'Koi delay nahi hoga ki guarantee nahi de sakti.',
    'क्या कोई देरी नहीं होगी?', 'Is the refund not overdue?',
    'I cannot confirm that it is not overdue.'])
def test_estimates_uncertainty_and_questions_are_preserved(text):
    check_public_refund_timeliness(text, context()[2])


def test_reference_date_changes_only_the_present_status_consistency_check():
    facts = context()[2]
    facts['reference_date'] = '2026-10-08'
    facts['calculations'][0]['inputs']['reference_date'] = facts['reference_date']
    check_public_refund_timeliness('The refund is not overdue.', facts)
    with pytest.raises(ValueError, match='unverified_refund_timeliness'):
        check_public_refund_timeliness('There will be no delay.', facts)
    facts['reference_date'] = '2026-10-20'
    facts['calculations'][0]['inputs']['reference_date'] = facts['reference_date']
    with pytest.raises(ValueError, match='unverified_refund_timeliness'):
        check_public_refund_timeliness('The refund is not overdue.', facts)


@pytest.mark.parametrize('mutation', ['no_claim', 'no_calculation', 'verified_record', 'ambiguous', 'mismatched_input'])
def test_guard_does_not_infer_public_projection_from_unrelated_inputs(mutation):
    facts = context()[2]
    if mutation == 'no_claim':facts.pop('customer_provided_refund_claim')
    elif mutation == 'no_calculation':facts['calculations'] = []
    elif mutation == 'verified_record':facts['verified_order'] = {'status': 'delivered'}
    elif mutation == 'ambiguous':
        other = copy.deepcopy(facts['calculations'][0]);other['result']['latest_date'] = '2026-10-12';facts['calculations'].append(other)
    else:facts['calculations'][0]['inputs']['initiated_on'] = '2026-10-07'
    check_public_refund_timeliness('There will be no delay.', facts)


class Client:
    def __init__(self, *answers):self.answers = list(answers);self.calls = []
    def complete(self, system, user, **options):
        self.calls.append({'system': system, 'payload': json.loads(user)})
        return json.dumps({'answer': self.answers.pop(0), 'covered': True, 'needs_clarification': False})


def test_real_generation_boundary_repairs_without_injecting_a_business_answer():
    query, sources, facts = context()
    good = 'Using the supplied initiation date, the latest expected refund date is 10 October 2026.'
    client = Client(good + ' There will be no delay.', good)
    result = document_reply(client, query, 'en', sources, facts=facts, context_provenance=True)
    assert result['answer'] == good
    assert result['generation_attempts'] == 2
    assert result['repair_errors'] == ['unverified_refund_timeliness']
    assert client.calls[0]['payload']['source_text'] == sorted(sources, key=lambda row: row['id'])
    assert result['repair_mode'] == 'source_public_refund_projection'
    assert client.calls[1]['payload']['deterministic_facts']['refund_projection']['latest_expected_date'] == '2026-10-10'
    assert 'reference_date' not in client.calls[1]['payload']
    assert 'Do not confirm a transaction happened' in client.calls[1]['system']
    assert 'expected_answer' not in client.calls[1]['payload']


def test_repeated_unsupported_promise_is_rejected_after_one_bounded_repair():
    query, sources, facts = context()
    bad = 'The latest expected refund date is 10 October 2026. There will be no delay.'
    client = Client(bad, bad)
    with pytest.raises(ValueError) as error:
        document_reply(client, query, 'en', sources, facts=facts, context_provenance=True)
    assert len(client.calls) == 2
    assert error.value.diagnostics['validation_error'] == 'unverified_refund_timeliness'
    assert validation_code('unverified_refund_timeliness:private customer suffix') == 'unverified_refund_timeliness'


@pytest.mark.parametrize('field', ['calculations', 'inputs', 'result'])
def test_malformed_projection_does_not_create_a_clock_proof(field):
    facts = context()[2]
    if field == 'calculations':facts['calculations'] = None
    else:facts['calculations'][0][field] = None
    check_public_refund_timeliness('The refund is not overdue.', facts)
