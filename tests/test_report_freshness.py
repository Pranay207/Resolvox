"""Report receipts must match current code/settings/fixtures, not filenames."""
import copy
import json
from pathlib import Path
import shutil

import pytest

from scripts import build_report as report
from scripts.resume_live_practice import fingerprint


@pytest.fixture
def tree(tmp_path, monkeypatch):
    actual = report.ROOT
    files = ['src/agent.py', 'src/document_answers.py', 'src/document_context.py',
             'src/voice.py', 'src/multilingual.py', 'src/normalize.py', 'src/languages.py',
             'src/answering.py', 'src/tools_wrapper.py', 'src/rule_bindings.json',
             'run.py', 'scripts/validate_voice_recovery.py', 'eval_adversarial.py', 'eval_holdout.py']
    for name in files:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# unit-test source: ' + name, encoding='utf-8')
    (tmp_path / 'tests').mkdir()
    for name in ('adversarial_cases.json', 'holdout_cases.json'):
        shutil.copyfile(actual / 'tests' / name, tmp_path / 'tests' / name)
    (tmp_path / 'sample_outputs').mkdir()
    monkeypatch.setattr(report, 'ROOT', tmp_path)
    return tmp_path


def practice(step=2, count=2, planned=2):
    expected = {'step': step, 'runtime_source_sha256': {'src/agent.py': 'current'},
                'dataset_sha256': {'practice/questions.csv': 'fixture'},
                'inference': {'LLM_MODEL': 'model'}}
    complete = count == planned
    data = {'configuration': {'evaluation_mode': 'live_prompt_only' if step == 1 else 'live_compose_true',
                              'provenance': copy.deepcopy(expected), 'inference_fingerprint': fingerprint(expected)},
            'complete': complete, 'summary': {'total': count, 'planned': planned, 'passed': count, 'complete': complete},
            'results': [{'id': str(index), 'prediction': {}} for index in range(count)]}
    return data, expected, [str(index) for index in range(planned)]


def select(data, expected, ids, step=2):
    return report.select_report_live(step, lambda _: data, expected_provenance=expected, expected_ids=ids)[1]


def test_report_accepts_actual_partial_prefix_but_baseline_requires_full_fixture():
    data, expected, ids = practice(count=1)
    assert select(data, expected, ids) is data
    baseline, expected, ids = practice(step=1, count=1)
    assert report.select_current_baseline(lambda _: baseline, expected_provenance=expected, expected_ids=ids)[1] == {}
    baseline, expected, ids = practice(step=1)
    assert report.select_current_baseline(lambda _: baseline, expected_provenance=expected, expected_ids=ids)[1] is baseline


@pytest.mark.parametrize('change', ['runtime', 'dataset', 'inference', 'fingerprint', 'mode', 'planned', 'row_id', 'flag'])
def test_report_rejects_stale_or_mismatched_practice(change):
    data, expected, ids = practice()
    if change in ('runtime', 'dataset', 'inference'):
        section = {'runtime': 'runtime_source_sha256', 'dataset': 'dataset_sha256', 'inference': 'inference'}[change]
        data['configuration']['provenance'][section]['changed'] = 'old'
    elif change == 'fingerprint':
        data['configuration']['inference_fingerprint'] = 'stale'
    elif change == 'mode':
        data['configuration']['evaluation_mode'] = 'offline_compose_false'
    elif change == 'planned':
        data['summary']['planned'] = 1
    elif change == 'row_id':
        data['results'][0]['id'] = 'other'
    else:
        data['complete'] = False
    assert select(data, expected, ids) == {}


def test_short_complete_baseline_cannot_replace_full_question_fixture():
    data, expected, _ = practice(step=1, count=1, planned=1)
    assert report.select_current_baseline(lambda _: data, expected_provenance=expected, expected_ids=['0', '1'])[1] == {}


