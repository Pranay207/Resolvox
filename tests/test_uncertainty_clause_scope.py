"""A model's insufficient-evidence flag cannot authorize a spoken policy denial."""
import json
import pytest
from src.agent import Agent, Resources
from src.grounding import abstention


@pytest.fixture
def resources():
    return Resources(dense=False)


# Explicit output hints isolate presentation from sparse-only query recall.
@pytest.mark.parametrize('language,question,proposal', [
    ('en', 'Are researcher reward vouchers available?', "We don't have researcher reward vouchers."),
    ('hi', 'Are researcher reward vouchers available?',
     'रिसर्चर रिवॉर्ड वाउचर नहीं मिलते और मेरे पास जानकारी नहीं है।'),
    ('hi-en', 'Are researcher reward vouchers available?',
     'Researcher reward vouchers nahi milte aur mere paas jaankari nahi hai.'),
])
def test_unproven_denials_are_rejected_before_host_abstention(resources, monkeypatch, language, question, proposal):
    calls = []
    def complete(system, user, **options):
        calls.append(json.loads(user))
        return json.dumps({'answer': proposal, 'covered': False, 'needs_clarification': False})
    monkeypatch.setattr(resources.llm, 'complete', complete)
    out = Agent(resources, compose=True).respond(question, language_hint=language)
    assert len(calls) == 2
    assert out['language'] == language
    assert out['answer'].endswith(abstention(language))
    assert proposal not in out['answer']
    assert not out['evidence_supported']
    assert out['composition'] == 'abstained_model_or_evidence'
    assert out['generation']['repair_errors'] == ['uncited_substantive_refusal'] * 2
    assert out['generation']['generation_attempts'] == 2
    assert out['tool_calls'] == []


def test_plain_validated_uncertainty_remains_the_models_own_message(resources, monkeypatch):
    proposed = 'I cannot confirm this from the supplied evidence.'
    monkeypatch.setattr(resources.llm, 'complete', lambda *a, **k: json.dumps({
        'answer': proposed, 'covered': False, 'needs_clarification': False}))
    out = Agent(resources, compose=True).respond('Are researcher reward vouchers available?')
    assert out['answer'].endswith(proposed)
    assert out['generation']['covered'] is False
    assert out['generation']['generation_attempts'] == 1
    assert out['decision'] == 'answer'


def test_focused_missing_detail_question_is_not_replaced_by_generic_uncertainty(resources, monkeypatch):
    question = 'Which program are you asking about?'
    monkeypatch.setattr(resources.llm, 'complete', lambda *a, **k: json.dumps({
        'answer': question, 'covered': False, 'needs_clarification': True}))
    out = Agent(resources, compose=True).respond('Are researcher reward vouchers available?')
    assert out['decision'] == 'clarify'
    assert out['answer'].endswith(question)
    assert 'uncertainty_answer_origin' not in out['generation']


def test_supported_document_answer_is_not_replaced_by_generic_uncertainty(resources, monkeypatch):
    answer = 'Books can be returned within 10 calendar days from delivery.'
    monkeypatch.setattr(resources.llm, 'complete', lambda *a, **k: json.dumps({
        'answer': answer, 'covered': True, 'needs_clarification': False}))
    out = Agent(resources, compose=True).respond('How long can I return books?')
    assert out['answer'].endswith(answer)
    assert out['evidence_supported']
    assert 'uncertainty_answer_origin' not in out['generation']


@pytest.mark.parametrize('proposal', [
    "We don't offer researcher vouchers, I have insufficient information.",
    "I cannot confirm this, and researcher vouchers are not available.",
    "Researcher vouchers are not offered, but I cannot confirm this.",
])
def test_a_qualifier_in_another_clause_does_not_authorize_a_policy_claim(resources, monkeypatch, proposal):
    calls = []
    def complete(*args, **options):
        calls.append(1)
        return json.dumps({'answer': proposal, 'covered': False, 'needs_clarification': False})
    monkeypatch.setattr(resources.llm, 'complete', complete)
    out = Agent(resources, compose=True).respond('Are researcher reward vouchers available?')
    assert len(calls) == 2
    assert proposal not in out['answer']
    assert out['answer'].endswith(abstention('en'))
    assert out['generation']['repair_errors'] == ['uncited_substantive_refusal'] * 2


def test_an_actual_uncertainty_repair_is_shown_without_an_authored_policy_answer(resources, monkeypatch):
    values = iter(["We don't have researcher vouchers.", 'I cannot confirm this from the supplied evidence.'])
    monkeypatch.setattr(resources.llm, 'complete', lambda *a, **k: json.dumps({
        'answer': next(values), 'covered': False, 'needs_clarification': False}))
    out = Agent(resources, compose=True).respond('Are researcher reward vouchers available?')
    assert out['answer'].endswith('I cannot confirm this from the supplied evidence.')
    assert out['generation']['generation_attempts'] == 2
    assert out['generation']['repair_errors'] == ['uncited_substantive_refusal']
    assert not out['evidence_supported']


@pytest.mark.parametrize('language,proposal', [
    ('en', 'The provided documents do not allow researcher reward vouchers.'),
    ('hi', 'जानकारी के मुताबिक शोधकर्ताओं को वाउचर नहीं मिलते।'),
    ('hi-en', 'Mere paas researcher reward vouchers nahi hain.'),
])
def test_source_reference_or_possession_is_not_a_lack_of_information(resources, monkeypatch, language, proposal):
    calls = []
    def complete(*args, **kwargs):
        calls.append(1)
        return json.dumps({'answer': proposal, 'covered': False, 'needs_clarification': False})
    monkeypatch.setattr(resources.llm, 'complete', complete)
    out = Agent(resources, compose=True).respond('Are researcher reward vouchers available?', language_hint=language)
    assert proposal not in out['answer']
    assert len(calls) == 2
    assert out['answer'].endswith(abstention(language))
    assert out['generation']['repair_errors'] == ['uncited_substantive_refusal'] * 2
