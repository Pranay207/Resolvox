"""Uncertainty flags must describe the generated answer, without altering evidence."""
import copy
import json
import pytest
from src.document_answers import document_reply, _source_absence_only, CONTEXT_SYSTEM, CONTEXT_LANGUAGE
from src.generation_diagnostics import GenerationValidationError, validation_code

SOURCE = {'id': 'orchid-help', 'text': 'Orchid service supports requests in the app.', 'doc_type': 'policy', 'status': 'current'}
ABSENT = 'There is no mention of an Aster pass in the provided policies.'
SAFE = 'I do not have enough information to confirm whether an Aster pass is offered.'

class Client:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = []
    def complete(self, system, user, **options):
        self.calls.append((system, json.loads(user), options))
        assert self.values, 'Unexpected third generation attempt'
        return json.dumps(self.values.pop(0), ensure_ascii=False)

def value(answer, covered=True, needs=False):
    return {'answer': answer, 'covered': covered, 'needs_clarification': needs}

def run(client, language='en', sources=None):
    return document_reply(client, 'Explain the Aster pass policy.', language,
        [SOURCE] if sources is None else sources, context_provenance=True)

@pytest.mark.parametrize('answer', [
    ABSENT,
    'The supplied documents do not mention an Aster pass.',
    'The policies contain no reference to an Aster pass.',
    'The source does not specify an Aster pass.',
    'नीति में Aster pass का उल्लेख नहीं है।',
    'Policy mein Aster pass ka zikr nahi hai.',
])
def test_source_absence_classifier_is_language_aware_without_changing_refusal_contract(answer):
    assert _source_absence_only(answer)

@pytest.mark.parametrize('language,answer', [
    ('en', 'I cannot confirm Aster pass availability because there is no mention of it in the supplied policies.'),
    ('hi', 'मेरे पास पर्याप्त जानकारी नहीं है, नीति में Aster pass का उल्लेख नहीं है।'),
    ('hi-en', 'Mere paas jaankari nahi hai, policy mein Aster pass ka zikr nahi hai.'),
])
def test_explicit_uncertainty_preserves_each_supported_language_and_original_flags(language, answer):
    out = run(Client(value(answer, covered=False)), language=language)
    assert out['reply_kind'] == 'uncertainty' and out['covered'] is False
    assert out['model_flags'] == {'covered': False, 'needs_clarification': False}
    assert out['answer'] == answer and out['source_ids'] == []
    assert out['generation_attempts'] == 1


def test_covered_consistency_does_not_relax_the_existing_strict_uncertainty_guard():
    client = Client(value(ABSENT, covered=False), value(ABSENT))
    with pytest.raises(GenerationValidationError) as caught:
        run(client)
    assert caught.value.diagnostics['repair_errors'] == [
        'uncited_substantive_refusal', 'source_absence_marked_covered']
    assert len(client.calls) == 2


def test_normal_agent_safely_abstains_after_both_invalid_uncertainty_attempts(monkeypatch):
    from src.agent import Agent, Resources
    resources = Resources(dense=False)
    values = [value(ABSENT, covered=False), value(ABSENT)]
    def complete(*args, **kwargs):
        assert values
        return json.dumps(values.pop(0))
    monkeypatch.setattr(resources.llm, 'complete', complete)
    out = Agent(resources, compose=True).respond('Is gift wrapping offered?')
    assert not values
    assert out['composition'] == 'abstained_model_or_evidence'
    assert out['generation']['repair_errors'] == [
        'uncited_substantive_refusal', 'source_absence_marked_covered']
    assert not out['evidence_supported']
    assert "don't have enough supported information" in out['answer']
    assert 'Aster pass' not in out['answer']

