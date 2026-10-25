"""Download the pinned, public NLLB ONNX translation files into ignored cache.

No PyTorch, remote Python code, authentication token, or speech service is used.
NLLB weights are CC-BY-NC-4.0 and intended here for an educational prototype.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.config import ROOT  # Load the project's Windows trust store, not an API client.
from src.translation import MODEL_REPO, MODEL_REVISION, MODEL_FILES, DEFAULT_MODEL_DIR


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def download_file(name: str, metadata: dict, folder: Path = DEFAULT_MODEL_DIR) -> dict:
    import requests

    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    expected = metadata['sha256']
    if path.exists() and path.stat().st_size == metadata['bytes'] and digest(path) == expected:
        print('Verified cached ' + name, flush=True)
        return {'file': name, **metadata}
    temporary = path.with_suffix(path.suffix + '.part')
    print('Downloading ' + name + ' (' + str(metadata['bytes']) + ' bytes)', flush=True)
    url = f'https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{name}'
    # Small, validated byte ranges recover reliably on networks that interrupt
    # long CDN streams. No signed redirect URLs or headers are logged.
    size = metadata['bytes']
    chunk_size = 4 * 1024 * 1024

    def chunk(start: int) -> tuple[int, bytes]:
        end = min(size, start + chunk_size) - 1
        for attempt in range(3):
            try:
                response = requests.get(url + f'?download=true&chunk={start}',
                                        headers={'Range': f'bytes={start}-{end}'}, timeout=(15, 30))
                response.raise_for_status()
                if response.status_code != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{size}':
                    raise ValueError('download_range_mismatch')
                if len(response.content) != end - start + 1:
                    raise ValueError('download_range_truncated')
                return start, response.content
            except (requests.RequestException, ValueError):
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
        raise RuntimeError('download_retry_limit')

    with temporary.open('wb') as output:
        output.truncate(size)
    downloaded = 0
    with ThreadPoolExecutor(max_workers=4) as executor, temporary.open('r+b') as output:
        pending = [executor.submit(chunk, start) for start in range(0, size, chunk_size)]
        for finished in as_completed(pending):
            offset, content = finished.result()
            output.seek(offset)
            output.write(content)
            downloaded += len(content)
            if downloaded // (32 * 1024 * 1024) != (downloaded - len(content)) // (32 * 1024 * 1024):
                print(name + ': ' + str(round(100 * downloaded / size)) + '%', flush=True)
    if temporary.stat().st_size != metadata['bytes'] or digest(temporary) != expected:
        raise ValueError('download_checksum_mismatch')
    temporary.replace(path)
    print('Verified ' + name, flush=True)
    return {'file': name, **metadata}


def main() -> int:
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            records = list(executor.map(lambda item: download_file(*item), MODEL_FILES.items()))
        DEFAULT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        (DEFAULT_MODEL_DIR / 'checksums.json').write_text(json.dumps({
            'repository': MODEL_REPO, 'revision': MODEL_REVISION,
            'license': 'CC-BY-NC-4.0',
            'license_url': 'https://creativecommons.org/licenses/by-nc/4.0/',
            'upstream': 'https://huggingface.co/facebook/nllb-200-distilled-600M',
            'files': records,
        }, indent=2) + '\n', encoding='utf-8')
        (DEFAULT_MODEL_DIR / 'ATTRIBUTION.txt').write_text(
            'NLLB-200 distilled 600M by Meta AI; ONNX export by Xenova.\n'
            'Weights: CC-BY-NC-4.0, https://creativecommons.org/licenses/by-nc/4.0/\n'
            'https://huggingface.co/facebook/nllb-200-distilled-600M\n'
            f'https://huggingface.co/{MODEL_REPO}/tree/{MODEL_REVISION}\n'
            'Used for this noncommercial educational prototype.\n'
            'Meta describes NLLB as a research model, not released for production deployment.\n',
            encoding='utf-8')
        print('Pinned local translation files are ready. No inference quality has been claimed.', flush=True)
        return 0
    except Exception as error:
        print('Translation setup failed: ' + type(error).__name__, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
