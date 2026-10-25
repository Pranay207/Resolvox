"""Public follow-ups retain only current, corrected facts; proof stays private."""
import json
import pytest
from src.agent import Agent, Resources

@pytest.fixture
def resource():
    return Resources(dense=False)

def capture_search(resource, monkeypatch):
    queries=[]
    original=resource.retriever.search
    def search(query,*args,**kwargs):
        queries.append(query)
        return original(query,*args,**kwargs)
    monkeypatch.setattr(resource.retriever,'search',search)
    return queries

def test_product_switch_replaces_previous_catalog_context(resource,monkeypatch):
    queries=capture_search(resource,monkeypatch)
    agent=Agent(resource,compose=False)
    agent.respond('What is the return period for ELE-0005 ordered on 10 October 2026?')
    agent.respond('What about HOM-0044 with that same placement date?')
    assert 'HOM-0044' in queries[-1] and 'ELE-0005' not in queries[-1]
    assert '2026-10-10' in queries[-1]
    agent.respond('Change that product to FSH-0026. What period applies now?')
    assert 'FSH-0026' in queries[-1] and 'HOM-0044' not in queries[-1]
    assert '2026-10-10' in queries[-1]

def test_date_correction_cannot_restore_superseded_delivery(resource,monkeypatch):
    queries=capture_search(resource,monkeypatch)
    agent=Agent(resource,compose=False)
    agent.respond('What return period applies to ELE-0005 delivered on 31 July 2026?')
    corrected=agent.respond('Correction: delivery was actually 1 August 2026. Revise the period.')
    assert corrected['intent']=='return'
    assert '2026-08-01' in queries[-1] and '31 July' not in queries[-1]
    agent.respond('Would Plus make that return window longer?')
    assert agent.state.public_context['delivered_on']=='2026-08-01'
    assert '2026-07-31' not in queries[-1]

def test_new_category_drops_previous_sku(resource,monkeypatch):
    queries=capture_search(resource,monkeypatch)
    agent=Agent(resource,compose=False)
    agent.respond('What return window applies to ELE-0005?')
    agent.respond('What about grocery instead?')
    assert 'ELE-0005' not in queries[-1]
    assert agent.state.public_context.get('category')=='grocery'

def test_pincode_word_does_not_request_cod(resource):
    out=Agent(resource,compose=False).respond('Is delivery available at pincode 411045?')
    assert 'serviceable' in out['facts']
    assert 'cod_available' not in out['facts']
    assert 'cod_eligible' not in out['facts']
    row = resource.data.pincodes['411045']
    assert out['facts']['serviceable'] is (row['serviceable'] == 'True')
    assert out['facts']['public_serviceability']['record']['serviceable'] == row['serviceable']
    assert not out['tool_calls']

def test_express_and_standard_are_both_answered(resource):
    out=Agent(resource,compose=False).respond('At pincode 411045, is Express possible and can Standard deliver?')
    assert out['facts']['serviceable'] is True
    assert out['facts']['express_available'] is False
    assert out['composition']=='document_excerpts'
    assert 'pincodes.csv:411045' in out['retrieved_chunk_ids']
    assert out['facts']['public_serviceability']['record']['serviceable']=='True'
    assert out['facts']['public_serviceability']['record']['express_available']=='False'

def test_hindi_verification_prompt_is_hindi(resource):
    out=Agent(resource,compose=False).respond('मेरे ऑर्डर 11112222 की स्थिति बताइए।')
    assert 'अंतिम 4 अंक' in out['answer']
    assert '???' not in out['answer']

def test_unknown_policy_retains_source_context_and_fake_uncertainty(resource,monkeypatch):
    seen=[]
    uncertainty='I do not have enough supported information to answer that question.'
    def complete(system,user,*args,**kwargs):
        seen.append(json.loads(user))
        return json.dumps({'answer':uncertainty,'covered':False,'needs_clarification':False})
    monkeypatch.setattr(resource.llm,'complete',complete)
    out=Agent(resource,compose=True).respond('Can I get a student discount?')
    assert len(seen)==1 and seen[0]['source_text']
    assert out['answer'].endswith(uncertainty)
    assert 'student discounts are unavailable' not in out['answer'].lower()
    assert out['composition']=='abstained_missing_evidence'
    assert not out['citations'] and not out['tool_calls']
    assert set(out['retrieved_chunk_ids']) <= {'STY-1'}
    assert out['retrieval_candidates'] and out['evidence_supported'] is False
    assert out['generation']['model_flags']=={'covered':False,'needs_clarification':False}
    recorded={s['id']:s for s in out['generation_context_sources']}
    assert set(recorded)=={s['id'] for s in seen[0]['source_text']}
    assert all({key:recorded[s['id']][key] for key in s}==s for s in seen[0]['source_text'])
    assert all(s['text']==resource.kb.chunks[s['id']].text for s in seen[0]['source_text'])
    assert 'verified_rule_summary' not in seen[0]

@pytest.mark.parametrize('question,expected_intent', [
    ('My pincode is 248001. What is the return period for ELE-0002?', 'return'),
    ('My pincode is 248001. Explain the warranty on ELE-0005.', 'warranty'),
])
def test_incidental_pincode_does_not_replace_policy_question(resource,question,expected_intent):
    out=Agent(resource,compose=False).respond(question)
    assert out['intent']==expected_intent and out['decision']=='answer'
    assert 'Standard delivery is' not in out['answer']
    assert 'serviceable' not in out['facts']

def test_unlisted_public_pincode_does_not_ask_for_private_order(resource):
    out=Agent(resource,compose=False).respond('Can you deliver to pincode 999999?')
    assert out['decision']=='refuse' and out['facts']['pincode_listed'] is False
    assert 'not listed' in out['answer']
    assert 'order ID' not in out['answer']
    assert not out['tool_calls']

def test_unknown_replacement_sku_cannot_reuse_previous_product(resource):
    agent=Agent(resource,compose=False)
    agent.respond('What is the return period for ELE-0002?')
    out=agent.respond('What about ELE-9999 instead?')
    assert out['decision']=='clarify' and out['facts']['catalog_match'] is False
    assert 'not find' in out['answer']
    assert 'ELE-0002' not in str(out['sources'])
    assert 'sku' not in agent.state.public_context

@pytest.mark.parametrize('question', [
    'Can I schedule a delivery at midnight?',
    'Is there a student discount?',
])
def test_uncovered_offline_route_is_explicit_source_inspection(resource,question,monkeypatch):
    monkeypatch.setattr(resource.llm,'complete',lambda *args,**kwargs:pytest.fail('Offline source inspection cannot call the model'))
    out=Agent(resource,compose=False).respond(question)
    assert out['composition']=='document_excerpts'
    assert 'offline; no generated answer' in out['answer']
    assert out['citations'] and out['retrieval_candidates']
    assert all(c['quote']==resource.kb.chunks[c['id']].text[:1100] for c in out['citations'])
    assert out['generation']=={} and out['generation_context_sources']==[]
    assert not out['tool_calls']


def test_corrected_catalog_identifier_resumes_original_policy(resource):
    agent=Agent(resource,compose=False)
    agent.respond('What is the warranty for ELE-9999?')
    out=agent.respond('ELE0005')
    assert out['intent']=='warranty' and out['decision']=='answer'
    assert 'products.csv:ELE-0005' in out['retrieved_chunk_ids']
