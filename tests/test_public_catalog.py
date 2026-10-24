"""Public postal data does not authenticate a caller or expose an order."""
import json
from src.agent import Agent,Resources


def test_public_cod_serviceability_uses_catalog_without_order_lookup():
    r=Resources(dense=False)
    out=Agent(r,compose=False).respond('Is COD delivery available at pincode 560034?')
    assert 'pincodes.csv:560034' in out['retrieved_chunk_ids']
    assert out['facts']['cod_available'] is True
    assert not out['verified'] and not out['tool_calls']
    assert 'available' in out['answer']


def test_postal_verification_value_never_becomes_public_query_context():
    r=Resources(dense=False);a=Agent(r,compose=False)
    a.respond('Order 89782837')
    out=a.respond('My delivery pincode is 560034')
    assert out['transcript']=='[verification value redacted]'
    assert '560034' not in json.dumps(out)
    assert not any(c.startswith('pincodes.csv:') for c in out['retrieved_chunk_ids'])


def test_postal_cod_flag_does_not_override_order_amount_limit():
    out=Agent(Resources(dense=False),compose=False).respond('Can I pay COD for 15000 rupees at pincode 560034?')
    assert out['facts']['cod_eligible'] is False
    assert 'not eligible' in out['answer'] and 'PAY-2' in out['retrieved_chunk_ids']
