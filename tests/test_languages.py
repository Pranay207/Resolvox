"""The registry covers ten Gnani languages and the Hinglish speech option."""
import pytest
from src.languages import LANGUAGE_NAMES, STT_CODES, TTS_CODES, TTS_VOICES, normalize_language, language_options

ROUTES = [
    ('en', 'en-IN', 'Kaveri'), ('hi', 'hi-IN', 'Nalini'),
    ('ta', 'ta-IN', 'Asmita'), ('te', 'te-IN', 'Suhana'),
    ('kn', 'kn-IN', 'Saanvi'), ('ml', 'ml-IN', 'Reshma'),
    ('mr', 'mr-IN', 'Zahira'), ('bn', 'bn-IN', 'Kirra'),
    ('gu', 'gu-IN', 'Falak'), ('pa', 'pa-IN', 'Mehuli'),
    ('hi-en', 'hi-en', 'Poorvi'),
]

@pytest.mark.parametrize('code,locale,voice', ROUTES)
def test_each_language_has_one_explicit_provider_route(code, locale, voice):
    assert normalize_language(code) == code
    assert normalize_language(' '+locale.upper().replace('-', '_')+' ') == code
    assert normalize_language(LANGUAGE_NAMES[code]) == code
    assert TTS_CODES[code] == locale
    assert TTS_VOICES[code] == voice
    assert STT_CODES[code] == ('en-IN' if code == 'hi-en' else locale)


def test_ten_distinct_base_languages_plus_hinglish():
    assert len(LANGUAGE_NAMES) == 11
    assert len(set(STT_CODES.values())) == 10
    assert language_options() == [route[0] for route in ROUTES]
    assert set(LANGUAGE_NAMES) == set(STT_CODES) == set(TTS_CODES) == set(TTS_VOICES)

@pytest.mark.parametrize('unsupported', ['', 'fr', 'fr-FR', 'en-US', 'auto', 'hi, en', None, 42])
def test_unknown_language_is_never_silently_replaced_with_english(unsupported):
    with pytest.raises(ValueError, match='[Ll]anguage'):
        normalize_language(unsupported)
