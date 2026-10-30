"""Unless denotes a hypothetical date; it must not grant exception eligibility."""
import pytest
from test_public_repair_contexts import window_fixture
from src.placement_conditions import check_placement_exception_answer
from src.document_answers import _constraint_text


def check(answer, ordinary=12, extended=24):
    facts,sources=window_fixture(ordinary,extended)
    check_placement_exception_answer(answer,facts,sources,normalizer=_constraint_text)

@pytest.mark.parametrize('ordinary,extended',[(12,24),(17,31),(8,19)])
def test_general_window_with_unless_exception_never_asserts_a_personal_order_date(ordinary,extended):
    check(f'The ordinary return window is {ordinary} calendar days from delivery. This standard window applies unless the order was placed between 3 April and 11 April 2031, in which case the window is {extended} days.',ordinary,extended)

@pytest.mark.parametrize('subject',['your order','the order','this purchase'])
def test_immediately_governed_date_is_hypothetical(subject):
    check(f'The standard window applies unless {subject} was placed between 3 April and 11 April 2031, in which case the general exception window is 24 days.')


def test_personal_ordinary_window_can_be_conditional_on_excluding_the_actual_range():
    check('You have 12 days to return it unless your order was placed between 3 April and 11 April 2031.')

@pytest.mark.parametrize('answer',[
    'Unless the item is unused, your order was placed between 3 April and 11 April 2031.',
    'Your order was placed between 3 April and 11 April 2031 unless the item is unused.',
    'Unless your order was placed during this period, you placed the order yesterday.',
])
def test_unrelated_unless_never_authorizes_another_personal_date_assertion(answer):
    with pytest.raises(ValueError,match='invented_placement_premise'):check(answer)

@pytest.mark.parametrize('answer',[
    'You get 24 days unless your order was placed between 3 April and 11 April 2031.',
    'Your order qualifies for 24 days unless the order was placed between 3 April and 11 April 2031.',
    'You have 24 days. The ordinary window applies unless the order was placed during that period.',
])
def test_unless_date_hypothesis_does_not_grant_unknown_exception_entitlement(answer):
    with pytest.raises(ValueError,match='unsupported_placement_exception_entitlement'):check(answer)

@pytest.mark.parametrize('condition',[
    'your order was not placed between 3 April and 11 April 2031',
    'your order was placed before 3 April or after 11 April 2031',
    'your order was placed between 11 April and 3 April 2031',
    'your order was placed between 3 April and 11 April 2032',
])
def test_reversed_negated_or_wrong_source_range_cannot_qualify_the_ordinary_claim(condition):
    with pytest.raises(ValueError):check('You have 12 days to return it unless '+condition+'.')
