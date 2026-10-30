from datetime import date
import pytest
from src.return_transition_claims import check_effective_return_windows


def sources(current=11,earlier=17):
    return [{'id':'CHANGE-X','doc_type':'policy','status':'current','effective_from':'2020-01-01','text':f'From 13 June 2024, the return window for portable devices and accessories is {current} days. Portable devices delivered before 13 June 2024 keep the earlier {earlier}-day window from version 2 of this policy.'}]

@pytest.mark.parametrize('current,earlier',[(11,17),(4,9),(13,23)])
@pytest.mark.parametrize('universal',['regardless of when it was delivered','regardless of the delivery date','no matter when it was received'])
def test_universal_current_window_cannot_erase_actual_historical_exception(current,earlier,universal):
    text=f'The return window for portable devices is {current} days, and this applies to every item {universal}.'
    with pytest.raises(ValueError,match='contradicted_effective_return_window'):
        check_effective_return_windows(text,sources(current,earlier),reference_date=date(2026,10,20))

@pytest.mark.parametrize('text',[
    'From 13 June 2024, the return window for portable devices is 11 days. Devices delivered before that date retain the earlier 17-day window.',
    'The return window for portable devices is 11 days regardless of the seller.',
    'It is incorrect to say the return window for portable devices is 11 days regardless of the delivery date.'])
def test_conditional_windows_seller_independence_and_negated_bad_descriptions_are_preserved(text):
    check_effective_return_windows(text,sources(),reference_date=date(2026,10,20))

def test_without_differing_historical_authority_no_exception_is_invented():
    check_effective_return_windows('The return window for portable devices is 11 days regardless of delivery date.',sources(11,11),reference_date=date(2026,10,20))
