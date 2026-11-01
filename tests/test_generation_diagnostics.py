"""Failure diagnostics are fake-client-only and never retain private content."""
import copy
import json
import socket

import pytest
import requests

import src.document_answers as document
from src.generation_diagnostics import (
    GenerationUnavailable, GenerationValidationError, failure_diagnostics,
    safe_attempt_metrics, validation_code,
)
from src.llm import LLMUnavailable


SOURCE = {'id': 'SYNTHETIC-DIAGNOSTICS',
          'text': 'Orchid returns allow 17 calendar days after delivery.',
          'doc_type': 'policy', 'status': 'current'}
PRIVATE = ('RAW_ANSWER_SENTINEL', 'PROMPT_SENTINEL', 'SOURCE_SENTINEL',
           'USER_SENTINEL', 'CREDENTIAL_SENTINEL', 'PROOF_SENTINEL', 'HEADER_SENTINEL')


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Diagnostics tests must not make network calls')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)


def metrics(number, *, cached=False):
    return {'cache_hit': cached, 'wall_ms': 12.5 * number,
            'http_attempts': 0 if cached else number, 'attempts': 0 if cached else number,
            'http_statuses': [] if cached else [200] * number,
            'last_http_status': 200, 'provider': PRIVATE[4],
            'prompt': PRIVATE[1], 'source_text': PRIVATE[2], 'answer': PRIVATE[0],
            'user': PRIVATE[3], 'private_proof': PRIVATE[5],
            'headers': {'Authorization': PRIVATE[6]}}


class Client:
    def __init__(self, *steps):
        self.steps = list(steps)
        self.calls = []
        self.last_metrics = {'wall_ms': 99999, 'headers': PRIVATE[-1]}

    def complete(self, system, user, json_mode=False, **options):
        self.calls.append({'system': system, 'payload': json.loads(user),
                           'json_mode': json_mode, 'options': options})
        assert self.steps, 'Unexpected third generation attempt'
        value, diagnostic = self.steps.pop(0)
        self.last_metrics = copy.deepcopy(diagnostic)
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, str) else json.dumps(value)


def run(client, *, context=True, private=False):
    return document.document_reply(client, 'What is the Orchid return window?', 'en',
                                   [SOURCE], context_provenance=context, private=private)


def context_answer():
    return {'answer': SOURCE['text'], 'covered': True, 'needs_clarification': False}


def assert_private_absent(value):
    serialized = json.dumps(value, allow_nan=False)
    assert all(token not in serialized for token in PRIVATE)
    assert all(key not in serialized for key in ('Authorization', 'source_text', 'previous_response'))


@pytest.mark.parametrize('context', [False, True])
def test_two_failed_validations_preserve_both_attempts_and_compatibility(context):
    client = Client(('not JSON ' + PRIVATE[0], metrics(1, cached=True)),
                    ('still not JSON ' + PRIVATE[0], metrics(2)))
    with pytest.raises(ValueError) as raised:
        run(client, context=context)
    assert isinstance(raised.value, GenerationValidationError)
    out = failure_diagnostics(raised.value)
    assert out['generation_failed'] is True and out['failure_kind'] == 'validation'
    assert out['repair_errors'] == ['invalid_json', 'invalid_json']
    assert out['generation_attempts'] == 2 and out['repair_attempted'] is True
    assert out['validation_error'] == 'invalid_json'
    assert out['attempt_metrics'][0]['cache_hit'] is True
    assert [item['wall_ms'] for item in out['attempt_metrics']] == [12.5, 25.0]
    assert [item['http_attempts'] for item in out['attempt_metrics']] == [0, 2]
    assert len(client.calls) == 2 and not client.steps
    assert client.calls[0]['options']['cache'] is True
    assert client.calls[1]['options']['cache'] is False
    assert all(call['options']['attempts'] == 1 for call in client.calls)
    assert client.calls[1]['payload']['repair_validation_error'] == 'invalid_json'
    assert_private_absent({'diagnostics': out, 'exception': str(raised.value)})


