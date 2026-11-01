"""Provider-neutral, bounded inference with settings-aware output caching."""
import hashlib
import json
import math
import os
import time
import tempfile
import threading
from datetime import timezone
from email.utils import parsedate_to_datetime
import requests
from .config import CACHE
from .response_runtime import remaining_seconds, local_inference_slot, InferenceBusy

class LLMUnavailable(RuntimeError):
    pass

def _retry_after_seconds(value):
    """Read server delay without storing headers or credential-bearing details."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    try:
        seconds = float(value)
    except ValueError:
        try:
            deadline = parsedate_to_datetime(value)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            seconds = max(0.0, deadline.timestamp() - time.time())
        except (TypeError, ValueError, OverflowError, OSError):
            return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


class LLM:
    def __init__(self, provider=None, model=None):
        self.provider = provider or os.getenv('LLM_PROVIDER', 'ollama')
        self.model = model or os.getenv('LLM_MODEL', 'qwen3:4b-instruct')
        self._thread = threading.local()
        self.last_provider = ''
        self.last_metrics = {}
        self.cache = CACHE / 'llm'
        self.cache.mkdir(exist_ok=True)

    @property
    def last_metrics(self):
        return getattr(self._thread, 'metrics', {})

    @last_metrics.setter
    def last_metrics(self, value):
        self._thread.metrics = value

    @property
    def last_provider(self):
        return getattr(self._thread, 'provider', '')

    @last_provider.setter
    def last_provider(self, value):
        self._thread.provider = value

    def complete(self, system, user, json_mode=False, cache=True, *, max_tokens=240,
                 timeout=None, attempts=1, schema=None):
        started = time.perf_counter()
        read_timeout = float(timeout or os.getenv('LLM_TIMEOUT', '120'))
        choices = [(self.provider, self.model, os.getenv('LLM_BASE_URL', 'http://127.0.0.1:11434'), os.getenv('LLM_API_KEY', ''))]
        if os.getenv('LLM_FALLBACK_PROVIDER'):
            choices.append((os.environ['LLM_FALLBACK_PROVIDER'], os.getenv('LLM_FALLBACK_MODEL', ''), os.getenv('LLM_FALLBACK_BASE_URL', ''), os.getenv('LLM_FALLBACK_API_KEY', '')))
        self.last_metrics = {'cache_hit': False, 'attempts': 0, 'http_attempts': 0,
                             'http_statuses': [], 'rate_limit_events': 0,
                             'rate_limit_retries': 0, 'rate_limit_wait_ms': 0.0,
                             'rate_limit_planned_wait_ms': 0.0}
        planned_wait = 0.0

        def send(url, **options):
            remaining = remaining_seconds()
            if remaining is not None:
                if remaining <= 0:
                    self.last_metrics.update(timed_out=True, budget_exhausted=True, unavailable=True)
                    raise LLMUnavailable('Response time budget exhausted.')
                connect = min(2.0, remaining / 4)
                options['timeout'] = (connect, min(read_timeout, remaining - connect))
            self.last_metrics['attempts'] += 1
            self.last_metrics['http_attempts'] += 1
            response = requests.post(url, **options)
            status = getattr(response, 'status_code', None)
            if type(status) is int:
                self.last_metrics['http_statuses'].append(status)
                self.last_metrics['last_http_status'] = status
            return response

        def throttled(response):
            nonlocal planned_wait
            self.last_metrics['rate_limit_events'] += 1
            self.last_metrics['rate_limit_last_http_status'] = 429
            retries = self.last_metrics['rate_limit_retries']
            headers = getattr(response, 'headers', {}) or {}
            delay = _retry_after_seconds(headers.get('Retry-After', headers.get('retry-after')))
            if delay is None:
                delay = float(2 ** retries)
            reason = 'retry_limit' if retries >= 3 else 'wait_budget' if delay > 60.0 - planned_wait else None
            if reason:
                self.last_metrics.update(rate_limit_exhausted=reason, unavailable=True,
                                         wall_ms=round(1000*(time.perf_counter()-started), 2))
                # Do not bypass a server delay through an outer attempt or a
                # fallback choice when this complete() call cannot honor it.
                raise LLMUnavailable('LLM rate limit exceeded the bounded retry budget; no response fabricated.')
            remaining = remaining_seconds()
            if remaining is not None and delay >= remaining:
                self.last_metrics.update(timed_out=True, budget_exhausted=True, unavailable=True)
                raise LLMUnavailable('Response time budget exhausted during rate limiting.')
            planned_wait += delay
            self.last_metrics['rate_limit_retries'] += 1
            self.last_metrics['rate_limit_planned_wait_ms'] = round(1000 * planned_wait, 2)
            waiting = time.perf_counter()
            try:
                time.sleep(delay)
            finally:
                measured = max(0.0, time.perf_counter() - waiting)
                self.last_metrics['rate_limit_wait_ms'] = round(
                    self.last_metrics['rate_limit_wait_ms'] + 1000 * measured, 2)

        for provider, model, base, key in choices:
            settings = {'provider': provider, 'model': model, 'base': base, 'temperature': 0,
                        'seed': 42, 'max_tokens': max_tokens, 'num_ctx': 4096,
                        'format': schema or ('json' if json_mode else None)}
            digest = hashlib.sha256(json.dumps([settings, system, user], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            path = self.cache / (digest + '.json')
            if cache and path.exists():
                try:
                    value = json.loads(path.read_text(encoding='utf-8'))
                    self.last_provider = value['provider']
                    self.last_metrics.update(cache_hit=True, wall_ms=round(1000*(time.perf_counter()-started), 2), provider=self.last_provider)
                    return value['text']
                except (ValueError, KeyError, OSError):
                    pass
            for attempt in range(attempts):
                try:
                    messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
                    if provider == 'ollama':
                        payload = {'model': model, 'messages': messages, 'stream': False, 'think': False,
                                   'keep_alive': '10m', 'options': {'temperature': 0, 'seed': 42, 'num_predict': max_tokens, 'num_ctx': 4096}}
                        if json_mode or schema:
                            payload['format'] = schema or 'json'
                        try:
                            with local_inference_slot(base):
                                response = send(base.rstrip('/')+'/api/chat', json=payload, timeout=(2, read_timeout))
                        except InferenceBusy:
                            self.last_metrics.update(busy=True, unavailable=True,
                                wall_ms=round(1000*(time.perf_counter()-started), 2))
                            raise LLMUnavailable('The local model is busy; please retry shortly.') from None
                    else:
                        payload = {'model': model, 'messages': messages, 'temperature': 0, 'max_tokens': max_tokens}
                        if json_mode or schema:
                            payload['response_format'] = {'type': 'json_object'}
                        while True:
                            response = send(base.rstrip('/')+'/chat/completions', headers={'Authorization': 'Bearer '+key}, json=payload, timeout=(2, read_timeout))
                            if getattr(response, 'status_code', None) != 429:
                                break
                            throttled(response)
                    response.raise_for_status()
                    data = response.json()
                    result = data['message']['content'] if provider == 'ollama' else data['choices'][0]['message']['content']
                    if not isinstance(result, str) or not result.strip():
                        raise ValueError('Empty model output')
                    self.last_provider = provider+':'+model
                    self.last_metrics.update(provider=self.last_provider, wall_ms=round(1000*(time.perf_counter()-started), 2))
                    for name in ('load_duration', 'prompt_eval_duration', 'eval_duration'):
                        if name in data:
                            self.last_metrics[name.replace('_duration', '_ms')] = round(data[name]/1e6, 2)
                    for name in ('prompt_eval_count', 'eval_count', 'done_reason'):
                        if name in data:
                            self.last_metrics[name] = data[name]
                    if cache:
                        temporary = None
                        try:
                            with tempfile.NamedTemporaryFile(dir=self.cache, suffix='.part', mode='w', encoding='utf-8', delete=False) as handle:
                                temporary = handle.name
                                json.dump({'text': result, 'provider': self.last_provider}, handle, ensure_ascii=False)
                            os.replace(temporary, path)
                        except OSError:
                            # A cache failure must not discard an actual validated response.
                            pass
                        finally:
                            if temporary:
                                try:
                                    os.unlink(temporary)
                                except OSError:
                                    pass
                    return result
                except (requests.RequestException, KeyError, ValueError) as exc:
                    if isinstance(exc, requests.Timeout):
                        self.last_metrics['timed_out'] = True
                    if attempt+1 < attempts:
                        time.sleep(min(2**attempt, 4))
        self.last_metrics.update(wall_ms=round(1000*(time.perf_counter()-started), 2), unavailable=True)
        raise LLMUnavailable('LLM unavailable or timed out; no response fabricated.')

BASELINE_SYSTEM = """You are ZentroMart's AI support assistant. You have no company documents or order access. Be honest about uncertainty, never invent completed actions or expose personal data. Answer in the customer's language in 2-3 sentences and disclose that you are an AI assistant. Return JSON with decision (answer, clarify, refuse, escalate) and answer. No markdown."""

def baseline(question, llm=None):
    client = llm or LLM()
    try:
        data = json.loads(client.complete(BASELINE_SYSTEM, question, json_mode=True))
        answer = str(data.get('answer', ''))
        if not answer:
            raise ValueError('Empty answer')
        if not any(x in answer.lower() for x in ['ai assistant', 'ai support', 'artificial intelligence', 'एआई', 'कृत्रिम बुद्धिमत्ता']):
            from .normalize import language
            lang = language(question)
            answer = {'en': "I'm ZentroMart's AI support assistant. ", 'hi': 'मैं ZentroMart की AI सहायता सहायक हूँ। ', 'hi-en': 'Main ZentroMart ki AI support assistant hoon. '}[lang]+answer
        return {'answer': answer, 'decision': data.get('decision', 'answer'), 'intent': 'baseline', 'retrieved_chunk_ids': [], 'sources': [], 'tool_calls': [], 'provider': client.last_provider, 'llm': client.last_metrics, 'mode': 'prompt_only'}
    except (LLMUnavailable, ValueError):
        return {'answer': '', 'decision': 'error', 'intent': 'baseline', 'retrieved_chunk_ids': [], 'sources': [], 'tool_calls': [], 'mode': 'blocked', 'error': 'LLM unavailable or invalid JSON'}
