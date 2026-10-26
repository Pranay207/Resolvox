"""Public category-role checks: direct production import; no source transform."""
import json
import socket

import pytest
from src import agent as module


class NoModel:
    last_metrics = {}
    def complete(self, *args, **kwargs):
        raise AssertionError('No live model calls are permitted')


class FakeTools:
    def lookup(self, oid, proof=None):
        return {}, {'name': 'lookup_order', 'arguments': {'order_id': oid},
                    'result': {'verified': False, 'verification_required': True}}
    def ticket(self, *args, **kwargs):
        raise AssertionError('No ticket mutation is permitted')


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    import requests
    def forbidden(*args, **kwargs):
        raise AssertionError('Network is forbidden in public-slot tests')
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)


@pytest.fixture
def resource():
    value = module.Resources(dense=False)
    value.llm = NoModel()
    value.tools = FakeTools()
    return value


@pytest.mark.parametrize('text', [
    "What happens if I'm not home when the courier comes?",
    'I am at home waiting for a courier.',
    'Nobody is home; please reschedule delivery.',
    'I will be away from home when it arrives.',
    'Can you deliver to my home?',
    'Home delivery is late.',
    'Main home par nahi hoon jab courier aaye.',
    'Ghar par nahin hun, courier ka kya hoga?',
    'Main ghar par hoon aur delivery ka wait hai.',
    '\u092e\u0948\u0902 home \u092a\u0930 \u0928\u0939\u0940\u0902 \u0939\u0942\u0901\u0964',
    '\u0918\u0930 \u092a\u0930 \u0915\u094b\u0908 \u0928\u0939\u0940\u0902 \u0939\u0948\u0964',
    '\u092e\u0948\u0902 \u0939\u094b\u092e \u092a\u0930 \u0928\u0939\u0940\u0902 \u0930\u0939\u0942\u0901\u0917\u093e\u0964',
    'home', 'ghar',
])
def test_location_or_unscoped_alias_cannot_establish_a_public_category(resource, text):
    assert module._public_category_candidate(resource.policy, text) is None
    agent = module.Agent(resource, compose=False)
    out = agent.respond(text)
    assert 'category' not in agent.state.public_context
    assert 'category' not in out.get('facts', {}).get('public_context', {})


@pytest.mark.parametrize('text', [
    'Home goods return policy?',
    'How long can I return home appliances?',
    'Home and kitchen return windows?',
    'Home & kitchen products',
    'Category: home',
    'My category is home.',
    'Home ka samaan return karna hai.',
    'Ghar ke samaan ki return policy?',
    '\u0918\u0930 \u0915\u0947 \u0909\u0924\u094d\u092a\u093e\u0926 \u0932\u094c\u091f\u093e\u0928\u0947 \u0939\u0948\u0902\u0964',
    '\u0939\u094b\u092e \u0915\u0940 \u0936\u094d\u0930\u0947\u0923\u0940',
    'Kitchen furniture return policy?',
    'I am not home, but what is the return policy for home goods?',
    'Are home products not returnable?',
    'Not only home products have a return policy.',
    'Can I not return home products?',
    'I cannot return home goods; what policy applies?',
])
def test_explicit_product_or_category_meaning_preserves_the_candidate(resource, text):
    assert module._public_category_candidate(resource.policy, text) == resource.policy._category('home')


@pytest.mark.parametrize('text', [
    'Not home', 'Not home products', 'Not home and kitchen',
    'No home goods', 'I do not want home products',
    "I don't mean home products.", "I don't want home goods.",
    'These are no longer home products.', 'Not really home goods.',
    'I am not buying home products.', 'Not home or kitchen products.',
    'Do not select the home category.',
    'Home category nahi hai.', 'Ghar ka samaan nahi hai.',
    'Home category is not.', 'Home goods are not.',
    '\u0939\u094b\u092e \u0915\u0940 \u0936\u094d\u0930\u0947\u0923\u0940 \u0928\u0939\u0940\u0902 \u0939\u0948\u0964',
])
def test_negated_category_is_not_a_positive_slot_even_when_awaiting(resource, text):
    assert module._public_category_candidate(resource.policy, text) is None
    assert module._public_category_candidate(resource.policy, text, awaiting_category=True) is None


def fake_generation(monkeypatch):
    calls = []
    def generated(client, query, language, sources, **options):
        calls.append({'question': query, **options})
        return {'answer': 'Synthetic supported response.', 'source_ids': [row['id'] for row in sources],
                'decision': 'answer', 'generation_attempts': 1, 'decision_origin': 'host_boolean_mapping'}
    monkeypatch.setattr(module, 'document_reply', generated)
    return calls


@pytest.mark.parametrize('reply', ['Home', 'ghar', '\u0918\u0930', '\u0939\u094b\u092e'])
def test_bare_home_alias_is_allowed_only_in_active_source_bound_category_reply(resource, monkeypatch, reply):
    calls = fake_generation(monkeypatch)
    agent = module.Agent(resource, compose=True)
    first = agent.respond('How many days do I have to return an item?', 'en')
    assert first['composition'] == 'source_input_clarification'
    assert first['generation']['required_input'] == 'return_category'
    second = agent.respond(reply, 'en')
    assert second['composition'] == 'grounded_llm'
    assert second['facts']['public_context']['category'] == resource.policy._category('home')
    assert len(calls) == 1 and calls[0]['question'].startswith('How many days')


