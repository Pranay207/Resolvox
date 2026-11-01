"""Authenticated record readings remain distinct from performed actions."""
import json

import pytest

from src.document_answers import document_reply

POLICY = {
    'id': 'SYNTHETIC-REFUND',
    'text': 'The refund reference can help the bank trace an existing refund.',
    'doc_type': 'policy', 'status': 'current',
}
RRN = '123456789012'
FACTS = {
    'verified_order': {
        'status': 'Delivered',
        'return_refund_completed_on': '2026-10-18',
        'return_rrn': RRN,
        'delivered_on': '2026-10-19',
    },
    'date_labels': {'2026-10-18': '18 October 2026', '2026-10-19': '19 October 2026'},
}


class Client:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def complete(self, system, user, json_mode=False, **kwargs):
        self.calls.append(kwargs)
        return json.dumps({
            'answer': self.text, 'decision': 'answer',
            'citations': [{'id': POLICY['id'], 'quote': POLICY['text']}],
        })


def reply(text, *, facts=None, private=True):
    client = Client(text)
    return document_reply(client, 'What does the verified order record show?', 'en',
                          [POLICY], facts=FACTS if facts is None else facts, private=private)


@pytest.mark.parametrize('text', [
    'The order record lists status as Delivered.',
    'The order record lists refund completed on 18 October 2026.',
    'The order record shows the refund was completed on 18 October 2026.',
    'The order record lists the refund has been completed on 18 October 2026.',
    'The verified order record shows refund completed on 2026-10-18.',
    'The recorded refund completion date is 18 October 2026.',
    'RRN: ' + RRN + '.',
    'The refund reference number (RRN) ' + RRN + '.',
    'The refund reference is ' + RRN + '.',
])
def test_actual_authenticated_record_fields_are_read_without_claiming_actions(text):
    out = reply(text)
    assert out['answer'] == text
    assert out['generation_attempts'] == 1


@pytest.mark.parametrize('text', [
    'The order record lists status as Shipped.',
    'The order record lists refund completed on 19 October 2026.',
    'The order record shows the refund was completed on 19 October 2026.',
    'The order record shows the refund was completed on 18 October 2026. I have issued a refund.',
    'The recorded refund completion date is 19 October 2026.',
    'RRN: 999999999999.',
    'The refund reference number (RRN) 999999999999.',
    'The refund reference number (RRN) ' + RRN + '. I have created a ticket.',
    'The refund reference is 999999999999.',
    'The phone number is ' + RRN + '.',
    'The refund reference is ' + RRN + '. I have issued your refund.',
    'The order record lists refund completed on 18 October 2026. I cancelled your order.',
])
def test_invalid_record_readings_and_assistant_claims_are_rejected(text):
    with pytest.raises(ValueError):
        reply(text)


@pytest.mark.parametrize('text', [
    'RRN: ' + RRN + '.',
    'The refund reference number (RRN) ' + RRN + '.',
    'The order record lists status as Delivered.',
    'The order record lists refund completed on 18 October 2026.',
    'The recorded refund completion date is 18 October 2026.',
])
def test_private_record_values_require_the_authenticated_boundary(text):
    with pytest.raises(ValueError):
        reply(text, private=False)
    with pytest.raises(ValueError):
        reply(text, facts={'date_labels': FACTS['date_labels']})


def test_unrelated_fact_field_cannot_allowlist_a_long_identifier():
    facts = {'verified_order': {'status': 'Delivered', 'phone': RRN}}
    with pytest.raises(ValueError):
        reply('RRN: ' + RRN + '.', facts=facts)


def test_truthful_record_completion_does_not_reenable_private_output_cache():
    client = Client('The order record lists refund completed on 18 October 2026.')
    document_reply(client, 'What does the record show?', 'en', [POLICY],
                   facts=FACTS, private=True)
    assert client.calls[0]['cache'] is False


def test_uncited_refusal_cannot_append_a_policy_claim_after_a_disclaimer():
    class RefusalClient:
        def complete(self, *args, **kwargs):
            return json.dumps({
                'answer': 'I do not have enough information, but returns are always free.',
                'decision': 'refuse', 'citations': [],
            })
    with pytest.raises(ValueError):
        document_reply(RefusalClient(), 'Are returns free?', 'en', [POLICY])


def test_valid_parenthesized_reference_keeps_action_guard_and_one_repair():
    class RepairClient:
        def __init__(self):self.calls=0
        def complete(self, system, user, **options):
            self.calls+=1
            text=('The refund reference number (RRN) '+RRN+'. I have created a ticket.'
                  if self.calls==1 else 'The refund reference number (RRN) '+RRN+'.')
            return json.dumps({'answer':text,'covered':True,'needs_clarification':False})
    client=RepairClient()
    out=document_reply(client,'What refund reference is recorded?','en',[POLICY],
                       facts=FACTS,private=True,context_provenance=True)
    assert out['repair_errors']==['unsupported_action']
    assert out['answer']=='The refund reference number (RRN) '+RRN+'.'
    assert client.calls==2