@pytest.mark.parametrize('answer', [
    ABSENT,
    'The supplied documents do not mention an Aster pass.',
    'The policies contain no reference to an Aster pass.',
])
def test_absence_marked_covered_gets_one_uncached_source_preserving_repair(answer):
    sources = [copy.deepcopy(SOURCE)]
    before = copy.deepcopy(sources)
    client = Client(value(answer), value(SAFE, covered=False))
    out = run(client, sources=sources)
    assert out['repair_errors'] == ['source_absence_marked_covered']
    assert out['generation_attempts'] == 2 and out['reply_kind'] == 'uncertainty'
    assert out['model_flags'] == {'covered': False, 'needs_clarification': False}
    first, repair = client.calls
    assert first[0] == CONTEXT_SYSTEM + '\n' + CONTEXT_LANGUAGE['en']
    assert first[1]['source_text'] == repair[1]['source_text'] == before == sources
    assert first[1]['question'] == repair[1]['question']
    assert 'repair_instruction' not in first[1]
    assert repair[1]['repair_validation_error'] == 'source_absence_marked_covered'
    assert first[2]['cache'] is True and repair[2]['cache'] is False
    assert first[2]['schema'] == repair[2]['schema']
    assert 'expected_answer' not in repair[1]

@pytest.mark.parametrize('text', [
    'Orchid service does not include an Aster pass.',
    'Aster passes are excluded under the supplied policy.',
    'Aster passes are available through the app.',
])
def test_documented_positive_and_negative_policy_explanations_keep_coverage(text):
    source = {**SOURCE, 'text': text}
    out = run(Client(value(text)), sources=[source])
    assert out['covered'] is True and out['generation_attempts'] == 1
    assert out['source_ids'] == [SOURCE['id']]


def test_repair_can_use_applicable_evidence_instead_of_forcing_false_coverage():
    source = {**SOURCE, 'text': 'Aster passes are available through the app.'}
    client = Client(value(ABSENT), value(source['text']))
    out = run(client, sources=[source])
    assert out['covered'] is True and out['generation_attempts'] == 2
    assert out['model_flags']['covered'] is True


def test_second_absence_with_true_coverage_is_rejected_without_flag_relabeling():
    client = Client(value(ABSENT), value(ABSENT))
    with pytest.raises(GenerationValidationError) as caught:
        run(client)
    assert caught.value.diagnostics['repair_errors'] == ['source_absence_marked_covered'] * 2
    assert len(client.calls) == 2

@pytest.mark.parametrize('answer', [
    'There is no mention of an Aster pass in the documents. Requests are supported in the app.',
    'The policies contain no reference to Aster passes, but requests are supported in the app.',
])
def test_partial_uncertainty_does_not_erase_a_supported_policy_explanation(answer):
    assert not _source_absence_only(answer)

@pytest.mark.parametrize('bad', [
    'There is no mention of a 99-day window in the policies.',
    'There is no mention of Aster passes in the policies. Your refund has been issued.',
    'There is no mention of Aster passes in the policies; contact aster@example.com.',
    'There is no mention of Aster passes in the policies, but returns are free.',
    'There is no mention of Aster passes in the policies. ' * 20,
])
def test_uncertainty_does_not_bypass_numeric_action_privacy_or_substantive_guards(bad):
    client = Client(value(ABSENT), value(bad, covered=False))
    with pytest.raises(GenerationValidationError):
        run(client)
    assert len(client.calls) == 2

@pytest.mark.parametrize('topic', ['copper engraving', 'Orion delivery program', 'gift wrapping'])
def test_unknown_topic_wording_is_not_bound_to_a_business_question(topic):
    absent = f'There is no mention of {topic} in the supplied documents.'
    safe = f'I do not have enough information to confirm {topic}.'
    out = run(Client(value(absent), value(safe, covered=False)))
    assert out['answer'] == safe and out['reply_kind'] == 'uncertainty'


def test_new_diagnostic_is_allowlisted_without_free_form_content():
    assert validation_code('source_absence_marked_covered') == 'source_absence_marked_covered'
    assert validation_code('arbitrary customer text') == 'invalid_response'
