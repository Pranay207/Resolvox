"""An initial affirmation must agree with the first requested permission."""
import json
import pytest
from src.answer_polarity import check_answer_acknowledgment
from src.document_answers import document_reply
from src.generation_diagnostics import validation_code


@pytest.mark.parametrize('query,answer', [
    ('Can I cancel a shipped order?', 'Yes, it cannot be cancelled after shipping.'),
    ('Can I cancel a shipped order?', 'Yes, you cannot cancel after shipping.'),
    ('Can I return this item?', 'Yes, returns are not allowed.'),
    ('Can I return this item?', 'Yes, you cannot return the item.'),
    ('ऑर्डर शिप हो गया है, क्या अब कैंसिल हो सकता है?', 'हां, अगर ऑर्डर शिप हो गया है तो इसे कैंसिल नहीं किया जा सकता है।'),
    ('क्या इसे रिटर्न कर सकते हैं?', 'हाँ, इसे रिटर्न नहीं किया जा सकता है।'),
    ('Shipped order cancel kar sakte hain kya?', 'Haan, order cancel nahi kiya ja sakta.'),
])
def test_contradictory_first_permission_is_rejected(query, answer):
    with pytest.raises(ValueError, match='^contradictory_answer_acknowledgment$'):
        check_answer_acknowledgment(answer, query)


@pytest.mark.parametrize('query,answer', [
    ('Can I cancel before shipping?', 'Yes, you can cancel before shipping.'),
    ('Can I cancel before shipping?', 'Yes, you can cancel before shipping, but it cannot be cancelled after shipping.'),
    ('Can I cancel a shipped order?', 'No, it cannot be cancelled after shipping.'),
    ('Can I cancel a shipped order?', 'An order cannot be cancelled after shipping.'),
    ("Is it true I cannot cancel after shipping?", 'Yes, it cannot be cancelled after shipping.'),
    ('क्या इसे कैंसिल नहीं कर सकते?', 'हाँ, इसे कैंसिल नहीं किया जा सकता है।'),
    ('Can I get a refund?', 'Yes, we cannot refund it directly, but a human colleague will review it.'),
    ('Can I return shoes?', 'Yes, there is no reverse pickup fee for Plus members.'),
    ('Can I cancel before shipping?', 'Yes, you can cancel before shipping and it cannot be cancelled after shipping.'),
    ('How can I cancel a shipped order?', 'Yes, it cannot be cancelled after shipping.'),
])
def test_conditions_negative_questions_and_staff_limits_are_preserved(query, answer):
    check_answer_acknowledgment(answer, query)


def test_presentation_edit_preserves_entire_generated_policy_suffix_without_extra_inference():
    source = {'id': 'changed-cancel-rule', 'doc_type': 'policy', 'status': 'current',
              'text': 'After shipping, an order cannot be cancelled.'}
    calls = []
    class Client:
        def complete(self, system, user, **options):
            calls.append((system, json.loads(user), options))
            return json.dumps({'answer': 'Yes, it cannot be cancelled after shipping.',
                               'covered': True, 'needs_clarification': False})
    out = document_reply(Client(), 'Can I cancel a shipped order?', 'en', [source], context_provenance=True)
    assert out['answer'] == 'it cannot be cancelled after shipping.'
    assert len(calls) == out['generation_attempts'] == 1
    assert out['repair_errors'] == [] and out['repair_attempted'] is False
    assert out['presentation_edits'] == [{'kind': 'remove_contradictory_opening_acknowledgment',
        'removed_prefix': 'Yes, ', 'inserted_text': '', 'remaining_text_unchanged': True}]
    assert calls[0][1]['source_text'] == [source]
    assert validation_code('contradictory_answer_acknowledgment:private suffix') == 'contradictory_answer_acknowledgment'


def test_prefix_edit_does_not_bypass_unsupported_number_validation():
    class Client:
        def complete(self, *args, **kwargs):
            return json.dumps({'answer': 'Yes, it cannot be cancelled after 19 days.',
                               'covered': True, 'needs_clarification': False})
    source = {'id': 'cancel-rule', 'doc_type': 'policy', 'status': 'current',
              'text': 'After shipping, an order cannot be cancelled.'}
    with pytest.raises(ValueError, match='unsupported_number'):
        document_reply(Client(), 'Can I cancel a shipped order?', 'en', [source], context_provenance=True)


def test_a_help_request_is_not_treated_as_an_eligibility_question():
    check_answer_acknowledgment('Yes, returns are not allowed after the window, but I can explain the rule.',
                               'Can you help me return an item?')


def test_a_changed_documented_permission_is_not_replaced_by_a_compiled_prohibition():
    source = {'id': 'changed-allowed-rule', 'doc_type': 'policy', 'status': 'current',
              'text': 'After shipping, orders can be cancelled through support.'}
    answer = 'Yes, orders can be cancelled after shipping through support.'
    class Client:
        def complete(self, *args, **kwargs):
            return json.dumps({'answer': answer, 'covered': True, 'needs_clarification': False})
    out = document_reply(Client(), 'Can I cancel a shipped order?', 'en', [source], context_provenance=True)
    assert out['answer'] == answer and out['generation_attempts'] == 1
