"""A taxonomy wording repair retains the full evidence and business checks."""
import json
import pytest
from src.document_answers import document_reply
from src.generation_diagnostics import GenerationValidationError


def source(hours):
    return {'id': 'REPORT-CHANGED', 'doc_type': 'policy', 'status': 'current',
            'text': f'Report damaged items within {hours} hours of delivery, with photos of the item and packaging. This applies to every category, including grocery and other non-returnable items.'}


class Client:
    def __init__(self, *answers):
        self.answers = iter(answers)
        self.calls = []
    def complete(self, system, user, **options):
        self.calls.append((system, json.loads(user), options))
        return json.dumps({'answer': next(self.answers), 'covered': True, 'needs_clarification': False})


@pytest.mark.parametrize('hours', [36, 72])
def test_repair_reads_changed_reporting_duration_and_keeps_original_evidence(hours):
    sources = [source(hours)]
    bad = f'यह सभी श्रेणियों, जैसे ग्रीन और अन्य वस्तुओं पर लागू है। {hours} घंटे में रिपोर्ट करें।'
    good = f'डिलीवरी के {hours} घंटे के भीतर सामान और पैकेजिंग की फ़ोटो के साथ रिपोर्ट करें।'
    client = Client(bad, good)
    out = document_reply(client, 'मेरा सामान टूटा हुआ आया है, क्या करना चाहिए?', 'hi', sources, context_provenance=True)
    assert out['answer'] == good and out['generation_attempts'] == 2
    assert out['repair_errors'] == ['unsupported_category_label']
    assert client.calls[0][1]['source_text'] == client.calls[1][1]['source_text'] == sources
    assert client.calls[1][2]['cache'] is False


def test_taxonomy_repair_still_rejects_an_invented_reporting_number():
    client = Client('This covers every category, including green.',
                    'Report the damaged item within 48 hours of delivery, with item and packaging photos.')
    with pytest.raises(GenerationValidationError, match='unsupported_number'):
        document_reply(client, 'How do I report damage?', 'en', [source(72)], context_provenance=True)


def test_compound_request_does_not_lose_other_supplied_policy_evidence():
    sources = [source(72), {'id': 'WARRANTY-CHANGED', 'doc_type': 'policy', 'status': 'current',
        'text': 'The brand warranty lasts 9 months. Claims go to the manufacturer service centre.'}]
    good = 'Report damage within 72 hours of delivery, with item and packaging photos. The brand warranty lasts 9 months, and claims go to the manufacturer service centre.'
    client = Client('This covers every category, including green.', good)
    out = document_reply(client, 'How do I report damage, and what brand warranty applies?', 'en', sources, context_provenance=True)
    assert out['answer'] == good
    assert client.calls[0][1]['source_text'] == client.calls[1][1]['source_text'] == sources
