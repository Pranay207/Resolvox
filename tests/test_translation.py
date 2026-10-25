"""Offline inference-contract tests; real translation quality is checked live."""
from types import SimpleNamespace

import numpy as np
import pytest

import src.translation as module
from src.translation import (LocalTranslator, TranslationError, TranslationUnavailable,
                             _protect_markers, _restore_markers)


def test_missing_weights_fail_closed_and_identical_language_needs_no_model(tmp_path):
    translator = LocalTranslator(tmp_path)
    assert not translator.available(tmp_path)
    assert translator.translate('same public policy', 'en', 'en') == 'same public policy'
    with pytest.raises(TranslationUnavailable, match='files_missing'):
        translator.translate('public policy', 'en', 'te')
    with pytest.raises(TranslationError, match='unsupported_translation_language'):
        translator.translate('public policy', 'en', 'zz')
    with pytest.raises(TranslationError, match='invalid_translation_input'):
        translator.translate('', 'en', 'te')


def test_available_requires_all_expected_file_lengths(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'MODEL_FILES', {'encoder.onnx': {'bytes': 3}, 'tokenizer.json': {'bytes': 2}})
    (tmp_path / 'encoder.onnx').write_bytes(b'123')
    assert not LocalTranslator.available(tmp_path)
    (tmp_path / 'tokenizer.json').write_bytes(b'12')
    assert LocalTranslator.available(tmp_path)
    (tmp_path / 'encoder.onnx').write_bytes(b'1')
    assert not LocalTranslator.available(tmp_path)


class Tokenizer:
    def token_to_id(self, token):
        return {'eng_Latn': 20, 'tel_Telu': 21, '</s>': 2}.get(token)

    def encode(self, text, add_special_tokens=False):
        assert add_special_tokens is False
        return SimpleNamespace(ids=[10, 11])

    def decode(self, ids, skip_special_tokens=True):
        assert ids == [30, 31]
        return 'తెలుగు సమాధానం'


class Encoder:
    def __init__(self):
        self.observed = None

    def run(self, names, inputs, options):
        self.observed = inputs
        return [np.ones((1, 4, 2), dtype=np.float32)]


class Decoder:
    def __init__(self, tokens=(30, 31, 2)):
        self.tokens = iter(tokens)
        self.observed = []

    def run(self, names, inputs, options):
        self.observed.append(inputs['input_ids'].tolist()[0])
        logits = np.zeros((1, 1, 40), dtype=np.float32)
        logits[0, -1, next(self.tokens)] = 10
        return [logits]


def test_greedy_decode_uses_source_language_prefix_and_forced_target_bos():
    models = SimpleNamespace(tokenizer=Tokenizer(), encoder=Encoder(), decoder=Decoder())
    assert LocalTranslator()._translate(models, 'public policy', 'en', 'te') == 'తెలుగు సమాధానం'
    assert models.encoder.observed['input_ids'].tolist() == [[20, 10, 11, 2]]
    assert models.decoder.observed == [[2, 21], [2, 21, 30], [2, 21, 30, 31]]


def test_truncated_generation_is_an_error_instead_of_a_partial_answer():
    models = SimpleNamespace(tokenizer=Tokenizer(), encoder=Encoder(), decoder=Decoder((30,) * 8))
    with pytest.raises(TranslationError, match='translation_token_limit'):
        LocalTranslator(max_tokens=8)._translate(models, 'policy', 'en', 'te')


def test_inference_error_does_not_expose_input_or_backend_exception():
    class BrokenEncoder:
        def run(self, *args):
            raise RuntimeError('private raw request should never escape')
    models = SimpleNamespace(tokenizer=Tokenizer(), encoder=BrokenEncoder(), decoder=Decoder())
    with pytest.raises(TranslationError) as error:
        LocalTranslator()._translate(models, 'private raw request', 'en', 'te')
    assert str(error.value) == 'translation_inference_failed'


def test_markers_preserve_values_and_accept_only_digit_formatting_changes():
    original = '[[VALUE_C]] refunds take [[VALUE_A]] to [[VALUE_B]] business days.'
    protected, markers = _protect_markers(original)
    assert 'VALUE' not in protected and len(markers) == 3
    assert _restore_markers(protected, markers, original) == original
    native_digits = protected.translate(str.maketrans('0123456789', '౦౧౨౩౪౫౬౭౮౯'))
    assert _restore_markers(native_digits, markers, original) == original
    damaged = protected.replace(next(iter(markers)), 'different')
    with pytest.raises(TranslationError, match='placeholder_changed'):
        _restore_markers(damaged, markers, original)
