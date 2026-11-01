"""Validate personal return-date premises against actual inputs and policy text.

This finite guard rejects assertions, never authors customer-facing prose. General
current windows and conditional exception explanations do not require a date.
"""
from datetime import date, datetime
import json
import re

from .grounding import _numeric_text
from .return_window_uncertainty import check_unknown_placement_window

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
    r'\u0906\u092a\u0915\u093e\s*(?:\u0911\u0930\u094d\u0921\u0930|\u0906\u0930\u094d\u0921\u0930)[^,;\u0964\n]{0,100}?'
    r'(?:\u0930\u0916\u093e\s*\u0917\u092f\u093e|\u0915\u093f\u092f\u093e\s*\u0917\u092f\u093e|'
    r'\u092a\u094d\u0932\u0947\u0938\s*\u0939\u0941\u0906|\u0926\u093f\u092f\u093e\s*\u0917\u092f\u093e)|'
    r'\baapka\s+order\b[^,;\u0964\n]{0,100}?\b(?:place\s+hua|placed|kiya\s+tha)\b|'
    r'\baapne\b.{0,80}\border\b.{0,50}\b(?:kiya|place)\b', re.I)
_DELIVERED_ASSERTION = re.compile(
    r'\b(?:it|this|that)\s+(?:was|is|has\s+been|had\s+been)\s+'
    r'(?:not\s+)?(?:delivered|received)\s+'
    r'(?:on|before|after|since|between|during|yesterday|today)\b|'
    r'\b(?:your|the|this)\s+(?:order|purchase|item|product)\s+(?:was|is|has\s+been)\s+'
    r'(?:not\s+)?(?:delivered|received)\b|'
    r'\b(?:your\s+delivery\s+date|delivery\s+date\s+(?:of|for)\s+'
    r'(?:your|the|this)\s+(?:order|purchase|item|product))\s+(?:is|was|falls|lies)\s+(?:on|before|after|between|within)\b|'
    r'\byou\s+(?:received|got)\b.{0,70}\b(?:on|before|after)\b|'
    r'\u0906\u092a\u0915[\u093e\u0940]\s*.{0,55}(?:\u0921\u093f\u0932\u0940\u0935\u0930|\u0935\u093f\u0924\u0930\u093f\u0924)'
    r'.{0,55}(?:\u0939\u0941\u0906|\u0939\u0941\u0908|\u0915\u093f\u092f\u093e\s*\u0917\u092f\u093e)|'
    r'\baapka\b.{0,60}\bdeliver(?:y|ed)?\b.{0,50}\b(?:hua|hui|tha|thi)\b', re.I)
