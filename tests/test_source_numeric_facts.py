"""Selected numeric facts and constraints must follow sources, never answer keys."""
from types import SimpleNamespace

from src.document_context import build_context


def source(sid, text, status='current'):
    return {'id': sid, 'text': text, 'status': status, 'doc_type': 'policy'}


def data():
    return SimpleNamespace(products={}, holidays={'2026-10-19'})


def return_sources(days=13, festive=31):
    return [source('RET-2', '| Clothing and bags | ' + str(days) + ' days | `fashion` |'),
            source('RET-8', 'Clothing orders placed between 03 September and 09 September 2026 can be returned within ' + str(festive) + ' days of delivery.')]


def test_standard_window_is_available_without_a_delivery_date():
    context = build_context('How long do I get to send back this kurta?', return_sources(), data(),
                            public_context={'category': 'fashion'})
    assert context['return_policy']['window_calendar_days'] == 13
    assert context['return_policy']['source_ids'] == ['RET-2']
    assert context['return_policy']['placement_exception']['window_calendar_days'] == 31
    assert context['calculations'] == []
    assert context['answer_constraints'] == [
        {'kind': 'quantity', 'value': 13, 'unit': 'calendar_day',
         'key': 'return_policy.window_calendar_days', 'source_ids': ['RET-2']}]


def test_current_successor_can_select_historical_window_without_old_table():
    sources = [source('RET-3', 'Electronics delivered before 1 September 2026 keep the earlier 12-day window.')]
    context = build_context('What was the return window?', sources, data(),
                            public_context={'category': 'electronics', 'delivered_on': '2026-08-20'})
    assert context['return_policy']['window_calendar_days'] == 12
    assert context['return_policy']['selection'] == 'historical_window'
    assert context['answer_constraints'][0]['value'] == 12
    assert context['answer_constraints'][0]['source_ids'] == ['RET-3']
    assert context['calculations'][0]['inputs']['calendar_days'] == 12
    assert context['calculations'][0]['result']['deadline'] == '2026-09-01'


def test_delivery_after_changed_historical_cutoff_keeps_current_table():
    sources = [source('RET-2', '| Electronics | 8 days | `electronics` |'),
               source('RET-3', 'Electronics delivered before 1 September 2026 keep the earlier 12-day window.'),
               source('RETv3-2', '| Electronics | 99 days |', status='superseded')]
    context = build_context('What is the return window?', sources, data(),
                            public_context={'category': 'electronics', 'delivered_on': '2026-09-01'})
    assert context['return_policy']['window_calendar_days'] == 8
    assert context['answer_constraints'][0]['value'] == 8


def test_known_placement_exception_selects_its_actual_value():
    context = build_context('How many days can I return it?', return_sources(), data(),
                            public_context={'category': 'fashion', 'placed_on': '2026-09-05',
                                            'delivered_on': '2026-09-10'})
    assert context['return_policy']['window_calendar_days'] == 31
    assert context['return_policy']['selection'] == 'placement_exception_window'
    assert context['answer_constraints'][0]['value'] == 31
    assert context['answer_constraints'][0]['source_ids'] == ['RET-8']
    assert context['calculations'][0]['result']['deadline'] == '2026-10-11'


def test_return_eligibility_question_does_not_require_duration_as_an_answer():
    context = build_context('Can I return this opened package?', return_sources(), data(),
                            public_context={'category': 'fashion'})
    assert context['return_policy']['window_calendar_days'] == 13
    assert context['answer_constraints'] == []


def test_refund_duration_does_not_accidentally_require_a_return_window():
    context = build_context('After I return this item, how long is the refund?', return_sources(), data(),
                            public_context={'category': 'fashion'})
    assert context['answer_constraints'] == []


def test_hindi_and_hinglish_duration_questions_select_source_value():
    questions = [
        '\u0932\u094c\u091f\u093e\u0928\u0947 \u0915\u0947 \u0932\u093f\u090f \u0915\u093f\u0924\u0928\u0947 \u0926\u093f\u0928 \u092e\u093f\u0932\u0947\u0902\u0917\u0947?',
        'Is kurta ko wapas karne ke liye kitne din hain?',
    ]
    for question in questions:
        context = build_context(question, return_sources(days=11), data(),
                                public_context={'category': 'fashion'})
        assert context['answer_constraints'][0]['value'] == 11


def test_explicit_refund_by_when_constraint_comes_from_calendar_calculation():
    sources = [source('REF-2', '| Credit or debit card | 2 to 4 business days |'),
               source('KB-00.3', 'A business day is Monday to Saturday, excluding holidays.')]
    context = build_context('My card refund was started on 17 October 2026. By which date should I have it?',
                            sources, data())
    constraint = context['answer_constraints'][0]
    assert constraint == {'kind': 'date', 'value': '2026-10-23', 'key': 'refund.latest_date',
                          'source_ids': ['REF-2', 'KB-00.3'], 'calculation_index': 0}
    assert context['calculations'][0]['result']['latest_date'] == constraint['value']
    assert 'data/holidays.csv' in context['calculations'][0]['source_ids']


def test_refund_timeline_without_explicit_date_request_has_no_date_constraint():
    sources = [source('REF-2', '| Credit or debit card | 2 to 4 business days |'),
               source('KB-00.3', 'A business day is Monday to Saturday, excluding holidays.')]
    context = build_context('My card refund started on 17 October 2026. How many business days does it take?',
                            sources, data())
    assert context['calculations'] and context['answer_constraints'] == []


def test_attempt_limit_is_read_from_changed_source_and_topic_bound():
    sources = [source('DEL-3', 'The courier makes up to 5 delivery attempts. A failed attempt allows rescheduling.')]
    context = build_context("What happens if I'm not home when the courier comes?", sources, data())
    assert context['delivery_policy'] == {'delivery_attempt_limit': 5, 'source_ids': ['DEL-3']}
    assert context['answer_constraints'] == [
        {'kind': 'number', 'value': 5, 'key': 'delivery_policy.delivery_attempt_limit', 'source_ids': ['DEL-3']}]
    unrelated = build_context('Is delivery available in my city?', sources, data())
    assert unrelated['answer_constraints'] == []


def test_ambiguous_missing_or_superseded_source_does_not_create_numeric_fact():
    ambiguous = source('DEL-3', 'We make up to 5 delivery attempts. We also make up to 2 attempts.')
    for selected in ([], [ambiguous], [source('DEL-3', 'Up to 5 attempts.', status='superseded')]):
        context = build_context('How many delivery attempts?', selected, data())
        assert 'delivery_policy' not in context
        assert context['answer_constraints'] == []
    context = build_context('What is the return window?', [], data(),
                            public_context={'category': 'fashion'})
    assert 'return_policy' not in context and context['answer_constraints'] == []