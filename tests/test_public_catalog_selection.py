"""Catalog variants remain source records, without choosing an arbitrary SKU."""
import json
from src.agent import Agent,Resources

class Client:
    last_metrics={}
    def __init__(self,answer):self.answer=answer;self.calls=[]
    def complete(self,system,user,**options):
        self.calls.append(json.loads(user))
        return json.dumps({'answer':self.answer,'covered':True,'needs_clarification':False})

def test_shared_title_variants_are_retained_without_selecting_one():
    r=Resources(dense=False)
    query="The Comfi Cotton Briefs (Pack of 3) doesn't fit. Can I send it back?"
    assert r.policy.product(query) is None
    matching=[p for p in r.data.products.values() if p['title'].split(',')[0] in query]
    assert len(matching)>1
    r.llm=Client('The Comfi Cotton Briefs (Pack of 3) cannot be returned for a change of mind.')
    out=Agent(r,compose=True).respond(query)
    assert out['composition']=='grounded_llm'
    ids={s['id'] for s in out['generation_context_sources']}
    assert {'products.csv:'+p['sku'] for p in matching}.issubset(ids)
    assert {p['sku'] for p in out['facts']['catalog']}=={p['sku'] for p in matching}
    assert out['facts']['public_context']=={'category':'innerwear'}
    assert len(r.llm.calls)==1

def test_unrelated_catalog_rows_do_not_enter_context():
    r=Resources(dense=False)
    r.llm=Client('Wallet refunds arrive within 2 hours after initiation.')
    out=Agent(r,compose=True).respond('How fast are refunds to the ZentroMart Wallet?')
    assert out['composition']=='grounded_llm'
    assert not any(s['doc_type']=='catalog' for s in out['generation_context_sources'])
    assert 'catalog' not in out['facts']
