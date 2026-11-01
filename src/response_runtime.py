"""Per-request deadlines, progress and local inference admission control."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import math
import os
import threading
import time

_scope = ContextVar('resolvox_response_scope', default=None)
_gates = {}
_gates_lock = threading.Lock()


class InferenceBusy(RuntimeError):
    pass


def configured_budget(name, default=180):
    try:
        seconds = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        raise ValueError('invalid_response_budget') from None
    if not math.isfinite(seconds) or seconds <= 0 or seconds > 600:
        raise ValueError('invalid_response_budget')
    return seconds


@contextmanager
def response_scope(seconds, progress=None):
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('invalid_response_budget')
    parent = _scope.get()
    deadline = time.monotonic() + seconds
    if parent:
        deadline = min(deadline, parent['deadline'])
        if progress is None:
            progress = parent['progress']
    token = _scope.set({'deadline': deadline, 'progress': progress})
    try:
        yield
    finally:
        _scope.reset(token)


def remaining_seconds():
    scope = _scope.get()
    return None if scope is None else max(0.0, scope['deadline'] - time.monotonic())


def progress(stage):
    scope = _scope.get()
    if scope and scope['progress']:
        scope['progress'](stage)


def bounded_generation(function):
    @wraps(function)
    def bounded(*args, **kwargs):
        with response_scope(configured_budget('RAG_RESPONSE_BUDGET')):
            return function(*args, **kwargs)
    return bounded


@contextmanager
def local_inference_slot(endpoint):
    # The laptop runs one local generation at a time. Reject excess work
    # promptly instead of letting another browser session wait in its queue.
    with _gates_lock:
        gate = _gates.setdefault(endpoint.rstrip('/'), threading.Lock())
    if not gate.acquire(blocking=False):
        raise InferenceBusy('local_model_busy')
    try:
        yield
    finally:
        gate.release()


def service_failure(generation):
    if generation.get('failure_kind') != 'model_unavailable':
        return None
    metrics = generation.get('attempt_metrics', [])
    if any(item.get('busy') is True for item in metrics):
        return 'busy'
    if any(item.get('timed_out') is True or item.get('budget_exhausted') is True for item in metrics):
        return 'timeout'
    return 'unavailable'


def service_message(code, language):
    messages = {
        'busy': {
            'en': 'The local assistant is handling another message. Please try again shortly.',
            'hi': 'स्थानीय सहायक अभी दूसरे संदेश का जवाब दे रहा है। कृपया थोड़ी देर बाद फिर कोशिश करें।',
            'hi-en': 'Local assistant abhi doosre message ka jawab de raha hai. Kripya thodi der baad phir try karein.',
        },
        'timeout': {
            'en': 'Preparing this reply took too long. Please try again or ask a shorter question; I have not confirmed an answer.',
            'hi': 'इस जवाब को तैयार करने में अधिक समय लगा। कृपया फिर कोशिश करें या छोटा सवाल पूछें; अभी कोई उत्तर पुष्ट नहीं हुआ है।',
            'hi-en': 'Is jawab ko taiyar karne mein zyada samay laga. Kripya phir try karein ya chhota sawal poochhein; abhi jawab confirm nahi hua hai.',
        },
        'unavailable': {
            'en': 'The answer service is unavailable right now. Please try again shortly.',
            'hi': 'उत्तर सेवा अभी उपलब्ध नहीं है। कृपया थोड़ी देर बाद फिर कोशिश करें।',
            'hi-en': 'Jawab ki service abhi available nahi hai. Kripya thodi der baad phir try karein.',
        },
    }
    return messages[code][language]
