"""The hosted application is explicit and cannot redirect credentials or tests."""
import os
import pytest
from src.app_profile import hosted_environment, GROQ_BASE
from scripts import run_app


def configured(tmp_path, text='LLM_API_KEY=fixture-key\n'):
    (tmp_path / '.env.hosted').write_text(text, encoding='utf-8')
    return tmp_path


def test_hosted_profile_isolated_from_local_settings_and_arbitrary_destinations(tmp_path):
    root=configured(tmp_path,'LLM_API_KEY=fixture-key\nLLM_BASE_URL=https://untrusted.invalid\nGNANI_API_KEY=wrong-speech-key\n')
    inherited={'LLM_PROVIDER':'ollama','LLM_BASE_URL':'http://127.0.0.1:11435','GNANI_API_KEY':'existing-speech-key','LLM_FALLBACK_PROVIDER':'other','LLM_FALLBACK_API_KEY':'other-key'}
    original=dict(inherited)
    env=hosted_environment(root,inherited)
    assert inherited==original
    assert env['LLM_BASE_URL']==GROQ_BASE and env['LLM_API_KEY']=='fixture-key'
    assert env['GNANI_API_KEY']=='existing-speech-key'
    assert env['LLM_FALLBACK_PROVIDER']==env['LLM_FALLBACK_API_KEY']==''
    assert env['LLM_MODEL']=='openai/gpt-oss-20b' and env['LLM_REASONING_EFFORT']=='low'


@pytest.mark.parametrize('text', ['', 'LLM_API_KEY=\n','LLM_MODEL=openai/gpt-oss-120b\n'])
def test_missing_hosted_key_does_not_use_an_unrelated_inherited_key(tmp_path,text):
    with pytest.raises(ValueError,match='ignored .env.hosted'):
        hosted_environment(configured(tmp_path,text),{'LLM_API_KEY':'unrelated-key'})


@pytest.mark.parametrize('text',[
    'LLM_API_KEY=fixture-key\nLLM_MODEL=unsupported\n',
    'LLM_API_KEY=fixture-key\nLLM_REASONING_EFFORT=invalid-value\n',
])
def test_invalid_profile_reports_no_secret_values(tmp_path,text):
    with pytest.raises(ValueError) as caught:
        hosted_environment(configured(tmp_path,text),{})
    assert 'fixture-key' not in str(caught.value)


def test_local_launcher_never_reads_hosted_profile(tmp_path,monkeypatch):
    monkeypatch.setattr(run_app,'ROOT',tmp_path)
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    calls=[]
    monkeypatch.setattr(run_app.subprocess,'call',lambda command,**options:calls.append((command,options)) or 0)
    assert run_app.main([])==0
    assert calls[0][1]['env']['LLM_PROVIDER']=='ollama'


def test_hosted_launcher_only_passes_key_in_child_environment(tmp_path,monkeypatch):
    configured(tmp_path)
    monkeypatch.setattr(run_app,'ROOT',tmp_path)
    calls=[]
    monkeypatch.setattr(run_app.subprocess,'call',lambda command,**options:calls.append((command,options)) or 0)
    assert run_app.main(['--hosted','--port','8512'])==0
    command,options=calls[0]
    assert 'fixture-key' not in ' '.join(command)
    assert options['env']['LLM_API_KEY']=='fixture-key'
    assert options['env']['LLM_BASE_URL']==GROQ_BASE
    assert '8512' in command


def test_batch_hosted_flag_is_explicit_and_excludes_offline_mode(monkeypatch):
    import run
    monkeypatch.setattr('sys.argv',['run.py','--audio_dir','input','--out_dir','output','--hosted','--offline-rules'])
    with pytest.raises(SystemExit) as caught:run.main()
    assert caught.value.code==2


def test_nonsecret_hosted_settings_can_bind_a_release_without_reading_a_key(tmp_path):
    from src.app_profile import hosted_settings
    settings=hosted_settings(tmp_path)
    assert settings['LLM_MODEL']=='openai/gpt-oss-20b'
    assert settings['LLM_BASE_URL']==GROQ_BASE
    assert 'LLM_API_KEY' not in settings
    assert settings['RAG_CLAIM_AUDIT']=='true'
