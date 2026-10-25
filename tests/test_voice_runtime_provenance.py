"""Fresh voice evidence must bind the actual unchanged runtime, without API calls."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

import generate_voice_samples as voice_samples


def runtime(tmp_path):
    folder = tmp_path / 'src'
    folder.mkdir()
    (folder / 'agent.py').write_text('VALUE = 1\n', encoding='utf-8')
    (folder / 'document_answers.py').write_text('ANSWER = True\n', encoding='utf-8')
    (folder / 'rule_bindings.json').write_text('{}', encoding='utf-8')
    (tmp_path / '.env').write_text('GNANI_API_KEY=never-read-or-copy', encoding='utf-8')
    return folder


def test_voice_runtime_snapshot_contains_actual_code_and_bindings_not_secrets(tmp_path):
    folder = runtime(tmp_path)
    values = voice_samples.runtime_source_hashes(tmp_path)
    assert set(values) == {'src/agent.py', 'src/document_answers.py', 'src/rule_bindings.json'}
    assert values['src/agent.py'] == hashlib.sha256((folder / 'agent.py').read_bytes()).hexdigest()
    assert 'never-read-or-copy' not in json.dumps(values)


def test_voice_runtime_provenance_detects_mutation_addition_and_removal(tmp_path):
    folder = runtime(tmp_path)
    initial = voice_samples.runtime_source_hashes(tmp_path)
    started = datetime.now().astimezone().isoformat()
    (folder / 'agent.py').write_text('VALUE = 2\n', encoding='utf-8')
    changed = voice_samples.finish_runtime_provenance(initial, started, True, tmp_path)
    assert changed['source_runtime_unchanged'] is False
    assert changed['runtime_source_sha256'] == initial
    (folder / 'agent.py').write_text('VALUE = 1\n', encoding='utf-8')
    (folder / 'new.py').write_text('NEW = True\n', encoding='utf-8')
    assert not voice_samples.finish_runtime_provenance(initial, started, True, tmp_path)['source_runtime_unchanged']
    (folder / 'new.py').unlink()
    (folder / 'rule_bindings.json').unlink()
    assert not voice_samples.finish_runtime_provenance(initial, started, True, tmp_path)['source_runtime_unchanged']


def prepare_main(monkeypatch, tmp_path, *, offline=False):
    folder = runtime(tmp_path)
    monkeypatch.setattr(voice_samples, 'ROOT', tmp_path)
    monkeypatch.setattr(voice_samples, 'SAMPLES', [])
    monkeypatch.setattr(voice_samples, 'GnaniVoice', lambda: object())
    monkeypatch.setattr(sys, 'argv', ['generate_voice_samples.py'] + (['--offline-rules'] if offline else []))
    result = {'total': 1, 'succeeded': 1, 'failed': 0, 'entries': [{'input': 'fresh-unit-mock.wav'}]}
    monkeypatch.setattr(voice_samples, 'run_batch', lambda *args, **kwargs: dict(result))
    monkeypatch.setattr(voice_samples, 'validate', lambda *args: {'passed': 1, 'failed': 0, 'checks': []})
    return folder


def test_fresh_voice_record_and_manifest_share_actual_provenance(monkeypatch, tmp_path):
    prepare_main(monkeypatch, tmp_path)
    assert voice_samples.main() == 0
    record = json.loads((tmp_path / 'sample_outputs/voice_validation.json').read_text(encoding='utf-8'))
    manifest = json.loads((tmp_path / 'sample_outputs/voice/manifest.json').read_text(encoding='utf-8'))
    for key in ('started_at_utc', 'finished_at_utc', 'runtime_source_sha256',
                'runtime_source_sha256_finished', 'source_runtime_unchanged',
                'live_llm_composition_enabled'):
        assert record[key] == manifest[key]
    assert record['source_runtime_unchanged'] is True
    assert record['live_llm_composition_enabled'] is True
    assert datetime.fromisoformat(record['finished_at_utc']) >= datetime.fromisoformat(record['started_at_utc'])
    assert 'never-read-or-copy' not in json.dumps(record)


def test_voice_provenance_records_actual_offline_setting(monkeypatch, tmp_path):
    prepare_main(monkeypatch, tmp_path, offline=True)
    assert voice_samples.main() == 0
    record = json.loads((tmp_path / 'sample_outputs/voice_validation.json').read_text(encoding='utf-8'))
    assert record['live_llm_composition_enabled'] is False
    assert record['batch']['live_llm_composition_enabled'] is False


def test_runtime_change_invalidates_new_voice_proof(monkeypatch, tmp_path):
    folder = prepare_main(monkeypatch, tmp_path)

    def batch(*args, **kwargs):
        (folder / 'agent.py').write_text('VALUE = 2\n', encoding='utf-8')
        return {'total': 1, 'succeeded': 1, 'failed': 0, 'entries': []}

    monkeypatch.setattr(voice_samples, 'run_batch', batch)
    assert voice_samples.main() == 1
    record = json.loads((tmp_path / 'sample_outputs/voice_validation.json').read_text(encoding='utf-8'))
    assert record['status'] == 'invalid_runtime_changed'
    assert record['source_runtime_unchanged'] is False
    assert record['batch']['succeeded'] == 1


def test_blocked_attempt_does_not_relabel_old_manifest_entries(monkeypatch, tmp_path):
    prepare_main(monkeypatch, tmp_path)
    output = tmp_path / 'sample_outputs/voice'
    output.mkdir(parents=True)
    (output / 'manifest.json').write_text(json.dumps({'entries': [{'input': 'old-run.wav'}]}), encoding='utf-8')

    def unavailable():
        raise voice_samples.VoiceUnavailable('Unit-test provider unavailable')

    monkeypatch.setattr(voice_samples, 'GnaniVoice', unavailable)
    assert voice_samples.main() == 2
    record = json.loads((tmp_path / 'sample_outputs/voice_validation.json').read_text(encoding='utf-8'))
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    assert record['status'] == manifest['status'] == 'blocked'
    assert manifest['entries'] == [] and 'old-run.wav' not in json.dumps(manifest)
    assert manifest['source_runtime_unchanged'] is True