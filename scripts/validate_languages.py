"""Reproducible Gnani-only synthetic language checks; never a human speech claim.

Run one language first: python scripts/validate_languages.py --languages te
Then resume all: python scripts/validate_languages.py --reuse-inputs
Completed passing cases are reused unless --rerun is supplied. Failed cases
remain in attempt_history when retried. --text-only never counts as voice proof.
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
import unicodedata
import wave

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

QUESTIONS = {
    'en': 'How many business days does a UPI refund take after initiation?',
    'hi': 'UPI रिफंड शुरू होने के बाद आने में कितने कार्यदिवस लगते हैं?',
    'bn': 'UPI রিফান্ড শুরু হওয়ার পরে পেতে কত কর্মদিবস লাগে?',
    'gu': 'UPI રિફંડ શરૂ થયા પછી મળવામાં કેટલા કામકાજના દિવસો લાગે છે?',
    'kn': 'UPI ಮರುಪಾವತಿ ಪ್ರಾರಂಭವಾದ ನಂತರ ಬರಲು ಎಷ್ಟು ಕೆಲಸದ ದಿನಗಳು ಬೇಕಾಗುತ್ತವೆ?',
    'ml': 'UPI റീഫണ്ട് ആരംഭിച്ചതിന് ശേഷം ലഭിക്കാൻ എത്ര പ്രവൃത്തി ദിവസങ്ങൾ എടുക്കും?',
    'mr': 'UPI परतावा सुरू झाल्यानंतर मिळण्यासाठी किती कामकाजाचे दिवस लागतात?',
    'pa': 'UPI ਰਿਫੰਡ ਸ਼ੁਰੂ ਹੋਣ ਤੋਂ ਬਾਅਦ ਮਿਲਣ ਲਈ ਕਿੰਨੇ ਕੰਮਕਾਜੀ ਦਿਨ ਲੱਗਦੇ ਹਨ?',
    'ta': 'UPI பணத்தைத் திரும்பப் பெறும் செயல்முறை தொடங்கிய பிறகு எத்தனை வேலை நாட்கள் ஆகும்?',
    'te': 'UPI రీఫండ్ ప్రారంభించిన తర్వాత రావడానికి ఎన్ని పని దినాలు పడుతుంది?',
    'hi-en': 'UPI refund initiate hone ke baad kitne business days lagte hain?',
}
ADDED_LANGUAGES = frozenset({'bn', 'gu', 'kn', 'ml', 'mr', 'pa', 'ta', 'te'})
SCRIPT_RANGES = {
    'hi': (0x0900, 0x097F), 'mr': (0x0900, 0x097F),
    'bn': (0x0980, 0x09FF), 'gu': (0x0A80, 0x0AFF),
    'kn': (0x0C80, 0x0CFF), 'ml': (0x0D00, 0x0D7F),
    'pa': (0x0A00, 0x0A7F), 'ta': (0x0B80, 0x0BFF),
    'te': (0x0C00, 0x0C7F),
}
NUMBER_WORDS = {
    'en': ('one', 'three'), 'hi-en': ('ek', 'teen'),
    'hi': ('एक', 'तीन'), 'mr': ('एक', 'तीन'),
    'bn': ('এক', 'তিন'), 'gu': ('એક', 'ત્રણ'),
    'kn': ('ಒಂದು', 'ಮೂರು'), 'ml': ('ഒന്ന്', 'മൂന്ന്'),
    'pa': ('ਇੱਕ', 'ਤਿੰਨ'), 'ta': ('ஒன்று', 'மூன்று'),
    'te': ('ఒకటి', 'మూడు'),
}
BUSINESS_DAYS = {
    'en': r'business\s+days?|working\s+days?',
    'hi-en': r'business\s+days?|working\s+days?|karyadivas|kaam.?kaj',
    'hi': r'कार्य\s*दिवस|कामकाज|कारोबारी\s*दिन|व्यावसायिक\s*दिन',
    'mr': r'कामकाज|कार्य\s*दिवस|व्यावसायिक\s*दिवस',
    'bn': r'কর্ম\s*দিবস|কাজের\s*দিন|কার্য\s*দিবস',
    'gu': r'કામકાજ|કાર્ય\s*દિવસ|વ્યવસાયિક\s*દિવસ',
    'kn': r'ಕೆಲಸದ\s*ದಿನ|ಕಾರ್ಯ\s*ದಿನ|ವ್ಯವಹಾರ.*ದಿನ',
    'ml': r'പ്രവൃത്തി\s*ദിവസ|പ്രവർത്തി\s*ദിവസ|ജോലി\s*ദിവസ|ബിസിനസ്\s*ദിവസ',
    'pa': r'ਕੰਮਕਾਜ|ਕਾਰੋਬਾਰੀ\s*ਦਿਨ|ਕੰਮ\s*ਦੇ\s*ਦਿਨ',
    'ta': r'வேலை\s*நாட்|வேலை\s*நாள்|வணிக\s*நாட்|பணி\s*நாட்',
    'te': r'పని\s*ది[నవ]|పనిదిన|వ్యాపార\s*ది[నవ]|కార్య\s*ది[నవ]',
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalized_numbers(text: str, code: str) -> str:
    normalized = ''.join(str(unicodedata.digit(c)) if c.isdigit() else c for c in text).lower()
    for words in {NUMBER_WORDS.get(code, ()), NUMBER_WORDS['en']}:
        for word, value in zip(words, ('1', '3')):
            normalized = re.sub(r'(?<!\w)' + re.escape(word) + r'(?!\w)', value, normalized)
    return normalized


def correct_duration(text: str, code: str) -> bool:
    value = normalized_numbers(text, code)
    # A short one-to-three range plus the business-day qualifier; calendar days
    # or an unrelated occurrence of the same numerals must not pass.
    return bool(re.search(r'(?<!\d)1[^\d]{0,24}3(?!\d)', value)
                and re.search(BUSINESS_DAYS[code], value, re.I))


def target_script(text: str, code: str) -> bool:
    if code in SCRIPT_RANGES:
        low, high = SCRIPT_RANGES[code]
        target_letters = sum(low <= ord(c) <= high and unicodedata.category(c).startswith('L') for c in text)
        other_indic_letters = sum(0x0900 <= ord(c) <= 0x0D7F and unicodedata.category(c).startswith('L')
                                  and not low <= ord(c) <= high for c in text)
        return target_letters >= 8 and target_letters > other_indic_letters
    return bool(re.search(r'[A-Za-z]{3,}', text)) and not any(
        0x0900 <= ord(c) <= 0x0D7F and unicodedata.category(c).startswith('L') for c in text)


def output_checks(output: dict, code: str) -> dict[str, bool]:
    answer = str(output.get('answer') or '')
    source_answer = str(output.get('source_answer') or answer)
    source_ids = {item.get('id') for item in output.get('sources', []) if isinstance(item, dict)}
    localization = output.get('localization') or {}
    translated = code not in ADDED_LANGUAGES or (
        localization.get('status') == 'translated'
        and localization.get('query_translated') is True
        and localization.get('answer_translated') is True
        and localization.get('roundtrip_checked') is True
    )
    # The English source answer is meaningful only for the adapter's new
    # languages. Existing Hindi/Hinglish answer plans are native and unchanged.
    source_facts = correct_duration(source_answer, 'en') if code in ADDED_LANGUAGES else correct_duration(answer, code)
    return {
        'grounded_answer': output.get('decision') == 'answer' and output.get('evidence_supported') is True,
        'refund_source': 'REF-2' in source_ids,
        'requested_language': output.get('language') == code,
        'target_script': target_script(answer, code),
        'target_refund_duration': correct_duration(answer, code),
        'source_refund_duration': source_facts,
        'translation_validated': translated,
    }


def wav_metadata(path: Path) -> dict:
    with wave.open(str(path), 'rb') as audio:
        duration = audio.getnframes() / audio.getframerate()
        if duration <= 0 or audio.getnchannels() <= 0 or not any(audio.readframes(audio.getnframes())):
            raise ValueError('empty_wav')
        return {'seconds': round(duration, 3), 'sample_rate': audio.getframerate(),
                'channels': audio.getnchannels(), 'sample_width': audio.getsampwidth(),
                'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def safe_failure(error: Exception) -> str:
    # Unexpected API exception messages can include request details. Persist
    # only an exception class, never its text, request, headers, or credentials.
    return re.sub(r'[^A-Za-z0-9_]', '', type(error).__name__)[:64] or 'Exception'


def evidence_provenance(root: Path = ROOT) -> dict:
    paths = ['scripts/validate_languages.py', 'src/languages.py', 'src/multilingual.py',
             'src/voice.py', 'src/agent.py', 'src/llm.py', 'src/grounding.py', 'src/translation.py']
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in paths if (root / name).is_file()}
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root,
                              capture_output=True, text=True, check=False)
    from src.translation import MODEL_REPO, MODEL_REVISION, MODEL_FILES, LocalTranslator
    return {'runtime_commit': revision.stdout.strip() if revision.returncode == 0 else None,
            'runtime_source_sha256': hashes,
            'translation_model': {'repository': MODEL_REPO, 'revision': MODEL_REVISION,
                                  'files': MODEL_FILES, 'available': LocalTranslator.available()}}


def refresh_summary(report: dict) -> None:
    cases = report['cases']
    planned = report['planned_languages']
    evaluated = [c for c in planned if c in cases and cases[c].get('status') not in {'running', 'interrupted'}]
    passed = [c for c in planned if cases.get(c, {}).get('status') == 'passed']
    text_passed = [c for c in planned if cases.get(c, {}).get('status') == 'text_only_passed']
    report['recorded_at_utc'] = utc_now()
    report['complete'] = len(evaluated) == len(planned)
    report['all_voice_passed'] = bool(planned) and len(passed) == len(planned)
    report['summary'] = {'planned': len(planned), 'evaluated': len(evaluated),
                         'voice_passed': len(passed), 'text_only_passed': len(text_passed),
                         'failed': sum(cases[c].get('status') == 'failed' for c in evaluated),
                         'pending': len(planned) - len(evaluated)}


def save_report(path: Path, report: dict) -> None:
    refresh_summary(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Windows indexers can briefly open a freshly written evidence file.
    # A bounded replacement retry avoids recording a passing API call as a
    # failed language solely because the report was momentarily locked.
    for attempt in range(5):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(.025 * (attempt + 1))


def run_validation(codes: list[str], *, output_path: Path, input_dir: Path,
                   artifact_dir: Path, names: dict, stt_codes: dict, tts_codes: dict,
                   voice_factory, agent_factory, reuse_inputs: bool = False,
                   text_only: bool = False, rerun: bool = False,
                   provenance: dict | None = None) -> dict:
    from src.normalize import redact

    report = json.loads(output_path.read_text(encoding='utf-8')) if output_path.exists() else {
        'schema_version': 1, 'started_at_utc': utc_now(), 'planned_languages': [],
        'cases': {}, 'attempt_history': [],
        'method': 'Synthetic native question -> Gnani TTS -> Gnani STT -> source-grounded agent -> Gnani reply TTS',
        'limitations': 'One synthetic refund question per language. This does not establish human, noisy, accented, or broad-domain accuracy.',
    }
    if report.get('schema_version') != 1:
        raise ValueError('Unsupported language validation report schema')
    report['planned_languages'] = list(dict.fromkeys(report['planned_languages'] + codes))
    report['current_runtime'] = provenance or {}
    save_report(output_path, report)
    input_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    voice = None if text_only else voice_factory()
    for code in codes:
        previous = report['cases'].get(code)
        desired_status = 'text_only_passed' if text_only else 'passed'
        same_runtime = previous and previous.get('provenance', {}).get('runtime_source_sha256') == (provenance or {}).get('runtime_source_sha256')
        if previous and previous.get('status') == desired_status and same_runtime and not rerun:
            print(f'[{code}] reused previous {desired_status}', flush=True)
            continue
        if previous:
            report['attempt_history'].append(previous)
        case = {'language': code, 'language_name': names[code], 'synthetic_question': QUESTIONS[code],
                'stt_language_code': stt_codes[code], 'tts_language_code': tts_codes[code],
                'mode': 'text_only' if text_only else 'live_gnani', 'started_at_utc': utc_now(),
                'status': 'running', 'stage': 'starting', 'provenance': provenance or {}, 'timings_ms': {}}
        case['attempt_id'] = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        report['cases'][code] = case
        save_report(output_path, report)
        start = time.perf_counter()
        stage_start = start

        def stage(name: str) -> None:
            nonlocal stage_start
            case['stage'] = name
            stage_start = time.perf_counter()
            save_report(output_path, report)

        def finish_stage(name: str) -> None:
            case['timings_ms'][name] = round(1000 * (time.perf_counter() - stage_start), 2)
            save_report(output_path, report)

        try:
            heard = QUESTIONS[code]
            if not text_only:
                question_path = input_dir / f'{code}.wav'
                question_fingerprint = hashlib.sha256((code + '\n' + QUESTIONS[code]).encode()).hexdigest()
                fingerprint_path = input_dir / f'{code}.question.sha256'
                stage('input_tts')
                reusable = (reuse_inputs and question_path.exists() and fingerprint_path.exists()
                            and fingerprint_path.read_text().strip() == question_fingerprint)
                if not reusable:
                    voice.synthesize(QUESTIONS[code], question_path, code)
                    fingerprint_path.write_text(question_fingerprint, encoding='ascii')
                case['input_audio'] = wav_metadata(question_path)
                case['input_audio']['reused'] = reusable
                finish_stage('input_tts')
                stage('stt')
                heard = voice.transcribe(question_path, stt_codes[code])
                if not isinstance(heard, str) or not heard.strip():
                    raise ValueError('empty_transcription')
                finish_stage('stt')
            stage('agent')
            output = agent_factory().respond(heard, language_hint=code)
            case.update({'redacted_transcript': redact(str(output.get('transcript') or '')),
                         'answer': redact(str(output.get('answer') or '')),
                         'source_answer': redact(str(output.get('source_answer') or '')),
                         'output_language': output.get('language'), 'decision': output.get('decision'),
                         'intent': output.get('intent'), 'composition': output.get('composition'),
                         'evidence_supported': output.get('evidence_supported'),
                         'sources': output.get('sources', []), 'facts': output.get('facts', {}),
                         'localization': output.get('localization'),
                         'agent_timings_ms': output.get('timings', {})})
            case['checks'] = output_checks(output, code)
            finish_stage('agent')
            if not text_only:
                stage('reply_tts')
                reply_path = artifact_dir / f"{code}_{case['attempt_id']}_reply.wav"
                voice.synthesize(case['answer'], reply_path, code)
                display_path = reply_path.relative_to(ROOT) if reply_path.is_relative_to(ROOT) else reply_path
                case['reply_audio'] = {'path': display_path.as_posix(), **wav_metadata(reply_path)}
                case['actual_spoken_language'] = output.get('language')
                case['spoken_language_evidence'] = ('Target-script reply text sent to the registered Gnani voice. '
                                                   'Audio language and intelligibility have not been independently reviewed.')
                case['checks']['real_input_audio'] = bool(case.get('input_audio', {}).get('seconds'))
                case['checks']['real_reply_audio'] = bool(case['reply_audio']['seconds'])
                finish_stage('reply_tts')
            case['status'] = desired_status if all(case['checks'].values()) else 'failed'
            case['stage'] = 'complete'
        except KeyboardInterrupt:
            case['status'] = 'interrupted'
            case['failure_code'] = 'KeyboardInterrupt'
            raise
        except Exception as error:
            case['status'] = 'failed'
            case['failure_code'] = safe_failure(error)
        finally:
            case['ended_at_utc'] = utc_now()
            case['timings_ms']['total'] = round(1000 * (time.perf_counter() - start), 2)
            save_report(output_path, report)
            print(f"[{code}] {case['status']} ({case['stage']})", flush=True)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--languages', nargs='+', default=list(QUESTIONS))
    parser.add_argument('--reuse-inputs', action='store_true')
    parser.add_argument('--text-only', action='store_true')
    parser.add_argument('--rerun', action='store_true', help='Retry passing cases too; preserve prior attempts.')
    parser.add_argument('--output', type=Path, default=ROOT / 'sample_outputs/language_validation.json')
    args = parser.parse_args(argv)
    try:
        from src.languages import LANGUAGE_NAMES, STT_CODES, TTS_CODES, normalize_language
        from src.multilingual import MultilingualAgent
        from src.voice import GnaniVoice

        codes = list(dict.fromkeys(normalize_language(c) for item in args.languages for c in item.split(',')))
        if any(c not in QUESTIONS for c in codes):
            raise ValueError('unsupported_language_code')
        report = run_validation(codes, output_path=args.output,
                                input_dir=ROOT / 'tmp/language_inputs',
                                artifact_dir=ROOT / 'sample_outputs/language_voice',
                                names=LANGUAGE_NAMES, stt_codes=STT_CODES, tts_codes=TTS_CODES,
                                voice_factory=GnaniVoice, agent_factory=MultilingualAgent,
                                reuse_inputs=args.reuse_inputs, text_only=args.text_only,
                                rerun=args.rerun, provenance=evidence_provenance())
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print('Language validation could not start: ' + safe_failure(error), file=sys.stderr)
        return 1
    expected = 'text_only_passed' if args.text_only else 'passed'
    print(json.dumps(report['summary']), flush=True)
    return int(any(report['cases'].get(code, {}).get('status') != expected for code in codes))


if __name__ == '__main__':
    raise SystemExit(main())
