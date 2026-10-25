"""Offline integration checks for the checked translation boundary, not fluency."""
import json
import re

import pytest

from src.agent import Agent, Resources
from src.llm import LLMUnavailable
from src.multilingual import (MultilingualAgent, _protect, _restore, _validate_roundtrip,
    _validate_script, _validate_tokens, _validate_query_intent, detect_language, normalize_native_digits)


class ScriptedLLM:
    def __init__(self, translations=(), core_answer=None):
        self.translations = list(translations)
        self.core_answer = core_answer
        self.calls = []
        self.last_metrics = {}
        self.last_provider = 'mock'

    def complete(self, system, user, *args, **kwargs):
        self.calls.append((system, user, kwargs))
        if 'faithful translation engine' not in system:
            if self.core_answer is None:
                raise LLMUnavailable('offline core mock')
            value = self.core_answer(json.loads(user))
            return json.dumps(value, ensure_ascii=False)
        if not self.translations:
            raise LLMUnavailable('offline translation mock')
        value = self.translations.pop(0)
        if isinstance(value, Exception):
            raise value
        return json.dumps({'translation': value}, ensure_ascii=False)


@pytest.fixture
def resources(monkeypatch):
    monkeypatch.delenv('TRANSLATION_MODEL', raising=False)
    monkeypatch.delenv('TRANSLATION_PROVIDER', raising=False)
    monkeypatch.delenv('TRANSLATION_TIMEOUT', raising=False)
    return Resources(dense=False)


def refund_llm():
    # Native acronym normalization leaves UPI as natural public payment context.
    def generated_from_sources(payload):
        assert 'verified_rule_summary' not in payload
        source = next(s for s in payload['source_text'] if s['id'] == 'REF-2')
        span = re.search(r'\|\s*UPI\s*\|\s*([^|]+)\|', source['text'])[1].strip()
        return {'decision': 'answer', 'answer': f'UPI refunds take {span} after initiation.',
                'citations': [{'id': source['id'], 'quote': source['text']}]}
    return ScriptedLLM([
        'How long does a UPI refund take?',
        'ప్రారంభించిన తర్వాత UPI రీఫండ్‌కు [[VALUE_A]] నుండి [[VALUE_B]] పని దినాలు పడుతుంది.',
        'UPI refunds take [[VALUE_A]] to [[VALUE_B]] business days after initiation.',
    ], core_answer=generated_from_sources)


def test_telugu_refund_uses_actual_sources_and_keeps_core_generation_route(resources):
    llm = refund_llm()
    resources.llm = llm
    agent = MultilingualAgent(resources, compose=True, translation_client=resources.llm)
    out = agent.respond('యూపీఐ రీఫండ్ ఎన్ని రోజుల్లో వస్తుంది?', language_hint='te')
    assert out['decision'] == 'answer' and out['evidence_supported']
    assert out['composition'] == 'grounded_llm'
    assert 'REF-2' in out['retrieved_chunk_ids']
    assert '1 to 3 business days' in out['source_answer']
    assert out['answer'].startswith('నేను ZentroMart AI')
    assert '1 నుండి 3' in out['answer'] and 'UPI' in out['answer']
    assert out['localization']['status'] == 'translated'
    assert out['localization']['roundtrip_checked']
    assert out['language'] == 'te' and agent.state.turn == 1
    translations = [(s,u,k) for s,u,k in llm.calls if 'translation engine' in s]
    assert len(translations) == 3
    assert all(k['cache'] is False and k['attempts'] == 1 and k['timeout'] == 20 for s,u,k in translations)
    assert any('source_text' in user for system,user,kwargs in llm.calls)


@pytest.mark.parametrize('text,code',[
    ('বাংলা ভাষায় বলুন', 'bn'), ('ગુજરાતીમાં કહો', 'gu'), ('ಕನ್ನಡದಲ್ಲಿ ಹೇಳಿ', 'kn'),
    ('മലയാളത്തിൽ പറയൂ', 'ml'), ('ਪੰਜਾਬੀ ਵਿੱਚ ਦੱਸੋ', 'pa'), ('தமிழில் சொல்லுங்கள்', 'ta'),
    ('తెలుగులో చెప్పండి', 'te'), ('हिंदी में बताइए', 'hi'),
])
def test_native_script_detection(text,code):
    assert detect_language(text) == code


