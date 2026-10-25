"""Return-table application scope under unrelated, broader retrieved context."""
from types import SimpleNamespace
import pytest
from src.document_context import build_context


def sources():
    return [dict(id='RET-2',status='current',doc_type='policy',
                 text='| Group | Return window | Catalog code |\n'
                      '| Garments | 23 days | `fashion` |\n'
                      '| Devices | 11 days | `electronics` |'),
            dict(id='RET-7',status='current',doc_type='policy',
                 text='Returned items are inspected. The refund is initiated within 4 business days of pickup after quality check.')]


def facts(query,**kwargs):
    return build_context(query,sources(),SimpleNamespace(products={},holidays=set()),**kwargs)

@pytest.mark.parametrize('query',[
    'After the warehouse inspects a return, when is the money sent?',
    'Once staff examine the returned goods, when does payment processing begin?',
    'When does a return reach your warehouse?',
    'How soon is the money sent once a return has passed inspection?',
    'How long does inspection of my returned item take?',
    'When will the courier collect my return?',
    'How long will transport of my return take?',
    'Does buying from a third-party merchant change the return rules?',
    'Return warehouse inspection ke baad paisa kab bheja jayega?',
    '\u0930\u093f\u091f\u0930\u094d\u0928 \u0915\u0940 \u091c\u093e\u0902\u091a \u0915\u0947 \u092c\u093e\u0926 \u092a\u0948\u0938\u093e \u0915\u092c \u092d\u0947\u091c\u093e \u091c\u093e\u090f\u0917\u093e?',
])
def test_processing_or_transport_time_is_not_return_window_application(query):
    assert 'required_application_inputs' not in facts(query)

@pytest.mark.parametrize('query',[
    'How long do I have to send it back?',
    'By when can I return this purchase?',
    'How many days am I allowed to return it?',
    'What is the return deadline?',
    'What is the return window?',
    'How long is the return period?',
    'Am I still allowed to return this?',
    'For how long after delivery is the item returnable?',
    'How many days for a return?',
    'How many days are available for sending a purchase back?',
    'Kab tak item wapas bhej sakta hoon?',
    'Wapas karne ke liye kitne din hain?',
    'Kitne din mein wapas karna hoga?',
    '\u0915\u093f\u0924\u0928\u0947 \u0926\u093f\u0928 \u092e\u0947\u0902 \u0935\u093e\u092a\u0938 \u0915\u0930\u0928\u093e \u0939\u094b\u0917\u093e?',
    '\u0930\u093f\u091f\u0930\u094d\u0928 \u0915\u0940 \u0938\u092e\u092f\u0938\u0940\u092e\u093e \u0915\u094d\u092f\u093e \u0939\u0948?',
])
def test_actual_return_window_application_keeps_missing_category_guard(query):
    required=facts(query)['required_application_inputs']
    assert required[0]['key']=='return_category'
    assert {row['return_window'] for row in required[0]['allowed_rows']}=={'23 days','11 days'}
    assert 'question' not in required[0]

@pytest.mark.parametrize('query',[
    'Compare return windows for all categories.',
    'Which categories are returnable?',
    'Sabhi categories ke return windows batao.',
    'Kaunsi categories returnable hain?',
    '\u0938\u092d\u0940 \u0936\u094d\u0930\u0947\u0923\u093f\u092f\u094b\u0902 \u0915\u0947 \u0930\u093f\u091f\u0930\u094d\u0928 \u092e\u0947\u0902 \u0915\u093f\u0924\u0928\u0947 \u0926\u093f\u0928 \u0939\u0948\u0902?',
])
def test_category_overview_does_not_need_one_individual_category(query):
    assert 'required_application_inputs' not in facts(query)


def test_resolved_category_still_uses_actual_changed_policy_row():
    result=facts('What is the return window?',public_context={'category':'fashion'})
    assert 'required_application_inputs' not in result
    assert result['return_policy']['window_calendar_days']==23


def test_explicit_window_and_refund_compound_still_needs_category():
    result=facts('What is the return window, and when is my refund sent?')
    assert result['required_application_inputs'][0]['key']=='return_category'
