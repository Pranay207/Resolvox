from datetime import date
import json
import pytest
from src.dates import business_add,business_elapsed,return_deadline,return_window,partial_refund
from src.normalize import number_words,order_id,proof_value,redact
from src.kb import KnowledgeBase
from src.agent import Agent,Resources

@pytest.fixture(scope='session')
def r(): return Resources(dense=False)

@pytest.mark.parametrize('start,n,expected',[('2026-10-17',1,'2026-10-20'),('2026-10-17',3,'2026-10-22'),('2026-10-17',7,'2026-10-27'),('2026-10-01',1,'2026-10-03'),('2026-11-07',1,'2026-11-10')])
def test_business_days(start,n,expected,r): assert business_add(date.fromisoformat(start),n,r.data.holidays).isoformat()==expected

def test_return_boundaries():
    assert return_deadline(date(2026,10,10),7)==date(2026,10,17)
    assert return_window('electronics',date(2026,7,31),None,7)==10
    assert return_window('electronics',date(2026,8,1),None,7)==7
    assert return_window('fashion',None,date(2026,10,15),15)==30
    assert return_window('fashion',None,date(2026,10,16),15)==15
    assert return_window('fashion',None,date(2026,9,30),15)==15

def test_coupon_math():
    assert partial_refund(1000,400,100,800)==300
    assert partial_refund(1000,400,100,500)==360
    assert partial_refund(1000,400,100,500,49)==311

@pytest.mark.parametrize('value,expected',[('double six four nine','6649'),('chhah hazaar chaar sau','6400'),('ele zero zero one to','ELE-0012'),('one two three four','1234'),('१२३४','1234')])
def test_spoken_numbers(value,expected): assert number_words(value)==expected

def test_grouped_id(): assert order_id('Order eight nine seven eight two eight three seven')=='89782837'

def test_policy_precedence(r):
    assert not r.kb.allowed(r.kb.chunks['RETv3-6'],True)
    assert not r.kb.allowed(r.kb.chunks['RETv3-2'])
    assert r.kb.allowed(r.kb.chunks['RETv3-2'],True)
    result=Agent(r).respond('How long do UPI refunds take?')
    assert 'REF-2' in result['retrieved_chunk_ids'] and 'FAQ-1' not in result['retrieved_chunk_ids']
    assert '1 to 3' in result['answer']

def test_verification_gate_and_lockout(r):
    a=Agent(r); pending=a.respond('Order 7746 1439')
    assert pending['decision']=='clarify' and not pending['verified']
    assert all('status' not in t['result'] for t in pending['tool_calls'])
    for i in range(2):
        out=a.respond('Last four digits 0000')
        assert '0000' not in json.dumps(out,ensure_ascii=False)
        assert out['decision']==('clarify' if i==0 else 'refuse')
    out=a.respond('Order 7746 1439')
    assert out['decision']=='refuse' and not out['tool_calls']

def test_order_switch_discards_verification(r):
    a=Agent(r); a.respond('Order 89782837'); ok=a.respond('Last four digits 4533')
    assert ok['verified'] and '4533' not in json.dumps(ok)
    switched=a.respond('Order 77461439')
    assert not switched['verified'] and switched['decision']=='clarify'
    assert a.state.order is None

def test_verification_secret_not_persisted(r):
    a=Agent(r); a.respond('Order 89782837'); out=a.respond('Last four digits 4533')
    dump=json.dumps(out,ensure_ascii=False)+repr(a.state)
    assert '4533' not in dump and 'delivery_pincode' not in a.state.order
    assert 'customer_first_name' not in a.state.order
    assert '+91' not in dump and 'customer_first_name' not in dump

def test_ticket_failure_not_success(r,monkeypatch):
    monkeypatch.setattr(r.tools.module,'create_ticket',lambda **kwargs:{'created':False})
    out=Agent(r).respond('I want a human agent')
    assert out['decision']=='escalate'
    assert 'could not be created' in out['answer'] and 'has been created' not in out['answer']

def test_no_private_table_reader(r):
    with pytest.raises(ValueError): r.data.read('customers')
