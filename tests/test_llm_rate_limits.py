"""Real rate-limit control flow with fake HTTP responses/clock; no API calls."""
from datetime import datetime, timezone
from email.utils import format_datetime
import json

import pytest
import requests

from src import llm


class Clock:
    def __init__(self):
        self.elapsed = 0.0
        self.epoch = 2_000_000_000.0
        self.waits = []
        self.oversleep = 0.0

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.elapsed += seconds + self.oversleep

    def perf_counter(self):
        return self.elapsed

    def time(self):
        return self.epoch + self.elapsed


class Response:
    def __init__(self, status=200, retry_after=None, *, text='{"answer":"synthetic"}', lower_header=False):
        self.status_code = status
        self.headers = {} if retry_after is None else {('retry-after' if lower_header else 'Retry-After'): retry_after}
        self.text = text
        self.json_calls = 0

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError('Synthetic HTTP error', response=self)

    def json(self):
        self.json_calls += 1
        assert self.status_code == 200, '429 bodies must never become model output'
        return {'choices': [{'message': {'content': self.text}}], 'message': {'content': self.text}}


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, 'CACHE', tmp_path)
    for name in ('LLM_FALLBACK_PROVIDER', 'LLM_FALLBACK_MODEL', 'LLM_FALLBACK_BASE_URL', 'LLM_FALLBACK_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('LLM_BASE_URL', 'https://unit.invalid/v1')
    monkeypatch.setenv('LLM_API_KEY', 'unit-test-credential-never-recorded')
    clock = Clock()
    monkeypatch.setattr(llm.time, 'sleep', clock.sleep)
    monkeypatch.setattr(llm.time, 'time', clock.time)
    monkeypatch.setattr(llm.time, 'perf_counter', clock.perf_counter)
    client = llm.LLM(provider='compatible', model='synthetic-model')
    return client, clock


def script(monkeypatch, *responses):
    pending = list(responses)
    calls = []
    def post(url, **options):
        calls.append({'url': url, **options})
        assert pending, 'Unbounded/early extra HTTP attempt'
        response = pending.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr(llm.requests, 'post', post)
    return calls


def complete(client, **options):
    return client.complete('Synthetic system', 'Synthetic user', json_mode=True, max_tokens=700, timeout=5, **options)


def test_numeric_retry_after_honored_with_identical_request_and_safe_metrics(monkeypatch, configured):
    client, clock = configured
    limited = Response(429, '2.25')
    calls = script(monkeypatch, limited, Response())
    assert complete(client) == '{"answer":"synthetic"}'
    assert clock.waits == [2.25] and len(calls) == 2
    assert calls[0] == calls[1]
    assert calls[0]['json']['max_tokens'] == 700
    assert calls[0]['json']['response_format'] == {'type': 'json_object'}
    assert calls[0]['timeout'] == (2, 5.0)
    assert limited.json_calls == 0
    metrics = client.last_metrics
    assert metrics['http_attempts'] == metrics['attempts'] == 2
    assert metrics['http_statuses'] == [429, 200]
    assert metrics['rate_limit_last_http_status'] == 429 and metrics['last_http_status'] == 200
    assert metrics['rate_limit_events'] == metrics['rate_limit_retries'] == 1
    assert metrics['rate_limit_wait_ms'] == metrics['rate_limit_planned_wait_ms'] == 2250.0
    encoded = json.dumps(metrics)
    assert 'credential' not in encoded and 'Authorization' not in encoded and 'Retry-After' not in encoded
    assert 'unit.invalid' not in encoded


def test_http_date_delay_uses_current_utc_time(monkeypatch, configured):
    client, clock = configured
    header = format_datetime(datetime.fromtimestamp(clock.epoch + 17, timezone.utc), usegmt=True)
    calls = script(monkeypatch, Response(429, header), Response())
    complete(client)
    assert len(calls) == 2 and clock.waits == [17.0]
    assert client.last_metrics['rate_limit_planned_wait_ms'] == 17000.0


def test_past_http_date_means_zero_wait_but_still_bounded_retry(monkeypatch, configured):
    client, clock = configured
    header = format_datetime(datetime.fromtimestamp(clock.epoch - 17, timezone.utc), usegmt=True)
    calls = script(monkeypatch, Response(429, header), Response())
    complete(client)
    assert len(calls) == 2 and clock.waits == [0.0]
    assert client.last_metrics['rate_limit_retries'] == 1


@pytest.mark.parametrize('header', [None, '', 'invalid', '-3', 'nan', 'inf', 'Infinity'])
def test_missing_or_invalid_delay_uses_safe_exponential_backoff(monkeypatch, configured, header):
    client, clock = configured
    calls = script(monkeypatch, Response(429, header), Response(429, header), Response(429, header), Response())
    complete(client)
    assert len(calls) == 4 and clock.waits == [1.0, 2.0, 4.0]
    assert client.last_metrics['rate_limit_retries'] == 3
    assert client.last_metrics['rate_limit_planned_wait_ms'] == 7000.0


def test_lowercase_header_is_accepted(monkeypatch, configured):
    client, clock = configured
    script(monkeypatch, Response(429, '3', lower_header=True), Response())
    complete(client)
    assert clock.waits == [3.0]


def test_server_wait_larger_than_budget_never_retries_early_or_uses_outer_attempt(monkeypatch, configured):
    client, clock = configured
    monkeypatch.setenv('LLM_FALLBACK_PROVIDER', 'compatible')
    monkeypatch.setenv('LLM_FALLBACK_MODEL', 'unused-fallback')
    monkeypatch.setenv('LLM_FALLBACK_BASE_URL', 'https://fallback.invalid/v1')
    calls = script(monkeypatch, Response(429, '61'))
    with pytest.raises(llm.LLMUnavailable, match='rate limit'):
        complete(client, attempts=8)
    assert len(calls) == 1 and clock.waits == []
    assert client.last_metrics['rate_limit_exhausted'] == 'wait_budget'
    assert client.last_metrics['rate_limit_retries'] == 0
    assert client.last_metrics['unavailable'] is True
    assert not list(client.cache.iterdir())


def test_remaining_budget_is_global_for_complete_call(monkeypatch, configured):
    client, clock = configured
    calls = script(monkeypatch, Response(429, '30'), Response(429, '31'))
    with pytest.raises(llm.LLMUnavailable):
        complete(client, attempts=5)
    assert len(calls) == 2 and clock.waits == [30.0]
    assert client.last_metrics['rate_limit_planned_wait_ms'] == 30000.0
    assert client.last_metrics['rate_limit_events'] == 2
    assert client.last_metrics['rate_limit_exhausted'] == 'wait_budget'


def test_exact_total_budget_is_honored_before_success(monkeypatch, configured):
    client, clock = configured
    calls = script(monkeypatch, Response(429, '20'), Response(429, '20'), Response(429, '20'), Response())
    complete(client)
    assert len(calls) == 4 and clock.waits == [20.0, 20.0, 20.0]
    assert client.last_metrics['rate_limit_planned_wait_ms'] == 60000.0


def test_three_retry_cap_applies_even_for_zero_delay_and_many_outer_attempts(monkeypatch, configured):
    client, clock = configured
    calls = script(monkeypatch, *[Response(429, '0') for _ in range(4)])
    with pytest.raises(llm.LLMUnavailable):
        complete(client, attempts=9)
    assert len(calls) == 4 and clock.waits == [0.0, 0.0, 0.0]
    assert client.last_metrics['rate_limit_events'] == 4
    assert client.last_metrics['rate_limit_retries'] == 3
    assert client.last_metrics['rate_limit_exhausted'] == 'retry_limit'


def test_measured_wait_is_recorded_separately_from_planned_wait(monkeypatch, configured):
    client, clock = configured
    clock.oversleep = .125
    script(monkeypatch, Response(429, '1'), Response())
    complete(client)
    assert client.last_metrics['rate_limit_planned_wait_ms'] == 1000.0
    assert client.last_metrics['rate_limit_wait_ms'] == 1125.0


def test_cache_hit_does_not_request_or_wait_and_resets_per_call_metrics(monkeypatch, configured):
    client, clock = configured
    calls = script(monkeypatch, Response(429, '1'), Response())
    first = complete(client)
    waits = list(clock.waits)
    assert complete(client) == first
    assert len(calls) == 2 and clock.waits == waits
    assert client.last_metrics['cache_hit'] is True
    assert client.last_metrics['attempts'] == client.last_metrics['http_attempts'] == 0
    assert client.last_metrics['rate_limit_events'] == client.last_metrics['rate_limit_retries'] == 0
    assert client.last_metrics['rate_limit_wait_ms'] == 0.0
    assert client.last_metrics['http_statuses'] == []


def test_cache_false_still_retries_but_does_not_persist(monkeypatch, configured):
    client, clock = configured
    calls = script(monkeypatch, Response(429, '1'), Response())
    complete(client, cache=False)
    assert len(calls) == 2 and clock.waits == [1.0]
    assert not list(client.cache.iterdir())


def test_non429_default_failure_keeps_single_attempt_no_new_wait(monkeypatch, configured):
    client, clock = configured
    calls = script(monkeypatch, Response(503))
    with pytest.raises(llm.LLMUnavailable):
        complete(client)
    assert len(calls) == 1 and clock.waits == []
    assert client.last_metrics['http_statuses'] == [503]
    assert client.last_metrics['rate_limit_events'] == 0


def test_non429_existing_outer_retry_behavior_is_unchanged(monkeypatch, configured):
    client, clock = configured
    calls = script(monkeypatch, Response(503), Response())
    complete(client, attempts=2)
    assert len(calls) == 2 and clock.waits == [1]
    assert client.last_metrics['rate_limit_retries'] == 0
    assert client.last_metrics['rate_limit_planned_wait_ms'] == 0.0


def test_network_failure_remains_generic_and_does_not_record_exception_details(monkeypatch, configured):
    client, clock = configured
    calls = script(monkeypatch, requests.Timeout('secret-shaped synthetic detail'))
    with pytest.raises(llm.LLMUnavailable) as exc:
        complete(client)
    assert len(calls) == 1 and clock.waits == []
    assert 'secret-shaped' not in str(exc.value) + json.dumps(client.last_metrics)
    assert client.last_metrics['http_attempts'] == 1 and client.last_metrics['http_statuses'] == []


def test_ollama_behavior_does_not_gain_compatible_throttle_retries(monkeypatch, configured):
    client, clock = configured
    client.provider = 'ollama'
    calls = script(monkeypatch, Response(429, '10'))
    with pytest.raises(llm.LLMUnavailable):
        complete(client)
    assert len(calls) == 1 and clock.waits == []
    assert calls[0]['url'].endswith('/api/chat')
    assert client.last_metrics['rate_limit_events'] == 0
