"""Synthetic changed-source tests; no inference, fixtures, or policy constants."""
import importlib.util
import json
from pathlib import Path
import pytest

from src import delivery_clock as helper


def source(text,**changes):
    return dict({'id':'Fictional-Schedule','text':text,'doc_type':'policy','status':'current'},**changes)


def check(answer,query='Can I schedule a delivery at midnight?',sources=None):
    return helper.check_delivery_clock_answer(answer,query,[] if sources is None else sources,reference_date='2031-05-12')


@pytest.mark.parametrize('answer',[
 'Midnight delivery is available.', 'Midnight delivery is unavailable.',
 'No, delivery slots are not available at midnight.', 'Yes, we can deliver at midnight.',
 'That time is outside the delivery window.', 'No, those slots are not available.',
 'We can schedule it.', 'Delivery is possible at noon.',
 'डिलीवरी मध्यरात्रि में उपलब्ध नहीं है।','मध्यरात्रि में डिलीवरी संभव है।',
 'Midnight delivery available nahi hai.', 'Raat delivery ho sakti hai.',
])
def test_missing_hours_never_authorize_positive_or_negative(answer):
    with pytest.raises(ValueError,match='unsupported_delivery_clock_availability'):check(answer)


@pytest.mark.parametrize('time', ['3:41 am','11:23 pm','07:18','noon','midnight','morning','शाम ८ बजे','raat 10 baje'])
@pytest.mark.parametrize('direction',['available','not available'])
def test_varied_customer_times_are_not_policy(time,direction):
    query='Can I schedule a delivery at '+time+'?'
    with pytest.raises(ValueError):check('Delivery is '+direction+' at '+time+'.',query)


@pytest.mark.parametrize('text',[
 'Express delivery is next business day if ordered before 2 pm.',
 'Grocery orders can be cancelled up to 2 hours before the start of the chosen delivery slot.',
 'The order-placement cutoff is midnight; delivery takes several business days.',
 'Cancellation is available before noon; contact delivery support.',
 'Refund processing is available from 09:00 to 18:00.',
])
def test_nonarrival_event_clocks_do_not_authorize_arrival(text):
    assert helper.derive_delivery_clock_constraints([source(text)],reference_date='2031-05-12')==[]
    with pytest.raises(ValueError):check('Midnight delivery is available.',sources=[source(text)])


@pytest.mark.parametrize('answer',[
 'Standard delivery takes several business days.',
 'Express delivery is next business day if ordered before 2 pm.',
 'Grocery orders can be cancelled before the chosen delivery slot.',
 'I cannot confirm whether midnight delivery is available from the supplied documents.',
 'The delivery time is not specified in these documents.',
 'मैं मध्यरात्रि डिलीवरी की पुष्टि नहीं कर सकता।',
 'Midnight delivery confirm nahi kar sakta.',
 'Which delivery time would you like?',
])
def test_ordinary_eta_cutoff_uncertainty_or_question_is_not_availability(answer):check(answer)


@pytest.mark.parametrize('answer',[
 'Delivery is available at 10:20.', 'Delivery is possible at 17:40.',
 'We deliver at noon.', 'डिलीवरी दोपहर में उपलब्ध है।',
])
def test_actual_changed_current_hours_support_inside_clock(answer):
    check(answer,sources=[source('Delivery hours: 10:20 to 17:40. Delivery is available during these hours.')])


def test_explicit_positive_does_not_create_unstated_negative_outside():
    sources=[source('Delivery is available between 10:20 and 17:40.')]
    with pytest.raises(ValueError):check('Midnight delivery is not available.',sources=sources)


def test_explicit_exclusive_window_supports_negative_outside_but_not_positive():
    sources=[source('Delivery is available only between 10:20 and 17:40.')]
    check('Midnight delivery is not available.',sources=sources)
    with pytest.raises(ValueError):check('Midnight delivery is available.',sources=sources)


def test_direct_negative_supports_same_clock_and_rejects_opposite():
    sources=[source('Delivery is not available at midnight.')]
    check('Midnight delivery is unavailable.',sources=sources)
    with pytest.raises(ValueError):check('Midnight delivery is available.',sources=sources)


