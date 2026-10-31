"""Pure release evidence checks; no inference, tools, speech or archive writes."""
from pathlib import Path
import csv, hashlib, json, os

STAGES = {
    'questions': 'eval_step2_live_current.json',
    'conversations': 'eval_step3_live_current.json',
    'adversarial': 'eval_adversarial_live_current.json',
    'holdout': 'eval_holdout_live_current.json',
    'baseline': 'eval_step1_live_current.json',
    'voice': 'voice_validation.json',
    'silence': 'voice_recovery.json',
}
DRIVERS = ('run.py', 'eval_adversarial.py', 'eval_holdout.py', 'generate_voice_samples.py',
           'scripts/resume_live_practice.py', 'scripts/validate_voice_recovery.py')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}

def snapshot(root, env=None):
    root = Path(root).resolve()
    if env is None:
        from dotenv import dotenv_values
        env = {**dotenv_values(root / '.env'), **os.environ}
    defaults = {'LLM_PROVIDER': 'ollama', 'LLM_MODEL': 'qwen3:4b-instruct',
                'LLM_TIMEOUT': '120', 'RAG_LLM_TIMEOUT': '120', 'DENSE_ENABLED': 'true',
                'REFERENCE_DATE': '2026-10-20', 'LLM_FALLBACK_PROVIDER': '',
                'LLM_FALLBACK_MODEL': '', 'GNANI_TTS_MODEL': ''}
    inference = {name: env.get(name, default) for name, default in defaults.items()}
    for name in ('LLM_BASE_URL', 'LLM_FALLBACK_BASE_URL'):
        inference[name + '_sha256'] = hashlib.sha256((env.get(name) or '').encode()).hexdigest()
    dataset = Path(env.get('DATASET_DIR') or 'Capstone_Project_Dataset_FTTT_2026')
    if not dataset.is_absolute():
        dataset = root / dataset
    if not (dataset / 'kb').is_dir() or not (dataset / 'tools/tools.py').is_file():
        raise ValueError('Configured official dataset is missing')
    # Match the existing sequential runner's public snapshot schema. Secrets and
    # append-only generated tickets do not enter selected inference/data inputs.
    def hashes(paths):
        return {p.relative_to(root).as_posix(): sha(p) for p in sorted(set(paths)) if p.is_file()}
    inputs = [p for p in dataset.rglob('*') if p.is_file()
              and p.suffix.lower() in {'.py', '.md', '.csv', '.json'}
              and p.relative_to(dataset).as_posix() != 'tools/tickets_created.csv']
    return {
        'runtime_source_sha256': hashes(list((root / 'src').glob('*.py')) + [root / 'src/rule_bindings.json']),
        'driver_source_sha256': hashes([root / name for name in DRIVERS]),
        'dataset_source_sha256': hashes(inputs),
        'fixture_sha256': hashes([root / 'tests/adversarial_cases.json', root / 'tests/holdout_cases.json']),
        'inference': inference,
    }

def matches_snapshot(value, expected):
    if not isinstance(value, dict):
        return False
    for key, current in expected.items():
        recorded = value.get(key)
        if key == 'driver_source_sha256':
            # The runner may record its own temporary launcher as extra
            # provenance; only shipped evaluation/batch drivers are required.
            if not isinstance(recorded, dict) or any(recorded.get(name) != digest for name, digest in current.items()):
                return False
        elif recorded != current:
            return False
    return True

def _ids(dataset, step):
    name = 'questions.csv' if step in (1, 2) else 'conversations.csv'
    with (dataset / 'practice' / name).open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    return [row['id'] if step in (1, 2) else row['conversation_id'] + '.' + row['turn'] for row in rows]

def _complete_practice(value, mode, ids):
    summary = value.get('summary', {})
    rows = value.get('results', [])
    if not isinstance(summary, dict) or not isinstance(value.get('configuration', {}), dict):
        return False
    passed = summary.get('passed')
    return (value.get('configuration', {}).get('evaluation_mode') == mode
            and value.get('complete') is True and summary.get('complete') is True
            and summary.get('planned') == len(ids) and summary.get('total') == len(ids)
            and type(passed) is int and 0 <= passed <= len(ids)
            and summary.get('errors') == 0 and isinstance(rows, list)
            and [row.get('id') for row in rows if isinstance(row, dict)] == ids
            and len(rows) == len(ids))

def baseline_comparable(baseline, grounded, ids):
    if not (_complete_practice(baseline, 'live_prompt_only', ids)
            and _complete_practice(grounded, 'live_compose_true', ids)):
        return False
    def inputs(value):
        provenance = value.get('configuration', {}).get('provenance', {})
        if not all(isinstance(provenance.get(key), dict) and provenance[key]
                   for key in ('runtime_source_sha256', 'dataset_sha256', 'inference')):
            return None
        return {key: val for key, val in provenance.items() if key not in ('step', 'evaluation_mode')}
    actual = inputs(baseline)
    return (actual is not None and actual == inputs(grounded)
            and all(isinstance(row.get('prediction'), dict)
                    and row['prediction'].get('mode') == 'prompt_only'
                    and row['prediction'].get('answer') and not row['prediction'].get('error')
                    and not row['prediction'].get('sources') and not row['prediction'].get('tool_calls')
                    for row in baseline['results']))

