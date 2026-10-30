"""Missing storefront evidence is uncertainty, not proof that no shop exists."""
from datetime import date
import json
import pytest
from src.store_presence import check_store_presence_claim
from src.document_answers import document_reply

TODAY=date(2026,10,20)
UNRELATED=[{'id':'DELIVERY-X','doc_type':'policy','status':'current','effective_from':'2020-01-01','text':'We deliver within the domestic serviceable area.'}]

@pytest.mark.parametrize('query,answer',[
    ('Do you have a shop in Cedar Bay?','No, we do not have a shop there.'),
    ('Are there any physical stores in Northport?','There is a physical store there.'),
    ('क्या आपकी कोई दुकान देवपुर में है?','देवपुर में कोई दुकान नहीं है।'),
    ('Kya aapki dukaan Surajpur mein hai?','Dukaan nahi hai.'),
    ('Where is your physical store?','Yes, we have a shop nearby.')])
def test_unrelated_documents_cannot_support_presence_or_absence(query,answer):
    with pytest.raises(ValueError,match='unsupported_physical_store_claim'):
        check_store_presence_claim(answer,query,UNRELATED,TODAY)

@pytest.mark.parametrize('answer',[
    'I have no information about physical stores.',
    'I cannot confirm whether there is a shop there.',
    'इस बारे में जानकारी नहीं है।', 'Dukaan ke baare mein jaankari nahi hai.'])
def test_qualified_uncertainty_is_preserved(answer):
    check_store_presence_claim(answer,'Do you have a physical shop?',UNRELATED,TODAY)

def test_uncertainty_cannot_hide_a_later_definite_presence_claim():
    with pytest.raises(ValueError,match='unsupported_physical_store_claim'):
        check_store_presence_claim('I have no information, but there is a shop nearby.','Do you have a physical shop?',UNRELATED,TODAY)

def test_delivery_and_an_online_shop_are_different_topics():
    check_store_presence_claim('We deliver domestically.','Does your store deliver domestically?',UNRELATED,TODAY)
    online=[{**UNRELATED[0],'text':'ZentroMart is an online store.'}]
    with pytest.raises(ValueError,match='unsupported_physical_store_claim'):
        check_store_presence_claim('There is no shop.','Do you have a physical shop?',online,TODAY)

@pytest.mark.parametrize('state',['current','superseded','future'])
def test_only_effective_current_explicit_store_evidence_makes_guard_decline(state):
    source={**UNRELATED[0],'text':'We operate physical stores in Cedar Bay.'}
    if state=='superseded':source['status']='superseded'
    if state=='future':source['effective_from']='2035-01-01'
    if state=='current':check_store_presence_claim('We have a shop.','Do you have a physical shop?',[source],TODAY)
    else:
        with pytest.raises(ValueError,match='unsupported_physical_store_claim'):
            check_store_presence_claim('We have a shop.','Do you have a physical shop?',[source],TODAY)

class Client:
    def __init__(self):self.calls=[]
    def complete(self,system,user,**options):
        self.calls.append(json.loads(user))
        value={'answer':'There is no shop.','covered':True,'needs_clarification':False} if len(self.calls)==1 else {'answer':"I don't have enough supported information.",'covered':False,'needs_clarification':False}
        return json.dumps(value)

def test_generation_boundary_repairs_denial_as_supported_uncertainty():
    client=Client();out=document_reply(client,'Do you have a physical shop in Cedar Bay?','en',UNRELATED,context_provenance=True)
    assert out['reply_kind']=='uncertainty' and out['covered'] is False
    assert out['repair_errors']==['unsupported_physical_store_claim']
    assert client.calls[0]['source_text']==client.calls[1]['source_text']
    assert 'expected_answer' not in client.calls[1]



def test_store_presence_alone_does_not_establish_order_pickup_service():
    query='Can I pick up my order from a store near me?'
    presence=[{**UNRELATED[0],'text':'We operate physical stores.'}]
    with pytest.raises(ValueError,match='unsupported_physical_store_claim'):
        check_store_presence_claim('No, store pickup is not allowed.',query,presence,TODAY)
    explicit=[{**UNRELATED[0],'text':'Store pickup is available.'}]
    check_store_presence_claim('Yes, store pickup is available.',query,explicit,TODAY)


@pytest.mark.parametrize('answer', [
    'There is no shop and I have no information about one.',
    'There is a shop, but I cannot confirm this.',
    'देवपुर में कोई दुकान नहीं है और इस बात की जानकारी नहीं है।',
    'Dukaan nahi hai aur jaankari nahi hai.',
])
def test_coordinated_uncertainty_cannot_hide_a_presence_or_absence_claim(answer):
    with pytest.raises(ValueError, match='unsupported_physical_store_claim'):
        check_store_presence_claim(answer, 'Do you have a physical shop?', UNRELATED, TODAY)


@pytest.mark.parametrize('language,answer', [
    ('en', 'There is no shop and I have no information about one.'),
    ('hi', 'देवपुर में कोई दुकान नहीं है और इस बात की जानकारी नहीं है।'),
    ('hi-en', 'Dukaan nahi hai aur jaankari nahi hai.'),
])
def test_noncovered_flag_never_bypasses_storefront_claim_validation(language, answer):
    class UncertainFlagClient:
        def __init__(self): self.calls = 0
        def complete(self, system, user, **options):
            self.calls += 1
            return json.dumps({'answer': answer, 'covered': False, 'needs_clarification': False})
    client = UncertainFlagClient()
    with pytest.raises(ValueError) as error:
        document_reply(client, 'Do you have a physical shop?', language, UNRELATED, context_provenance=True)
    assert client.calls == 2
    assert error.value.diagnostics['repair_errors'] == ['unsupported_physical_store_claim'] * 2
