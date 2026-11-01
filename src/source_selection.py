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


def focus_policy_context(selected, candidates, preferred_ids=(), *, query=None, facet_count=0):
    """Focus generation on actual search ranks while retaining dependencies.

    Full retrieval stays in the audit trace. The context keeps the strongest
    direct matches, actual route hints, all catalog rows and appended source
    dependencies. More question facets expand the direct-match allowance.
    No source text, policy value, evidence ID or expected answer is authored.
    Unknown candidate metadata retains the original context conservatively.
    """
    if not isinstance(candidates, (list, tuple)) or not candidates:
        return selected
    rows = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            return selected
        chunk = candidate.get('chunk')
        ident = getattr(chunk, 'id', None)
        role, rank = candidate.get('retrieval_role'), candidate.get('direct_rank')
        if role not in {'direct', 'dependency'} or (role == 'direct' and (type(rank) is not int or rank < 1)):
            return selected
        if isinstance(ident, str):
            rows[ident] = candidate
    if not rows:
        return selected
    # Unfamiliar wording must retain broad recall. Focus only when the
    # leading actual source has strong literal support for the query concepts.
    from .retrieval import tokenize
    terms = set(tokenize(query or '')) - {'zentromart', 'policy', 'support', 'customer', 'question', 'information'}
    leading = min((item for item in rows.values() if item['retrieval_role'] == 'direct'),
                  key=lambda item: item['direct_rank'], default=None)
    leading_id = getattr(leading.get('chunk'), 'id', None) if leading else None
    source = next((row for row in selected if row['id'] == leading_id), None)
    overlap = terms & set(tokenize(source['text'])) if source else set()
    if len(terms) < 2 or len(overlap) < 2 or len(overlap) / len(terms) < .6:
        return selected
    limit = min(8, 2 + max(0, facet_count - 1))
    keep = set(preferred_ids)
    keep.update(ident for ident, item in rows.items()
                if item['retrieval_role'] == 'dependency' or item['direct_rank'] <= limit)
    keep.update(row['id'] for row in selected if row.get('doc_type') in {'catalog', 'meta'})
    focused = [row for row in selected if row['id'] in keep]
    # A focus failure must not manufacture an unsupported no-evidence path.
    return focused if any(row.get('doc_type') in _ANSWER_TYPES for row in focused) else selected
