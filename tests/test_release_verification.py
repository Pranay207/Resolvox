"""Release checks reject stale evidence and tampered in-memory archive fixtures."""
import hashlib
import io
import json
import zipfile

import pytest

import package_submission
from scripts.verify_package import verify_manifest


def write_json(root, name, value):
    path = root / 'sample_outputs' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def read_json(root, name):
    return json.loads((root / 'sample_outputs' / name).read_text(encoding='utf-8'))


@pytest.fixture
def verified_tree(tmp_path, monkeypatch):
    """Synthetic evidence only; no speech, LLM, video or PDF authoring occurs."""
    (tmp_path / 'src').mkdir()
    for name in ('agent.py', 'document_answers.py', 'document_context.py'):
        (tmp_path / 'src' / name).write_text('# synthetic test source\n', encoding='utf-8')
    monkeypatch.setattr(package_submission, 'ROOT', tmp_path)
    monkeypatch.setattr(package_submission, 'mp4_duration', lambda path: 90.)
    hashes = package_submission.runtime_source_hashes()
    for step, total in ((2, 52), (3, 96)):
        write_json(tmp_path, f'eval_step{step}_live_current.json', {
            'configuration': {'evaluation_mode': 'live_compose_true',
                              'provenance': {'runtime_source_sha256': hashes}},
            'summary': {'planned': total, 'total': total, 'passed': total,
                        'failed': 0, 'errors': 0, 'complete': True},
            'complete': True, 'results': [{} for _ in range(total)],
        })
    write_json(tmp_path, 'engineering_verification.json', {
        'runtime_source_sha256': hashes, 'pytest': {'passed': 3, 'total': 3, 'exit_code': 0},
    })
    write_json(tmp_path, 'voice_validation.json', {
        'runtime_source_sha256': hashes, 'runtime_source_sha256_finished': hashes,
        'source_runtime_unchanged': True, 'status': 'tested', 'live_llm_composition_enabled': True,
        'batch': {'total': 6, 'succeeded': 6, 'failed': 0},
        'semantic_validation': {'passed': 6, 'failed': 0, 'checks': [{'passed': True} for _ in range(6)]},
    })
    pdf = b'%PDF synthetic page-count fixture\n' + b'/Type /Page\n' * 4
    (tmp_path / 'report.pdf').write_bytes(pdf)
    write_json(tmp_path, 'pdf_qa.json', {
        'runtime_source_sha256': hashes, 'pdf_sha256': hashlib.sha256(pdf).hexdigest(),
        'pages': 4, 'visually_reviewed_pages': [1, 2, 3, 4], 'layout_issues_found': False,
    })
    return tmp_path


def test_current_complete_passing_evidence_satisfies_non_demo_release_gates(verified_tree):
    release = package_submission.status()
    assert release['ready_to_submit'] is True
    assert release['blockers'] == []
    assert release['answer_path'] == 'document_context_generation'


@pytest.mark.parametrize('change', ['missing', 'stale', 'legacy'])
def test_perfect_historical_live_score_cannot_clear_current_blocker(verified_tree, change):
    name = 'eval_step2_live_current.json'
    data = read_json(verified_tree, name)
    if change == 'missing':
        (verified_tree / 'sample_outputs' / name).unlink()
    else:
        hashes = data['configuration']['provenance']['runtime_source_sha256']
        if change == 'stale':
            hashes['src/agent.py'] = '0' * 64
        else:
            hashes.pop('src/document_answers.py')
        write_json(verified_tree, name, data)
    release = package_submission.status()
    assert release['ready_to_submit'] is False
    assert any('questions verification missing or stale' in x for x in release['blockers'])


@pytest.mark.parametrize('change', ['partial', 'failed', 'error'])
def test_live_completion_and_passing_counts_are_required(verified_tree, change):
    name = 'eval_step2_live_current.json'
    data = read_json(verified_tree, name)
    if change == 'partial':
        data['summary'].update(total=3, passed=3, complete=False)
        data['results'] = data['results'][:3]
        data['complete'] = False
    elif change == 'failed':
        data['summary'].update(passed=51, failed=1)
    else:
        data['summary']['errors'] = 1
    write_json(verified_tree, name, data)
    release = package_submission.status()
    assert release['ready_to_submit'] is False
    assert any('questions verification' in x for x in release['blockers'])