def test_marathi_requires_explicit_selection_and_then_keeps_numeric_followup():
    assert detect_language('माझा परतावा कधी येईल?', 'mr') == 'mr'
    assert detect_language('1234', previous='mr') == 'mr'
    assert detect_language('Please explain', previous='mr') == 'en'


@pytest.mark.parametrize('text,expected',[
    ('ఒకటి రెండు మూడు నాలుగు', '1234'), ('ஒன்று இரண்டு மூன்று நான்கு', '1234'),
    ('ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು', '1234'), ('ഒന്ന് രണ്ട് മൂന്ന് നാല്', '1234'),
    ('એક બે ત્રણ ચાર', '1234'), ('এক দুই তিন চার', '1234'),
    ('एक दोन तीन चार', '1234'), ('ਇੱਕ ਦੋ ਤਿੰਨ ਚਾਰ', '1234'),
    ('నా అంకెలు ౧౨౩౪', 'నా అంకెలు 1234'),
])
def test_native_digit_sequences(text,expected):
    assert normalize_native_digits(text) == expected


def test_mask_restores_entities_without_putting_their_values_in_model_text():
    original = 'Order 89782837; last digits 4533; me@example.com; phone +919876543210; ELE-0012; 2026-10-25'
    masked, values = _protect(original)
    for value in ('89782837','4533','me@example.com','9876543210','ELE-0012','2026-10-25'):
        assert value not in masked
    assert _restore(masked, values) == original


@pytest.mark.parametrize('code',['bn','gu','kn','ml','mr','pa','ta','te'])
def test_offline_mode_is_explicit_and_never_calls_model_or_tools(resources,monkeypatch,code):
    llm = ScriptedLLM()
    resources.llm = llm
    monkeypatch.setattr(resources.tools,'lookup',lambda *a,**k: pytest.fail('lookup in disabled translation'))
    out = MultilingualAgent(resources,compose=False).respond('UPI refund?',language_hint=code)
    assert out['localization']['status'] == 'unavailable_offline'
    assert out['language'] == code and out['decision'] == 'clarify'
    assert not out['tool_calls'] and not out['sources'] and not llm.calls


@pytest.mark.parametrize('hint',['en','hi','hi-en'])
def test_legacy_language_hints_are_honored_without_translation(resources,hint):
    agent = MultilingualAgent(resources,compose=False)
    out = agent.respond('How long does a UPI refund take?',language_hint=hint)
    assert out['language'] == hint and 'localization' not in out
    expected = Agent(resources,compose=False).respond('How long does a UPI refund take?',language_hint=hint)
    assert out['answer'] == expected['answer']


def test_failed_query_translation_does_not_reach_tools(resources,monkeypatch):
    resources.llm = ScriptedLLM(['How long does a UPI refund take?'])
    # Input order ID is private; dropping its placeholder must fail closed.
    monkeypatch.setattr(resources.tools,'lookup',lambda *a,**k:pytest.fail('unexpected lookup'))
    agent = MultilingualAgent(resources,compose=True,translation_client=resources.llm)
    out = agent.respond('నా ఆర్డర్ 89782837 ఎక్కడ?',language_hint='te')
    assert out['localization']['status'] == 'query_translation_failed'
    assert agent.state.turn == 0 and not out['tool_calls']


def test_new_order_revokes_existing_auth_even_when_translation_fails(resources):
    agent = MultilingualAgent(resources,compose=False)
    agent.respond('Order 89782837')
    assert agent.respond('Last four digits 4533')['verified']
    agent.compose = True
    resources.llm = agent.translation_client = ScriptedLLM([LLMUnavailable('test')])
    out = agent.respond('నా ఆర్డర్ 77461439',language_hint='te')
    assert not out['verified'] and agent.state.order is None
    assert agent.state.order_id == '77461439'
    assert agent.state.pending_issue == agent.state.pending_intent == ''


def test_spoken_proof_stays_out_of_translation_input_output_and_state(resources):
    agent = MultilingualAgent(resources,compose=False)
    agent.respond('Order 89782837')
    agent.compose = True
    # Isolated digits need no input translation. Only safe English reply text
    # goes to translation, and deliberately unavailable output cannot undo auth.
    llm = ScriptedLLM([LLMUnavailable('test')])
    agent.translation_client = resources.llm = llm
    out = agent.respond('నాలుగు ఐదు మూడు మూడు',language_hint='te')
    assert out['verified'] and agent.state.order
    assert '4533' not in json.dumps(out,ensure_ascii=False) + repr(agent.state)
    assert 'నాలుగు ఐదు మూడు మూడు' not in out['transcript']
    assert llm.calls and all('4533' not in user for system,user,kwargs in llm.calls)
    assert out['localization']['status'] == 'answer_translation_failed'