def test_engineering_displays_actual_failures_but_rejects_stale_runtime(tree):
    data = {'runtime_source_sha256': report.current_core_hashes(),
            'pytest': {'total': 7, 'passed': 5, 'exit_code': 1}}
    assert report.current_engineering(data) is data
    assert '5/7 passed' in report.engineering_text(report.current_engineering(data))
    data['runtime_source_sha256']['src/document_context.py'] = 'old'
    assert report.current_engineering(data) == {}
    assert 'pending' in report.engineering_text(report.current_engineering(data))


def voice_record():
    hashes = report.current_core_hashes()
    return {'runtime_source_sha256': hashes, 'runtime_source_sha256_finished': dict(hashes),
            'source_runtime_unchanged': True, 'live_llm_composition_enabled': True, 'status': 'tested',
            'batch': {'total': 6, 'succeeded': 6, 'failed': 0, 'entries': [{} for _ in range(6)]},
            'semantic_validation': {'passed': 6, 'failed': 0, 'checks': [{'passed': True} for _ in range(6)]}}


def test_voice_current_counts_are_selected_only_with_current_start_and_end(tree):
    data = voice_record()
    assert report.current_voice(data) is data
    data['semantic_validation']['checks'][0]['passed'] = False
    data['semantic_validation'].update(passed=5, failed=1)
    data['status'] = 'failed'
    assert report.current_voice(data) is data  # A fresh failed run stays honestly failed.
    data['runtime_source_sha256_finished']['src/agent.py'] = 'changed'
    assert report.current_voice(data) == {}
    assert 'pending' in report.voice_text(report.current_voice(data))


@pytest.mark.parametrize('change', ['unchanged', 'mode', 'count', 'missing_hash'])
def test_voice_stale_or_incomplete_success_is_not_promoted(tree, change):
    data = voice_record()
    if change == 'unchanged':
        data['source_runtime_unchanged'] = False
    elif change == 'mode':
        data['live_llm_composition_enabled'] = False
    elif change == 'count':
        data['batch']['entries'].pop()
    else:
        data['runtime_source_sha256'].pop('src/document_answers.py')
    assert report.current_voice(data) == {}


def test_recovery_requires_its_actual_operational_sources_and_full_one_case(tree):
    names = ['scripts/validate_voice_recovery.py', 'run.py', 'src/voice.py',
             'src/agent.py', 'src/multilingual.py', 'src/normalize.py',
             'src/languages.py', 'src/answering.py', 'src/tools_wrapper.py']
    data = {'provenance': {'runtime_source_sha256': {name: report._sha(tree / name) for name in names}},
            'complete': True, 'status': 'tested', 'speech_provider': 'Gnani only',
            'live_llm_composition_enabled': False,
            'summary': {'planned': 1, 'evaluated': 1, 'passed': 1, 'failed': 0}}
    assert report.current_recovery(data) is data
    data['provenance']['runtime_source_sha256']['run.py'] = 'old'
    assert report.current_recovery(data) == {}
    assert 'pending' in report.recovery_summary_text(report.current_recovery(data), {})


def adversarial_record(tree):
    cases = json.loads((tree / 'tests/adversarial_cases.json').read_text(encoding='utf-8'))
    ids = [case['id'] for case in cases]
    ids += [f'MULTI_{kind}{index}' for index in range(1, 7) for kind in ('LOCK', 'SWITCH')]
    hashes = report.current_core_hashes()
    hashes['eval_adversarial.py'] = report._sha(tree / 'eval_adversarial.py')
    return {'runtime_source_sha256': hashes, 'runtime_source_sha256_finished': dict(hashes),
            'source_runtime_unchanged': True, 'mode': 'live_compose_true', 'complete': True, 'status': 'tested',
            'configuration': {'evaluation_mode': 'live_compose_true',
                              'fixture_sha256': report._sha(tree / 'tests/adversarial_cases.json')},
            'summary': {'total': len(ids), 'planned': len(ids), 'passed': len(ids), 'failed': 0, 'complete': True},
            'results': [{'id': ident, 'passed': True, 'prediction': {}} for ident in ids]}


def test_adversarial_requires_actual_live_fixture_and_complete_stateful_ids(tree):
    data = adversarial_record(tree)
    assert len(data['results']) == 77 and report.current_adversarial(data) is data
    data['results'].pop()
    assert report.current_adversarial(data) == {}


