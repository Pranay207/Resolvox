"""Provider-neutral, bounded inference with settings-aware output caching."""
import hashlib
import json
import os
import time
import requests
from .config import CACHE

class LLMUnavailable(RuntimeError):
    pass

class LLM:
    def __init__(self, provider=None, model=None):
        self.provider = provider or os.getenv('LLM_PROVIDER', 'ollama')
        self.model = model or os.getenv('LLM_MODEL', 'qwen3:1.7b')
        self.last_provider = ''
        self.last_metrics = {}
        self.cache = CACHE / 'llm'
        self.cache.mkdir(exist_ok=True)

    def complete(self, system, user, json_mode=False, cache=True, *, max_tokens=240,
                 timeout=None, attempts=1, schema=None):
        started = time.perf_counter()
        read_timeout = float(timeout or os.getenv('LLM_TIMEOUT', '30'))
        choices = [(self.provider, self.model, os.getenv('LLM_BASE_URL', 'http://127.0.0.1:11434'), os.getenv('LLM_API_KEY', ''))]
        if os.getenv('LLM_FALLBACK_PROVIDER'):
            choices.append((os.environ['LLM_FALLBACK_PROVIDER'], os.getenv('LLM_FALLBACK_MODEL', ''), os.getenv('LLM_FALLBACK_BASE_URL', ''), os.getenv('LLM_FALLBACK_API_KEY', '')))
        self.last_metrics = {'cache_hit': False, 'attempts': 0}
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
                except (ValueError, KeyError):
                    pass
            for attempt in range(attempts):
                self.last_metrics['attempts'] += 1
                try:
                    messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
                    if provider == 'ollama':
                        payload = {'model': model, 'messages': messages, 'stream': False, 'think': False,
                                   'keep_alive': '10m', 'options': {'temperature': 0, 'seed': 42, 'num_predict': max_tokens, 'num_ctx': 4096}}
                        if json_mode or schema:
                            payload['format'] = schema or 'json'
                        response = requests.post(base.rstrip('/')+'/api/chat', json=payload, timeout=(2, read_timeout))
                    else:
                        payload = {'model': model, 'messages': messages, 'temperature': 0, 'max_tokens': max_tokens}
                        if json_mode or schema:
                            payload['response_format'] = {'type': 'json_object'}
                        response = requests.post(base.rstrip('/')+'/chat/completions', headers={'Authorization': 'Bearer '+key}, json=payload, timeout=(2, read_timeout))
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
                        path.write_text(json.dumps({'text': result, 'provider': self.last_provider}, ensure_ascii=False), encoding='utf-8')
                    return result
                except (requests.RequestException, KeyError, ValueError):
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
