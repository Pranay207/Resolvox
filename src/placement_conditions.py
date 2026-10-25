"""Validate personal return-date premises against actual inputs and policy text.

This finite guard rejects assertions, never authors customer-facing prose. General
current windows and conditional exception explanations do not require a date.
"""
from datetime import date, datetime
import re

from .grounding import _numeric_text

_PLACEMENT = re.compile(
    r'(?P<category>[A-Za-z][A-Za-z ,&-]+?)\s+from\s+orders\s+placed\s+between\s+'
    r'(?P<start>\d{1,2}\s+[A-Za-z]+(?:\s+\d{4})?)\s+and\s+'
    r'(?P<end>\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+'
    r'can\s+be\s+returned\s+within\s+(?P<days>\d+)\s+days\s+of\s+delivery', re.I)
_HISTORICAL = re.compile(
    r'(?P<category>[A-Za-z][A-Za-z ,&-]+?)\s+delivered\s+before\s+'
    r'(?P<boundary>\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+'
    r'keep\s+the\s+earlier\s+(?P<days>\d+)[- ]day\s+window', re.I)
_CONDITIONAL = re.compile(
    r'\b(?:if|provided|assuming|when|whether)\b|'
    r'\bfor\s+(?:orders?|items?|products?)\s+(?:placed|ordered|delivered)\b|'
    r'\u092f\u0926\u093f|\u0905\u0917\u0930|\b(?:agar|yadi)\b', re.I)
_CAUSAL = re.compile(
    r'\b(?:since|because)\b|\u091a\u0942\u0902\u0915\u093f|'
    r'\u0915\u094d\u092f\u094b\u0902\u0915\u093f|\b(?:kyunki|chunki)\b', re.I)
_PLACED_ASSERTION = re.compile(
    r'\b(?:your|the|this)\s+(?:order|purchase)\s+(?:was|is|has\s+been)\s+'
    r'(?:not\s+)?(?:placed|made|ordered)\b|'
    r'\byou\s+(?:placed|ordered|purchased)\b|'
    r'\b(?:your\s+(?:order|purchase)\s+date|(?:order|placement)\s+date\s+of\s+'
    r'(?:your|the|this)\s+(?:order|purchase))\s+(?:is|was|falls|lies)\s+(?:on|before|after|between|within)\b|'
    r'\u0906\u092a\u0915\u093e\s*(?:\u0911\u0930\u094d\u0921\u0930|\u0906\u0930\u094d\u0921\u0930).{0,100}'
    r'(?:\u0930\u0916\u093e\s*\u0917\u092f\u093e|\u0915\u093f\u092f\u093e\s*\u0917\u092f\u093e|'
    r'\u092a\u094d\u0932\u0947\u0938\s*\u0939\u0941\u0906|\u0926\u093f\u092f\u093e\s*\u0917\u092f\u093e)|'
    r'\baapka\s+order\b.{0,100}\b(?:place\s+hua|placed|kiya\s+tha)\b|'
    r'\baapne\b.{0,80}\border\b.{0,50}\b(?:kiya|place)\b', re.I)
_DELIVERED_ASSERTION = re.compile(
    r'\b(?:your|the|this)\s+(?:order|purchase|item|product)\s+(?:was|is|has\s+been)\s+'
    r'(?:not\s+)?(?:delivered|received)\b|'
    r'\b(?:your\s+delivery\s+date|delivery\s+date\s+(?:of|for)\s+'
    r'(?:your|the|this)\s+(?:order|purchase|item|product))\s+(?:is|was|falls|lies)\s+(?:on|before|after|between|within)\b|'
    r'\byou\s+(?:received|got)\b.{0,70}\b(?:on|before|after)\b|'
    r'\u0906\u092a\u0915[\u093e\u0940]\s*.{0,55}(?:\u0921\u093f\u0932\u0940\u0935\u0930|\u0935\u093f\u0924\u0930\u093f\u0924)'
    r'.{0,55}(?:\u0939\u0941\u0906|\u0939\u0941\u0908|\u0915\u093f\u092f\u093e\s*\u0917\u092f\u093e)|'
    r'\baapka\b.{0,60}\bdeliver(?:y|ed)?\b.{0,50}\b(?:hua|hui|tha|thi)\b', re.I)
_ENTITLEMENT = re.compile(
    r'\byou\s+(?:have|get|receive|qualify|are\s+eligible|are\s+entitled)\b|'
    r'\b(?:your|the|this)\s+(?:order|purchase|item|product)\s+(?:qualifies|is\s+eligible|gets|has)\b|'
    r'\bit\s+(?:qualifies|is\s+eligible)\b|'
    r'\u0906\u092a\u0915\u094b.{0,60}(?:\u0926\u093f\u0928|\u0905\u0935\u0927\u093f)|'
    r'\u0906\u092a\u0915\u093e\s*(?:\u0911\u0930\u094d\u0921\u0930|\u0906\u0930\u094d\u0921\u0930).{0,100}'
    r'(?:\u092a\u093e\u0924\u094d\u0930|\u092f\u094b\u0917\u094d\u092f)|'
    r'\baapko\b.{0,60}\bdin\b|\baapka\s+order\b.{0,90}\b(?:eligible|qualify)\b', re.I)
