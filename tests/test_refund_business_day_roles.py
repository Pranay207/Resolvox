from datetime import date
from types import SimpleNamespace
import pytest
from src.document_context import build_context
from src.document_answers import _date_mentions
from src.refund_arrival_claims import check_public_refund_business_day_roles


def facts(weekdays='Monday to Saturday',holidays=()):
    sources=[{'id':'REF-2','status':'current','doc_type':'policy','text':'| UPI | 2 to 4 business days |'},
             {'id':'KB-00.3','status':'current','doc_type':'policy','text':f'A business day is {weekdays}, excluding warehouse holidays.'}]
    return build_context('My UPI refund started on 6 October 2026; when will it arrive?',sources,SimpleNamespace(products={},holidays=set(holidays)))


def check(text,context):check_public_refund_business_day_roles(text,context,date_mentions=_date_mentions)

@pytest.mark.parametrize('text',[
    'The first business day is 8 October 2026.',
    '8 October 2026 par pahla business day hai.',
    '8 October 2026 पहला कार्यदिवस है।',
    'The second working day is 9 October 2026.'])
def test_lower_arrival_bound_is_not_day_one_after_initiation(text):
    with pytest.raises(ValueError,match='conflicted_refund_business_day_role'):check(text,facts())

@pytest.mark.parametrize('text',[
    'The first business day is 7 October 2026.',
    'The second business day is 8 October 2026.',
    'The first business day of the expected range is 8 October 2026.',
    'The expected range is 8 October 2026 to 10 October 2026.',
    'I cannot confirm that the first business day is 8 October 2026.'])
def test_correct_roles_and_uncertainty_are_preserved(text):check(text,facts())

def test_changed_calendar_holidays_change_the_expected_ordinal_date():
    changed=facts(holidays={'2026-10-07'})
    check('The first business day is 8 October 2026.',changed)
    with pytest.raises(ValueError,match='conflicted_refund_business_day_role'):
        check('The first business day is 7 October 2026.',changed)
