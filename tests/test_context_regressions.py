from src.normalize import order_id,proof_value
from src.agent import Agent,Resources


def test_literal_entities_are_not_merged_with_speech_homophones():
    assert order_id('Please check order 35061733 for me')=='35061733'
    assert order_id('Please check order 3506 1733 for me')=='35061733'
    assert proof_value('1234 for verification')=='1234'


def test_safety_warning_survives_a_troubleshooting_followup():
    a=Agent(Resources(dense=False),compose=False)
    a.respond('The battery is swollen')
    out=a.respond('Should I try charging it again?')
    assert out['decision']=='escalate'
    assert 'Stop using' in out['answer']


def test_disputed_account_activity_gets_immediate_handoff():
    out=Agent(Resources(dense=False),compose=False).respond('There is account activity that I did not authorize.')
    assert out['intent']=='fraud' and out['decision']=='escalate'
    assert [t['name'] for t in out['tool_calls']]==['create_ticket']


def test_repeat_issue_is_resumed_immediately_after_verification(monkeypatch):
    r=Resources(dense=False)
    def lookup(oid,proof=None):
        order={'order_id':oid,'contacts_last_7_days':2,'status':'shipped'} if proof=='1234' else {}
        return order,{'name':'lookup_order','arguments':{'order_id':oid,'verification_value':'[REDACTED]'},'result':{'verified':bool(order)}}
    monkeypatch.setattr(r.tools,'lookup',lookup)
    a=Agent(r,compose=False)
    a.respond('I have an unresolved issue with order 11112222')
    out=a.respond('Last four digits 1234')
    assert out['decision']=='escalate'
    ticket=next(t for t in out['tool_calls'] if t['name']=='create_ticket')
    assert 'unresolved issue' in ticket['arguments']['summary']
    assert '[verification value redacted]' not in ticket['arguments']['summary']
