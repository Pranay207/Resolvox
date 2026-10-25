"""The submitted app retains its native theme without shipping local secrets."""
import hashlib
import json
from pathlib import Path
import zipfile

import package_submission


def test_release_preserves_app_theme_and_excludes_local_settings(tmp_path, monkeypatch):
    theme = (Path(__file__).resolve().parents[1] / '.streamlit/config.toml').read_bytes()
    (tmp_path / '.streamlit').mkdir()
    (tmp_path / '.streamlit/config.toml').write_bytes(theme)
    (tmp_path / '.streamlit/secrets.toml').write_text('private = "local-only"')
    (tmp_path / '.env').write_text('GNANI_API_KEY=local-only')
    (tmp_path / 'app.py').write_text('import streamlit as st\nst.title("Resolvox")\n')
    monkeypatch.setattr(package_submission, 'ROOT', tmp_path)
    monkeypatch.setattr(package_submission, 'status', lambda: {'ready_to_submit': False})

    assert package_submission.main() == 0

    with zipfile.ZipFile(tmp_path / 'dist/pranay_voiceops.zip') as archive:
        assert archive.read('.streamlit/config.toml') == theme
        assert '.env' not in archive.namelist()
        assert '.streamlit/secrets.toml' not in archive.namelist()
        manifest = json.loads(archive.read('package_manifest.json'))
        entry = next(row for row in manifest['files'] if row['path'] == '.streamlit/config.toml')
        assert entry['sha256'] == hashlib.sha256(theme).hexdigest()


def test_package_keeps_linked_engineering_xml_logs_without_widening_private_inputs(tmp_path, monkeypatch):
    expected = {
        'sample_outputs/engineering_artifacts/current/pytest.xml': b'<testsuite tests="3" failures="0"/>',
        'sample_outputs/engineering_artifacts/current/pytest.log': b'3 passed',
        'sample_outputs/engineering_artifacts/current/dataset_validation.log': b'PASS synthetic dataset',
    }
    forbidden = {
        'sample_outputs/unrelated.log',
        'sample_outputs/unrelated.xml',
        'tests/unrelated.xml',
        'sample_outputs/history/engineering_artifacts/old/pytest.log',
        'sample_outputs/engineering_artifacts/current/.env',
        'sample_outputs/voice_inputs/identity.wav',
        'sample_outputs/history/archive/sample_outputs/voice_inputs/identity.wav',
        'sample_outputs/history/archive/sample_outputs/voice_inputs/proof.json',
        'sample_outputs/engineering_artifacts/current/voice_inputs/proof.log',
        'sample_outputs/engineering_artifacts/current/voice_inputs/proof.xml',
        'Capstone_Project_Dataset_FTTT_2026/data/customers.csv',
        '.cache/private.json',
        '.venv/private.py',
        '.env',
        '.streamlit/secrets.toml',
    }
    for name, content in expected.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for name in forbidden:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'private or out of scope synthetic fixture')
    monkeypatch.setattr(package_submission, 'ROOT', tmp_path)
    monkeypatch.setattr(package_submission, 'status', lambda: {'ready_to_submit': False})

    assert package_submission.main() == 0

    with zipfile.ZipFile(tmp_path / 'dist/pranay_voiceops.zip') as archive:
        names = set(archive.namelist())
        assert expected.keys() <= names
        assert not names.intersection(forbidden)
        assert not any('voice_inputs' in Path(name).parts for name in names)
        manifest = json.loads(archive.read('package_manifest.json'))
        entries = {entry['path']: entry for entry in manifest['files']}
        for name, content in expected.items():
            assert archive.read(name) == content
            assert entries[name]['bytes'] == len(content)
            assert entries[name]['sha256'] == hashlib.sha256(content).hexdigest()
