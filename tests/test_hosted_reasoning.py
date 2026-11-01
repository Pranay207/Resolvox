"""Reasoning settings must be provider-correct and cache-isolated."""
import json
from types import SimpleNamespace
import pytest
from src.llm import LLM, LLMUnavailable


def transport(monkeypatch):
    calls=[]
    def post(url,**options):
        payload=options['json'];calls.append(payload)
        content=json.dumps({'answer':payload.get('reasoning_effort','local')})
        data={'message':{'content':content}} if url.endswith('/api/chat') else {'choices':[{'message':{'content':content}}]}
        return SimpleNamespace(status_code=200,json=lambda:data,raise_for_status=lambda:None)
    monkeypatch.setattr('src.llm.requests.post',post)
    monkeypatch.setenv('LLM_FALLBACK_PROVIDER','')
    return calls


def test_hosted_reasoning_changes_do_not_reuse_another_effort_cache(tmp_path,monkeypatch):
    calls=transport(monkeypatch);client=LLM(provider='compatible',model='fixture');client.cache=tmp_path
    monkeypatch.setenv('LLM_BASE_URL','https://hosted.invalid/v1')
    for effort in ('low','high','low'):
        monkeypatch.setenv('LLM_REASONING_EFFORT',effort)
        assert json.loads(client.complete('Return JSON.','question',json_mode=True))['answer']==effort
    assert [call['reasoning_effort'] for call in calls]==['low','high']
    assert client.last_metrics['cache_hit'] is True


def test_ollama_never_receives_compatible_provider_reasoning_flag(monkeypatch):
    calls=transport(monkeypatch)
    monkeypatch.setenv('LLM_REASONING_EFFORT','not-an-ollama-option')
    client=LLM(provider='ollama',model='fixture')
    client.complete('Return JSON.','question',cache=False)
    assert 'reasoning_effort' not in calls[0]
    assert calls[0]['think'] is False


def test_invalid_hosted_effort_stops_before_any_request(monkeypatch):
    calls=transport(monkeypatch)
    monkeypatch.setenv('LLM_REASONING_EFFORT','invalid-private-setting')
    client=LLM(provider='compatible',model='fixture')
    with pytest.raises(LLMUnavailable) as caught:client.complete('Return JSON.','question',cache=False)
    assert not calls and 'invalid-private-setting' not in str(caught.value)


def test_explicit_hosted_schema_uses_constrained_output_without_changing_local_format(monkeypatch):
    calls=transport(monkeypatch)
    monkeypatch.setenv('LLM_STRUCTURED_OUTPUT','json_schema')
    schema={'type':'object','properties':{'answer':{'type':'string'}},'required':['answer'],'additionalProperties':False}
    LLM(provider='compatible',model='fixture').complete('Return JSON.','question',cache=False,schema=schema)
    assert calls[0]['response_format']=={'type':'json_schema','json_schema':{'name':'agent_response','strict':True,'schema':schema}}


def test_hosted_unicode_regex_preserves_language_restriction_and_original_schema(monkeypatch):
    import copy,re
    calls=transport(monkeypatch)
    monkeypatch.setenv('LLM_STRUCTURED_OUTPUT','json_schema')
    schema={'type':'object','properties':{'answer':{'type':'string','pattern':r'^[^\u0900-\u097f]*$'}},'required':['answer'],'additionalProperties':False}
    original=copy.deepcopy(schema)
    LLM(provider='compatible',model='fixture').complete('Return JSON.','question',cache=False,schema=schema)
    pattern=calls[0]['response_format']['json_schema']['schema']['properties']['answer']['pattern']
    assert schema==original and r'\u0900' not in pattern
    for text in ('Hello','Namaste','नमस्ते','123'):
        assert bool(re.fullmatch(pattern,text))==bool(re.fullmatch(schema['properties']['answer']['pattern'],text))


def test_real_hinglish_schema_converts_unicode_after_an_escaped_backslash():
    import re
    from src.document_answers import _generation_schema
    from src.llm import _hosted_schema
    original=_generation_schema('hi-en',True)['properties']['answer']['pattern']
    converted=_hosted_schema({'pattern':original})['pattern']
    assert r'\u0000' not in converted
    for text in ('Hello','Namaste','नमस्ते','123','quote"here','back\\slash','line\nfeed'):
        assert bool(re.fullmatch(original,text))==bool(re.fullmatch(converted,text))
    literal=r'\\u0041'
    assert _hosted_schema({'pattern':literal})['pattern']==literal


def test_hosted_schema_keeps_joint_text_length_and_language_constraints_exact():
    import re
    from src.document_answers import _generation_schema
    from src.llm import _hosted_schema
    original=_generation_schema('hi-en',True)['properties']['answer']
    converted=_hosted_schema({'properties':{'answer':original}})['properties']['answer']
    assert converted['minLength']==original['minLength']==1
    assert converted['maxLength']==original['maxLength']==1800
    assert '{1,1800}' not in converted['pattern']
    def accepts(schema,text):
        return schema['minLength']<=len(text)<=schema['maxLength'] and bool(re.fullmatch(schema['pattern'],text))
    for text in ('','a','a'*1800,'a'*1801,'Namaste','नमस्ते','quote"here','back\\slash','line\nfeed'):
        assert accepts(original,text)==accepts(converted,text)
