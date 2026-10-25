"""Live Gnani-only recovery check for one second of digital silence.

Run after the required text evaluations, not alongside them:
    python scripts/validate_voice_recovery.py

The input is generated PCM silence, never synthesized speech or a human clip.
No alternate speech provider or live language-model composition is used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit
import wave

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def relative_path(path: Path) -> str:
    return (path.relative_to(ROOT) if path.is_relative_to(ROOT) else path).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wav_details(path: Path) -> dict:
    with wave.open(str(path), 'rb') as audio:
        frames = audio.readframes(audio.getnframes())
        expected = audio.getnframes() * audio.getsampwidth() * audio.getnchannels()
        if not frames or len(frames) != expected or audio.getframerate() <= 0:
            raise ValueError('invalid_or_empty_wav')
        return {'path': relative_path(path), 'sha256': sha256(path),
                'bytes': path.stat().st_size, 'frames': audio.getnframes(),
                'sample_rate': audio.getframerate(), 'sample_width': audio.getsampwidth(),
                'channels': audio.getnchannels(),
                'seconds': round(audio.getnframes() / audio.getframerate(), 3),
                'non_silent_pcm': bool(any(frames))}


def create_silence(path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b'\x00\x00' * 16000)
    return wav_details(path)


class ObservedVoice:
    """Observe actual HTTP outcomes and speech presence without logging headers."""

    def __init__(self, delegate):
        self.delegate = delegate
        self.stt_calls = 0
        self.tts_calls = 0
        self.stt_http_statuses = []
        self.tts_http_statuses = []
        self.stt_failure_type = None
        self.recognized_speech_from_silence = False
        # GnaniVoice uses requests.Session. Response hooks observe only the
        # endpoint path and status; credentials and response bodies stay private.
        session = getattr(delegate, 'session', None)
        if session is not None and hasattr(session, 'hooks'):
            session.hooks.setdefault('response', []).append(self._response)

    def _response(self, response, *args, **kwargs):
        path = urlsplit(response.url).path
        if path == '/stt/v3':
            self.stt_http_statuses.append(int(response.status_code))
        elif path == '/api/v1/tts/inference':
            self.tts_http_statuses.append(int(response.status_code))

    def transcribe(self, path, language):
        self.stt_calls += 1
        try:
            text = self.delegate.transcribe(path, language)
            # Digital silence contains no speech. Any recognized letters or
            # digits are hallucinated content, even if the agent later clarifies.
            self.recognized_speech_from_silence = bool(re.search(r'[^\W_]', text, re.UNICODE))
            return text
        except Exception as error:
            self.stt_failure_type = type(error).__name__
            raise

    def synthesize(self, text, path, language):
        self.tts_calls += 1
        return self.delegate.synthesize(text, path, language)

    def evidence(self) -> dict:
        return {'stt_calls': self.stt_calls, 'tts_calls': self.tts_calls,
                'stt_http_statuses': self.stt_http_statuses,
                'tts_http_statuses': self.tts_http_statuses,
                'stt_failure_type': self.stt_failure_type,
                'recognized_speech_from_silence': self.recognized_speech_from_silence}


def provenance() -> dict:
    names = ['scripts/validate_voice_recovery.py', 'run.py', 'src/voice.py',
             'src/agent.py', 'src/multilingual.py', 'src/normalize.py',
             'src/languages.py', 'src/answering.py', 'src/tools_wrapper.py']
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                              text=True, capture_output=True, check=False)
    return {'runtime_commit': revision.stdout.strip() if revision.returncode == 0 else None,
            'runtime_source_sha256': {name: sha256(ROOT / name) for name in names if (ROOT / name).is_file()}}


def assess_recovery(batch: dict, folder: Path, observer: ObservedVoice) -> dict:
    from src.normalize import redact

    entries = batch.get('entries', [])
    exact = batch.get('total') == 1 and len(entries) == 1 and entries[0].get('input') == 'silence.wav'
    entry = entries[0] if entries else {}
    prediction_path = folder / (entry.get('output_prefix', 'missing') + '.json')
    prediction = json.loads(prediction_path.read_text(encoding='utf-8')) if prediction_path.is_file() else {}
    answer = str(prediction.get('answer') or '')
    reply = None
    audio_name = entry.get('audio')
    if audio_name:
        try:
            reply = wav_details(folder / audio_name)
        except (OSError, EOFError, ValueError, wave.Error):
            pass
    checks = {
        'exact_silent_input': exact,
        'real_gnani_stt_response': observer.stt_calls == 1 and 200 in observer.stt_http_statuses,
        'silence_not_hallucinated_as_speech': not observer.recognized_speech_from_silence,
        'clarification_decision': prediction.get('decision') == 'clarify',
        'unclear_audio_intent': prediction.get('intent') == 'unclear_audio',
        'clear_repeat_request': bool(re.search(
            r'\b(?:please|could you|can you)\b.{0,55}\b(?:repeat|record|speak|say|try)\b'
            r'|\b(?:repeat|record|say|try)\b.{0,55}\b(?:again|clear|clip)\b', answer, re.I)),
        'no_private_actions_or_tickets': not prediction.get('tool_calls') and not prediction.get('verified', False),
        'no_claimed_completed_action': not bool(re.search(
            r'\b(?:ticket|refund|return|cancellation)\b.{0,30}\b(?:created|approved|processed|completed|submitted)\b'
            r'|\b(?:created|approved|processed|completed|submitted)\b.{0,30}\b(?:ticket|refund|return|cancellation)\b', answer, re.I)),
        'real_gnani_tts_response': observer.tts_calls >= 1 and 200 in observer.tts_http_statuses,
        'valid_non_silent_reply_wav': bool(reply and reply['non_silent_pcm'] and reply['seconds'] > 0),
    }
    return {'passed': all(checks.values()), 'checks': checks,
            'redacted_transcript': redact(str(prediction.get('transcript') or '')),
            'answer': redact(answer), 'decision': prediction.get('decision'),
            'intent': prediction.get('intent'), 'sources': prediction.get('sources', []),
            'tool_calls_count': len(prediction.get('tool_calls', [])),
            'reply_audio': reply, 'voice_timings_ms': prediction.get('voice_timings', {}),
            'batch_entry_status': entry.get('status'),
            'batch_counts': {key: batch.get(key) for key in ['total', 'succeeded', 'failed']},
            'batch_startup_ms': batch.get('startup_ms'), 'batch_wall_ms': batch.get('batch_wall_ms'),
            'observation': observer.evidence()}


def save_report(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for attempt in range(5):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(.025 * (attempt + 1))


def run_check(*, report_path: Path = ROOT / 'sample_outputs/voice_recovery.json',
              input_root: Path = ROOT / 'tmp/voice_recovery_inputs',
              output_root: Path = ROOT / 'sample_outputs/voice_recovery',
              voice_factory=None, batch_runner=None) -> dict:
    # Imports and resource initialization stay behind this explicit execution
    # boundary. Importing the script for offline tests never calls a provider.
    if voice_factory is None:
        from src.voice import GnaniVoice
        voice_factory = GnaniVoice
    if batch_runner is None:
        from run import run_batch
        batch_runner = run_batch
    attempt_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    input_dir = input_root / attempt_id
    output_dir = output_root / attempt_id
    input_audio = create_silence(input_dir / 'silence.wav')
    previous = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else None
    history = previous.get('attempt_history', []) + [{key: value for key, value in previous.items() if key != 'attempt_history'}] if previous else []
    record = {'schema_version': 1, 'status': 'running', 'complete': False,
              'attempt_id': attempt_id, 'started_at_utc': utc_now(),
              'speech_provider': 'Gnani only', 'live_llm_composition_enabled': False,
              'input_kind': 'one_second_digital_silence', 'input_audio': input_audio,
              'scope': 'One synthetic digital-silence clip through real Gnani STT and reply TTS. This is not a human speech, noisy speech, or intelligibility test.',
              'expected_behavior': 'Ask for a clear repeat, produce genuine reply audio, perform no private action or ticket creation.',
              'provenance': provenance(), 'attempt_history': history}
    save_report(report_path, record)
    started = time.perf_counter()
    try:
        observer = ObservedVoice(voice_factory())
        batch = batch_runner(input_dir, output_dir, language='en-IN', session_mode='independent',
                             compose=False, voice=observer)
        assessment = assess_recovery(batch, output_dir, observer)
        record.update(assessment=assessment, status='tested' if assessment['passed'] else 'failed', complete=True)
        record['summary'] = {'planned': 1, 'evaluated': 1, 'passed': int(assessment['passed']),
                             'failed': int(not assessment['passed'])}
    except KeyboardInterrupt:
        record.update(status='interrupted', complete=False)
        raise
    except Exception as error:
        record.update(status='failed', complete=True,
                      failure_code=re.sub(r'[^A-Za-z0-9_]', '', type(error).__name__)[:64],
                      summary={'planned': 1, 'evaluated': 1, 'passed': 0, 'failed': 1})
    finally:
        record['ended_at_utc'] = utc_now()
        record['wall_ms'] = round(1000 * (time.perf_counter() - started), 2)
        save_report(report_path, record)
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'sample_outputs/voice_recovery.json')
    args = parser.parse_args(argv)
    try:
        result = run_check(report_path=args.output)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print('Voice recovery check could not start: ' + type(error).__name__, file=sys.stderr)
        return 1
    print(json.dumps({'status': result['status'], 'complete': result['complete'],
                      'summary': result.get('summary')}), flush=True)
    return 0 if result['status'] == 'tested' else 1


if __name__ == '__main__':
    raise SystemExit(main())
