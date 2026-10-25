"""The conditional consequence is bound to an actual source bullet, not an ID."""
import copy,json,hashlib
import pytest
from src.source_semantics import derive_source_constraints,validate_source_semantics
from src.document_answers import document_reply

SOURCE={'id':'new-refund-rule','text':'''## Refund initiation
- **Cancelled before shipping:** on cancellation.
- **Returned item:** after quality check.
- **Prepaid order refused at the door or not delivered after 4 attempts:** once the parcel reaches the depot, usually 8 to 11 calendar days after the last delivery attempt.
''','doc_type':'policy','status':'current'}

@pytest.mark.parametrize('answer',[
    'If the third delivery attempt fails, the parcel goes to the warehouse and a refund is initiated.',
    'Every returned-to-origin order gets a refund.',
    'After failed delivery, you will get a refund.',
    'For any RTO order, the refund starts at the warehouse.',
    'For a failed delivery, the refund does not require a prepaid order.',
    'Prepaid is not necessary: failed delivery causes a refund.',
    'Delivery attempt fails. The refund will start at the warehouse.',
    'Delivery fail hua to refund shuru hoga.',
    'Since your order was prepaid, after the third attempt fails your refund will be initiated.',
    'Your order was not prepaid, but after the third attempt fails a refund will be initiated.',
    'If your order was not prepaid, failed delivery will lead to a refund.',
    'For prepaid orders this rule applies. Your order was not prepaid, but if the third attempt fails a refund will be initiated.',
    '\u0921\u093f\u0932\u0940\u0935\u0930\u0940 \u0905\u0938\u092b\u0932 \u0939\u094b\u0928\u0947 \u092a\u0930 \u0930\u093f\u092b\u0902\u0921 \u0936\u0941\u0930\u0942 \u0939\u094b\u0924\u093e \u0939\u0948\u0964',
])
def test_unknown_payment_does_not_become_unconditional_failed_delivery_entitlement(answer):
    answer=answer.encode().decode('unicode_escape') if '\\u' in answer else answer
    with pytest.raises(ValueError,match='source_refund_condition_missing:prepaid'):
        validate_source_semantics(answer,[SOURCE])

@pytest.mark.parametrize('answer',[
    'For prepaid orders, a failed delivery refund is initiated once the parcel reaches the depot.',
    'If the order was prepaid, a refund follows failed delivery once the parcel reaches the depot.',
    'If the order was paid in advance, the refund follows failed delivery.',
    'For prepaid RTO orders the refund starts at the depot.',
    'For prepaid orders, this delivery rule applies. If the third attempt fails, a refund is initiated once the parcel reaches the warehouse.',
    'Prepaid delivery fail hui to refund warehouse pahunchne par shuru hota hai.',
    'Delivery has up to four attempts. The parcel is returned to origin afterwards.',
    'A returned item refund starts after quality check.',
    'Cancelled-before-shipping refunds start at cancellation.',
    'Failed delivery does not mean a refund is guaranteed.',
    'No refund is guaranteed after failed delivery.',
    'I cannot confirm a refund after failed delivery.',
    'Delivery can fail after repeated attempts. A returned item refund starts after its quality check.',
])
def test_preserves_condition_or_does_not_make_the_scoped_refund_promise(answer):
    assert validate_source_semantics(answer,[SOURCE])


def test_constraint_keeps_actual_antecedent_consequence_and_hash():
    before=copy.deepcopy(SOURCE)
    item=next(x for x in derive_source_constraints([SOURCE]) if x['kind']=='conditional_rto_refund')
    assert item['source_ids']==[SOURCE['id']]
    assert '4 attempts' in item['source_antecedent'] and '8 to 11' in item['source_consequence']
    assert item['payment_condition']=='prepaid'
    assert item['source_sha256'][SOURCE['id']]==hashlib.sha256(SOURCE['text'].encode()).hexdigest()
    assert SOURCE==before


def test_removing_source_condition_changes_constraints_without_a_code_answer_change():
    changed=dict(SOURCE,text=SOURCE['text'].replace('Prepaid order','Every order'))
    assert derive_source_constraints([changed])==[]
    validate_source_semantics('Every RTO order gets a refund.',[changed])


def test_a_prepaid_mention_in_another_bullet_is_not_a_scoped_antecedent():
    changed=dict(SOURCE,text=SOURCE['text'].replace('Prepaid order','Order')+'\nPrepaid payments are accepted.')
    assert derive_source_constraints([changed])==[]


class Client:
    def __init__(self,*answers):self.answers=list(answers);self.calls=[]
    def complete(self,system,user,**options):
        self.calls.append((json.loads(user),options))
        return json.dumps({'answer':self.answers.pop(0),'covered':True,'needs_clarification':False})


def test_existing_single_repair_uses_the_actual_condition_and_never_a_policy_template():
    client=Client('If an attempt fails, refund initiation occurs once the parcel reaches the depot.','If an order is prepaid, failed-delivery refund initiation occurs once the parcel reaches the depot.')
    out=document_reply(client,'What happens to failed delivery?','en',[SOURCE],context_provenance=True)
    assert out['generation_attempts']==2 and out['repair_errors']==['source_refund_condition_missing:prepaid']
    first,repair=client.calls
    assert repair[0]['source_text']==first[0]['source_text']==[SOURCE]
    assert repair[0]['repair_source_constraints']==derive_source_constraints([SOURCE])
    assert repair[1]['cache'] is False
    assert out['evaluated_source_constraints']==derive_source_constraints([SOURCE])
