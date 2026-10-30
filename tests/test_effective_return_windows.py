"""Dated return-window claims follow changed source values, never a question ID."""
from datetime import date
import copy
import json
import pytest
from src.return_transition_claims import check_effective_return_windows
from src.document_answers import document_reply

SOURCE = {'id': 'change-orchid', 'text': 'From **4 March 2031**, the return window for electrical devices and accessories is 6 days. Electrical devices delivered before 4 March 2031 keep the earlier 9-day window.', 'doc_type': 'policy', 'status': 'current', 'effective_from': '2030-01-01'}

def check(answer, sources=None, reference='2031-05-12'):
    return check_effective_return_windows(answer, [SOURCE] if sources is None else sources, reference_date=reference)

@pytest.mark.parametrize('prefix', ['As of', 'From', 'Effective from', 'Starting on'])
@pytest.mark.parametrize('verb', ['is', 'was', 'will be'])
def test_explicit_wrong_current_window_is_rejected(prefix, verb):
    with pytest.raises(ValueError, match='contradicted_effective_return_window'):
        check(f'{prefix} 4 March 2031, the return window for electrical devices {verb} 9 days.')

@pytest.mark.parametrize('days', [4, 11, 23])
def test_correct_mutated_source_value_is_accepted_and_old_value_rejected(days):
    source = {**SOURCE, 'text': SOURCE['text'].replace('is 6 days', f'is {days} days')}
    before = copy.deepcopy(source)
    records = check(f'As of 4 March 2031, the return window for electrical devices is {days} calendar days.', [source])
    assert records[0]['days'] == days and records[0]['source_id'] == SOURCE['id']
    assert source == before
    with pytest.raises(ValueError):
        check('As of 4 March 2031, the return window for electrical devices is 6 days.', [source])

@pytest.mark.parametrize('answer', [
    'The earlier window was 9 days from delivery.',
    'Items delivered before 4 March 2031 retain the earlier 9-day window.',
    'The historical window was 9 days. As of 4 March 2031, the return window for electrical devices is 6 days.',
    'As of 3 March 2031, the return window for electrical devices was 9 days.',
    'As of 4 March 2031, the return window for books is 9 days.',
    'It is incorrect to say that as of 4 March 2031, the return window for electrical devices is 9 days.',
])
def test_historical_other_category_and_explicitly_negated_descriptions_are_preserved(answer):
    check(answer)

@pytest.mark.parametrize('change', [
    {'status': 'superseded'}, {'doc_type': 'marketing'}, {'effective_from': '2035-01-01'},
    {'effective_from': 'invalid'}, {'id': None}, {'text': None},
])
def test_missing_inactive_or_nonpolicy_authority_does_not_bind_a_value(change):
    check('As of 4 March 2031, the return window for electrical devices is 9 days.', [{**SOURCE, **change}])


def test_future_transition_is_not_applied_early():
    check('As of 4 March 2031, the return window for electrical devices is 9 days.', reference='2031-03-01')


def test_conflicting_current_sources_are_not_arbitrarily_resolved():
    other = {**SOURCE, 'id': 'change-violet', 'text': SOURCE['text'].replace('is 6 days', 'is 11 days')}
    check('As of 4 March 2031, the return window for electrical devices is 9 days.', [SOURCE, other])


def test_source_hash_and_date_follow_source_mutation():
    a = check('As of 4 March 2031, the return window for electrical devices is 6 days.')
    changed = {**SOURCE, 'text': SOURCE['text'].replace('4 March 2031', '7 April 2031')}
    b = check('As of 7 April 2031, the return window for electrical devices is 6 days.', [changed])
    assert a[0]['source_sha256'] != b[0]['source_sha256']
    assert b[0]['effective_on'] == '2031-04-07'


class Client:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []
    def complete(self, system, user, **options):
        self.calls.append((json.loads(user), options))
        assert self.answers
        return json.dumps({'answer': self.answers.pop(0), 'covered': True, 'needs_clarification': False})


def test_document_generation_gets_one_source_preserving_repair(monkeypatch):
    import src.document_answers as module
    monkeypatch.setattr(module, 'REFERENCE_DATE', date(2031, 5, 12))
    bad = 'The earlier window was 9 days. As of 4 March 2031, the return window for electrical devices is 9 days.'
    good = 'The earlier return window was 9 days from delivery.'
    client = Client(bad, good)
    out = document_reply(client, 'What was the earlier return window?', 'en', [SOURCE], context_provenance=True)
    assert out['answer'] == good
    assert out['repair_errors'] == ['contradicted_effective_return_window']
    assert len(client.calls) == 2 and client.calls[1][1]['cache'] is False
    assert client.calls[0][0]['source_text'] == client.calls[1][0]['source_text'] == [SOURCE]
    assert 'repair_instruction' not in client.calls[0][0]
    assert 'dates and categories' in client.calls[1][0]['repair_instruction']
