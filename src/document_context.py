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
PUBLIC_FIELDS = frozenset({'sku', 'category', 'placed_on', 'delivered_on'})
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


def _return_calculation(order, public, catalog, sources):
    policy = sources.get('RET-2')
    delivered = _date(order.get('delivered_on') or public.get('delivered_on'))
    if not policy or not delivered:
        return []
    categories = {row.get('return_category') for row in catalog if row.get('return_category')}
    if public.get('category'):
        categories.add(public['category'])
    categories.update(item.get('return_category') for item in order.get('items', []) if item.get('return_category'))
    if len(categories) != 1:
        return []
    category = next(iter(categories))
    matching = [(cells[0], int(span[1])) for cells in _rows(policy) if len(cells) == 3
                and cells[2] == category and (span := re.fullmatch(r'(\d+) days', cells[1], re.I))]
    if len(matching) != 1:
        return []
    label, days = matching[0]
    ids = ['RET-2']
    placed = _date(order.get('placed_at') or public.get('placed_on'))
    if category == 'electronics' and 'RET-3' in sources:
        historical = re.search(r'delivered before\s+(\d{1,2} \w+ \d{4}).*?earlier\s+(\d+)[- ]day', _text(sources['RET-3']), re.I | re.S)
        if historical and (boundary := _word_date(historical[1])):
            ids.append('RET-3')
            if delivered < boundary:
                days = int(historical[2])
    if category == 'fashion' and 'RET-8' in sources:
        festive = re.search(r'placed between\s+(\d{1,2} \w+)\s+and\s+(\d{1,2} \w+ \d{4}).*?within\s+(\d+)\s+days', _text(sources['RET-8']), re.I | re.S)
        if festive:
            end = _word_date(festive[2])
            begin = _word_date(festive[1] + ' ' + festive[2][-4:])
            # Without the placement date, which window applies is unresolved.
            if not placed or not begin or not end:
                return []
            ids.append('RET-8')
            if begin <= placed <= end:
                days = int(festive[3])
    return [{'operation': 'return_calendar_deadline', 'source_ids': ids,
             'inputs': {'category': category, 'category_label': label,
                        'delivery_date': delivered.isoformat(),
                        'placement_date': placed.isoformat() if placed else None,
                        'calendar_days': days},
             'result': {'deadline': (delivered + timedelta(days=days)).isoformat()}}]


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
    context['calculations'].extend(_return_calculation(order, public, catalog, source_map))
    service_facts, service_calculations = _public_serviceability(query, source_map, data)
    context.update(service_facts)
    context['calculations'].extend(service_calculations)
    # Hashes make the parsed numeric inputs auditable against retrieved bytes.
    used = {sid for calculation in context['calculations'] for sid in calculation['source_ids'] if sid in source_map}
    if used:
        context['calculation_source_sha256'] = {
            sid: hashlib.sha256(source_map[sid]['text'].encode('utf-8')).hexdigest()
            for sid in sorted(used)}
    context['date_labels'] = _date_labels(context)
    return context
