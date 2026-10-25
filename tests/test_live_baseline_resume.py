"""Resumable current baselines use only an LLM prompt, without agent context."""
import json

import pytest

from scripts.resume_live_practice import _id, _units, run_evaluation
from src.llm import baseline


def gold(ident):
    return {'id': ident, 'question': 'Public question ' + ident,
            'expected_decision': 'answer', 'must_include': 'supported',
            'must_not_include': '', 'gold_evidence': '', 'expected_tool_calls': ''}


def dependencies():
    calls, created = [], []

    class FakeLLM:
        last_provider = 'mock:model'
        last_metrics = {'attempts': 1, 'cache_hit': False}

        def __init__(self):
            created.append(True)

        def complete(self, system, user, json_mode=False):
            assert json_mode is True
            calls.append({'system': system, 'user': user})
            return json.dumps({'decision': 'answer', 'answer': 'supported'})

    return calls, created, FakeLLM


def run(path, dataset, client, **kwargs):
    return run_evaluation(1, path, dataset=dataset, baseline_fn=baseline,
                          llm_factory=client,
                          resources_factory=lambda: pytest.fail('baseline must never create resources'),
                          agent_factory=lambda **kw: pytest.fail('baseline must never create an agent'),
                          provenance_factory=lambda step: {'step': step, 'fixed': True}, **kwargs)


def test_prompt_only_resume_calls_only_remaining_questions_and_preserves_mode(tmp_path):
    calls, created, client = dependencies()
    path = tmp_path / 'eval_step1_live_current.json'
    dataset = [gold('one'), gold('two'), gold('three')]
    partial = run(path, dataset, client, max_new_units=1)
    first_saved = json.loads(path.read_text())['results'][0]
    assert not partial['complete'] and partial['total'] == 1
    complete = run(path, dataset, client)
    saved = json.loads(path.read_text())
    assert complete['complete'] and complete['passed'] == complete['planned'] == 3
    assert saved['configuration']['evaluation_mode'] == 'live_prompt_only'
    assert saved['results'][0] == first_saved
    assert [call['user'] for call in calls] == [row['question'] for row in dataset]
    assert len(created) == 2
    assert run(path, dataset, client) == complete
    assert len(created) == 2 and len(calls) == 3
    assert complete['composition_counts'] == {'prompt_only': 3}


def test_actual_baseline_prompt_contains_no_company_evidence_or_tools(tmp_path):
    calls, _, client = dependencies()
    run(tmp_path / 'current.json', [gold('single')], client)
    assert len(calls) == 1
    assert calls[0]['user'] == 'Public question single'
    assert 'no company documents or order access' in calls[0]['system']
    assert 'source_text' not in calls[0]['user'] and 'verified_order' not in calls[0]['user']
    prediction = json.loads((tmp_path / 'current.json').read_text())['results'][0]['prediction']
    assert prediction['sources'] == prediction['retrieved_chunk_ids'] == prediction['tool_calls'] == []
    assert prediction['intent'] == 'baseline' and prediction['mode'] == 'prompt_only'


def test_baseline_does_not_overwrite_historical_step1_artifact(tmp_path):
    _, _, client = dependencies()
    path = tmp_path / 'eval_step1.json'
    path.write_text('preserved baseline')
    with pytest.raises(ValueError, match='historical'):
        run(path, [gold('single')], client)
    assert path.read_text() == 'preserved baseline'


def test_changed_baseline_provenance_blocks_resume_before_client_creation(tmp_path):
    calls, created, client = dependencies()
    path = tmp_path / 'current.json'
    dataset = [gold('one'), gold('two')]
    run(path, dataset, client, max_new_units=1)
    before = path.read_bytes()
    with pytest.raises(ValueError, match='settings changed'):
        run_evaluation(1, path, dataset=dataset, baseline_fn=baseline,
                       llm_factory=lambda: pytest.fail('must not create client'),
                       provenance_factory=lambda step: {'step': step, 'changed': True})
    assert path.read_bytes() == before and len(created) == len(calls) == 1