@pytest.mark.parametrize('change', ['legacy', 'offline', 'semantic_failure', 'runtime_changed'])
def test_old_or_failed_voice_score_cannot_clear_speech_blocker(verified_tree, change):
    data = read_json(verified_tree, 'voice_validation.json')
    if change == 'legacy':
        data.pop('runtime_source_sha256')
    elif change == 'offline':
        data['live_llm_composition_enabled'] = False
    elif change == 'runtime_changed':
        data['source_runtime_unchanged'] = False
    else:
        data['semantic_validation']['failed'] = 1
        data['semantic_validation']['checks'][0]['passed'] = False
    write_json(verified_tree, 'voice_validation.json', data)
    release = package_submission.status()
    assert release['ready_to_submit'] is False
    assert any('Gnani speech semantic validation' in x for x in release['blockers'])


@pytest.mark.parametrize('change', ['pdf_bytes', 'runtime_hash', 'visual_review'])
def test_report_qa_must_cover_current_pdf_and_runtime(verified_tree, change):
    data = read_json(verified_tree, 'pdf_qa.json')
    if change == 'pdf_bytes':
        path = verified_tree / 'report.pdf'
        path.write_bytes(path.read_bytes() + b'changed bytes')
    elif change == 'runtime_hash':
        data['runtime_source_sha256']['src/document_context.py'] = '0' * 64
    else:
        data['visually_reviewed_pages'] = [1, 2, 3]
    write_json(verified_tree, 'pdf_qa.json', data)
    release = package_submission.status()
    assert release['report_pages'] == 4
    assert release['ready_to_submit'] is False
    assert any('report visual QA' in x for x in release['blockers'])


def test_source_change_invalidates_otherwise_perfect_current_evidence(verified_tree):
    (verified_tree / 'src' / 'agent.py').write_text('# changed source\n', encoding='utf-8')
    release = package_submission.status()
    assert release['ready_to_submit'] is False
    assert len(release['blockers']) == 5  # two live runs, engineering, speech, PDF QA


def test_missing_demo_remains_an_explicit_final_blocker(verified_tree, monkeypatch):
    monkeypatch.setattr(package_submission, 'mp4_duration', lambda path: None)
    release = package_submission.status()
    assert release['ready_to_submit'] is False
    assert release['blockers'] == ['User-recorded demo.mp4 missing or duration unverified']


def archive_fixture(files, entries=None):
    if entries is None:
        entries = [{'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                   for name, data in files.items()]
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        archive.writestr('package_manifest.json', json.dumps({'files': entries}))
    stream.seek(0)
    return stream


def test_manifest_verifies_every_archived_deliverable_byte():
    with zipfile.ZipFile(archive_fixture({'README.md': b'synthetic'})) as archive:
        assert verify_manifest(archive) == {'manifest_verified': True, 'manifest_deliverables': 1}


@pytest.mark.parametrize('tamper', ['payload', 'size', 'missing', 'extra', 'duplicate_manifest'])
def test_manifest_rejects_tampering_and_incomplete_coverage(tamper):
    files = {'README.md': b'synthetic'}
    entries = [{'path': 'README.md', 'bytes': 9,
                'sha256': hashlib.sha256(b'synthetic').hexdigest()}]
    if tamper == 'payload':
        files['README.md'] = b'SYNTHETIC'  # same length, different digest
    elif tamper == 'size':
        entries[0]['bytes'] = 10
    elif tamper == 'missing':
        entries.clear()
    elif tamper == 'extra':
        files['unlisted.txt'] = b'extra'
    else:
        entries.append(dict(entries[0]))
    with zipfile.ZipFile(archive_fixture(files, entries)) as archive:
        with pytest.raises(ValueError):
            verify_manifest(archive)
