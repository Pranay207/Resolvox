"""Minimal source-derived facts for document-first answer generation.

This module never chooses customer-facing policy wording. Numeric policy inputs
are parsed from the supplied retrieval results; absent or ambiguous evidence
produces no calculation. The caller must pass orders only after verification.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import re

from .config import REFERENCE_DATE
from .warranty_durations import warranty_duration_context, warranty_duration_constraints
from .source_semantics import derive_source_constraints
from .return_conditions import return_condition_context

# Record fields, not policy thresholds. Explicit allowlists also filter nested
# items: organizer records contain identities that must not enter model context.
ORDER_FIELDS = frozenset({
    'status', 'placed_at', 'promised_date', 'shipped_on', 'delivered_on',
    'payment_method', 'delivery_type', 'delivery_attempts', 'is_plus',
    'total_inr', 'subtotal_inr', 'coupon_code', 'coupon_discount_inr',
    'coupon_min_order_inr', 'delivery_fee_inr', 'cod_fee_inr',
    'contacts_last_7_days', 'return_sku', 'return_line_no', 'return_qty',
    'return_reason', 'return_status', 'return_requested_on', 'return_pickup_on',
    'return_qc_passed_on', 'return_refund_initiated_on', 'return_refund_method',
    'return_refund_amount_inr', 'return_refund_completed_on', 'return_rrn',
    'return_reverse_pickup_fee_inr', 'cancellation_refund_initiated_on',
    'cancellation_refund_method', 'cancellation_refund_amount_inr',
    'cancellation_rrn', 'rto_refund_initiated_on', 'rto_refund_method',
    'rto_refund_amount_inr', 'rto_rrn', 'damage_sku', 'damage_issue',
    'damage_reported_at', 'damage_hours_after_delivery',
    'damage_photos_attached', 'damage_status', 'express_late_credit_inr',
    'express_late_credit_on',
})
ITEM_FIELDS = frozenset({'line_no', 'sku', 'title', 'return_category', 'qty', 'unit_price_inr'})
CATALOG_FIELDS = frozenset({'sku', 'title', 'brand', 'return_category', 'price_inr', 'fulfilled_by', 'assured', 'warranty_months', 'description'})
PUBLIC_FIELDS = frozenset({'sku', 'category', 'placed_on', 'delivered_on', 'payment_method'})
DAY_NAMES = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')


def _record(record, fields):
    return {key: value for key, value in record.items()
            if key in fields and isinstance(value, (str, int, float, bool, type(None)))}


def _date(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except (ValueError, TypeError):
        return None


def _word_date(value):
    from datetime import datetime
    for pattern in ('%d %B %Y', '%d %b %Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            continue
    return None


def _text(source):
    return re.sub(r'[*`]', '', source.get('text', ''))


def _rows(source):
    for line in _text(source).splitlines():
        if line.lstrip().startswith('|'):
            yield [cell.strip() for cell in line.strip().strip('|').split('|')]


def _calendar(sources, data):
    rule = sources.get('KB-00.3')
    if not rule:
        return None
    # Parse the actual weekday interval instead of imposing a calendar in code.
    names = '|'.join(DAY_NAMES)
    match = re.search(r'\b(' + names + r')\s+(?:to|through)\s+(' + names + r')\b', _text(rule), re.I)
    if not match:
        return None
    first, last = [DAY_NAMES.index(value.lower()) for value in match.groups()]
    weekdays = {(first + offset) % len(DAY_NAMES)
                for offset in range((last - first) % len(DAY_NAMES) + 1)}
    # data is the public catalog/calendar reader, never the private CSV reader.
    holidays = {parsed for value in getattr(data, 'holidays', ()) if (parsed := _date(value))}
    return weekdays, holidays


def _business_add(start, days, calendar):
    weekdays, holidays = calendar
    current, counted = start, 0
    while counted < days:
        current += timedelta(days=1)
        if current.weekday() in weekdays and current not in holidays:
            counted += 1
    return current


def _business_elapsed(start, end, calendar):
    weekdays, holidays = calendar
    current, counted = start, 0
    while current < end:
        current += timedelta(days=1)
        counted += current.weekday() in weekdays and current not in holidays
    return counted


def _payment(value):
    value = re.sub(r'[_-]', ' ', str(value or '').lower())
    if 'neft' in value or ('bank' in value and 'cod' in value):
        return 'cod_bank'
    if 'wallet' in value and ('cod' in value or 'cash' in value):
        return 'cod_wallet'
    if 'upi' in value:
        return 'upi'
    if 'card' in value:
        return 'card'
    if 'net' in value and 'bank' in value:
        return 'netbanking'
    if 'wallet' in value:
        return 'wallet'
    return None


def _refund_calculations(order, sources, data, today):
    policy = sources.get('REF-2')
    calendar = _calendar(sources, data)
    if not policy or not calendar:
        return []
    bounds = {}
    for cells in _rows(policy):
        if len(cells) != 2:
            continue
        key = _payment(cells[0])
        span = re.search(r'\b(\d+)\s+(?:to|-)\s+(\d+)\s+business days\b', cells[1], re.I)
        if key and span and int(span[1]) <= int(span[2]):
            bounds.setdefault(key, []).append((int(span[1]), int(span[2])))
    results = []
    for event in ('return', 'cancellation', 'rto'):
        field = event + '_refund_initiated_on'
        started = _date(order.get(field))
        method = order.get(event + '_refund_method') or order.get('payment_method')
        values = set(bounds.get(_payment(method), ()))
        if not started or len(values) != 1:
            continue
        lower, upper = values.pop()
        inputs = {'initiated_on': started.isoformat(), 'payment_method': method,
                  'minimum_business_days': lower, 'maximum_business_days': upper,
                  'reference_date': today.isoformat(),
                  'holidays': sorted(day.isoformat() for day in calendar[1]),
                  'business_weekdays': sorted(calendar[0])}
        results.append({'operation': 'refund_business_date_range',
                        'source_ids': ['REF-2', 'KB-00.3', 'data/holidays.csv'],
                        'record_field': field, 'inputs': inputs,
                        'result': {'earliest_date': _business_add(started, lower, calendar).isoformat(),
                                   'latest_date': _business_add(started, upper, calendar).isoformat(),
                                   'elapsed_business_days': _business_elapsed(started, today, calendar)}})
    return results


def _public_refund_claim(query):
    """Extract a minimal customer claim, never a verified transaction record."""
    # Require one explicit dated initiation claim. Do not infer a missing year,
    # choose between competing dates/methods, or retain the customer's raw text.
    refund = r'\brefund\b|\u0930\u093f\u092b\u093c?\u0902\u0921'
    initiated = r'\b(?:initiated|started|began|begun)\b|\bshuru\s+(?:hua|hui|ho\s+gaya|ho\s+gayi)\b|\u0936\u0941\u0930\u0942\s+(?:\u0939\u0941\u0906|\u0939\u0941\u0908|\u0939\u094b\s+\u0917\u092f\u093e|\u0939\u094b\s+\u0917\u0908)'
    negated = r"\b(?:not|never|hasn['\u2019]?t|wasn['\u2019]?t|nahi|nahin)\b|\u0928\u0939\u0940\u0902?"
    dates = set()
    for match in re.finditer(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)', query):
        value = _date(match[0])
        if value:
            dates.add(value)
    months = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        '\u091c\u0928\u0935\u0930\u0940': 1,
        '\u092b\u093c\u0930\u0935\u0930\u0940': 2,
        '\u092b\u0930\u0935\u0930\u0940': 2,
        '\u092e\u093e\u0930\u094d\u091a': 3,
        '\u0905\u092a\u094d\u0930\u0948\u0932': 4,
        '\u092e\u0908': 5, '\u091c\u0942\u0928': 6,
        '\u091c\u0941\u0932\u093e\u0908': 7,
        '\u0905\u0917\u0938\u094d\u0924': 8,
        '\u0938\u093f\u0924\u0902\u092c\u0930': 9,
        '\u0905\u0915\u094d\u091f\u0942\u092c\u0930': 10,
        '\u0928\u0935\u0902\u092c\u0930': 11,
        '\u0926\u093f\u0938\u0902\u092c\u0930': 12,
    }
    named_date = r'(?<!\d)(\d{1,2})(?:st|nd|rd|th)?\s+(' + '|'.join(map(re.escape, months)) + r')\s+(\d{4})(?!\d)'
    for match in re.finditer(named_date, query, re.I):
        try:
            dates.add(date(int(match[3]), months[match[2].casefold()], int(match[1])))
        except ValueError:
            pass
    if len(dates) != 1:
        return None
    # The dated clause must itself discuss refund initiation, rather than a
    # delivery date in one sentence and an undated refund in another sentence.
    dated_claim = False
    for clause in re.split(r'[.!?;\n]+', query):
        if not re.search(refund, clause, re.I):
            continue
        date_in_clause = re.search(named_date, clause, re.I) or re.search(r'\d{4}-\d{2}-\d{2}', clause)
        if not date_in_clause:
            continue
        for match in re.finditer(initiated, clause, re.I):
            if not re.search(negated, clause[max(0, match.start()-35):match.end()+20], re.I):
                dated_claim = True
    if not dated_claim:
        return None
    patterns = {
        'upi': r'\bupi\b|\u092f\u0942\u092a\u0940\u0906\u0908',
        'card': r'\bcards?\b|\u0915\u093e\u0930\u094d\u0921',
        'netbanking': r'\bnet\s*bank(?:ing)?\b|\u0928\u0947\u091f\s*\u092c\u0948\u0902\u0915(?:\u093f\u0902\u0917)?',
        'wallet': r'\bwallet\b|\u0935\u0949\u0932\u0947\u091f',
        'cod_bank': r'\bneft\b|\bbank\s+transfer\b',
    }
    methods = {method for method, pattern in patterns.items() if re.search(pattern, query, re.I)}
    if len(methods) != 1:
        return None
    method = methods.pop()
    if method == 'wallet' and re.search(r'\bcod\b|cash[ -]on[ -]delivery', query, re.I):
        method = 'cod_wallet'
    return {'initiated_on': dates.pop().isoformat(), 'payment_method': method,
            'verified': False, 'origin': 'customer_provided',
            'transaction_status_confirmed': False}


def _public_refund_calculations(query, sources, data, today):
    claim = _public_refund_claim(query)
    if not claim:
        return None, []
    # Reuse the same generic source-parsed arithmetic as verified records,
    # while retaining the distinct unverified origin in every derived result.
    inputs = {'return_refund_initiated_on': claim['initiated_on'],
              'return_refund_method': claim['payment_method']}
    calculations = _refund_calculations(inputs, sources, data, today)
    for calculation in calculations:
        calculation['record_field'] = 'customer_provided_refund_claim.initiated_on'
        calculation['input_status'] = 'customer_provided_unverified'
        calculation['inputs']['customer_statement_verified'] = False
        # Public claims project a future range; elapsed time as of the dataset
        # reference date is unrelated and easily confused with range length.
        # Verified records retain their separately scoped elapsed-day facts.
        calculation['result'].pop('elapsed_business_days', None)
    return claim, calculations


def _selected_return_policy(order, public, catalog, sources):
    """Select a numeric source row, preserving unresolved date exceptions."""
    categories = {row.get('return_category') for row in catalog if row.get('return_category')}
    if public.get('category'):
        categories.add(public['category'])
    categories.update(item.get('return_category') for item in order.get('items', []) if item.get('return_category'))
    if len(categories) != 1:
        return None
    category = next(iter(categories))
    matching = [(cells[0], int(span[1])) for cells in _rows(sources.get('RET-2', {}))
                if len(cells) == 3 and cells[2] == category
                and (span := re.fullmatch(r'(\d+) days', cells[1], re.I))]
    selected = None
    if len(matching) == 1:
        label, days = matching[0]
        selected = {'category': category, 'category_label': label,
                    'window_calendar_days': days, 'source_ids': ['RET-2'],
                    'selection': 'standard_window'}
    delivered = _date(order.get('delivered_on') or public.get('delivered_on'))
    placed = _date(order.get('placed_at') or public.get('placed_on'))
    if category == 'electronics' and 'RET-3' in sources:
        historical = re.search(r'delivered before\s+(\d{1,2} \w+ \d{4}).*?earlier\s+(\d+)[- ]day', _text(sources['RET-3']), re.I | re.S)
        if historical and (boundary := _word_date(historical[1])):
            if delivered and delivered < boundary:
                selected = {'category': category,
                            'window_calendar_days': int(historical[2]),
                            'source_ids': ['RET-3'], 'selection': 'historical_window',
                            'delivery_before': boundary.isoformat()}
            elif selected:
                selected['historical_exception'] = {
                    'delivery_before': boundary.isoformat(),
                    'window_calendar_days': int(historical[2]), 'source_ids': ['RET-3']}
    if selected and category == 'fashion' and 'RET-8' in sources:
        festive = re.search(r'placed between\s+(\d{1,2} \w+)\s+and\s+(\d{1,2} \w+ \d{4}).*?within\s+(\d+)\s+days', _text(sources['RET-8']), re.I | re.S)
        if festive:
            end = _word_date(festive[2])
            begin = _word_date(festive[1] + ' ' + festive[2][-4:])
            if begin and end:
                selected['placement_exception'] = {
                    'placed_from': begin.isoformat(), 'placed_through': end.isoformat(),
                    'window_calendar_days': int(festive[3]), 'source_ids': ['RET-8']}
                if placed and begin <= placed <= end:
                    selected['window_calendar_days'] = int(festive[3])
                    selected['source_ids'] = ['RET-8']
                    selected['selection'] = 'placement_exception_window'
                elif not placed:
                    selected['placement_date_unavailable'] = True
    return selected


def _return_calculation(order, public, catalog, sources):
    selected = _selected_return_policy(order, public, catalog, sources)
    delivered = _date(order.get('delivered_on') or public.get('delivered_on'))
    if not selected or not delivered or selected.get('placement_date_unavailable'):
        return []
    placed = _date(order.get('placed_at') or public.get('placed_on'))
    days = selected['window_calendar_days']
    return [{'operation': 'return_calendar_deadline', 'source_ids': selected['source_ids'],
             'inputs': {'category': selected['category'],
                        'category_label': selected.get('category_label', selected['category']),
                        'delivery_date': delivered.isoformat(),
                        'placement_date': placed.isoformat() if placed else None,
                        'calendar_days': days},
             'result': {'deadline': (delivered + timedelta(days=days)).isoformat()}}]


def _source_delivery_policy(sources):
    source = sources.get('DEL-3')
    if not source:
        return None
    values = {int(match[1]) for match in re.finditer(r'\bup\s+to\s+(\d+)\s+(?:delivery\s+)?attempts?\b', _text(source), re.I)}
    if len(values) != 1:
        return None
    return {'delivery_attempt_limit': values.pop(), 'source_ids': ['DEL-3']}


def _answer_constraints(query, context, sources):
    """Require only question-relevant, host-derived numeric facts, never prose."""
    constraints = []
    return_topic = bool(re.search(r'\breturn\w*\b|\bsend.{0,15}back\b|\b(?:wapas|vaapas|lauta\w*)\b|\u0930\u093f\u091f\u0930\u094d\u0928|\u0932\u094c\u091f\u093e|\u0935\u093e\u092a\u0938', query, re.I))
    duration = bool(re.search(r'\b(?:window|period|days?|deadline|duration)\b|\bhow\s+long\b|\bhow\s+much\s+time\b|\bkitn[aei]\w*.{0,12}\bdin\b|\u0926\u093f\u0928|\u0905\u0935\u0927\u093f', query, re.I))
    refund_topic = bool(re.search(r'\brefund\b|\u0930\u093f\u092b\u093c?\u0902\u0921', query, re.I))
    explicit_return_window = bool(re.search(r'\breturn\s+(?:window|period|deadline|duration)\b', query, re.I))
    selected = context.get('return_policy')
    if selected and return_topic and duration and (not refund_topic or explicit_return_window):
        constraints.append({'kind': 'quantity', 'value': selected['window_calendar_days'],
                            'unit': 'calendar_day', 'key': 'return_policy.window_calendar_days',
                            'source_ids': selected['source_ids']})
    by_when = bool(re.search(r'\bby\s+(?:(?:which|what)\s+(?:date|day)|when)\b|\blatest(?:\s+(?:refund|arrival|expected))?\s+date\b|\bwhen\b.{0,50}\b(?:arriv\w*|reach\w*|receiv\w*|get|have|expect\w*|show|credit\w*)\b|\bkab\s+tak\b|\u0915\u092c\s*\u0924\u0915|\u0915\u093f\u0938\s+\u0924\u093e\u0930\u0940\u0916', query, re.I))
    calculations = [(index, row) for index, row in enumerate(context.get('calculations', []))
                    if row.get('operation') == 'refund_business_date_range'
                    and row.get('result', {}).get('latest_date')]
    if refund_topic and by_when and len(calculations) == 1:
        index, calculation = calculations[0]
        ids = [sid for sid in calculation['source_ids'] if sid in sources]
        if ids:
            constraints.append({'kind': 'date', 'value': calculation['result']['latest_date'],
                                'key': 'refund.latest_date', 'source_ids': ids,
                                'calculation_index': index})
    attempts_topic = bool(re.search(r'\battempts?\b|\b(?:not\s+(?:at\s+)?home|courier\s+comes|miss(?:ed)?\s+(?:the\s+)?delivery)\b|\bghar.{0,15}nahi\b|\u0918\u0930.{0,15}\u0928\u0939\u0940|\u0921\u093f\u0932\u0940\u0935\u0930\u0940.{0,15}\u092a\u094d\u0930\u092f\u093e\u0938', query, re.I))
    delivery = context.get('delivery_policy')
    if delivery and attempts_topic:
        constraints.append({'kind': 'number', 'value': delivery['delivery_attempt_limit'],
                            'key': 'delivery_policy.delivery_attempt_limit',
                            'source_ids': delivery['source_ids']})
    return constraints


def _boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {'true', 'false'}:
        return value.lower() == 'true'
    return None


def _amount(value):
    try:
        number = Decimal(value.replace(',', ''))
        return int(number) if number == number.to_integral_value() else float(number)
    except (ValueError, TypeError, ArithmeticError):
        return None


def _public_serviceability(query, sources, data):
    """Return explicit public location facts, never authentication evidence."""
    want_cod = bool(re.search(r'\bcod\b|cash[ -]on[ -]delivery|cash.{0,15}(?:door|deliver)|\u0915\u0948\u0936|\u0928\u0915\u0926', query, re.I))
    want_express = bool(re.search(r'\bexpress\b|\u090f\u0915\u094d\u0938\u092a\u094d\u0930\u0947\u0938', query, re.I))
    service_request = want_cod or want_express or bool(re.search(r'\b(?:deliver(?:y)?|serviceable|serviceability|prepaid)\b|\u0921\u093f\u0932\u0940\u0935\u0930\u0940|\u092a\u0939\u0941\u0901\u091a', query, re.I))
    explicit_pins = set(re.findall(r'(?:pin\s*code|postal\s*code|\u092a\u093f\u0928\u0915\u094b\u0921)\s*(?:(?:is|at|of)\s*|[:=]\s*)?(\d{6})(?!\d)', query, re.I))
    candidates = set(re.findall(r'(?<!\d)\d{6}(?!\d)', query))
    # Six-digit currency amounts are not locations. A source-bound match may
    # resolve an omitted postal label; unlisted codes require an explicit label.
    source_pins = {sid.split(':', 1)[1] for sid in sources if sid.startswith('pincodes.csv:')}
    pins = explicit_pins or (candidates & source_pins)
    if not service_request or len(pins) != 1:
        return {}, []
    pin = pins.pop()
    sid = 'pincodes.csv:' + pin
    source = sources.get(sid)
    if not source:
        registry = getattr(data, 'pincodes', None)
        return ({'pincode_listed': False} if registry is not None and pin not in registry else {}), []
    try:
        row = json.loads(source['text'])
    except (ValueError, TypeError):
        return {}, []
    if not isinstance(row, dict) or str(row.get('pincode')) != pin:
        return {}, []
    serviceable = _boolean(row.get('serviceable'))
    if serviceable is None:
        return {}, []
    facts = {'pincode_listed': True, 'serviceable': serviceable}
    cod_flag = _boolean(row.get('cod_available'))
    express_flag = _boolean(row.get('express_available'))
    if want_cod and cod_flag is not None:
        facts['cod_available'] = serviceable and cod_flag
    if want_express and express_flag is not None:
        facts['express_available'] = serviceable and express_flag
    # An amount is used only when explicitly monetary and unambiguous; the
    # public pincode must never be mistaken for a basket price.
    amount_query = re.sub(r'(?<!\d)' + re.escape(pin) + r'(?!\d)', '', query)
    money = r'(\d[\d,]*(?:\.\d+)?)'
    amounts = []
    for pattern in (r'(?:\u20b9|\b(?:rs\.?|inr))\s*' + money,
                    money + r'\s*(?:rupees?|\u0930\u0941\u092a\u092f\u0947)\b',
                    r'\b(?:amount|worth|basket|priced?)(?:\s+(?:of|at|is))?\s*' + money):
        amounts.extend(_amount(match[1]) for match in re.finditer(pattern, amount_query, re.I))
    amounts = set(value for value in amounts if value is not None and value >= 0)
    calculation = []
    policy = sources.get('PAY-2')
    if want_cod and 'cod_available' in facts and policy and len(amounts) == 1:
        caps = re.findall(r'orders?\s+up\s+to\s*(?:\u20b9|rs\.?|inr)?\s*' + money, _text(policy), re.I)
        maximums = {_amount(value) for value in caps}
        maximums.discard(None)
        if len(maximums) == 1:
            amount = amounts.pop()
            maximum = maximums.pop()
            eligible = facts['cod_available'] and amount <= maximum
            facts['cod_eligible'] = eligible
            calculation.append({'operation': 'cod_amount_eligibility',
                                'source_ids': [sid, 'PAY-2'],
                                'inputs': {'order_amount_inr': amount,
                                           'maximum_order_inr': maximum,
                                           'serviceable': serviceable,
                                           'cod_available': facts['cod_available']},
                                'result': {'cod_eligible': eligible}})
    facts['public_serviceability'] = {
        'source_ids': [sid],
        'record': _record(row, {'city', 'state', 'pincode', 'metro', 'serviceable', 'cod_available', 'express_available'}),
    }
    return facts, calculation


def _date_labels(value):
    """Equivalent date spellings, derived only from already included facts."""
    labels = {}
    if isinstance(value, dict):
        for item in value.values():
            labels.update(_date_labels(item))
    elif isinstance(value, list):
        for item in value:
            labels.update(_date_labels(item))
    elif isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}(?:$|T)", value):
        parsed = _date(value)
        if parsed:
            labels[parsed.isoformat()] = f"{parsed.day} {parsed:%B %Y}"
    return labels


def _return_application_facet(query):
    """Recognize a requested return boundary/application, not generic time.

    This finite language check does not infer an answer or pick a category.
    A nearby returned item does not make money-processing time a return window.
    """
    # An overview of categories/conditions needs no individual table row.
    if re.search(
            r'\b(?:which|what)\s+(?:product\s+)?(?:categor\w*|items?|kinds?|types?)\b|'
            r'\b(?:kaun\s*si|kaunsi|kaunse)\b.{0,24}\b(?:categor\w*|items?|products?)\b|'
            r'\u0915\u094c\u0928.{0,16}(?:\u0936\u094d\u0930\u0947\u0923|\u0909\u0924\u094d\u092a\u093e\u0926|\u0935\u0938\u094d\u0924\u0941)', query, re.I):
        return False
    action = (r'(?:\breturn\w*\b|\bsend\w*\b.{0,20}\bback\b|\b(?:wapas|vaapas|lauta\w*)\b|'
              r'\u0930\u093f\u091f\u0930\u094d\u0928|\u0935\u093e\u092a\u0938|\u0932\u094c\u091f\u093e)')
    boundary = (r'(?:\b(?:window|deadline|cutoff|eligib\w*|returnability)\b|'
                r'\b(?:allowed|eligible|returnable)\b|\b(?:aakhri|akhri|antim)\s+(?:din|date|tareekh)\b|'
                r'\u0938\u092e\u092f\u0938\u0940\u092e\u093e|\u0905\u0902\u0924\u093f\u092e\s*(?:\u0926\u093f\u0928|\u0924\u093e\u0930\u0940\u0916)|'
                r'\u092a\u093e\u0924\u094d\u0930|\u092f\u094b\u0917\u094d\u092f)')
    explicit = (r'\b(?:return\s+(?:period|duration)|(?:period|duration)\s+(?:for|of)\s+(?:a\s+)?return)\b|'
                r'\u0930\u093f\u091f\u0930\u094d\u0928\s*(?:\u0905\u0935\u0927\u093f|\u0915\u093e\s*\u0938\u092e\u092f)|'
                r'\u0932\u094c\u091f\u093e\u0928\u0947\s*\u0915\u0940\s*\u0905\u0935\u0927\u093f')
    question_time = (r'(?:\b(?:how\s+long|how\s+many\s+days|by\s+when|until\s+when|kab\s+tak|kitn\w*\s+din)\b|'
                     r'\u0915\u092c\s*\u0924\u0915|\u0915\u093f\u0924\u0928\u0947\s*\u0926\u093f\u0928|\u0915\u093f\u0924\u0928\u093e\s*\u0938\u092e\u092f)')
    permission = (r'\b(?:can|may|could)\s+(?:i|we)\b|\b(?:am\s+i|are\s+we)\s+(?:still\s+)?allowed\b|'
                  r'\b(?:do\s+i|do\s+we)\s+have\b|\b(?:kar|bhej|lauta)\w*\s+(?:sakt\w*|sakte|sakti)\b|'
                  r'\u0915\u0930\s*\u0938\u0915|\u092d\u0947\u091c\s*\u0938\u0915|\u0932\u094c\u091f\u093e\s*\u0938\u0915')
    # Clause boundaries keep a refund deadline in another sentence from
    # becoming an obligation to apply the return-category table.
    for clause in re.split(r'[.!?;\u0964\n]|\b(?:and|but|aur)\b|\u0914\u0930', query, flags=re.I):
        if not re.search(action, clause, re.I):
            continue
        if re.search(explicit, clause, re.I) or re.search(boundary, clause, re.I):
            return True
        if re.search(permission, clause, re.I):
            return True
        # A personal return action with an explicit time boundary is an
        # application request. Generic 'when money is sent' is not this facet.
        if re.search(question_time, clause, re.I) and re.search(
                r'\b(?:to|for)\s+(?:a\s+)?(?:return|send\w*)\b|\b(?:karn[ae]|bhejn[ae]|lautane)\b|'
                r'\u0915\u0930\u0928[\u093e\u0947]|\u092d\u0947\u091c\u0928[\u093e\u0947]|\u0932\u094c\u091f\u093e\u0928[\u093e\u0947]', clause, re.I):
            return True
    return False


def _missing_application_inputs(query, sources, facts):
    by_id = {row['id']: row for row in sources if row.get('status', 'current') == 'current'
             and row.get('doc_type', 'policy') == 'policy' and row.get('id')}
    # Asking to compare/list the whole table does not require choosing one row.
    if re.search(
            r'\b(?:compare|all categories|each category|every category|all payment methods|each payment method)\b|'
            r'\u0924\u0941\u0932\u0928\u093e|'
            r'(?:\u0938\u092d\u0940|\u0939\u0930|\u092a\u094d\u0930\u0924\u094d\u092f\u0947\u0915).{0,30}'
            r'(?:\u0936\u094d\u0930\u0947\u0923|\u0915\u0948\u091f\u0947\u0917\u0930|\u092d\u0941\u0917\u0924\u093e\u0928|\u0924\u0930\u0940\u0915)|'
            r'\b(?:sabhi|saare|sare|sab|har)\b.{0,30}\b(?:categor\w*|payment|methods?|taree?ke?|tarike?|windows?)\b', query, re.I):
        return []
    return_topic = bool(re.search(r'\breturn\w*\b|send.{0,15}back|\b(?:wapas|vaapas|lauta\w*)\b|\u0932\u094c\u091f\u093e|\u0935\u093e\u092a\u0938|\u0930\u093f\u091f\u0930\u094d\u0928', query, re.I))
    refund_topic = bool(re.search(r'\brefund\b|\u0930\u093f\u092b\u093c?\u0902\u0921', query, re.I))
    duration = bool(re.search(r'\b(?:window|period|days?|duration|when|soon)\b|\bhow\s+long\b|\bkab\b|\bkitn\w*.{0,12}\bdin\b|\u0926\u093f\u0928|\u0915\u092c|\u0905\u0935\u0927\u093f', query, re.I))
    required = []
    if return_topic and _return_application_facet(query) and 'RET-2' in by_id:
        options = [{'return_category': cells[2], 'return_window': cells[1]}
                   for cells in _rows(by_id['RET-2']) if len(cells) == 3
                   and re.fullmatch(r'[a-z]+(?:_[a-z]+)*', cells[2])
                   and re.fullmatch(r'(?:\d+\s+(?:calendar\s+)?days?|not\s+returnable)', cells[1], re.I)]
        known = {facts.get('public_context', {}).get('category'), facts.get('return_policy', {}).get('category')}
        known.update(row.get('return_category') for row in facts.get('catalog', []) if isinstance(row, dict))
        known.update(row.get('return_category') for row in facts.get('verified_order', {}).get('items', []) if isinstance(row, dict))
        known.discard(None)
        allowed = {row['return_category'] for row in options}
        if len(options) > 1 and len(known & allowed) != 1:
            required.append({'key': 'return_category', 'source_ids': ['RET-2'],
                             'lookup_column': 'return_category', 'allowed_rows': options,
                             'reason': 'unresolved_policy_table_lookup'})
    # An initiation clock after pickup/QC is not a payment-method lookup.
    # Require a method only for arrival/timeline applications, leaving table
    # comparisons and source-wide initiation questions unforced.
    initiation = bool(re.search(r'\b(?:initiat\w*|start\w*|begin\w*|shuru)\b|\u0936\u0941\u0930\u0942|\u0906\u0930\u0902\u092d', query, re.I))
    receipt = bool(re.search(
        r'\b(?:receiv\w*|credit\w*|arriv\w*|reflect\w*|reach\w*|deposit\w*|get|latest|by\s+when|by\s+what\s+date|'
        r'mil\w*|aay\w*|aeg\w*|aayeg\w*|kab\s+tak)\b|'
        r'\u092e\u093f\u0932|\u0906\u090f|\u0906\u092f|\u091c\u092e\u093e|\u0915\u092c\s*\u0924\u0915|\u0915\u093f\u0938\s+\u0924\u093e\u0930\u0940\u0916', query, re.I))
    initiation_only = initiation and not receipt
    cod = bool(re.search(r'\bcod\b|cash[ -]on[ -]delivery', query, re.I))
    dated_application = initiation and receipt and bool(re.search(
        r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)|(?<!\d)\d{1,2}\s+[A-Za-z\u0900-\u097f]+\s+\d{4}(?!\d)', query))
    cod_overview = cod and not dated_application
    if refund_topic and duration and not initiation_only and not cod_overview and 'REF-2' in by_id:
        options = [{'payment_method': _payment(cells[0]), 'label': cells[0], 'timeline': cells[1]}
                   for cells in _rows(by_id['REF-2']) if len(cells) == 2 and _payment(cells[0])]
        if cod:
            options = [row for row in options if row['payment_method'].startswith('cod_')]
        order = facts.get('verified_order', {})
        known = {_payment(facts.get('customer_provided_refund_claim', {}).get('payment_method')),
                 _payment(facts.get('public_context', {}).get('payment_method'))}
        recorded = [order.get(prefix + '_refund_method') for prefix in ('return', 'cancellation', 'rto')]
        known.update(_payment(value) for value in recorded if value)
        if not any(recorded):
            known.add(_payment(order.get('payment_method')))
        for key, pattern in {
            'upi': r'\bupi\b|\u092f\u0942\u092a\u0940\u0906\u0908',
            'card': r'\bcard\b|\u0915\u093e\u0930\u094d\u0921',
            'netbanking': r'\bnet\s*bank(?:ing)?\b|\u0928\u0947\u091f\s*\u092c\u0948\u0902\u0915',
            'wallet': r'\bwallet\b|\u0935\u0949\u0932\u0947\u091f',
            'cod_bank': r'\bneft\b|\bbank\s+transfer\b',
        }.items():
            if re.search(pattern, query, re.I):
                if key == 'wallet' and re.search(r'\bcod\b|cash[ -]on[ -]delivery', query, re.I):
                    key = 'cod_wallet'
                known.add(key)
        known.discard(None)
        allowed = {row['payment_method'] for row in options}
        if len(options) > 1 and len(known & allowed) != 1:
            required.append({'key': 'payment_method', 'source_ids': ['REF-2'],
                             'lookup_column': 'payment_method', 'allowed_rows': options,
                             'reason': 'unresolved_policy_table_lookup'})
    return required


def build_context(query, sources, data, verified_order=None, public_context=None):
    """Build source facts, never a policy answer or predicted disposition.

    ``verified_order`` is accepted only at the caller's authenticated boundary;
    this function cannot authenticate an order. Sources are public chunk dicts.
    ``public_context`` carries explicit catalog/date slots from the conversation.
    Unknown fields and private nested fields are discarded, not redacted copies.
    """
    source_map = {source['id']: source for source in sources
                  if isinstance(source, dict) and isinstance(source.get('id'), str)
                  and isinstance(source.get('text'), str)
                  and source.get('status', 'current') == 'current'}
    public = _record(public_context or {}, PUBLIC_FIELDS)
    if 'payment_method' in public:
        normalized_method = _payment(public['payment_method'])
        if normalized_method:
            public['payment_method'] = normalized_method
        else:
            public.pop('payment_method')
    order = _record(verified_order or {}, ORDER_FIELDS)
    if verified_order:
        order['items'] = [_record(item, ITEM_FIELDS)
                          for item in verified_order.get('items', []) if isinstance(item, dict)]
    catalog = []
    for source in source_map.values():
        if source.get('file', '').replace('\\', '/').endswith('data/products.csv') or source['id'].startswith('products.csv:'):
            try:
                row = json.loads(source['text'])
            except (ValueError, TypeError):
                continue
            if isinstance(row, dict):
                safe = _record(row, CATALOG_FIELDS)
                if safe.get('sku'):
                    catalog.append(safe)
    # Verified item SKUs and explicit public slots can select catalog records;
    # they do not permit reading the private order/customer CSVs.
    skus = {item.get('sku') for item in order.get('items', [])}
    if public.get('sku'):
        skus.add(public['sku'])
    for sku in sorted(value for value in skus if isinstance(value, str)):
        if sku in getattr(data, 'products', {}) and not any(row['sku'] == sku for row in catalog):
            catalog.append(_record(data.products[sku], CATALOG_FIELDS))
    context = {'reference_date': REFERENCE_DATE.isoformat(), 'calculations': []}
    if order:
        context['verified_order'] = order
    if public:
        context['public_context'] = public
    if catalog:
        context['catalog'] = catalog
    context['calculations'].extend(_refund_calculations(order, source_map, data, REFERENCE_DATE))
    if not verified_order:
        claim, claim_calculations = _public_refund_calculations(query, source_map, data, REFERENCE_DATE)
        if claim:
            context['customer_provided_refund_claim'] = claim
            context['calculations'].extend(claim_calculations)
    selected_return = _selected_return_policy(order, public, catalog, source_map)
    if selected_return:
        context['return_policy'] = selected_return
    delivery_policy = _source_delivery_policy(source_map)
    if delivery_policy:
        context['delivery_policy'] = delivery_policy
    context['calculations'].extend(_return_calculation(order, public, catalog, source_map))
    service_facts, service_calculations = _public_serviceability(query, source_map, data)
    context.update(service_facts)
    context['calculations'].extend(service_calculations)
    context.update(return_condition_context(query, source_map, reference_date=REFERENCE_DATE.isoformat()))
    context.update(warranty_duration_context(query, source_map, reference_date=REFERENCE_DATE.isoformat(), sku=public.get('sku')))
    context['answer_constraints'] = _answer_constraints(query, context, source_map)
    context['answer_constraints'].extend(warranty_duration_constraints(context))
    source_semantic_constraints = derive_source_constraints(list(source_map.values()))
    if source_semantic_constraints:
        context['source_semantic_constraints'] = source_semantic_constraints
    required_inputs = _missing_application_inputs(query, list(source_map.values()), context)
    if required_inputs:
        context['required_application_inputs'] = required_inputs
    # Hashes make the parsed numeric inputs auditable against retrieved bytes.
    used = {sid for calculation in context['calculations'] for sid in calculation['source_ids'] if sid in source_map}
    for fact in (context.get('return_policy', {}), context.get('delivery_policy', {})):
        used.update(sid for sid in fact.get('source_ids', []) if sid in source_map)
    used.update(sid for sid in context.get('return_condition_policy', {}).get('source_ids', []) if sid in source_map)
    if used:
        context['calculation_source_sha256'] = {
            sid: hashlib.sha256(source_map[sid]['text'].encode('utf-8')).hexdigest()
            for sid in sorted(used)}
    context['date_labels'] = _date_labels(context)
    return context
