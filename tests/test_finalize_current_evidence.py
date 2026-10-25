"""The finalizer summarizes real receipts and never manufactures completion."""
import hashlib
import json
import sys

import pytest

from scripts import finalize_evidence


def put(root, name, value):
    path = root / 'sample_outputs' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def get(root, name):
    return json.loads((root / 'sample_outputs' / name).read_text(encoding='utf-8'))


@pytest.fixture
def receipts(tmp_path, monkeypatch):
    (tmp_path / 'src').mkdir()
    hashes = {}
    for name in ('agent.py', 'document_answers.py', 'document_context.py'):
        path = tmp_path / 'src' / name
        path.write_text('# synthetic runtime\n', encoding='utf-8')
        hashes['src/' + name] = hashlib.sha256(path.read_bytes()).hexdigest()
    put(tmp_path, 'engineering_verification.json', {
        'runtime_source_sha256': hashes,
        'pytest': {'passed': 7, 'total': 7, 'exit_code': 0},
    })
    for step, total in ((2, 52), (3, 96)):
        results = [{'prediction': {'composition': 'grounded_llm',
                                  'llm': {'provider': 'mock:actual-model', 'cache_hit': False}}}
                   for _ in range(total)]
        results[0] = {'prediction': {'composition': 'deterministic_guardrail'}}
        put(tmp_path, f'eval_step{step}_live_current.json', {
            'configuration': {'evaluation_mode': 'live_compose_true', 'llm_model': 'actual-model:4b',
                              'provenance': {'runtime_source_sha256': hashes}},
            'summary': {'planned': total, 'total': total, 'passed': total,
                        'failed': 0, 'errors': 0, 'complete': True},
            'complete': True, 'results': results,
        })
    put(tmp_path, 'voice_validation.json', {
        'runtime_source_sha256': hashes, 'runtime_source_sha256_finished': hashes,
        'source_runtime_unchanged': True, 'status': 'tested', 'live_llm_composition_enabled': True,
        'batch': {'total': 6, 'succeeded': 6, 'failed': 0, 'entries': [{} for _ in range(6)]},
        'semantic_validation': {'passed': 6, 'failed': 0, 'checks': [{'passed': True} for _ in range(6)]},
    })
    (tmp_path / 'SUBMISSION_STATUS.json').write_text(json.dumps({
        'runtime_source_sha256': hashes, 'ready_to_submit': False, 'blockers': ['Demo pending'],
    }), encoding='utf-8')
    put(tmp_path, 'eval_step2_live_postfix_partial.json', {'summary': {'passed': 32, 'total': 32}})
    for name in ('README.md', 'VERIFICATION.md', 'BRIEF_CHECKLIST.md', 'report.md', 'report.pdf'):
        (tmp_path / name).write_bytes(b'preserved existing document')
    put(tmp_path, 'final_summary.json', {'old': 'preserve unchanged'})
    monkeypatch.setattr(finalize_evidence, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['finalize_evidence.py'])
    return tmp_path


def run_summary(root):
    assert finalize_evidence.main() == 0
    return get(root, 'final_evaluation.json')


def test_finalizer_uses_actual_models_composition_and_counts_without_rewriting_documents(receipts):
    before = {path: path.read_bytes() for path in receipts.rglob('*') if path.is_file()}
    data = run_summary(receipts)
    assert data['validation_passed'] is True and data['complete'] is True
    assert data['ready'] is False and data['ready_to_submit'] is False
    questions = data['current_live_practice']['2']
    assert questions['configuration']['llm_model'] == 'actual-model:4b'
    assert questions['composition_counts'] == {'grounded_llm': 51, 'deterministic_guardrail': 1}
    assert questions['actual_provider_counts']['mock:actual-model'] == 51
    assert data['engineering']['pytest'] == {'passed': 7, 'total': 7, 'exit_code': 0}
    assert 'sample_outputs/eval_step2_live_postfix_partial.json' in data['historical_evidence_paths']
    assert all(path.read_bytes() == content for path, content in before.items())
    assert set(path for path in receipts.rglob('*') if path.is_file()) - set(before) == {
        receipts / 'sample_outputs' / 'final_evaluation.json'}


