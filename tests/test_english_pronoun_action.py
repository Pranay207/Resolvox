"""Actual-module behavioral controls for a bounded generic pronoun prerequisite."""
import os
import socket
import sys
import pytest
import requests
if os.environ.get('RESOLVOX_ENGLISH_ACTION_TEST_ROOT'):
    sys.path.insert(0, os.environ['RESOLVOX_ENGLISH_ACTION_TEST_ROOT'])
from src import grounding as guard
from src.document_answers import _validate_context


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('No HTTP/model calls in action-classification controls')
    monkeypatch.setattr(requests.sessions.Session, 'request', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)


PRIMARY='A refund to UPI takes 1 to 3 business days after it is initiated.'
SOURCE={'id':'test-source','text':'UPI refunds arrive in 1 to 3 business days after initiation.'}


@pytest.mark.parametrize('text', [
    PRIMARY,
    'A refund takes two to four working days after it is initiated.',
    'A payment via NEFT takes 2 days after it is approved.',
    'A pickup takes 1 business day after it is scheduled.',
    'An order takes 2 calendar days after it is created.',
    'A request through portal takes from 3 to 6 hours after it is raised.',
    'A ticket takes between one and three hours after it is issued.',
    'A return takes 2-4 weeks after it is approved.',
])
def test_generic_present_clock_with_present_prerequisite_is_not_a_completed_claim(text):
    view=guard._english_pronoun_prerequisite_view(text)
    assert view != text
    assert view.endswith('after a generic prerequisite.')
    assert not guard._completed_action(text)


@pytest.mark.parametrize('claim', [
    'I have created a ticket.',
    'Your refund has been processed.',
    'The order is cancelled.',
    'The payment was credited.',
])
@pytest.mark.parametrize('position', ['before','consequent','neighbor'])
def test_actual_action_claims_before_after_and_in_neighbors_remain_rejected(claim,position):
    if position=='before':
        text=claim+' '+PRIMARY
    elif position=='consequent':
        text=PRIMARY[:-1]+', '+claim
    else:
        text=PRIMARY+' '+claim
    assert guard._english_pronoun_prerequisite_view(text)==text
    assert guard._completed_action(text)


@pytest.mark.parametrize('text', [
    PRIMARY.replace('it is initiated','it was initiated'),
    PRIMARY.replace('it is initiated','it has been initiated'),
    PRIMARY.replace('it is initiated','it had been initiated'),
    PRIMARY.replace('it is initiated','it is already initiated'),
    PRIMARY.replace('it is initiated','it is initiated today'),
    PRIMARY.replace('it is initiated','it is initiated now'),
    PRIMARY.replace('it is initiated','it is initiated on 14 October 2026'),
    PRIMARY.replace('it is initiated','it is initiated on Monday'),
    PRIMARY.replace('it is initiated','it is initiated by me'),
    PRIMARY.replace('it is initiated','it is initiated by our team'),
    PRIMARY.replace('A refund','Your refund'),
    PRIMARY.replace('A refund','My refund'),
    PRIMARY.replace('A refund','The refund'),
    PRIMARY.replace('takes','took'),
    PRIMARY.replace('takes','will take'),
    PRIMARY.replace('A refund to UPI','A refund to your account'),
    PRIMARY.replace('A refund to UPI','A refund to my account'),
    'Today, '+PRIMARY,
    'On Monday, '+PRIMARY,
    PRIMARY+' It was yesterday.',
    PRIMARY+' It is done.',
    PRIMARY+' Initiated on 14 October 2026.',
    PRIMARY[:-1],
])
def test_personal_past_current_dated_actor_and_unbounded_forms_are_not_exempted(text):
    if text==PRIMARY[:-1]:
        # An actual end-of-text is an explicit boundary, even without punctuation.
        assert not guard._completed_action(text)
    else:
        assert guard._english_pronoun_prerequisite_view(text)==text
        assert guard._completed_action(text)


@pytest.mark.parametrize('text', [
    'The refund is processed within 3 to 5 business days.',
    'I have processed your refund.',
    'Your refund has been initiated.',
    'A refund is initiated today.',
    'The payment was completed.',
    'If a refund is initiated, I have created a ticket.',
    'रिफंड जारी कर दिया गया है।',
])
def test_unconditioned_english_and_hindi_action_guards_are_preserved(text):
    assert guard._english_pronoun_prerequisite_view(text)==text
    assert guard._completed_action(text)


@pytest.mark.parametrize('text', [
    'A refund to UPI takes 1 to 3 business days after it is not initiated.',
    'The refund has not been initiated.',
    'The refund is not processed.',
    'No refund status is available.',
])
def test_negation_and_uncertainty_do_not_invent_performed_actions(text):
    assert guard._english_pronoun_prerequisite_view(text)==text
    assert not guard._completed_action(text)


def test_uncertain_neighbor_does_not_erase_actual_claim():
    text=PRIMARY+' I have created a ticket. Its status is unknown.'
    assert guard._completed_action(text)
    assert guard._english_pronoun_prerequisite_view(text)==text


def test_only_prerequisite_bytes_change():
    text='  '+PRIMARY+'  '
    view=guard._english_pronoun_prerequisite_view(text)
    assert view==text.replace('after it is initiated','after a generic prerequisite')


def test_exact_correct_primary_passes_both_context_and_strict_source_validation():
    value={'answer':PRIMARY,'covered':True,'needs_clarification':False}
    result=_validate_context(value,[SOURCE],{},'en',query='How long does a refund to UPI take after initiation?')
    assert result['answer']==PRIMARY and result['covered'] is True
    assert result['decision']=='answer' and result['source_ids']==[SOURCE['id']]
    strict={'answer':PRIMARY,'covered':True,'citations':[{'id':SOURCE['id'],'quote':SOURCE['text']}]}
    assert guard.validate_generated(strict,[SOURCE])==(PRIMARY,[SOURCE['id']])


@pytest.mark.parametrize('answer,code', [
    (PRIMARY.replace('1 to 3','1 to 5'),'unsupported_number'),
    (PRIMARY.replace('business days','hours'),'unsupported_quantity_unit'),
    (PRIMARY.replace('business days','calendar days'),'unsupported_quantity_unit'),
    (PRIMARY+' I have created a ticket.','unsupported_action'),
    (PRIMARY+' Reach user@example.com.','unsupported_action'),
    ('For help, reach user@example.com.','private_identifier'),
])
def test_source_quantity_action_and_privacy_guards_remain_enforced(answer,code):
    value={'answer':answer,'covered':True,'citations':[{'id':SOURCE['id'],'quote':SOURCE['text']}]}
    with pytest.raises(ValueError,match=code):
        guard.validate_generated(value,[SOURCE])

@pytest.mark.parametrize('suffix', [
    ' It went through.',
    ' It succeeded.',
    ', which confirms completion.',
    ' हो गया।',
    ' कर दिया।',
    ' Normal policy limits apply.',
    ' Its status is unknown.',
])
def test_any_neighbor_or_consequent_prose_structurally_declines_exemption(suffix):
    text=(PRIMARY[:-1] if suffix.startswith(',') else PRIMARY)+suffix
    assert guard._english_pronoun_prerequisite_view(text)==text
    assert guard._completed_action(text)


@pytest.mark.parametrize('route', [
    'UPI that went through',
    'UPI sent Monday',
    'UPI that succeeded',
    'a bank transfer',
])
def test_multiword_route_cannot_hide_a_relative_or_reduced_action_claim(route):
    text=PRIMARY.replace('to UPI','to '+route)
    assert guard._english_pronoun_prerequisite_view(text)==text
    assert guard._completed_action(text)
