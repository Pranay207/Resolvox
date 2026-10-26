"""Actual-module date/duration boundary controls; no source wrappers or models."""
import os
import socket
import sys
import pytest
import requests
if os.environ.get('RESOLVOX_QUANTITY_DATE_TEST_ROOT'):
    sys.path.insert(0,os.environ['RESOLVOX_QUANTITY_DATE_TEST_ROOT'])
from src.grounding import _quantities,numbers,validate_generated

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args,**kwargs):raise AssertionError('No network/model calls')
    monkeypatch.setattr(requests.sessions.Session,'request',denied)
    monkeypatch.setattr(socket,'create_connection',denied)

@pytest.mark.parametrize('text',[
    '1 August 2026 se 7 din',
    '12 May 2033 to 4 days',
    '2033-06-13 se 4 din',
    '29 February 2032 and 4 days',
])
def test_complete_valid_calendar_endpoint_is_not_a_duration(text):
    quantity='7' if text.startswith('1 August') else '4'
    assert _quantities(text)=={(quantity,'day')}

@pytest.mark.parametrize('text,expected',[
    ('12 May 2033 days',{('2033','day')}),
    ('2033-06-13 days',{('06','day'),('13','day')}),
    ('12 May 2033.5 days',{('2033.5','day')}),
    ('2033-06-13.5 days',{('06','day'),('13.5','day')}),
    ('-12 May 2033 se 4 days',{('2033','day'),('4','day')}),
    ('12 May 2033-4 days',{('2033','day'),('4','day')}),
    ('12 May 2033 + 4 days',{('4','day')}),
    ('29 February 2033 se 4 days',{('2033','day'),('4','day')}),
    ('31 April 2033 se 4 days',{('2033','day'),('4','day')}),
    ('7 to 2033 days',{('7','day'),('2033','day')}),
    ('business days ko 1 se 3 din',{('1','business_day'),('3','business_day')}),
])
def test_ambiguous_invalid_partial_and_real_ranges_retain_existing_unit_checks(text,expected):
    assert _quantities(text)==expected

@pytest.mark.parametrize('answer,passes',[
    ('From 1 August 2026 se 7 din applies.',True),
    ('From 1 August 2026 se 8 din applies.',False),
    ('From 1 August 2026 se 7 hours applies.',False),
    ('From 1 August 2026 se 7 business days applies.',False),
])
def test_trailing_quantity_and_unit_remain_source_bound(answer,passes):
    source={'id':'date-rule','text':'The rule dated 1 August 2026 allows 7 calendar days. The separate fee is 8 rupees.'}
    value={'answer':answer,'covered':True,'citations':[{'id':source['id'],'quote':source['text']}]}
    if passes:
        validate_generated(value,[source])
    else:
        with pytest.raises(ValueError,match='unsupported_quantity_unit'):
            validate_generated(value,[source])


def test_date_digits_still_pass_through_numeric_support_checks():
    source={'id':'date-rule','text':'The rule dated 1 August 2026 allows 7 calendar days.'}
    answer='From 1 August 2099 se 7 din applies.'
    assert numbers(answer)>={'1','2099','7'}
    value={'answer':answer,'covered':True,'citations':[{'id':source['id'],'quote':source['text']}]}
    with pytest.raises(ValueError,match='unsupported_number'):
        validate_generated(value,[source])