"""Explicit prefixed business units remain bound to their local range."""
import pytest
from src.grounding import _quantities,validate_generated

@pytest.mark.parametrize('text',[
    'business days ko 1 se 3 din',
    'business days 1 to 3 days',
    'working days mein 1 se 3 din',
    '1 se 3 business din',
    '1 to 3 working din',
])
def test_local_explicit_business_unit_can_precede_or_follow_range(text):
    assert _quantities(text)=={('1','business_day'),('3','business_day')}

@pytest.mark.parametrize('text',[
    'business days apply. 1 to 3 days',
    'business days ko, 1 se 3 din',
    'business days holidays excluded and then 1 to 3 days',
    'It takes 1 to 3 days',
    'nonbusiness days ko 1 se 3 din',
    'non-business days ko 1 se 3 din',
    'not business days 1 to 3 days',
    'not working days mein 1 se 3 din',
    'non business days ko 1 se 3 din',
])
def test_generic_days_do_not_inherit_a_remote_business_unit(text):
    assert _quantities(text)=={('1','day'),('3','day')}

@pytest.mark.parametrize('text',[
    'business days ko 1 se 3 calendar days',
    'working days mean 1 to 3 calendar days',
])
def test_explicit_calendar_unit_is_never_converted(text):
    assert _quantities(text)=={('1','calendar_day'),('3','calendar_day')}

@pytest.mark.parametrize('answer,passes',[
    ('The policy takes business days ko 1 se 3 din.',True),
    ('The policy takes 1 se 3 business din.',True),
    ('The policy takes 1 se 3 calendar din.',False),
    ('The policy takes 1 se 3 din.',False),
])
def test_equivalence_preserves_actual_source_units_without_relaxing_other_quantities(answer,passes):
    source={'id':'new-unit-rule','text':'UPI refund arrival is 1 to 3 business days.'}
    candidate={'answer':answer,'covered':True,'citations':[{'id':source['id'],'quote':source['text']}]}
    if passes:validate_generated(candidate,[source])
    else:
        with pytest.raises(ValueError,match='unsupported_quantity_unit'):
            validate_generated(candidate,[source])


def test_thousands_separator_still_normalizes_as_one_quantity():
    assert _quantities('It costs 1,000 rupees.')=={('1000','money')}