def current_practice(value, step, expected, dataset, root):
    config = value.get('configuration', {})
    if not isinstance(config, dict):
        return False
    provenance = config.get('provenance', {})
    if not isinstance(provenance, dict):
        return False
    runtime = dict(expected['runtime_source_sha256'])
    runtime['scripts/resume_live_practice.py'] = expected['driver_source_sha256']['scripts/resume_live_practice.py']
    prefix = dataset.relative_to(root).as_posix() + '/'
    inputs = {name[len(prefix):]: digest for name, digest in expected['dataset_source_sha256'].items()
              if name.startswith(prefix) and (name[len(prefix):].startswith(('kb/', 'data/', 'practice/'))
                                             or name[len(prefix):] == 'tools/tools.py')}
    inference = {name: val for name, val in expected['inference'].items() if name != 'GNANI_TTS_MODEL'}
    mode = 'live_prompt_only' if step == 1 else 'live_compose_true'
    return (provenance == {'step': step, 'evaluation_mode': mode,
                          'runtime_source_sha256': runtime, 'dataset_sha256': inputs, 'inference': inference}
            and config.get('inference_fingerprint') == hashlib.sha256(
                json.dumps(provenance, sort_keys=True, separators=(',', ':')).encode()).hexdigest())

def complete_extra_stage(name, value):
    summary = value.get('summary', {})
    if not isinstance(summary, dict):
        return False
    if name in ('adversarial', 'holdout'):
        count, key, mode = (77, 'total', 'live_compose_true') if name == 'adversarial' else (91, 'evaluated', 'llm_compose_true')
        rows = value.get('results', [])
        return (value.get('mode') == mode and summary.get('complete') is True
                and summary.get('planned') == summary.get(key) == summary.get('passed') == count
                and summary.get('failed') == 0 and isinstance(rows, list) and len(rows) == count)
    if name == 'voice':
        batch = value.get('batch', {})
        return (isinstance(batch, dict) and batch.get('total') == 6
                and isinstance(batch.get('entries'), list) and len(batch['entries']) == 6)
    if name == 'silence':
        return (value.get('status') == 'tested' and value.get('complete') is True
                and value.get('speech_provider') == 'Gnani only'
                and summary.get('planned') == summary.get('evaluated') == summary.get('passed') == 1
                and summary.get('failed') == 0 and value.get('assessment', {}).get('passed') is True)
    return True

def blockers(root):
    root = Path(root)
    if (root / 'sample_outputs/targeted_live_validation.json').is_file():
        from scripts.targeted_release import blockers as targeted_blockers
        return targeted_blockers(root)
    try:
        expected = snapshot(root)
        required = {'src/agent.py', 'src/document_answers.py', 'src/document_context.py', 'src/rule_bindings.json'}
        if not required <= expected['runtime_source_sha256'].keys() or not all(
                name in expected['driver_source_sha256'] for name in DRIVERS):
            raise ValueError('Required runtime or verification driver is missing')
        # dataset paths are bound in the snapshot; locate the same selected root.
        candidates = [root / name for name in expected['dataset_source_sha256'] if name.endswith('/practice/questions.csv')]
        if len(candidates) != 1:
            raise ValueError('Question fixture is absent or ambiguous')
        dataset = candidates[0].parent.parent
        question_ids, conversation_ids = _ids(dataset, 1), _ids(dataset, 3)
        if len(question_ids) != 52 or len(conversation_ids) != 96:
            raise ValueError('Official practice fixture sizes changed')
    except (OSError, ValueError, KeyError):
        return ['Current selected runtime, dataset, configuration or verification drivers cannot be bound']
    output = root / 'sample_outputs'
    baseline, grounded = read(output / STAGES['baseline']), read(output / STAGES['questions'])
    failures = []
    if (not baseline_comparable(baseline, grounded, question_ids)
            or not current_practice(baseline, 1, expected, dataset, root)
            or not current_practice(grounded, 2, expected, dataset, root)):
        failures.append('Complete current same-model Step 1 comparison missing, stale or erroneous')
    conversations = read(output / STAGES['conversations'])
    if (not _complete_practice(conversations, 'live_compose_true', conversation_ids)
            or not current_practice(conversations, 3, expected, dataset, root)):
        failures.append('Current conversation results do not match the complete official fixture')
    receipt = read(output / 'live_sequence_receipt.json')
    if (receipt.get('complete') is not True or receipt.get('all_frozen_inputs_unchanged') is not True
            or not matches_snapshot(receipt.get('snapshot_started'), expected)
            or not matches_snapshot(receipt.get('snapshot_finished'), expected)):
        failures.append('Complete verification sequence with current source/data/configuration/driver snapshots is required')
    stages = receipt.get('stages', [])
    if not isinstance(stages, list):
        stages = []
    for name, file in STAGES.items():
        candidates = [stage for stage in stages if isinstance(stage, dict) and stage.get('stage') == name]
        if len(candidates) != 1:
            failures.append('Current verification stage missing or duplicated: ' + name)
            continue
        stage = candidates[0]; artifact = stage.get('artifact', {})
        path = output / file
        # A completed low-scoring baseline is a valid comparison, never a policy pass.
        exit_ok = stage.get('exit_code') == 0 or (name == 'baseline'
            and stage.get('exit_code') == 1 and baseline_comparable(baseline, grounded, question_ids))
        if (stage.get('execution_complete') is not True or not exit_ok
                or not complete_extra_stage(name, read(path))
                or stage.get('all_frozen_inputs_unchanged') is not True
                or stage.get('stopped_for_input_change') is not False
                or not matches_snapshot(stage.get('snapshot_started'), expected)
                or not matches_snapshot(stage.get('snapshot_finished'), expected)
                or not path.is_file() or not isinstance(artifact, dict)
                or artifact.get('path') != 'sample_outputs/' + file
                or artifact.get('sha256') != sha(path)):
            failures.append('Verification stage is stale, incomplete, failed or has changed artifact bytes: ' + name)
    return failures
