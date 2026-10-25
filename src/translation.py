"""Local research translation with pinned quantized NLLB ONNX weights.

Weights: Meta NLLB-200 distilled 600M, Xenova ONNX conversion,
CC-BY-NC-4.0. Educational/noncommercial prototype; not a production claim.
Download explicitly with scripts/setup_translation.py; runtime never downloads.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from collections import Counter
import re
import threading
import time
import unicodedata

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = ROOT / '.cache/translation/nllb-200-distilled-600M'
MODEL_REPO = 'Xenova/nllb-200-distilled-600M'
MODEL_REVISION = '261c31d1a5732c67cdd16d80e8d6088507c7ccea'
MODEL_FILES = {
    'onnx/encoder_model_quantized.onnx': {
        'bytes': 419120483, 'sha256': '5cde664eacba07a62f198857ec6c06e09572b1ebb77c8137f1fa99ac604a3a28'},
    'onnx/decoder_model_quantized.onnx': {
        'bytes': 470533055, 'sha256': 'ddea619b640379609719becf91a488c5e6ce4c4b2052efbb5388edaed465a552'},
    'tokenizer.json': {
        'bytes': 17331224, 'sha256': '8ac789ad7dabea44d41537822d48c516ba358374c51813e2cba78c006e150c94'},
}
FLORES_CODES = {
    'en': 'eng_Latn', 'hi': 'hin_Deva', 'bn': 'ben_Beng', 'gu': 'guj_Gujr',
    'kn': 'kan_Knda', 'ml': 'mal_Mlym', 'mr': 'mar_Deva', 'pa': 'pan_Guru',
    'ta': 'tam_Taml', 'te': 'tel_Telu',
}
PLACEHOLDER = re.compile(r'\[\[VALUE_[A-Z]+\]\]')


def _protect_markers(text: str) -> tuple[str, dict[str, str]]:
    """Represent opaque caller placeholders as synthetic copyable numerals.

    These are generated markers, never the masked customer values. NLLB is not
    an instruction-following model and cannot be told to copy VALUE_A syntax.
    Every marker must survive exactly; no recovery invents a missing value.
    """
    mapping = {}
    base = 731901
    for token in dict.fromkeys(PLACEHOLDER.findall(text)):
        while str(base) in text or str(base) in mapping:
            base += 1
        mapping[str(base)] = token
        base += 1
    reverse = {token: marker for marker, token in mapping.items()}
    return PLACEHOLDER.sub(lambda match: reverse[match.group()], text), mapping


def _restore_markers(text: str, mapping: dict[str, str], original: str) -> str:
    normalized = ''.join(str(unicodedata.digit(char)) if char.isdigit() else char for char in text)
    for marker, token in mapping.items():
        # Some writing systems group digits with spaces or commas. Accept only
        # that formatting change, while preserving the exact digit sequence.
        pattern = r'(?<!\d)' + r'[ ,\u00a0]*'.join(marker) + r'(?!\d)'
        normalized = re.sub(pattern, lambda _: token, normalized)
    if Counter(PLACEHOLDER.findall(normalized)) != Counter(PLACEHOLDER.findall(original)):
        raise TranslationError('translation_placeholder_changed')
    return normalized


class TranslationError(RuntimeError):
    """Safe, bounded translation failure, without exposing input text."""


class TranslationUnavailable(TranslationError):
    pass


class _Models:
    def __init__(self, directory: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        self.encoder = ort.InferenceSession(str(directory / 'onnx/encoder_model_quantized.onnx'),
                                            sess_options=options, providers=['CPUExecutionProvider'])
        self.decoder = ort.InferenceSession(str(directory / 'onnx/decoder_model_quantized.onnx'),
                                            sess_options=options, providers=['CPUExecutionProvider'])
        self.tokenizer = Tokenizer.from_file(str(directory / 'tokenizer.json'))
        self.lock = threading.Lock()


_LOAD_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _cached_models(directory: str) -> _Models:
    return _Models(Path(directory))


def _models(directory: str) -> _Models:
    with _LOAD_LOCK:
        return _cached_models(directory)


class LocalTranslator:
    """Shared lazy CPU sessions; bounded greedy decoding and no text cache."""

    def __init__(self, model_dir: Path | None = None, *, max_tokens: int = 160,
                 timeout_seconds: float = 35):
        self.directory = Path(model_dir or DEFAULT_MODEL_DIR)
        self.max_tokens = min(max(8, max_tokens), 256)
        self.timeout_seconds = min(max(1., timeout_seconds), 120.)

    @staticmethod
    def available(model_dir: Path | None = None) -> bool:
        directory = Path(model_dir or DEFAULT_MODEL_DIR)
        return all((directory / name).is_file() and (directory / name).stat().st_size == info['bytes']
                   for name, info in MODEL_FILES.items())

    def translate(self, text: str, source_code: str, target_code: str) -> str:
        if source_code not in FLORES_CODES or target_code not in FLORES_CODES:
            raise TranslationError('unsupported_translation_language')
        if not isinstance(text, str) or not text.strip() or len(text) > 2200:
            raise TranslationError('invalid_translation_input')
        if source_code == target_code:
            return text
        if not self.available(self.directory):
            raise TranslationUnavailable('local_translation_files_missing')
        try:
            models = _models(str(self.directory.resolve()))
            if not models.lock.acquire(timeout=self.timeout_seconds):
                raise TranslationError('translation_busy')
            try:
                protected, markers = _protect_markers(text)
                translated = self._translate(models, protected, source_code, target_code)
                return _restore_markers(translated, markers, text)
            finally:
                models.lock.release()
        except TranslationError:
            raise
        except Exception:
            raise TranslationError('local_translation_failed') from None

    def _translate(self, models, text: str, source_code: str, target_code: str) -> str:
        import onnxruntime as ort

        began = time.perf_counter()
        tokenizer = models.tokenizer
        src_id = tokenizer.token_to_id(FLORES_CODES[source_code])
        tgt_id = tokenizer.token_to_id(FLORES_CODES[target_code])
        eos = tokenizer.token_to_id('</s>')
        if None in (src_id, tgt_id, eos):
            raise TranslationError('translation_language_token_missing')
        tokens = tokenizer.encode(text, add_special_tokens=False).ids
        if len(tokens) > 480:
            raise TranslationError('translation_input_too_long')
        # The pinned tokenizer config specifies legacy_behaviour=false:
        # source language, sentence tokens, EOS; target is forced decoder BOS.
        input_ids = np.asarray([[src_id] + tokens + [eos]], dtype=np.int64)
        attention_mask = np.ones_like(input_ids)
        run_options = ort.RunOptions()
        deadline = threading.Timer(self.timeout_seconds, lambda: setattr(run_options, 'terminate', True))
        deadline.daemon = True
        deadline.start()
        try:
            encoded = models.encoder.run(None, {'input_ids': input_ids, 'attention_mask': attention_mask}, run_options)[0]
            generated = [eos, tgt_id]
            for _ in range(self.max_tokens):
                if time.perf_counter() - began > self.timeout_seconds:
                    raise TranslationError('translation_timeout')
                values = models.decoder.run(['logits'], {
                    'input_ids': np.asarray([generated], dtype=np.int64),
                    'encoder_hidden_states': encoded,
                    'encoder_attention_mask': attention_mask,
                }, run_options)[0]
                next_id = int(np.argmax(values[0, -1, :]))
                if next_id == eos:
                    result = tokenizer.decode(generated[2:], skip_special_tokens=True).strip()
                    if not result:
                        raise TranslationError('translation_empty')
                    return result
                generated.append(next_id)
            raise TranslationError('translation_token_limit')
        except TranslationError:
            raise
        except Exception:
            if run_options.terminate or time.perf_counter() - began >= self.timeout_seconds:
                raise TranslationError('translation_timeout') from None
            raise TranslationError('translation_inference_failed') from None
        finally:
            deadline.cancel()