_NEGATED = re.compile(r"\b(?:not|never|cannot|can't|doesn't|does\s+not|nahi|nahin)\b|\u0928\u0939\u0940\u0902", re.I)
_EPISTEMIC = re.compile(
    r"\b(?:I|we)\s+(?:cannot|can't|do\s+not|don't)\s+(?:know|confirm|verify|determine)\b|"
    r'\u092e\u0948\u0902.{0,25}(?:\u0928\u0939\u0940\u0902|\u092a\u0924\u093e\s*\u0928\u0939\u0940\u0902)|'
    r'\bmujhe\s+(?:nahi|nahin)\s+pata\b', re.I)


def _text(source):
    return re.sub(r'[*`]', '', source.get('text', ''))


def _words(value):
    return set(re.findall(r'[a-z]+', value.casefold())) - {'and', 'the', 'products', 'items'}


def _active(source, reference):
    if source.get('doc_type') != 'policy' or source.get('status') != 'current':
        return False
    effective = source.get('effective_from')
    if not effective:
        return True
    try:
        return date.fromisoformat(effective) <= date.fromisoformat(reference)
    except (TypeError, ValueError):
        return False


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _source_date(value, year=None):
    if year is not None:
        value += ' ' + str(year)
    for pattern in ('%d %B %Y', '%d %b %Y'):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    return None


def _inputs(facts, field, public_field):
    order, public = facts.get('verified_order', {}), facts.get('public_context', {})
    if not isinstance(order, dict) or not isinstance(public, dict):
        raise ValueError('unbound_return_date_input')
    for record, key, origin in ((order, field, 'verified_order'),
                                (public, public_field, 'customer_provided_unverified')):
        if key in record and record[key] not in (None, ''):
            parsed = _date(record[key])
            if parsed is None:
                raise ValueError('unbound_return_date_input')
            return parsed, origin
    return None, 'missing'


def _actual(sources):
    values = sources.values() if isinstance(sources, dict) else sources
    return {s['id']: s for s in values if isinstance(s, dict)
            and isinstance(s.get('id'), str) and isinstance(s.get('text'), str)}


def _window_binding(policy, actual, reference):
    category = policy.get('category')
    if not isinstance(category, str):
        raise ValueError('unbound_return_date_policy')
    labels = []
    for source in actual.values():
        if not _active(source, reference):
            continue
        for line in _text(source).splitlines():
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if len(cells) == 3 and cells[2] == category:
                match = re.fullmatch(r'(\d+)\s+days', cells[1], re.I)
                if match:
                    labels.append((cells[0], int(match[1])))
    if len(set(labels)) != 1:
        raise ValueError('unbound_return_date_policy')
    return labels[0]


def _source_exception(exception, actual, reference, label, *, kind):
    error = 'unbound_' + kind + '_exception'
    ids = exception.get('source_ids') if isinstance(exception, dict) else None
    if not isinstance(ids, list) or not ids or any(not isinstance(sid, str) or sid not in actual for sid in ids):
        raise ValueError(error)
    parsed = []
    for sid in ids:
        source = actual[sid]
        if not _active(source, reference):
            raise ValueError(error)
        matches = []
        parser = _PLACEMENT if kind == 'placement' else _HISTORICAL
        for match in parser.finditer(_text(source)):
            scope = _words(match['category'])
            expected = _words(label)
            # The historical source can use a shorter category name than the table.
            if not scope or (scope != expected if kind == 'placement' else not scope <= expected):
                continue
            days = int(match['days'])
            if kind == 'placement':
                end = _source_date(match['end'])
                begin = _source_date(match['start']) if re.search(r'\d{4}$', match['start']) else _source_date(match['start'], end.year if end else None)
                if begin and end and begin <= end and days > 0:
                    matches.append((begin, end, days))
            else:
                boundary = _source_date(match['boundary'])
                if boundary and days > 0:
                    matches.append((boundary, days))
        if len(set(matches)) != 1:
            raise ValueError(error)
        parsed.extend(matches)
    if len(set(parsed)) != 1:
        raise ValueError(error)
    return parsed[0], ids


def placement_exception_status(facts, sources):
    """Rebind existing placement facts; do not infer a customer placement date."""
    policy = facts.get('return_policy', {})
    if not isinstance(policy, dict) or not policy.get('placement_exception'):
        return None
    actual, reference = _actual(sources), facts.get('reference_date')
    label, standard_days = _window_binding(policy, actual, reference)
    exception = policy['placement_exception']
    (begin, end, days), ids = _source_exception(exception, actual, reference, label, kind='placement')
    if (_date(exception.get('placed_from')) != begin or _date(exception.get('placed_through')) != end
            or type(exception.get('window_calendar_days')) is not int or exception['window_calendar_days'] != days):
        raise ValueError('unbound_placement_exception')
    placed, origin = _inputs(facts, 'placed_at', 'placed_on')
    unavailable = policy.get('placement_date_unavailable')
    if unavailable is not None and type(unavailable) is not bool:
        raise ValueError('unbound_return_date_input')
    if (unavailable is True and placed) or (unavailable is False and not placed):
        raise ValueError('unbound_return_date_input')
    return {'applicability': 'unknown' if not placed else 'met' if begin <= placed <= end else 'not_met',
            'input_origin': origin, 'placement_date': placed.isoformat() if placed else None,
            'placed_from': begin.isoformat(), 'placed_through': end.isoformat(),
            'window_calendar_days': days, 'standard_window_calendar_days': standard_days, 'source_ids': ids}


