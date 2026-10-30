import copy, json
import pytest
from src.repair_contexts import damage_reporting_restatement_inputs
from src.document_answers import document_reply

TODAY = '2026-10-20'

def report(hours=72):
    return {'id': 'REPORT-NEW', 'file': 'new_reporting.md', 'doc_type': 'policy',
            'status': 'current', 'effective_from': '2026-01-01',
            'text': f'Report a damaged or wrong item within {hours} hours of delivery, with photos of the item and packaging. This applies to every category, including grocery and other non-returnable items.'}


@pytest.mark.parametrize('hours', [36, 84])
def test_simple_reporting_view_retains_exact_changed_source_and_excludes_staff_route(hours):
    original = report(hours)
    staff = {**original, 'id': 'STAFF-X', 'text': 'High-value claims must be handed over by the support agent.'}
    result = damage_reporting_restatement_inputs('My item arrived broken. What should I do?', {}, [original, staff], TODAY)
    assert result['sources'] == [original]
    assert result['sources'][0]['text'] == original['text']
    assert result['facts'] == {}


@pytest.mark.parametrize('question', [
    'How do I report damage and claim a refund?',
    'What warranty applies to my damaged product?',
    'I reported damage after 72 hours. What now?',
    'मेरा सामान टूटा है और मुझे रिफंड चाहिए।',
    'My SKU-X2 arrived damaged. What should I do?',
    'How much is the pickup fee for my broken item?',
])
def test_compound_late_or_product_specific_requests_keep_complete_view(question):
    assert damage_reporting_restatement_inputs(question, {}, [report()], TODAY) is None


@pytest.mark.parametrize('facts', [{'verified_order': {'order_id': 'NEW'}}, {'catalog': [{}]}, {'public_context': {'sku': 'NEW'}}, {'operational_escalation': {'reason': 'review'}}])
def test_personal_or_operational_decisions_keep_complete_view(facts):
    assert damage_reporting_restatement_inputs('My item arrived broken. What now?', facts, [report()], TODAY) is None


def test_ambiguous_inactive_future_and_unresolved_linked_rules_do_not_get_focused():
    source = report()
    assert damage_reporting_restatement_inputs('My item arrived broken.', {}, [source, {**source, 'id': 'OTHER-X'}], TODAY) is None
    for changed in [dict(source, status='superseded'), dict(source, effective_from='2027-01-01'), dict(source, text=source['text'] + ' Follow LINK-8.')]:
        assert damage_reporting_restatement_inputs('My item arrived broken.', {}, [changed], TODAY) is None


def test_generation_uses_original_reporting_section_and_final_original_validation():
    first = 'यह हर श्रेणी, जैसे ग्रीन और दूसरी वस्तुओं पर लागू है।'
    good = 'डिलीवरी के 72 घंटे के भीतर सामान और पैकेजिंग की फ़ोटो के साथ रिपोर्ट करें।'
    calls = []
    class Client:
        def complete(self, system, user, **options):
            calls.append(json.loads(user))
            return json.dumps({'answer': first if len(calls) == 1 else good, 'covered': True, 'needs_clarification': False})
    sources = [report(), {**report(), 'id': 'STAFF-X', 'text': 'High-value claims require the support agent to create a ticket.'}]
    result = document_reply(Client(), 'मेरा सामान टूटा हुआ आया है, अब क्या करूँ?', 'hi', sources, context_provenance=True)
    assert result['answer'] == good
    assert result['repair_mode'] == 'source_reporting_restatement'
    assert len(calls[0]['source_text']) == 2 and calls[1]['source_text'] == [report()]
    assert result['context_source_ids'] == ['REPORT-NEW', 'STAFF-X']
    assert result['repair_context_sources'] == [report()]
