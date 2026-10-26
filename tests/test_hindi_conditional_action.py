"""Behavioral controls for actual staged/applied src.grounding; no source wrappers."""
import os
from pathlib import Path
import socket
import sys
import pytest
import requests
if os.environ.get('RESOLVOX_HINDI_TEST_ROOT'):
    sys.path.insert(0, os.environ['RESOLVOX_HINDI_TEST_ROOT'])
from src import grounding as draft

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('No network/model calls in grammatical-scope tests')
    monkeypatch.setattr(requests.sessions.Session, 'request', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)


@pytest.mark.parametrize('text', [
    'अगर ऑर्डर शिप हो गया है तो इसे कैंसिल नहीं किया जा सकता है।',
    'हां, अगर ऑर्डर शिप हो गया है तो इसे कैंसिल नहीं किया जा सकता है।',
    'यदि कोई ऑर्डर शिप हो चुका है, जानकारी देखें।',
    'यदि एक टिकट बनाया गया है तो अगला नियम लागू होता है।',
    'अगर रिफंड जारी किया गया है, जानकारी देखें।',
    'अगर भुगतान पूरा हो गया है। नियम देखें।',
])
def test_bounded_generic_prerequisite_is_not_a_performed_action_claim(text):
    assert not draft._completed_action(text)


@pytest.mark.parametrize('claim', [
    'मैंने टिकट बना दिया है।',
    'आपका टिकट बनाया गया है।',
    'रिफंड जारी कर दिया गया है।',
    'ऑर्डर रद्द कर दिया गया है।',
])
@pytest.mark.parametrize('position', ['before', 'consequent', 'neighbor'])
def test_completed_claims_before_after_and_in_neighboring_clauses_are_retained(claim, position):
    condition = 'अगर ऑर्डर शिप हो गया है'
    if position == 'before':
        text = claim + ' ' + condition + ' तो जानकारी देखें।'
    elif position == 'consequent':
        text = condition + ' तो ' + claim
    else:
        text = condition + ', जानकारी देखें। ' + claim
    assert draft._completed_action(text)


@pytest.mark.parametrize('text', [
    'अगर आपका ऑर्डर शिप हो गया है तो जानकारी देखें।',
    'अगर मेरा ऑर्डर शिप हो गया है तो जानकारी देखें।',
    'अगर ऑर्डर मैंने रद्द कर दिया है तो जानकारी देखें।',
    'अगर ऑर्डर हमारे द्वारा रद्द किया गया है तो जानकारी देखें।',
    'अगर रिफंड आपको जारी हुआ है तो जानकारी देखें।',
    'अगर ऑर्डर 14 अक्टूबर 2026 को शिप हो गया है तो जानकारी देखें।',
    'अगर ऑर्डर शिप हो गया है और टिकट बना दिया गया है तो जानकारी देखें।',
    'अगर टिकट बना दिया है तो जानकारी देखें।',
    'अगर ऑर्डर शिप हो गया है',
    'समझ लें कि अगर ऑर्डर शिप हो गया है तो जानकारी देखें।',
])
def test_actor_specific_dated_coordinated_and_unbounded_forms_are_not_exempted(text):
    assert draft._hindi_generic_prerequisite_view(text) == text
    assert draft._completed_action(text)


@pytest.mark.parametrize('text', [
    'ऑर्डर शिप हो गया है।',
    'टिकट बनाया गया है।',
    'रिफंड जारी कर दिया गया है।',
    'I have processed your refund.',
    'Your order has been cancelled.',
    'The refund is processed within 3 to 5 business days.',
    'If a refund is initiated, I have created a ticket.',
])
def test_unconditioned_status_and_english_action_guards_remain_unchanged(text):
    assert draft._completed_action(text)


@pytest.mark.parametrize('text', [
    'अगर ऑर्डर शिप हो गया है तो जानकारी उपलब्ध नहीं है।',
    'यदि टिकट बनाया गया है तो उसकी स्थिति की पुष्टि नहीं है।',
    'ऑर्डर रद्द नहीं हुआ है।',
    'इसकी पुष्टि नहीं है।',
])
def test_uncertainty_or_negation_does_not_invent_a_completed_consequence(text):
    assert not draft._completed_action(text)