def test_prompt_only_failure_is_saved_truthfully_not_replaced(tmp_path):
    class InvalidLLM:
        last_metrics = {}
        last_provider = 'mock:model'

        def complete(self, *args, **kwargs):
            return 'not JSON'

    summary = run(tmp_path / 'current.json', [gold('one')], InvalidLLM)
    saved = json.loads((tmp_path / 'current.json').read_text())
    assert summary['complete'] and summary['passed'] == 0 and summary['errors'] == 1
    assert saved['results'][0]['prediction']['mode'] == 'blocked'
    assert saved['configuration']['evaluation_mode'] == 'live_prompt_only'


def test_first_two_steps_use_independent_question_units():
    dataset = [gold('one'), gold('two')]
    for step in (1, 2):
        assert _units(dataset, step) == [[dataset[0]], [dataset[1]]]
        assert _id(dataset[0], step) == 'one'
    turns = [{'conversation_id': 'A', 'turn': '1'}, {'conversation_id': 'A', 'turn': '2'}]
    assert _units(turns, 3) == [turns] and _id(turns[1], 3) == 'A.2'

def current_baseline_fixture():
    from scripts.resume_live_practice import fingerprint
    provenance = {'step': 1, 'runtime_source_sha256': {'src/llm.py': 'fresh'},
                  'dataset_sha256': {'practice/questions.csv': 'fixed-fixture'}}
    return {'configuration': {'evaluation_mode': 'live_prompt_only', 'llm_provider': 'mock',
                             'llm_model': 'new-model', 'provenance': provenance,
                             'inference_fingerprint': fingerprint(provenance)},
            'complete': True, 'summary': {'total': 1, 'planned': 1, 'passed': 0, 'complete': True},
            'results': [{'id': 'one', 'prediction': {}}]}


def test_report_selects_only_complete_current_prompt_only_baseline():
    import copy
    from scripts.build_report import select_current_baseline
    data = current_baseline_fixture()
    expected = data['configuration']['provenance']
    def select(record):
        return select_current_baseline(lambda _: record, expected_provenance=expected, expected_ids=['one'])
    name, selected = select(data)
    assert name == 'eval_step1_live_current.json' and selected is data
    for variant in ('partial', 'wrong_mode', 'stale_runtime', 'missing_row'):
        changed = copy.deepcopy(data)
        if variant == 'partial':
            changed['summary']['complete'] = False
        elif variant == 'wrong_mode':
            changed['configuration']['evaluation_mode'] = 'live_compose_true'
        elif variant == 'stale_runtime':
            changed['configuration']['provenance']['runtime_source_sha256']['src/llm.py'] = 'old'
        else:
            changed['results'] = []
        assert select(changed)[1] == {}, variant


def test_report_compares_recorded_models_without_assuming_old_baseline():
    from scripts.build_report import baseline_comparison_text
    base = current_baseline_fixture()
    matching = {'configuration': {'llm_provider': 'mock', 'llm_model': 'new-model'}}
    different = {'configuration': {'llm_provider': 'mock', 'llm_model': 'other-model'}}
    assert 'same configured provider/model' in baseline_comparison_text(base, matching, current=True)
    assert 'does not isolate retrieval alone' in baseline_comparison_text(base, matching, current=True)
    assert 'confound' in baseline_comparison_text(base, different, current=True)
    assert 'historical' in baseline_comparison_text(base, matching, current=False)


def test_step1_cli_uses_current_filename_and_retains_recorded_failure_exit(monkeypatch):
    import sys
    from scripts import resume_live_practice as driver
    captured = {}

    def evaluate(step, output, **kwargs):
        captured.update(step=step, output=output.name)
        return {'complete': True, 'passed': 0, 'total': 1}

    monkeypatch.setattr(sys, 'argv', ['resume_live_practice.py', '--step', '1'])
    monkeypatch.setattr(driver, 'run_evaluation', evaluate)
    assert driver.main() == 1
    assert captured == {'step': 1, 'output': 'eval_step1_live_current.json'}
