import pytest
from src.refund_arrival_claims import check_public_refund_timeliness


def projection():
    return {'reference_date': '2031-02-03',
        'customer_provided_refund_claim': {'initiated_on': '2031-02-01', 'verified': False},
        'calculations': [{'operation': 'refund_business_date_range',
            'input_status': 'customer_provided_unverified',
            'record_field': 'customer_provided_refund_claim.initiated_on',
            'inputs': {'customer_statement_verified': False, 'initiated_on': '2031-02-01', 'reference_date': '2031-02-03'},
            'result': {'earliest_date': '2031-02-04', 'latest_date': '2031-02-06'}}]}


@pytest.mark.parametrize('answer', [
    'There is no delay.', 'There have been no additional delays.',
    'Uss date par koi delay nahi hai.', 'Abhi deri nahin hui.',
    'कोई देरी नहीं है।', 'विलंब नहीं हुआ।'])
def test_a_future_estimated_deadline_does_not_certify_a_delay_free_transaction(answer):
    with pytest.raises(ValueError, match='unverified_refund_timeliness'):
        check_public_refund_timeliness(answer, projection())


@pytest.mark.parametrize('answer', [
    'I cannot confirm that there is no delay.',
    'There is no delay cannot be guaranteed.',
    'The refund is not overdue.',
    'If there is no delay, the estimate remains a projection.',
    'Based on the supplied date, expected arrival is between 4 and 6 February 2031.'
])
def test_uncertainty_conditional_explanations_and_calendar_comparisons_stay_valid(answer):
    check_public_refund_timeliness(answer, projection())


def test_verified_records_are_outside_this_unverified_projection_guard():
    facts = projection(); facts['verified_order'] = {'status': 'delivered'}
    check_public_refund_timeliness('There is no delay.', facts)