@pytest.mark.parametrize('repair', [False, True])
def test_provider_failure_metrics_include_the_failing_call_and_no_extra_attempt(repair):
    steps = [('not JSON', metrics(1, cached=True))] if repair else []
    steps.append((LLMUnavailable(PRIVATE[4]), metrics(2 if repair else 1)))
    client = Client(*steps)
    with pytest.raises(LLMUnavailable) as raised:
        run(client)
    assert isinstance(raised.value, GenerationUnavailable)
    out = failure_diagnostics(raised.value)
    assert out['failure_kind'] == 'model_unavailable'
    assert out['generation_attempts'] == 1 + int(repair)
    assert out['repair_attempted'] is repair
    assert out['repair_errors'] == (['invalid_json'] if repair else [])
    assert len(out['attempt_metrics']) == len(client.calls) == 1 + int(repair)
    assert out['attempt_metrics'][-1]['http_attempts'] == (2 if repair else 1)
    assert_private_absent({'diagnostics': out, 'exception': str(raised.value)})


def test_validator_history_retains_distinct_safe_codes():
    invalid_answer = dict(context_answer(), answer='The return window is 92 calendar days.')
    client = Client(('not JSON', metrics(1)), (invalid_answer, metrics(2)))
    with pytest.raises(GenerationValidationError) as raised:
        run(client)
    assert failure_diagnostics(raised.value)['repair_errors'] == ['invalid_json', 'unsupported_number']


@pytest.mark.parametrize('error,expected', [
    ('answer_constraint_missing:' + PRIVATE[5], 'answer_constraint_missing'),
    (PRIVATE[4], 'invalid_response'),
])
def test_dynamic_validator_suffix_and_unknown_exception_text_never_escape(monkeypatch, error, expected):
    def rejected(*args, **kwargs):
        raise ValueError(error)
    monkeypatch.setattr(document, '_validate', rejected)
    private_source = dict(SOURCE, text=SOURCE['text'] + ' ' + PRIVATE[2])
    client = Client(({'answer': PRIVATE[0]}, metrics(1)), ({'answer': PRIVATE[0]}, metrics(2)))
    with pytest.raises(GenerationValidationError) as raised:
        document.document_reply(client, PRIVATE[1] + ' ' + PRIVATE[3], 'en', [private_source],
                                facts={'private_proof': PRIVATE[5]}, private=True)
    out = failure_diagnostics(raised.value)
    assert out['repair_errors'] == [expected, expected]
    # Inference inputs retain the original bounded repair behavior.
    assert client.calls[1]['payload']['repair_validation_error'] == error
    assert all(call['options']['cache'] is False for call in client.calls)
    assert_private_absent({'diagnostics': out, 'exception': str(raised.value)})


def test_successful_answer_control_fields_and_existing_metrics_are_unchanged():
    client = Client((context_answer(), metrics(1)))
    out = run(client)
    assert out['answer'] == SOURCE['text'] and out['decision'] == 'answer'
    assert out['source_ids'] == [SOURCE['id']]
    assert out['generation_attempts'] == 1 and out['repair_attempted'] is False
    assert out['attempt_metrics'] == [metrics(1)]
    assert 'generation_failed' not in out


def test_successful_repair_does_not_change_existing_error_history_or_call_contract():
    client = Client(('not JSON', metrics(1)), (context_answer(), metrics(2)))
    out = run(client, private=True)
    assert out['answer'] == SOURCE['text'] and out['decision'] == 'answer'
    assert out['repair_errors'] == ['invalid_json'] and out['generation_attempts'] == 2
    assert out['attempt_metrics'] == [metrics(1), metrics(2)]
    assert all(call['options']['cache'] is False for call in client.calls)
    assert all(call['options']['attempts'] == 1 for call in client.calls)
    assert all(call['options']['max_tokens'] == 700 for call in client.calls)


