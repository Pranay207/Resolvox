"""Preserve bounded, already-retrieved policy context without planner answers.

This is a source-flow selector, NOT a semantic-coverage or entailment classifier.
The caller must have re-bound every KB row to its current authorized source and
looked up each catalog row independently. It never adds IDs or reads fixtures.
"""

_ANSWER_TYPES = frozenset({'policy', 'help', 'catalog'})
_SUPPORT_TYPES = frozenset({'meta'})


def select_policy_context(pool, preferred_ids=()):
    """Return actual supplied policy rows; hints only influence their ordering.

    All vetted search candidates of an answer-bearing type remain available.
    Pure style/agent guides, FAQs and marketing cannot establish policy support.
    Metadata is supplemental and cannot by itself open a generation path.
    Input is bounded upstream by the search limit plus matched catalog records.
    Semantic answer coverage still belongs to generation/validation; selection
    alone must never force ``covered=True`` or manufacture a reply.
    """
    if not isinstance(pool, (list, tuple)):
        return []
    available = {}
    for source in pool:
        if not isinstance(source, dict):
            continue
        ident, text = source.get('id'), source.get('text')
        if not isinstance(ident, str) or not ident.strip():
            continue
        if not isinstance(text, str) or not text.strip():
            continue
        if source.get('doc_type') not in _ANSWER_TYPES | _SUPPORT_TYPES:
            continue
        available.setdefault(ident, source)
    if not any(row.get('doc_type') in _ANSWER_TYPES for row in available.values()):
        return []
    # Do not create a source from a hint or replace any source text with a plan.
    hints = preferred_ids if isinstance(preferred_ids, (list, tuple)) else ()
    ordered = [available[ident] for ident in hints if isinstance(ident, str) and ident in available]
    ordered += list(available.values())
    return list({row['id']: row for row in ordered}.values())
