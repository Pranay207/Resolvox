"""Explicit hosted application settings; local evaluation settings stay separate."""
from pathlib import Path
from dotenv import dotenv_values

GROQ_BASE = 'https://api.groq.com/openai/v1'


def hosted_settings(root):
    values = dotenv_values(Path(root) / '.env.hosted')
    model = values.get('LLM_MODEL') or 'openai/gpt-oss-20b'
    if model not in {'openai/gpt-oss-120b', 'openai/gpt-oss-20b'}:
        raise ValueError('Choose a supported GPT-OSS model in .env.hosted.')
    effort = values.get('LLM_REASONING_EFFORT') or 'low'
    if effort not in {'low', 'medium', 'high'}:
        raise ValueError('LLM_REASONING_EFFORT must be low, medium or high.')
    env = dict(LLM_PROVIDER='compatible', LLM_BASE_URL=GROQ_BASE,
               LLM_MODEL=model, LLM_REASONING_EFFORT=effort,
               LLM_STRUCTURED_OUTPUT='json_schema', RAG_CLAIM_AUDIT='true',
               LLM_TIMEOUT='15', RAG_LLM_TIMEOUT='15', RAG_RESPONSE_BUDGET='30',
               UI_RESPONSE_BUDGET='45', COMPOSE_WITH_LLM='true')
    # An explicit Groq profile must not leak a key to another endpoint or
    # silently fall back to an unapproved/slower answer service.
    for name in ('LLM_FALLBACK_PROVIDER', 'LLM_FALLBACK_BASE_URL',
                 'LLM_FALLBACK_MODEL', 'LLM_FALLBACK_API_KEY'):
        env[name] = ''
    return env


def hosted_environment(root, inherited):
    values = dotenv_values(Path(root) / '.env.hosted')
    key = values.get('LLM_API_KEY') or values.get('GROQ_API_KEY')
    if not isinstance(key, str) or not key.strip():
        raise ValueError('Add LLM_API_KEY to the ignored .env.hosted file to use --hosted.')
    return {**inherited, **hosted_settings(root), 'LLM_API_KEY': key.strip()}