@pytest.mark.parametrize('bad', [True, -1, float('nan'), float('inf'), 10 ** 1000, PRIVATE[4], {}],
                         ids=['bool', 'negative', 'nan', 'infinite', 'huge_integer', 'string', 'mapping'])
def test_untyped_nonfinite_negative_or_out_of_bounds_numbers_are_omitted(bad):
    out = safe_attempt_metrics({'wall_ms': bad, 'http_attempts': bad})
    assert out == {}


def test_metrics_and_error_history_have_bounded_size_and_defensive_copies():
    giant = metrics(1)
    giant['http_statuses'] = [429] * 1000
    exc = GenerationValidationError(['unsupported_number:' + PRIVATE[5]] * 1000, [giant] * 1000)
    out = failure_diagnostics(exc)
    assert len(out['repair_errors']) == len(out['attempt_metrics']) == out['generation_attempts'] == 2
    assert len(out['attempt_metrics'][0]['http_statuses']) == 16
    out['attempt_metrics'][0]['wall_ms'] = 100
    assert failure_diagnostics(exc)['attempt_metrics'][0]['wall_ms'] == 12.5
    assert_private_absent(failure_diagnostics(exc))


def test_pre_call_failure_has_zero_attempts_and_cannot_publish_stale_metrics():
    out = failure_diagnostics(ValueError(PRIVATE[4]), attempts=0, last_metrics=metrics(1))
    assert out['generation_attempts'] == 0 and out['repair_attempted'] is False
    assert out['attempt_metrics'] == [] and out['repair_errors'] == ['invalid_response']
    assert validation_code('unsupported_number:' + PRIVATE[5]) == 'unsupported_number'
    assert_private_absent(out)


def agent_resources(monkeypatch, client):
    import src.agent as module
    monkeypatch.setattr(module, 'LLM', lambda: client)
    return module, module.Resources(dense=False)


@pytest.mark.parametrize('repair', [False, True])
def test_agent_abstention_preserves_failed_diagnostics_without_private_metrics(monkeypatch, repair):
    steps = [('not JSON', metrics(1, cached=True))] if repair else []
    steps.append((LLMUnavailable(PRIVATE[4]), metrics(2 if repair else 1)))
    client = Client(*steps)
    module, resources = agent_resources(monkeypatch, client)
    out = module.Agent(resources, compose=True).respond('How many days can I return shoes?', 'en')
    assert out['composition'] == 'abstained_model_or_evidence'
    assert out['decision'] == 'refuse' and out['evidence_supported'] is False
    assert out['generation']['generation_attempts'] == 1 + int(repair)
    assert len(out['generation']['attempt_metrics']) == len(client.calls) == 1 + int(repair)
    assert out['validation_error'] == 'model_unavailable_or_invalid'
    assert out['llm']['http_attempts'] == (2 if repair else 1)
    assert_private_absent({'generation': out['generation'], 'llm': out['llm'],
                           'validation_error': out['validation_error'], 'answer': out['answer']})


def test_agent_pre_call_failure_has_zero_metrics_and_sanitized_error(monkeypatch):
    client = Client()
    module, resources = agent_resources(monkeypatch, client)
    def failed(*args, **kwargs):
        raise ValueError(PRIVATE[4])
    monkeypatch.setattr(module, 'document_reply', failed)
    out = module.Agent(resources, compose=True).respond('How many days can I return shoes?', 'en')
    assert out['composition'] == 'abstained_model_or_evidence'
    assert out['generation']['generation_attempts'] == 0
    assert out['generation']['attempt_metrics'] == [] and out['llm'] == {}
    assert out['timings']['llm_ms'] == 0 and not client.calls
    assert out['validation_error'] == 'invalid_response'
    assert_private_absent({'generation': out['generation'], 'validation_error': out['validation_error']})