def test_later_uncertainty_does_not_erase_an_actual_completed_claim():
    text = 'अगर ऑर्डर शिप हो गया है तो रिफंड जारी कर दिया गया है। बाकी जानकारी की पुष्टि नहीं है।'
    assert draft._completed_action(text)


def test_only_the_antecedent_view_changes_and_the_consequent_is_byte_preserved():
    antecedent = 'अगर कोई ऑर्डर शिप हो गया है'
    consequence = ' तो स्थिति पढ़ें।'
    viewed = draft._hindi_generic_prerequisite_view(antecedent + consequence)
    assert viewed == 'अगर सामान्य शर्त' + consequence
    claim = antecedent + ' तो आपका रिफंड जारी कर दिया गया है।'
    assert draft._hindi_generic_prerequisite_view(claim) == claim
    assert draft._completed_action(claim)


@pytest.mark.parametrize('text', [
    'मैंने, अगर ऑर्डर शिप हो गया है, इसे पूरा कर दिया है।',
    'ग्राहक ने, अगर ऑर्डर शिप हो गया है, इसे पूरा कर दिया है।',
    'अगर ऑर्डर शिप हो गया है तो वह हो गया है।',
    'अगर ऑर्डर शिप हो गया है तो आपका काम पूरा है।',
    'अगर ऑर्डर आज शिप हो गया है तो जानकारी देखें।',
    'अगर भुगतान कल हो गया है तो जानकारी देखें।',
    'अगर ऑर्डर शिप हो गया है तो जानकारी देखें। यदि टिकट बनाया गया है तो नियम देखें।',
])
def test_other_completion_person_or_temporal_cues_decline_masking(text):
    assert draft._hindi_generic_prerequisite_view(text) == text
    assert draft._completed_action(text)


@pytest.mark.parametrize('text', [
    'अगर ऑर्डर १४ अक्टूबर २०२६ को शिप हो गया है तो जानकारी देखें।',
    'यदि टिकट १५ अक्टूबर को बनाया गया है तो विवरण देखें।',
    'अगर रिफंड राहुल को जारी किया गया है तो जानकारी देखें।',
    'अगर भुगतान १४ हो गया है तो जानकारी देखें।',
    'अगर भुगतान १४-अक्टूबर हो गया है तो जानकारी देखें।',
    'अगर रिफंड राहुल-को जारी किया गया है तो जानकारी देखें।',
    'अगर टिकट ग्राहक-को बनाया गया है तो विवरण देखें।',
])
def test_unicode_digits_and_explicit_recipients_are_not_masked(text):
    assert draft._hindi_generic_prerequisite_view(text) == text
    assert draft._completed_action(text)


@pytest.mark.parametrize('claim', [None, 'आपका टिकट बनाया गया है।', 'मैंने रिफंड जारी कर दिया है।'])
def test_shared_strict_validator_keeps_action_rejection_after_conditional_view(claim):
    source = {'id': 'test-source', 'text': 'ऑर्डर की स्थिति के अनुसार नियम देखें।'}
    value = {'answer': 'अगर ऑर्डर शिप हो गया है तो जानकारी देखें।' + ((' ' + claim) if claim else ''),
             'covered': True, 'citations': [{'id': source['id'], 'quote': source['text']}]}
    if claim:
        with pytest.raises(ValueError, match='unsupported_action'):
            draft.validate_generated(value, [source])
    else:
        assert draft.validate_generated(value, [source]) == (value['answer'], [source['id']])


@pytest.mark.parametrize('text', [
    'अगर ऑर्डर सोमवार रद्द हुआ है तो जानकारी देखें।',
    'अगर टिकट अक्टूबर बनाया गया है तो विवरण देखें।',
    'अगर ऑर्डर अज्ञात हो गया है तो जानकारी देखें।',
])
def test_extra_temporal_or_unknown_predicate_tokens_do_not_fit_closed_grammar(text):
    assert draft._hindi_generic_prerequisite_view(text) == text
    assert draft._completed_action(text)