def test_cli_count_is_only_a_consistency_assertion_and_cannot_forge_tests(receipts, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['finalize_evidence.py', '--pytest-passed', '999'])
    with pytest.raises(SystemExit) as error:
        finalize_evidence.main()
    assert error.value.code == 2
    assert not (receipts / 'sample_outputs' / 'final_evaluation.json').exists()
    assert get(receipts, 'engineering_verification.json')['pytest']['passed'] == 7


def test_matching_cli_count_preserves_actual_failed_test_total_and_exit_code(receipts, monkeypatch):
    data = get(receipts, 'engineering_verification.json')
    data['pytest'].update(passed=6, exit_code=1)
    put(receipts, 'engineering_verification.json', data)
    monkeypatch.setattr(sys, 'argv', ['finalize_evidence.py', '--pytest-passed', '6'])
    summary = run_summary(receipts)
    assert summary['validation_passed'] is False
    assert summary['engineering']['pytest'] == {'passed': 6, 'total': 7, 'exit_code': 1}
    assert get(receipts, 'engineering_verification.json') == data


@pytest.mark.parametrize('change', ['missing', 'stale', 'legacy'])
def test_old_perfect_score_or_partial_history_cannot_become_current(receipts, change):
    name = 'eval_step2_live_current.json'
    data = get(receipts, name)
    if change == 'missing':
        (receipts / 'sample_outputs' / name).unlink()
    else:
        hashes = data['configuration']['provenance']['runtime_source_sha256']
        if change == 'stale':
            hashes['src/agent.py'] = '0' * 64
        else:
            hashes.pop('src/document_answers.py')
        put(receipts, name, data)
    summary = run_summary(receipts)
    row = summary['current_live_practice']['2']
    assert row['runtime_current'] is False and row['summary'] == {}
    assert row['composition_counts'] == {}
    assert summary['validation_passed'] is False and summary['ready'] is False
    assert summary['full_live_practice_rerun_complete'] is False


def test_partial_current_run_retains_actual_counts_and_incomplete_status(receipts):
    data = get(receipts, 'eval_step2_live_current.json')
    data['results'] = data['results'][:3]
    data['summary'].update(total=3, passed=3, complete=False)
    data['complete'] = False
    put(receipts, 'eval_step2_live_current.json', data)
    summary = run_summary(receipts)
    row = summary['current_live_practice']['2']
    assert row['runtime_current'] is True and row['summary']['total'] == 3
    assert row['summary']['planned'] == 52 and row['complete'] is False
    assert summary['validation_passed'] is False


def test_completed_failing_run_is_complete_without_being_a_pass(receipts):
    data = get(receipts, 'eval_step2_live_current.json')
    data['summary'].update(passed=51, failed=1)
    put(receipts, 'eval_step2_live_current.json', data)
    summary = run_summary(receipts)
    assert summary['complete'] is True and summary['validation_passed'] is False
    assert summary['current_live_practice']['2']['summary']['passed'] == 51
    assert summary['ready_to_submit'] is False


def test_missing_or_legacy_voice_success_does_not_become_current_validation(receipts):
    data = get(receipts, 'voice_validation.json')
    data.pop('runtime_source_sha256')
    put(receipts, 'voice_validation.json', data)
    summary = run_summary(receipts)
    assert summary['voice']['runtime_current'] is False
    assert summary['voice']['passed'] is False and summary['validation_passed'] is False
    assert summary['voice']['semantic_validation']['passed'] == 6


def test_pending_missing_speech_is_reported_without_inventing_a_result(receipts):
    (receipts / 'sample_outputs' / 'voice_validation.json').unlink()
    summary = run_summary(receipts)
    assert summary['voice']['status'] == 'pending'
    assert summary['voice']['semantic_validation'] == {}
    assert summary['validation_passed'] is False


def test_submission_ready_requires_a_fresh_actual_release_receipt(receipts):
    release = json.loads((receipts / 'SUBMISSION_STATUS.json').read_text())
    release.update(ready_to_submit=True, blockers=[])
    release['runtime_source_sha256']['src/agent.py'] = '0' * 64
    (receipts / 'SUBMISSION_STATUS.json').write_text(json.dumps(release))
    summary = run_summary(receipts)
    assert summary['validation_passed'] is True
    assert summary['ready'] is False and summary['submission_status']['runtime_current'] is False