def test_agent_two_validator_failures_keep_the_complete_sanitized_history(monkeypatch):
    invalid_answer = dict(context_answer(), answer='The return window is 92 calendar days.')
    client = Client(('not JSON', metrics(1, cached=True)), (invalid_answer, metrics(2)))
    module, resources = agent_resources(monkeypatch, client)
    out = module.Agent(resources, compose=True).respond('How many days can I return shoes?', 'en')
    assert out['composition'] == 'abstained_model_or_evidence' and out['decision'] == 'refuse'
    assert out['generation']['repair_errors'] == ['invalid_json', 'answer_constraint_missing']
    assert out['generation']['validation_error'] == 'answer_constraint_missing'
    assert out['validation_error'] == 'document_generation_failed:answer_constraint_missing'
    assert out['generation']['generation_attempts'] == 2 and len(client.calls) == 2
    assert_private_absent({'generation': out['generation'], 'llm': out['llm'],
                           'validation_error': out['validation_error'], 'answer': out['answer']})


@pytest.mark.parametrize('unavailable', [False, True])
def test_agent_handover_failure_keeps_ticket_outcome_and_diagnostics(monkeypatch, unavailable):
    final = LLMUnavailable(PRIVATE[4]) if unavailable else 'still not JSON ' + PRIVATE[0]
    client = Client(('not JSON', metrics(1)), (final, metrics(2)))
    module, resources = agent_resources(monkeypatch, client)
    class Tools:
        calls = 0
        def ticket(self, *args, **kwargs):
            self.calls += 1
            return {'created': True}, {'name': 'create_ticket', 'result': {'created': True}}
        def lookup(self, *args, **kwargs):
            pytest.fail('Unexpected private lookup')
    resources.tools = Tools()
    product = next(value for value in resources.data.products.values() if int(value['price_inr']) > 10000)
    out = module.Agent(resources, compose=True).respond('My ' + product['sku'] + ' is damaged.', 'en')
    assert out['composition'] == 'operational_handover_generation_failed'
    assert out['decision'] == 'escalate' and resources.tools.calls == 1
    assert 'A ticket has been created' in out['answer']
    assert out['generation']['tool_outcome_origin'] == 'actual_create_ticket_result'
    assert out['generation']['generation_attempts'] == 2
    assert out['generation']['repair_errors'] == (['invalid_json'] if unavailable else ['invalid_json', 'invalid_json'])
    assert len(out['generation']['attempt_metrics']) == len(client.calls) == 2
    assert_private_absent({'attempt_metrics': out['generation']['attempt_metrics'],
                           'llm': out['llm'], 'validation_error': out['validation_error']})



def test_new_bound_placement_window_code_is_retained_without_dynamic_private_suffix():
    code='unsupported_placement_exception_personal_window'
    exc=GenerationValidationError([code+':'+PRIVATE[5]]*2,[metrics(1),metrics(2)])
    out=failure_diagnostics(exc)
    assert out['repair_errors']==[code,code] and out['validation_error']==code
    assert out['generation_attempts']==2 and len(out['attempt_metrics'])==2
    assert_private_absent({'diagnostics':out,'exception':str(exc)})


@pytest.mark.parametrize('metric,code', [('busy','busy'),('timed_out','timeout'),('budget_exhausted','timeout')])
def test_agent_transport_failure_is_not_reported_as_missing_policy(monkeypatch, metric, code):
    diagnostic = metrics(1)
    diagnostic[metric] = True
    client = Client((LLMUnavailable(PRIVATE[4]), diagnostic))
    module, resources = agent_resources(monkeypatch, client)
    out = module.Agent(resources, compose=True).respond('How many days can I return shoes?', 'en')
    assert out['service_error'] == code
    assert out['evidence_supported'] is False
    assert 'retrieved documents' not in out['answer']
    assert not out['tool_calls']
    assert_private_absent(out['answer'])