@pytest.mark.parametrize('change', ['fixture', 'runner', 'end_hash', 'mode'])
def test_adversarial_old_or_offline_record_never_becomes_current(tree, change):
    data = adversarial_record(tree)
    if change == 'fixture':
        data['configuration']['fixture_sha256'] = 'old'
    elif change == 'runner':
        data['runtime_source_sha256']['eval_adversarial.py'] = 'old'
    elif change == 'end_hash':
        data['runtime_source_sha256_finished']['src/agent.py'] = 'old'
    else:
        data['mode'] = 'offline_compose_false'
    assert report.current_adversarial(data) == {}


def holdout_record(tree):
    import eval_holdout
    fixture = json.loads((tree / 'tests/holdout_cases.json').read_text(encoding='utf-8'))
    coverage = eval_holdout.validate_fixture(fixture)
    ids = [case['id'] for case in fixture['single_cases']]
    ids += [scenario['id'] + '/' + turn['id'] for scenario in fixture['scenarios'] for turn in scenario['turns']]
    record = {'mode': 'llm_compose_true', 'coverage': coverage,
              'scorer': {'source_sha256': report._sha(tree / 'eval_holdout.py'),
                         'version': eval_holdout.SCORER_VERSION, 'frozen_rubric_unchanged': True},
              'summary': {'planned': len(ids), 'evaluated': len(ids), 'passed': len(ids), 'failed': 0, 'complete': True},
              'results': [{'id': ident, 'judgment': {'passed': True}} for ident in ids]}
    artifact = tree / 'sample_outputs/eval_holdout_live_current.json'
    artifact.write_text(json.dumps(record), encoding='utf-8')
    hashes = report.current_core_hashes()
    receipt = {'receipt_scope': 'frozen_validation_batch',
               'artifact': 'sample_outputs/eval_holdout_live_current.json',
               'artifact_sha256': report._sha(artifact), 'runtime_source_sha256': hashes,
               'runtime_source_sha256_finished': dict(hashes), 'source_runtime_unchanged': True}
    return record, receipt


def test_holdout_requires_digest_bound_frozen_batch_receipt(tree):
    record, receipt = holdout_record(tree)
    assert len(record['results']) == 91
    assert report.current_holdout(record, {}) == {}
    assert report.current_holdout(record, receipt) is record
    assert receipt['receipt_scope'] == 'frozen_validation_batch'  # Never per-stage snapshots.


@pytest.mark.parametrize('change', ['digest', 'scope', 'start', 'end', 'unchanged', 'artifact'])
def test_stale_or_mismatched_holdout_receipt_is_pending(tree, change):
    record, receipt = holdout_record(tree)
    if change == 'digest':
        receipt['artifact_sha256'] = 'other-bytes'
    elif change == 'scope':
        receipt['receipt_scope'] = 'claimed_exact_stage'
    elif change == 'start':
        receipt['runtime_source_sha256']['src/agent.py'] = 'old'
    elif change == 'end':
        receipt['runtime_source_sha256_finished']['src/document_context.py'] = 'old'
    elif change == 'unchanged':
        receipt['source_runtime_unchanged'] = False
    else:
        receipt['artifact'] = 'sample_outputs/eval_holdout.json'
    assert report.current_holdout(record, receipt) == {}


@pytest.mark.parametrize('change', ['mode', 'coverage', 'scorer', 'rows'])
def test_holdout_receipt_cannot_promote_wrong_mode_fixture_or_partial_run(tree, change):
    record, receipt = holdout_record(tree)
    if change == 'mode':
        record['mode'] = 'offline_compose_false'
    elif change == 'coverage':
        record['coverage']['rubric_sha256'] = 'changed'
    elif change == 'scorer':
        record['scorer']['source_sha256'] = 'old'
    else:
        record['results'].pop()
    artifact = tree / receipt['artifact']
    artifact.write_text(json.dumps(record), encoding='utf-8')
    receipt['artifact_sha256'] = report._sha(artifact)
    assert report.current_holdout(record, receipt) == {}