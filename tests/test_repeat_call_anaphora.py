"""Same-issue call anaphora must still use verified, source-bound counts."""
from types import SimpleNamespace
import pytest
from src.escalation_rules import derive_escalation


def sources(threshold=3,days=11):
    return [dict(id='rule-varying',doc_type='agent_guide',status='current',effective_from='2020-01-01',
                 text=f'Hand over for repeat contact. For the repeat-contact rule, use the contacts_last_{days}_days field returned by order lookup. It counts earlier contacts only, not the current one. Escalate when it is {threshold} or more.'),
            dict(id='workflow-varying',doc_type='agent_guide',status='current',effective_from='2020-01-01',
                 text='Create a ticket before handing over.')]


def decision(query,order,**options):
    result=derive_escalation(query,sources(**options),SimpleNamespace(holidays=set()),
                             verified_order=order,reference_date='2026-10-20')
    return next(r for r in result['decisions'] if r['reason']=='repeat_contact')


@pytest.mark.parametrize('query',[
    "This is the third time I'm calling about this in a week.",
    'Main is hafte teesri baar call kar rahi hoon isi baare mein.',
    'I called about this earlier.',
    'मैं फिर कॉल कर रही हूँ इसी बारे में।',
    'मैं इसी बारे में फोन कर रही हूँ।',
])
def test_call_context_does_not_need_an_explicit_refund_or_delivery_noun(query):
    row=decision(query,{'contacts_last_11_days':3})
    assert row['applicable'] is True
    assert row['facts']['earlier_contact_count']==3
    assert row['source_ids']==['rule-varying','workflow-varying']


@pytest.mark.parametrize('threshold,count,expected',[(3,2,False),(3,3,True),(5,3,False),(5,5,True)])
def test_query_ordinal_does_not_override_source_threshold_or_verified_count(threshold,count,expected):
    row=decision("This is the third time I'm calling about this.",{'contacts_last_11_days':count},threshold=threshold)
    assert row['applicable'] is expected
    assert row['facts']['earlier_contact_threshold']==threshold


@pytest.mark.parametrize('query',[
    'Call this colour indigo.', 'Whom should I call?',
    'I am not calling about this.', 'If I call about this, what happens?',
    'I am calling about this, but it is a different question.',
])
def test_unrelated_negative_hypothetical_and_new_topics_do_not_gain_a_route(query):
    assert decision(query,{'contacts_last_11_days':9})['applicable'] is False


def test_customer_claim_alone_cannot_create_a_verified_count():
    assert decision("This is the third time I'm calling about this.",None)['applicable'] is False
    row=decision("This is the third time I'm calling about this.",{'status':'delivered'})
    assert row['applicable'] is None and row['missing_inputs']==['contacts_last_11_days']
