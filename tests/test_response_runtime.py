"""Request budgets and admission control without external services."""
import json
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
import requests

from src import llm, response_runtime as runtime


class Response:
    status_code = 200
    headers = {}
    def raise_for_status(self):
        pass
    def json(self):
        return {'message': {'content': '{"answer":"synthetic"}'}}


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, 'CACHE', tmp_path)
    monkeypatch.setenv('LLM_BASE_URL', 'http://local-model.invalid:11434')
    monkeypatch.delenv('LLM_FALLBACK_PROVIDER', raising=False)
    now = [10.0]
    monkeypatch.setattr(runtime.time, 'monotonic', lambda: now[0])
    return llm.LLM(provider='ollama', model='synthetic'), now


def test_one_deadline_is_shared_by_generation_and_repair(monkeypatch, configured):
    client, now = configured
    calls = []
    def post(url, **options):
        calls.append(options['timeout'])
        now[0] += 6
        return Response()
    monkeypatch.setattr(llm.requests, 'post', post)
    with runtime.response_scope(10):
        client.complete('s', 'first', cache=False, timeout=600)
        client.complete('s', 'repair', cache=False, timeout=600)
        with pytest.raises(llm.LLMUnavailable, match='budget'):
            client.complete('s', 'third', cache=False, timeout=600)
    assert calls == [(2.0, 8.0), (1.0, 3.0)]
    assert client.last_metrics['budget_exhausted'] is True
    assert client.last_metrics['http_attempts'] == 0
    assert runtime.remaining_seconds() is None


def test_nested_scope_never_extends_parent_deadline(configured):
    _, now = configured
    events = []
    with runtime.response_scope(8, events.append):
        now[0] += 3
        with runtime.response_scope(100):
            assert runtime.remaining_seconds() == 5
            runtime.progress('repairing')
    assert events == ['repairing']


def test_busy_local_model_fails_promptly_without_http(monkeypatch, configured):
    client, _ = configured
    monkeypatch.setattr(llm.requests, 'post', lambda *a, **k: pytest.fail('Busy requests must not be queued'))
    with runtime.local_inference_slot('http://local-model.invalid:11434'):
        with pytest.raises(llm.LLMUnavailable, match='busy'):
            client.complete('s', 'u', cache=False)
    assert client.last_metrics['busy'] is True
    assert client.last_metrics['http_attempts'] == 0


def test_transport_timeout_is_distinguished_without_exception_details(monkeypatch, configured):
    client, _ = configured
    def fail(*a, **k):
        raise requests.ReadTimeout('private-provider-detail')
    monkeypatch.setattr(llm.requests, 'post', fail)
    with pytest.raises(llm.LLMUnavailable):
        client.complete('s', 'u', cache=False)
    assert client.last_metrics['timed_out'] is True
    assert 'private-provider-detail' not in json.dumps(client.last_metrics)


def test_shared_client_metrics_are_isolated_between_threads(configured):
    client, _ = configured
    barrier = threading.Barrier(2)
    def task(number):
        client.last_metrics = {'request': number}
        client.last_provider = str(number)
        barrier.wait(timeout=3)
        return client.last_metrics, client.last_provider
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(task, [1, 2]))
    assert first == ({'request': 1}, '1')
    assert second == ({'request': 2}, '2')
    assert client.last_metrics == {}


def test_cache_write_failure_does_not_drop_a_real_response(monkeypatch, configured):
    client, _ = configured
    monkeypatch.setattr(llm.requests, 'post', lambda *a, **k: Response())
    def fail(*a):
        raise PermissionError('synthetic filesystem denial')
    monkeypatch.setattr(llm.os, 'replace', fail)
    assert client.complete('s', 'u') == '{"answer":"synthetic"}'
    assert not list(client.cache.glob('*.part'))


@pytest.mark.parametrize('value', ['nan', 'inf', '0', '-1', '601', 'bad'])
def test_invalid_budgets_are_rejected(monkeypatch, value):
    monkeypatch.setenv('UI_RESPONSE_BUDGET', value)
    with pytest.raises(ValueError, match='invalid_response_budget'):
        runtime.configured_budget('UI_RESPONSE_BUDGET')


@pytest.mark.parametrize('code,metric', [('busy', 'busy'), ('timeout', 'timed_out'), ('timeout', 'budget_exhausted')])
def test_model_service_failures_do_not_claim_missing_policy(code, metric):
    generation = {'failure_kind': 'model_unavailable', 'attempt_metrics': [{metric: True}]}
    assert runtime.service_failure(generation) == code
    assert 'document' not in runtime.service_message(code, 'en')
    assert runtime.service_failure({'failure_kind': 'validation'}) is None


def test_speech_retry_cannot_sleep_beyond_its_total_budget(monkeypatch):
    from src.voice import GnaniVoice, VoiceError
    now = [10.0]
    monkeypatch.setattr(runtime.time, 'monotonic', lambda: now[0])
    monkeypatch.setenv('SPEECH_REQUEST_BUDGET', '4')
    voice = GnaniVoice('synthetic-placeholder', sleep=lambda _: pytest.fail('Must not sleep beyond budget'))
    calls = []
    def post(*args, **kwargs):
        calls.append(kwargs['timeout'])
        now[0] += 3.5
        return type('Limited', (), {'status_code':503})()
    monkeypatch.setattr(voice.session, 'post', post)
    with pytest.raises(VoiceError, match='time budget'):
        voice._request('/synthetic')
    assert calls == [(1.0, 3.0)]


def test_speech_respects_the_remaining_shared_response_budget(monkeypatch):
    from src.voice import GnaniVoice, VoiceError
    now = [10.0]
    monkeypatch.setattr(runtime.time, 'monotonic', lambda: now[0])
    voice = GnaniVoice('synthetic-placeholder')
    calls = []
    def post(*args, **kwargs):
        calls.append(kwargs['timeout'])
        return type('Success', (), {'status_code':200})()
    monkeypatch.setattr(voice.session, 'post', post)
    with runtime.response_scope(4):
        now[0] += 3
        voice._request('/synthetic')
        now[0] += 1
        with pytest.raises(VoiceError, match='time budget'):
            voice._request('/synthetic')
    assert calls == [(0.25, 0.75)]


def test_request_releases_windows_execution_hold_after_error(monkeypatch):
    calls=[]
    def state(flags):
        calls.append(flags)
        return 0x80000000
    monkeypatch.setattr(runtime,'_set_execution_state',state)
    with pytest.raises(RuntimeError):
        with runtime.response_scope(5):
            raise RuntimeError('synthetic request failure')
    assert calls==[0x80000001,0x80000000]
    assert runtime.remaining_seconds() is None


def test_nested_generation_uses_only_one_execution_hold(monkeypatch):
    calls=[]
    monkeypatch.setattr(runtime,'_set_execution_state',lambda flags:calls.append(flags) or 0x80000000)
    with runtime.response_scope(10):
        with runtime.response_scope(5):
            assert calls==[0x80000001]
    assert calls==[0x80000001,0x80000000]


def test_unsupported_execution_hold_does_not_break_inference(monkeypatch):
    monkeypatch.setattr(runtime,'_set_execution_state',lambda flags:None)
    with runtime.response_scope(5):
        assert runtime.remaining_seconds()>0