def test_answer_translation_failure_does_not_repeat_ticket_creation(resources,monkeypatch):
    tickets=[]
    def ticket(summary,oid,reason,intent):
        tickets.append(reason)
        result={'created':True,'ticket_id':'synthetic-ticket'}
        return result,{'name':'create_ticket','arguments':{'reason':reason},'result':result}
    monkeypatch.setattr(resources.tools,'ticket',ticket)
    llm=ScriptedLLM(['I want a human agent', LLMUnavailable('test')])
    resources.llm=llm
    agent=MultilingualAgent(resources,compose=True,translation_client=resources.llm)
    out=agent.respond('నాకు మానవ ప్రతినిధి కావాలి',language_hint='te')
    assert tickets == ['human_requested'] or len(tickets)==1
    assert out['localization']['status']=='answer_translation_failed'
    assert len([x for x in out['tool_calls'] if x['name']=='create_ticket'])==1
    assert agent.state.turn==1


def test_translator_cannot_turn_refund_question_into_ticket_creation(resources,monkeypatch):
    resources.llm=ScriptedLLM(['I want a human agent'])
    monkeypatch.setattr(resources.tools,'ticket',lambda *a,**k:pytest.fail('translation must not trigger a ticket'))
    out=MultilingualAgent(resources,compose=True,translation_client=resources.llm).respond('రీఫండ్ ఎప్పుడు వస్తుంది?',language_hint='te')
    assert out['localization']['status']=='query_translation_failed'
    assert not out['tool_calls']


@pytest.mark.parametrize('wrong',[
    'Refunds take [[VALUE_A]] days.',
    'క Your refund takes [[VALUE_A]] business days after initiation.',
    'हिंदी में [[VALUE_A]] दिन।',
])
def test_wrong_or_token_native_script_is_rejected(wrong):
    with pytest.raises(ValueError):
        _validate_script(wrong,'te')


@pytest.mark.parametrize('original,wrong',[
    ('Refunds take 1 to 3 business days after initiation.', 'Refunds take 1 to 5 business days after initiation.'),
    ('Refunds take 1 to 3 business days after initiation.', 'Refunds take 1 to 3 calendar days after initiation.'),
    ('This is not refundable unless damaged.', 'This is refundable unless damaged.'),
    ('Refunds take 1 to 3 business days after initiation.', 'Refunds take 1 to 3 business days before initiation.'),
    ('Which payment method did you use?', 'What do you want?'),
    ('I cannot cancel this order.', 'I cancelled this order.'),
])
def test_roundtrip_rejects_quantity_condition_content_and_action_drift(original,wrong):
    with pytest.raises(ValueError):
        _validate_roundtrip(original,wrong)


def test_roundtrip_accepts_working_days_synonym():
    _validate_roundtrip('UPI refunds take 1 to 3 business days after initiation.',
                        'UPI refunds take 1 to 3 working days after initiation.')


def test_placeholder_mutation_and_new_values_are_rejected():
    with pytest.raises(ValueError):
        _validate_tokens('Order [[VALUE_A]]', 'Order [[VALUE_B]]')
    with pytest.raises(ValueError):
        _validate_tokens('Order [[VALUE_A]]', 'Order [[VALUE_A]] 1234')
    with pytest.raises(ValueError):
        _validate_tokens('Order [[VALUE_A]]', 'Order [[VALUE_A]] five')


@pytest.mark.parametrize('text,translated,code',[
    ('আপনার রিফান্ড নীতি কী?', 'What is your refund policy?', 'bn'),
    ('રિફંડના નિયમો શું છે?', 'What are the refund rules?', 'gu'),
    ('ਮੇਰੇ ਆਰਡਰ ਨਾਲ ਕੀ ਹੋਇਆ?', 'What happened to my order?', 'pa'),
])
def test_short_negation_words_do_not_match_inside_ordinary_words(text,translated,code):
    _validate_query_intent(text,translated,code)


def test_true_bengali_negation_is_preserved():
    with pytest.raises(ValueError):
        _validate_query_intent('মানব প্রতিনিধি চাই না', 'I want a human agent', 'bn')


