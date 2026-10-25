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
