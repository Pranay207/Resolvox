"""Language routes shared by the console, agent and Gnani speech adapter.

The ten base languages match Gnani Prisma REST's documented locale list.
Hinglish is an additional code-mixed TTS option; its STT route remains en-IN.
Provider references (verified 25 October 2026):
https://docs.gnani.ai/api/STT/speech-to-text
https://docs.gnani.ai/api/TTS/available-voices
"""

LANGUAGE_NAMES = {
    'en': 'English',
    'hi': 'Hindi',
    'ta': 'Tamil',
    'te': 'Telugu',
    'kn': 'Kannada',
    'ml': 'Malayalam',
    'mr': 'Marathi',
    'bn': 'Bengali',
    'gu': 'Gujarati',
    'pa': 'Punjabi',
    'hi-en': 'Hinglish',
}
STT_CODES = {code: f'{code}-IN' for code in LANGUAGE_NAMES if code != 'hi-en'}
STT_CODES['hi-en'] = 'en-IN'
TTS_CODES = {code: f'{code}-IN' for code in LANGUAGE_NAMES if code != 'hi-en'}
TTS_CODES['hi-en'] = 'hi-en'
TTS_VOICES = {
    'en': 'Kaveri', 'hi': 'Nalini', 'ta': 'Asmita', 'te': 'Suhana',
    'kn': 'Saanvi', 'ml': 'Reshma', 'mr': 'Zahira', 'bn': 'Kirra',
    'gu': 'Falak', 'pa': 'Mehuli', 'hi-en': 'Poorvi',
}


def normalize_language(value: str) -> str:
    """Accept an internal code, Indian locale or display name; reject unknowns.

    Only supported routes are accepted. For example en-US is not silently
    rewritten into en-IN, and an unsupported language never becomes English.
    """
    if not isinstance(value, str):
        raise ValueError('Language must be a supported code or Indian locale')
    key = value.strip().replace('_', '-').lower()
    aliases = {code: code for code in LANGUAGE_NAMES}
    aliases.update({locale.lower(): code for code, locale in TTS_CODES.items()})
    aliases.update({name.lower(): code for code, name in LANGUAGE_NAMES.items()})
    try:
        return aliases[key]
    except KeyError:
        raise ValueError(f'Unsupported language: {value!r}') from None


def language_options() -> list[str]:
    """Return stable internal codes, suitable for a UI's format_func labels."""
    return list(LANGUAGE_NAMES)
