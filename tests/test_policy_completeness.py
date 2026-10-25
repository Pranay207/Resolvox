"""Policy answers must preserve independently requested facts and record limits."""
import pytest
from src.agent import Resources
from src.answering import classify


@pytest.fixture(scope="module")
def policy():
    return Resources(dense=False).policy


def test_pickup_question_keeps_window_and_seller_terms(policy):
    product=next(p for p in policy.data.products.values() if p["return_category"]=="fashion" and p["fulfilled_by"]!="ZentroMart")
    q=f'For {product["sku"]}, what return window and reverse pickup charge can the seller impose on a non-Plus customer?'
    p=policy.plan(q,classify(q))
    assert p.facts["return_days"]==15
    assert "49" in p.en and "same return windows and pickup rules" in p.en
    assert {"RET-2","RET-6","MKS-2",f'products.csv:{product["sku"]}'}<=set(p.ids)


def test_pickup_to_bank_stages_are_refund_intent(policy):
    q='For a returned purchase paid by credit card, compare pickup-to-initiation and initiation-to-bank stages.'
    assert classify(q)=="refund"
    p=policy.plan(q,classify(q))
    assert "quality check" in p.en and "2 business days" in p.en
    assert "5 to 7 business days" in p.en and {"RET-7","REF-2"}<=set(p.ids)


def test_historical_exception_is_explained(policy):
    p=policy.plan('For a speaker delivered on 30 July 2026, explain the return period.',"return")
    assert p.facts["return_days"]==10
    assert "before 1 August 2026" in p.en and "historical exception" in p.en
    assert {"RET-3","RETv3-2"}<=set(p.ids)


@pytest.mark.parametrize("day,days,explanation",[(1,30,"inside the offer"),(15,30,"inside the offer"),(16,15,"outside the offer")])
def test_sale_placement_boundary_is_explicit(policy,day,days,explanation):
    p=policy.plan(f'For shoes ordered on {day} October 2026, does the festive return period apply?',"return")
    assert p.facts["return_days"]==days and explanation in p.en
    assert "from delivery" in p.en


def test_plus_does_not_extend_historical_or_current_window(policy):
    p=policy.plan('Does Plus extend returns for earbuds delivered on 2 August 2026?',"return")
    assert p.facts["return_days"]==7 and "Plus does not extend" in p.en
    assert "PLS-2" in p.ids


def test_refund_precedence_has_the_governing_source(policy):
    p=policy.plan('The general FAQ gives a different refund period. What is the UPI rule after initiation?',"refund")
    assert "1 to 3 business days" in p.en and "current policy takes precedence" in p.en
    assert {"REF-2","KB-00.1"}<=set(p.ids)


def test_expired_grocery_is_an_exception_to_change_of_mind_rule(policy):
    q='My grocery delivery arrived expired; explain the exception, photos and remedy.'
    p=policy.plan(q,classify(q))
    assert {"RET-5","DWM-1","DWM-2"}<=set(p.ids)
    assert "48 hours" in p.en and "item and packaging" in p.en
    assert "free replacement or full refund including delivery fees" in p.en


def test_pending_refund_shares_record_without_claiming_bank_credit(policy):
    order={"payment_method":"upi","return_refund_initiated_on":"2026-10-20","return_refund_method":"upi","return_refund_amount_inr":3210,"return_rrn":"RRN-TEST","return_refund_completed_on":""}
    p=policy.plan('Has the refund reached my bank?',"refund",order)
    assert p.decision=="answer" and "1 to 3 business days" in p.en
    assert "3210 rupees" in p.en and "RRN-TEST" in p.en
    assert "Completion is not recorded" in p.en and "cannot confirm" in p.en
    assert "REF-6" in p.ids and p.facts["refund_completion_recorded"] is False


def test_overdue_refund_includes_amount_and_ticket_policy(policy):
    order={"payment_method":"upi","return_refund_initiated_on":"2026-07-20","return_refund_method":"upi","return_refund_amount_inr":3210,"return_rrn":"RRN-TEST"}
    p=policy.plan('My refund has not arrived.',"refund",order)
    assert p.decision=="escalate" and "3210 rupees" in p.en
    assert {"REF-6","ESC-1","ESC-2"}<=set(p.ids)


def test_repeat_contact_explains_earlier_contacts(policy):
    p=policy.plan('Same unresolved issue.',"repeat",{"contacts_last_7_days":2})
    assert p.decision=="escalate"
    assert "2 earlier contacts" in p.en and "third contact" in p.en


def test_delivery_comparison_computes_each_requested_basket(policy):
    p=policy.plan('Compare Standard delivery charges on baskets worth ₹512 and ₹452.',"delivery")
    assert "512 rupee basket, Standard delivery costs 0 rupees" in p.en
    assert "452 rupee basket, Standard delivery costs 40 rupees" in p.en


def test_redirect_office_uses_address_policy(policy):
    q='Could the courier redirect it to my office?'
    assert classify(q)=="delivery"
    p=policy.plan(q,classify(q),{"status":"shipped","shipped_on":"2026-10-18"})
    assert "cannot be changed" in p.en and p.ids==["DEL-6"]


def test_hindi_tracking_localizes_order_status_and_month(policy):
    p=policy.plan('मेरे पार्सल की स्थिति और तारीख क्या है?',"delivery",{"status":"shipped","promised_date":"2026-10-28"})
    assert "शिप" in p.hi and "28 अक्टूबर 2026" in p.hi
    assert "shipped" not in p.text("hi") and "October" not in p.text("hi")


def test_return_money_reference_is_refund_rather_than_return_eligibility():
    assert classify('Has the return money reached my bank; what reference can the bank trace?')=="refund"


def test_plus_fee_and_window_answer_does_not_contradict_itself(policy):
    p=policy.plan('As a Plus member, what is the return window and pickup fee for shoes?',"pickup")
    assert "pickup costs 0 rupees" in p.en
    assert "pickup costs 49 rupees" not in p.en and "pickup fee;" not in p.en
    assert p.facts["return_days"]==15


def test_iso_placement_context_explains_sale_basis(policy):
    p=policy.plan('For shoes, what period applies? Order placed on 2026-10-11.',"return")
    assert p.facts["return_days"]==30
    assert "placement date of 11 October 2026" in p.en
    assert "inside the offer" in p.en


def test_ordinary_refund_does_not_require_precedence_evidence(policy):
    p=policy.plan('When will the refund arrive?',"refund",{"payment_method":"upi","return_refund_initiated_on":"2026-10-20"})
    assert "KB-00.1" not in p.ids and "KB-00.3" in p.ids


@pytest.mark.parametrize("text,expected",[("Delivered on 31 July 2025","2025-07-31"),("Delivered on 2025-07-31T18:20:00","2025-07-31"),("Delivered on 1 August 2027","2027-08-01"),("Delivered on 31st July","2026-07-31")])
def test_explicit_date_year_is_preserved(policy,text,expected):
    assert policy._date_in(text).isoformat()==expected


@pytest.mark.parametrize("text",["Delivered on 2025-02-29","Delivered on 31 April 2025","Delivered on 0000-01-01"])
def test_invalid_date_does_not_become_a_reference_year_date(policy,text):
    assert policy._date_in(text) is None


def test_explicit_prior_year_delivery_does_not_gain_a_future_deadline(policy):
    p=policy.plan('For electronics delivered on 31 July 2025, what return period applied?',"return")
    assert p.facts["return_days"]==10
    assert p.facts["deadline"]=="2025-08-10"
    assert p.facts["eligible"] is False
