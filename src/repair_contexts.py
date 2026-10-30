"""Bounded evidence-only inputs for final public-policy repair attempts.

No business answer strings or practice fixtures are read. Every duration/count
is rebound to actual supplied policy text before a focused view is returned.
"""
import json
import re
from datetime import date
from .placement_conditions import placement_exception_status
from .grounding import _numeric_text
from .inference_facts import project_inference_facts


def _active(source, reference):
    if source.get('doc_type') != 'policy' or source.get('status') != 'current':
        return False
    if source.get('effective_from'):
        try:
            if date.fromisoformat(source['effective_from']) > date.fromisoformat(str(reference)[:10]):
                return False
        except (TypeError, ValueError):
            return False
    return True


def unresolved_return_window_inputs(facts, sources):
    status = placement_exception_status(facts, sources)
    if not status or status['applicability'] != 'unknown' or status['input_origin'] != 'missing':
        return None
    policy = facts['return_policy']
    ids = set(status['source_ids']) | set(policy['source_ids'])
    reference = facts['reference_date']
    by_id = {source['id']: source for source in sources}
    if not ids <= by_id.keys():
        return None
    for source in sources:
        text = re.sub(r'[*`]', '', source.get('text', ''))
        if (_active(source, reference) and re.search(r'\breturn\s+windows?\b.{0,180}\bdelivery\b', text, re.I | re.S)):
            ids.add(source['id'])
        if source.get('doc_type') == 'catalog' and source.get('status') == 'current':
            try:
                row = json.loads(source['text'])
            except (ValueError, TypeError):
                continue
            if isinstance(row, dict) and row.get('return_category') == policy['category']:
                ids.add(source['id'])
    selected = [source for source in sources if source['id'] in ids]
    if sum(len(source['text']) for source in selected) > 4800:
        return None
    relevant = [item for item in facts.get('answer_constraints', [])
                if item.get('key') == 'return_policy.window_calendar_days']
    return {'sources': selected, 'facts': project_inference_facts(facts), 'placement_scope': status}


def delivery_attempt_inputs(facts, sources, constraints):
    requested = [item for item in constraints
                 if item.get('key') == 'delivery_policy.delivery_attempt_limit']
    if len(requested) != 1 or requested[0].get('kind') != 'number':
        return None
    limit = requested[0]['value']
    policy = facts.get('delivery_policy', {})
    if type(limit) is not int or policy.get('delivery_attempt_limit') != limit:
        return None
    by_id = {source['id']: source for source in sources}
    ids = set(requested[0]['source_ids'])
    if not ids or not ids <= by_id.keys():
        return None
    for ident in ids:
        source = by_id[ident]
        if not _active(source, facts.get('reference_date')):
            return None
        values = {int(match) for match in re.findall(r'\bup\s+to\s+(\d+)\s+delivery\s+attempts?\b',
                                                     _numeric_text(source['text']), re.I)}
        if values != {limit}:
            return None
    # Keep actual linked sections, including the conditions on consequences.
    pending = list(ids)
    while pending:
        source = by_id[pending.pop()]
        for ident in re.findall(r'\b[A-Z][A-Z0-9]{1,15}-\d{1,4}\b', source['text']):
            if ident in ids:
                continue
            if ident not in by_id or not _active(by_id[ident], facts.get('reference_date')):
                return None
            ids.add(ident); pending.append(ident)
            if len(ids) > 5:
                return None
    selected = [source for source in sources if source['id'] in ids]
    if sum(len(source['text']) for source in selected) > 4800:
        return None
    semantic = [item for item in facts.get('source_semantic_constraints', [])
                if set(item.get('source_ids', [])) <= ids]
    return {'sources': selected, 'facts': {'delivery_policy': policy,
        'answer_constraints': requested, 'source_semantic_constraints': semantic}}