def test_faithful_negative_human_preference_cannot_create_a_ticket(resources,monkeypatch):
    llm=ScriptedLLM(['I do not want a human agent'])
    monkeypatch.setattr(resources.tools,'ticket',lambda *a,**k:pytest.fail('negated handover must not create a ticket'))
    out=MultilingualAgent(resources,compose=True,translation_client=llm).respond('মানব প্রতিনিধি চাই না',language_hint='bn')
    assert out['localization']['status']=='query_translation_failed'


def test_local_translator_client_seam_keeps_masked_values(resources):
    class FakeLocal:
        def __init__(self): self.calls=[]
        def translate(self,text,source_code,target_code):
            self.calls.append((text,source_code,target_code))
            return 'Which payment method did you use?'
    client=FakeLocal()
    agent=MultilingualAgent(resources,compose=True,translation_client=client)
    assert agent._translate('ఏ పద్ధతిలో చెల్లించారు?', 'te','en')=='Which payment method did you use?'
    assert len(client.calls)==1


def test_missing_local_weights_fail_closed_without_implicit_llm(resources,monkeypatch):
    from src.translation import LocalTranslator
    monkeypatch.setattr(LocalTranslator,'available',lambda *a:False)
    resources.llm=ScriptedLLM()
    agent=MultilingualAgent(resources,compose=True,translation_engine='local')
    out=agent.respond('రీఫండ్ ఎప్పుడు?',language_hint='te')
    assert out['localization']['status']=='query_translation_failed'
    assert not resources.llm.calls and not out['tool_calls']


@pytest.mark.parametrize('translated',["I don't want a human agent", 'I do not want a human agent'])
def test_english_negative_preferences_are_safe_with_regional_reply_hint(translated):
    with pytest.raises(ValueError):
        _validate_query_intent(translated,translated,'te')


def test_reversed_duration_range_is_not_equivalent():
    with pytest.raises(ValueError):
        _validate_roundtrip('UPI refunds take 1 to 3 business days after initiation.',
                            'UPI refunds take 3 to 1 business days after initiation.')


@pytest.mark.parametrize('original',['యూపీఐ', 'யூபிஐ', 'ಯುಪಿಐ', 'യുപിഐ', 'यूपीआई', 'ইউপিআই', 'યુપીઆઈ', 'ਯੂਪੀਆਈ'])
def test_public_upi_native_alias_stays_natural_while_numbers_are_masked(original):
    masked, values = _protect(original + ' 1234')
    assert 'UPI' in masked and '1234' not in masked
    assert _restore(masked,values)=='UPI 1234'


def test_translation_cannot_omit_public_upi_payment_context(resources):
    llm=ScriptedLLM(['How long does a refund take?'])
    out=MultilingualAgent(resources,compose=True,translation_client=llm).respond('యూపీఐ రీఫండ్ ఎప్పుడు?',language_hint='te')
    assert out['localization']['status']=='query_translation_failed'


@pytest.mark.parametrize('alias',['యుపీఐ','யுபிஐ','യൂപിഐ','ಯೂಪಿಐ','యూ.పీ.ఐ'])
def test_common_upi_vowel_and_punctuation_variants(alias):
    assert _protect(alias)[0]=='UPI'


def test_equivalent_refund_clock_start_wording_keeps_business_day_facts():
    _validate_roundtrip('UPI refunds take 1 to 3 business days after initiation.',
        '1 to 3 working days from the start of UPI refunds.')


def test_start_of_business_is_not_refund_initiation():
    with pytest.raises(ValueError):
        _validate_roundtrip('UPI refunds take 1 to 3 business days after initiation.',
            'UPI refunds take 1 to 3 working days from the start of business.')


@pytest.mark.parametrize('text',[
    'यू पी आई रिफंड शुरू होने के बाद आने में कितने कार्य दिवस लगते हैं',
    'यूपीआई रिफंड में कितने दिन लगते हैं?',
    'यू.पी.आई. रिफंड में कितने दिन लगते हैं?',
])
def test_required_hindi_upi_stt_spelling_uses_refund_policy(resources,text):
    out=Agent(resources,compose=False).respond(text)
    assert out['decision']=='answer' and out['language']=='hi'
    assert 'REF-2' in out['retrieved_chunk_ids']
    assert '1' in out['answer'] and '3' in out['answer']
    assert 'भुगतान तरीका' not in out['answer']
