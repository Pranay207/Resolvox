import json
import pytest
from src.document_answers import document_reply

SOURCE = {'id': 'REPORT-66', 'file': 'changed_reporting.md', 'doc_type': 'policy', 'status': 'current',
    'text': 'Report damaged items within 66 hours of delivery, with photos of the item and packaging. This applies to every category, including grocery.'}
GOOD = 'Report the damaged item within 66 hours of delivery, with item and packaging photos.'


class Client:
    def __init__(self, final):
        self.final = final
        self.calls = []
    def complete(self, system, user, **options):
        self.calls.append((system, json.loads(user)))
        if len(self.calls) == 1:
            value = {'answer': 'This applies to every category, including green.', 'covered': True, 'needs_clarification': False}
        else:
            value = self.final
        return json.dumps(value)


def run(client):
    return document_reply(client, 'How do I report my damaged item?', 'en', [SOURCE], context_provenance=True)


def test_reporting_support_flag_is_explicitly_mapped_and_preserves_model_boolean():
    result = run(Client({'answer': GOOD, 'has_document_support': True, 'needs_clarification': False}))
    assert result['answer'] == GOOD
    assert result['model_flags'] == {'covered': True, 'needs_clarification': False}
    contract = result['reporting_support_contract']
    assert contract['field_alias'] == {'has_document_support': 'covered'}
    assert contract['original_model_flags'] == {'has_document_support': True, 'needs_clarification': False}


def test_support_alias_never_coerces_a_false_model_flag_into_supported_policy():
    with pytest.raises(ValueError, match='uncited_numeric_or_long_reply'):
        run(Client({'answer': GOOD, 'has_document_support': False, 'needs_clarification': False}))


def test_old_ambiguous_flag_cannot_override_the_requested_reporting_schema():
    with pytest.raises(ValueError, match='invalid_response_fields'):
        run(Client({'answer': GOOD, 'covered': True, 'needs_clarification': False}))


def test_explicit_support_does_not_bypass_changed_source_duration_validation():
    with pytest.raises(ValueError, match='unsupported_number'):
        run(Client({'answer': 'Report within 48 hours of delivery, with photos.', 'has_document_support': True, 'needs_clarification': False}))


def test_support_metadata_is_never_allowed_in_the_spoken_reply():
    with pytest.raises(ValueError, match='internal_metadata_in_answer'):
        run(Client({'answer': 'has_document_support=true. ' + GOOD, 'has_document_support': True, 'needs_clarification': False}))