def test_source_mutation_changes_supported_time_and_fingerprint():
    before=source('Delivery is available at 07:18.')
    after=source('Delivery is available at 08:19.')
    assert helper.derive_delivery_clock_constraints([before])[0]['source_sha256'] != helper.derive_delivery_clock_constraints([after])[0]['source_sha256']
    check('Delivery is available at 07:18.','Can delivery arrive at 07:18?',[before])
    with pytest.raises(ValueError):check('Delivery is available at 07:18.','Can delivery arrive at 07:18?',[after])


@pytest.mark.parametrize('change',[{'status':'superseded'},{'doc_type':'marketing'},{'doc_type':''},{'effective_from':'2040-01-01'}])
def test_noncurrent_lower_or_unknown_authority_is_not_support(change):
    with pytest.raises(ValueError):check('Midnight delivery is available.',sources=[source('Delivery is available at midnight.',**change)])


def test_current_policy_overrides_help_and_conflicting_same_authority_fails_closed():
    yes=source('Delivery is available at midnight.')
    no=source('Delivery is not available at midnight.',id='Other')
    with pytest.raises(ValueError):check('Midnight delivery is available.',sources=[yes,no])
    check('Midnight delivery is available.',sources=[yes,dict(no,doc_type='help')])


def test_service_specific_hours_cannot_be_transferred():
    sources=[source('Express delivery is available at midnight.')]
    check('Express delivery is available at midnight.',sources=sources)
    with pytest.raises(ValueError):check('Standard delivery is available at midnight.',sources=sources)
    with pytest.raises(ValueError):check('Delivery is available at midnight.',sources=sources)


def test_source_antecedent_is_not_stripped():
    sources=[source('If a customer is eligible, delivery is available at midnight.')]
    with pytest.raises(ValueError):check('Delivery is available at midnight.',sources=sources)


def test_order_cutoff_in_answer_does_not_hide_later_arrival_assertion():
    with pytest.raises(ValueError):check('If ordered before noon, delivery is available at midnight.')


def test_earlier_uncertainty_does_not_rescue_independent_claim():
    with pytest.raises(ValueError):check('I cannot confirm it, delivery is not available at midnight.')
    with pytest.raises(ValueError):check('I cannot confirm it but delivery is not available at midnight.')


def test_trace_evidence_and_sources_are_actual_and_unchanged():
    sources=[source('Delivery is available at noon.')];before=json.dumps(sources,sort_keys=True)
    result=check('Delivery is available at noon.',sources=sources)
    assert result[0]['source_ids']==[sources[0]['id']]
    assert result[0]['evidence'] in sources[0]['text'].casefold()
    assert before==json.dumps(sources,sort_keys=True)


@pytest.mark.parametrize('answer',[
 'मध्यरात्रि में डिलीवरी नहीं मिलती है।',
 'Midnight delivery band hai.',
 'Delivery occurs only during the morning.',
 'I cannot confirm it and midnight delivery is not available.',
])
def test_additional_local_availability_predicates_do_not_bypass(answer):
    with pytest.raises(ValueError):check(answer)


def test_range_cannot_cross_unsupported_overnight_hours():
    sources=[source('Delivery is available between 10:20 and 17:40.')]
    check('Delivery is available between 11:20 and 16:40.',sources=sources)
    with pytest.raises(ValueError):check('Delivery is available between 16:40 and 11:20.',sources=sources)


def test_overnight_source_window_supports_only_its_contained_segments():
    sources=[source('Delivery is available between 21:20 and 03:40.')]
    check('Delivery is available between 22:20 and 02:40.',sources=sources)
    with pytest.raises(ValueError):check('Delivery is available between 02:40 and 22:20.',sources=sources)


@pytest.mark.parametrize('answer',[
 'The documents do not specify delivery times.',
 'I can only confirm the promised delivery date.',
 'The order record can show its promised delivery date.',
])
def test_neutral_document_or_record_statements_are_not_slot_claims(answer):check(answer)


@pytest.mark.parametrize('answer',['Yes, you can.','No, you cannot.','We cannot schedule it.'])
def test_direct_capability_stance_uses_the_question_clock_scope(answer):
    with pytest.raises(ValueError):check(answer)