def test_unrelated_courier_reply_does_not_resolve_category_workflow(resource, monkeypatch):
    fake_generation(monkeypatch)
    agent = module.Agent(resource, compose=True)
    agent.respond('How many days do I have to return an item?', 'en')
    out = agent.respond('I am not home when the courier arrives.', 'en')
    assert 'category' not in agent.state.public_context
    assert 'category' not in out.get('facts', {}).get('public_context', {})
    assert not out.get('generation', {}).get('workflow_input_resolution')


def test_location_followup_does_not_replace_known_product_with_household_category(resource):
    agent = module.Agent(resource, compose=False)
    product = next(iter(resource.data.products))
    agent.state.public_context = {'sku': product}
    agent.state.last_intent = 'delivery'
    agent.respond('What if I am not home when it comes?', 'en')
    assert agent.state.public_context.get('sku') == product
    assert 'category' not in agent.state.public_context


def test_new_topic_clears_old_category_and_does_not_infer_from_home_location(resource):
    agent = module.Agent(resource, compose=False)
    agent.state.public_context = {'category': resource.policy._category('home'), 'delivered_on': '2026-09-05'}
    agent.state.last_intent = 'return'
    agent.respond('Explain Express delivery when nobody is home.', 'en')
    assert agent.state.public_context == {}


def test_order_switch_clears_public_slots_and_deferred_category_scope(resource):
    agent = module.Agent(resource, compose=False)
    agent.state.public_context = {'category': resource.policy._category('home'), 'delivered_on': '2026-09-05'}
    agent.state.source_input_workflow = {'awaiting_reply': True, 'requirement': {'key': 'return_category'}}
    agent.respond('What is the status of order 87654321?', 'en')
    assert agent.state.public_context == {}
    assert agent.state.source_input_workflow == {}


def test_changed_source_category_code_is_not_overwritten_by_legacy_alias(resource, monkeypatch):
    from dataclasses import replace
    calls = fake_generation(monkeypatch)
    for sid, chunk in list(resource.kb.chunks.items()):
        if '`home_kitchen`' in chunk.text:
            resource.kb.chunks[sid] = replace(chunk, text=chunk.text.replace('`home_kitchen`', '`interiors`'))
    resource.retriever = module.Retriever(resource.kb, dense=False)
    agent = module.Agent(resource, compose=True)
    first = agent.respond('How many days do I have to return an item?', 'en')
    assert first['composition'] == 'source_input_clarification'
    second = agent.respond('Home', 'en')
    assert second['facts']['public_context']['category'] == 'interiors'
    assert agent.state.public_context['category'] == 'interiors'
    assert len(calls) == 1


def test_product_and_unambiguous_other_category_override_incidental_home_location(resource):
    agent = module.Agent(resource, compose=False)
    product = next(p for p in resource.data.products.values() if p['return_category'] != resource.policy._category('home'))
    agent.respond('I am not home. What is the return window for ' + product['sku'] + '?', 'en')
    assert agent.state.public_context.get('sku') == product['sku']
    assert 'category' not in agent.state.public_context
    assert module._public_category_candidate(resource.policy, 'Not home products, books instead.') == resource.policy._category('books')


@pytest.mark.parametrize('reply', ['Not home', 'at home', 'home par', 'ghar par'])
def test_short_location_or_negation_cannot_bypass_through_active_category_workflow(resource, monkeypatch, reply):
    fake_generation(monkeypatch)
    agent = module.Agent(resource, compose=True)
    agent.respond('How many days do I have to return an item?', 'en')
    out = agent.respond(reply, 'en')
    assert 'category' not in agent.state.public_context
    assert 'category' not in out.get('facts', {}).get('public_context', {})
    assert not out.get('generation', {}).get('workflow_input_resolution')


def test_stale_source_workflow_cannot_legitimize_bare_home(resource, monkeypatch):
    from dataclasses import replace
    fake_generation(monkeypatch)
    agent = module.Agent(resource, compose=True)
    agent.respond('How many days do I have to return an item?', 'en')
    workflow = agent.state.source_input_workflow
    for sid in workflow['source_sha256']:
        if sid in resource.kb.chunks:
            chunk = resource.kb.chunks[sid]
            resource.kb.chunks[sid] = replace(chunk, text=chunk.text + '\nChanged source binding.')
            break
    out = agent.respond('Home', 'en')
    assert 'category' not in agent.state.public_context
    assert not out.get('generation', {}).get('workflow_input_resolution')


def test_payment_method_clarification_does_not_authorize_bare_home(resource, monkeypatch):
    fake_generation(monkeypatch)
    agent = module.Agent(resource, compose=True)
    first = agent.respond('How long does a refund take to arrive?', 'en')
    assert first['generation']['required_input'] == 'payment_method'
    out = agent.respond('Home', 'en')
    assert 'category' not in agent.state.public_context
    assert not out.get('generation', {}).get('workflow_input_resolution')