def delivery_exception_status(facts, sources):
    """Rebind an existing historical cutoff; reference_date is not delivery input."""
    policy = facts.get('return_policy', {})
    if not isinstance(policy, dict):
        return None
    exception = policy.get('historical_exception')
    if exception is None and policy.get('selection') == 'historical_window':
        exception = {key: policy.get(key) for key in ('delivery_before', 'window_calendar_days', 'source_ids')}
    if exception is None:
        return None
    actual, reference = _actual(sources), facts.get('reference_date')
    try:
        label, standard_days = _window_binding(policy, actual, reference)
    except ValueError:
        # A selected historical window can be supplied by its source alone.
        # Bind its category scope to the actual source phrase below; do not
        # fabricate a missing current numeric window.
        if policy.get('selection') != 'historical_window' or not isinstance(policy.get('category'), str):
            raise
        label, standard_days = policy['category'].replace('_', ' '), None
    (boundary, days), ids = _source_exception(exception, actual, reference, label, kind='delivery')
    if (_date(exception.get('delivery_before')) != boundary or type(exception.get('window_calendar_days')) is not int
            or exception['window_calendar_days'] != days):
        raise ValueError('unbound_delivery_exception')
    delivered, origin = _inputs(facts, 'delivered_on', 'delivered_on')
    return {'applicability': 'unknown' if not delivered else 'met' if delivered < boundary else 'not_met',
            'input_origin': origin, 'delivery_date': delivered.isoformat() if delivered else None,
            'delivery_before': boundary.isoformat(), 'window_calendar_days': days,
            'standard_window_calendar_days': standard_days, 'source_ids': ids}


def _conditional(clause, position):
    # A condition must govern this predicate, not an earlier comma clause.
    prefix = clause[:position].rsplit(',', 1)[-1]
    return bool(_CONDITIONAL.search(prefix)) and not _CAUSAL.search(prefix)


def _implicit_date_condition(clause, kind):
    subject = r'orders?' if kind == 'placement' else r'(?:orders?|items?|products?)'
    predicate = r'(?:placed|ordered)' if kind == 'placement' else r'delivered'
    return bool(re.search(r'\bfor\s+' + subject + r'\s+' + predicate + r'\b|'
                          r'\b(?:if|provided|assuming|when|whether)\s+'
                          r'(?:it\s+(?:was|is|has\s+been)\s+)?' + predicate + r'\b', clause, re.I))


def _mentions_days(clause, days, normalizer):
    normalized = normalizer(clause.casefold().replace('-', ' '))
    return bool(re.search(r'(?<!\d)' + re.escape(str(days)) + r'\s*(?:calendar\s*)?(?:days?|din|\u0926\u093f\u0928)(?![A-Za-z])', normalized, re.I))


def check_placement_exception_answer(answer, facts, sources, *, normalizer=_numeric_text):
    """Check unsupported personal date premises and definite exception entitlement."""
    policy = facts.get('return_policy', {})
    if not isinstance(policy, dict) or not policy:
        return
    placement = placement_exception_status(facts, sources)
    delivery = delivery_exception_status(facts, sources)
    if placement is None and delivery is None:
        return
    inputs = {'placement': _inputs(facts, 'placed_at', 'placed_on')[0],
              'delivery': _inputs(facts, 'delivered_on', 'delivered_on')[0]}
    for clause in re.split(r'[.!?;\u0964\n]+', answer):
        conditional_dates = {}
        for kind, pattern in (('placement', _PLACED_ASSERTION), ('delivery', _DELIVERED_ASSERTION)):
            asserted = pattern.search(clause)
            conditional_dates[kind] = bool(asserted and _conditional(clause, asserted.start())) or _implicit_date_condition(clause, kind)
            if inputs[kind] is None and asserted and not conditional_dates[kind]:
                if not _EPISTEMIC.search(clause[:asserted.start()]):
                    raise ValueError('invented_' + kind + '_premise')
        entitlement = _ENTITLEMENT.search(clause)
        if not entitlement:
            continue
        local = clause[max(0, entitlement.start() - 15):entitlement.end() + 15]
        if _NEGATED.search(local):
            continue
        for kind, status in (('placement', placement), ('delivery', delivery)):
            if not status or status['applicability'] == 'met' or conditional_dates[kind]:
                continue
            if (status['window_calendar_days'] != status['standard_window_calendar_days']
                    and _mentions_days(clause, status['window_calendar_days'], normalizer)):
                raise ValueError('unsupported_' + kind + '_exception_entitlement')