_ENTITLEMENT = re.compile(
    r'\b(?:it|(?:your|the|this)\s+(?:order|purchase|item|product|unit))\s+falls?\s+under\b|'
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


def _delivery_date_property_assertions(clause, facts, sources):
    """Find dated individual-property claims about actual supplied identifiers.

    Catalog identity is not evidence of a delivery event. This finite grammar
    does not infer dates, parse relative input, or judge all date comparisons.
    """
    identifiers = set()
    for key in ('public_context', 'verified_order'):
        record = facts.get(key, {})
        sku = record.get('sku') if isinstance(record, dict) else None
        if isinstance(sku, str) and sku.strip():
            identifiers.add(sku)
    category = facts.get('return_policy', {}).get('category')
    reference = _date(facts.get('reference_date'))
    for source in _actual(sources).values():
        if source.get('doc_type') != 'catalog' or source.get('status') != 'current':
            continue
        effective = source.get('effective_from')
        if effective and (not reference or not _date(effective) or _date(effective) > reference):
            continue
        try:
            row = json.loads(source['text'])
        except (TypeError, ValueError):
            continue
        if (isinstance(row, dict) and row.get('return_category') == category
                and isinstance(row.get('sku'), str) and row['sku'].strip()):
            identifiers.add(row['sku'])
    if not identifiers:
        return []
    identity = r'(?:' + '|'.join(re.escape(value) for value in sorted(identifiers, key=len, reverse=True)) + r')'
    identity = r'(?<![A-Za-z0-9_-])`?' + identity + r'`?(?![A-Za-z0-9_-])'
    subject = (r'(?:(?:the\s+)?delivery\s+date\s+(?:of|for)\s+(?:the\s+)?(?:sku\s+)?' + identity
               + r'|' + identity + r"(?:'s|\u2019s)\s+delivery\s+date)")
    temporal = (r'(?P<date>\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|'
                r'(?:this|that|the)\s+(?:date|cut[ -]?off)|(?:the\s+)?cut[ -]?off|today|yesterday)')
    pattern = re.compile(subject + r'\s+(?:is|was|falls|lies)\s+(?:not\s+)?'
                         r'(?:on\s+or\s+(?:before|after)|on|before|after|since)\s+' + temporal + r'\b', re.I)
    request = re.compile(r'^\s*(?:(?:can|could|would)\s+you\s+(?:please\s+)?|please\s+)'
                         r'(?:confirm|check)(?:\s+that)?\s*$', re.I)
    other_scope = re.compile(r'\b(?:estimated|expected|promised|scheduled|proposed|projected|refund|payment|warehouse|shipment)\s*$', re.I)
    result = []
    for match in pattern.finditer(clause):
        value = match['date']
        if re.match(r'\d', value) and _date(value) is None and _source_date(value) is None:
            continue
        prefix = clause[:match.start()]
        if request.fullmatch(prefix) or other_scope.search(prefix):
            continue
        result.append(match)
    return result


def _unless_placement_hypothesis(clause, position):
    # Only an immediately governing unless marks this date predicate as
    # hypothetical. It does not prove that an exception applies.
    prefix = clause[:position].rsplit(',', 1)[-1]
    return bool(re.search(r'\bunless\s*$', prefix, re.I))


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


def _requested_date_predicate(clause, position):
    """A scoped request for a date is not an assertion that the event happened."""
    prefix = re.split(r'[,;]|\b(?:but|however|yet|then)\b|लेकिन|परंतु', clause[:position], flags=re.I)[-1]
    suffix = clause[position:]
    return bool(
        re.search(r'\b(?:tell|confirm|clarify|check)\s+(?:me\s+|us\s+)?whether\s*$', prefix, re.I)
        or (re.search(r'(?:बताएं|बताएँ|बताइए|पुष्टि\s*करें)\s*(?:कि\s*)?$', prefix)
            and re.search(r'या\s*नहीं', suffix)))


def _uncertain_predicate(clause, position):
    # Uncertainty governs only the immediate predicate, not a later assertion.
    prefix = re.split(r'[,;]|\b(?:and|but|however|yet|then)\b', clause[:position], flags=re.I)[-1]
    return bool(_EPISTEMIC.search(prefix))


def _mentions_days(clause, days, normalizer):
    normalized = normalizer(clause.casefold().replace('-', ' '))
    return bool(re.search(r'(?<!\d)' + re.escape(str(days)) + r'\s*(?:calendar\s*)?(?:days?|din|\u0926\u093f\u0928)(?![A-Za-z])', normalized, re.I))


def _check_deictic_delivery_membership(answer, status, normalizer):
    """Reject asserted personal membership in a source-dated delivery class.

    The caller has independently rebound status to actual selected source text.
    Generic rules are fine. A named product model is not a dated individual unit.
    """
    if not status or status.get('input_origin') != 'missing':
        return
    boundary = _date(status.get('delivery_before'))
    if boundary is None:
        raise ValueError('unbound_delivery_exception')
    actual_dates = [boundary.isoformat(), f'{boundary.day} {boundary:%B %Y}',
                    f'{boundary.day:02d} {boundary:%B %Y}', f'{boundary.day} {boundary:%b %Y}']
    date_reference = (r'(?:' + '|'.join(re.escape(x) for x in actual_dates) +
                      r'|(?:this|that|the)\s+(?:date|cut[ -]?off)|(?:the\s+)?cut[ -]?off)')
    dated_class = re.compile(
        r'\b(?:delivered|received|deliveries)\b.{0,45}'
        r'\b(?:on\s+or\s+after|on\s+or\s+before|before|after|since|from|prior\s+to|earlier\s+than|later\s+than)\s+'
        + date_reference + r'\b', re.I)
    personal = r'(?:this\s+(?:one|1|item|unit|order|purchase)|your\s+(?:item|product|unit|order|purchase)|yours)'
    member = re.compile(
        r'\b(?:including|excluding|such\s+as|like)\s+' + personal + r'\b|'
        r'\b' + personal + r'\s+(?:belongs?|falls?|is\s+(?:included|among|one|1))\b.{0,35}'
        r'\b(?:this|that|these|those|same)\s+(?:group|class|category|batch|set|items?|products?)\b', re.I)
    conditional_personal_date = re.compile(
        r'\b(?:if|provided|assuming|when|whether)\b[^,;]{0,35}'
        r'\b(?:' + personal + r'|it)\b[^,;]{0,30}\b(?:delivered|received)\s+'
        r'(?:on\s+or\s+after|on\s+or\s+before|on|before|after|since|from|prior\s+to|earlier\s+than|later\s+than)\s+'
        + date_reference + r'\b', re.I)
    previous_dated_class = False
    for original in re.split(r'[.!?;\u0964\n]+', answer):
        # Numeric normalization removes commas; preserve their clause scope.
        clause = normalizer(original.casefold().replace(',', ';'))
        current_dated_class = bool(dated_class.search(clause))
        for match in member.finditer(clause):
            if not (current_dated_class or previous_dated_class):
                continue
            if _uncertain_predicate(clause, match.start()):
                continue
            # An explicit condition must govern this personal date/membership,
            # not merely an unrelated condition about the item's condition.
            prefix = re.split(r'[,;]', clause[:match.start()])[-1]
            conditional_membership = bool(re.search(
                r'\b(?:if|provided|assuming|when|whether)\s*(?:that\s+)?$', prefix, re.I))
            if (conditional_membership or conditional_personal_date.search(clause)) and not _CAUSAL.search(clause):
                continue
            raise ValueError('invented_delivery_class_membership')
        previous_dated_class = current_dated_class


def _check_personal_current_window(answer, status, normalizer):
    """Do not apply a date-dependent current window to an undated personal unit.

    ``status`` has just been rebound by delivery_exception_status. This finite
    English predicate check does not establish general semantic entailment.
    """
    if not status or status.get('input_origin') != 'missing':
        return
    current = status.get('standard_window_calendar_days')
    if type(current) is not int or current == status.get('window_calendar_days'):
        return
    boundary = _date(status.get('delivery_before'))
    if boundary is None:
        raise ValueError('unbound_delivery_exception')
    dates = [boundary.isoformat(), f'{boundary.day} {boundary:%B %Y}',
             f'{boundary.day:02d} {boundary:%B %Y}', f'{boundary.day} {boundary:%b %Y}']
    date_reference = (r'(?:' + '|'.join(re.escape(value.casefold()) for value in dates) +
                      r'|(?:this|that|the)\s+(?:date|cut[ -]?off)|(?:the\s+)?cut[ -]?off)')
    unit = r'(?:purchase|order|item|product|unit)'
    personal_unit = r'(?:your|this)\s+(?:[A-Za-z0-9_-]+\s+){0,6}' + unit
    # A category or named model is not necessarily an individual delivered unit.
    personal = re.compile(
        r'\b(?:the\s+(?:item|product|unit)|it)\s+(?:can|may|must)\s+be\s+returned\b|'
        r'\byour\s+return\s+(?:deadline|window|period|duration)\b|'
        r'\bfor\s+' + personal_unit + r'\s*[,;]\s*(?:the\s+)?(?:return\s+)?(?:deadline|window|period|duration)\b|'
        r'\b(?:deadline|window|period|duration|time)\b[^.;]{0,90}\b' + personal_unit + r'\b|'
        r'\b' + personal_unit + r'\b[^.;]{0,90}\b(?:return\w*|deadline|window)\b|'
        r'\byou\s+(?:have|get|receive|can|may|must)\b', re.I)
    subject = (r'(?:(?:your|the|this)\s+(?!(?:other|another|different)\b)(?:[A-Za-z0-9_-]+\s+){0,6}' + unit +
               r'|it|you|items?|orders?|products?)')
    auxiliaries = r'(?:(?:was|were|is|are|has\s+been|have\s+been)\s+)?'
    conditional_delivery = re.compile(
        r'(?:\b(?:if|provided|assuming|when|whether)\s+(?:' + subject + r'\s+)?' + auxiliaries +
        r'|\bfor\s+(?:items?|orders?|products?)\s+)'
        r'(?:delivered|received|got)\s+(?:(?:it|the\s+(?:item|order|product))\s+)?'
        r'(?P<comparison>on\s+or\s+after|after|since|from)\s+' + date_reference + r'\b', re.I)
    for original in re.findall(r'[^.!?;\u0964\n]+[.!?;\u0964\n]?', answer):
        clause = normalizer(original.casefold().replace(',', ';'))
        if not _mentions_days(clause, current, normalizer):
            continue
        if not re.search(r'\b(?:return\w*|deadline|window)\b', clause, re.I):
            continue
        matches = list(personal.finditer(clause))
        if not matches:
            continue
        if re.match(r'^\s*(?:is|are|can|could|does|do|would|will|what|which|when|whether)\b', clause) and '?' in original:
            continue
        for match in matches:
            if _uncertain_predicate(clause, match.start()):
                continue
            tail = re.split(r';|\b(?:and|but|however|yet|then)\b', clause[match.end():], maxsplit=1)[0]
            personal_claim = clause[match.start():match.end()] + tail
            if not _mentions_days(personal_claim, current, normalizer):
                continue
            qualified = False
            if not re.search(r'\b(?:regardless|irrespective|whatever)\b', personal_claim):
                for condition in conditional_delivery.finditer(clause):
                    if condition.end() <= match.start():
                        gap = clause[condition.end():match.start()]
                        # A condition must directly introduce this predicate,
                        # not a preceding general rule or coordinated claim.
                        qualified = bool(re.fullmatch(r'\s*;?\s*(?:then\s+)?(?:the\s+)?', gap))
                    elif condition.start() >= match.end():
                        gap = clause[match.end():condition.start()]
                        qualified = (not re.search(r';|\b(?:and|but|however|yet|then|regardless|irrespective)\b', gap)
                                     and _mentions_days(gap, current, normalizer))
                    if qualified:
                        break
            if not qualified:
                raise ValueError('unsupported_delivery_exception_personal_window')


def check_placement_exception_answer(answer, facts, sources, *, normalizer=_numeric_text, query=None):
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
    _check_deictic_delivery_membership(answer, delivery, normalizer)
    for clause in re.split(r'[.!?;\u0964\n]+', answer):
        if delivery is not None and inputs['delivery'] is None:
            for asserted in _delivery_date_property_assertions(clause, facts, sources):
                if not _conditional(clause, asserted.start()) and not _uncertain_predicate(clause, asserted.start()):
                    raise ValueError('invented_delivery_premise')
        conditional_dates = {}
        for kind, pattern in (('placement', _PLACED_ASSERTION), ('delivery', _DELIVERED_ASSERTION)):
            assertions = list(pattern.finditer(clause))
            conditional_dates[kind] = any(_conditional(clause, match.start()) for match in assertions) or _implicit_date_condition(clause, kind)
            for asserted in assertions:
                if inputs[kind] is None and not _conditional(clause, asserted.start()):
                    if kind == 'placement' and _unless_placement_hypothesis(clause, asserted.start()):
                        continue
                    if not (_uncertain_predicate(clause, asserted.start())
                            or _requested_date_predicate(clause, asserted.start())):
                        raise ValueError('invented_' + kind + '_premise')
        for entitlement in _ENTITLEMENT.finditer(clause):
            if _uncertain_predicate(clause, entitlement.start()):
                continue
            local = clause[max(0, entitlement.start() - 15):entitlement.end() + 15]
            if _NEGATED.search(local):
                continue
            # A preceding uncertain amount is not this predicate's duration.
            claim = re.split(r'[,;]|\b(?:and|but|however|yet|then)\b', clause[entitlement.start():], flags=re.I)[0]
            for kind, status in (('placement', placement), ('delivery', delivery)):
                if not status or status['applicability'] == 'met' or conditional_dates[kind]:
                    continue
                if (status['window_calendar_days'] != status['standard_window_calendar_days']
                        and _mentions_days(claim, status['window_calendar_days'], normalizer)):
                    raise ValueError('unsupported_' + kind + '_exception_entitlement')
    _check_personal_current_window(answer, delivery, normalizer)
    check_unknown_placement_window(answer, placement, sources,
        category=policy.get('category'), normalizer=normalizer, query=query)
