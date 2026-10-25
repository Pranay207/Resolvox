"""Finite source-derived warranty-duration facts, without authored answers.

Catalog scope and the source's warranty subject remain part of every quantity.
Absent or ambiguous evidence produces no duration obligation.
"""
from datetime import date
import hashlib
import json
import re

from .grounding import _quantities, _quantity_supported

_ASSURANCE = re.compile(
    r'Products\s+marked\s+assured\s*=\s*(?P<flag>true|false)\s+in\s+the\s+catalog\s+'
    r'carry\s+(?:a|an)\s+(?P<months>\d+)[- ]month\s+(?P<name>[^.!?\n]+?)\s+warranty\b', re.I)
_BRAND_LINK = re.compile(
    r'\bwarranty\s+(?:period|duration)\s+is\s+(?:listed|specified)\s+in\s+the\s+'
    r'warranty_months\s+column\s+of\s+the\s+product\s+catalog\b', re.I)
_BRAND = re.compile(r"\b(?:brand|manufacturer(?:'s)?)\s+warrant(?:y|ies)\b|"
                    r'(?:\u092c\u094d\u0930\u093e\u0902\u0921|\u0928\u093f\u0930\u094d\u092e\u093e\u0924\u093e)\s*(?:\u0915\u0940\s*)?\u0935\u093e\u0930\u0902\u091f\u0940|'
                    r'\b(?:brand|manufacturer)\s+ki\s+warranty\b', re.I)
_WARRANTY = re.compile(r'warrant(?:y|ies)|\u0935\u093e\u0930\u0902\u091f\u0940', re.I)
_DURATION = re.compile(r'\bduration\b|\bperiod\b|\bhow\s+long\b|\b(?:months?|years?)\b|'
                       r'\bkitn[aei]\w*\b|\u0915\u093f\u0924\u0928|\u0905\u0935\u0927\u093f|\u092e\u0939\u0940\u0928|\u0938\u093e\u0932', re.I)
_OFFERED = re.compile(r'\b(?:have|has|carry|carries|include[ds]?|offered|eligible|is\s+there|come[sd]?\s+with)\b', re.I)
_ROUTE_QUESTION = re.compile(r'\b(?:claim|file|raise|kaise|kahan)\b|\u0915\u094d\u0932\u0947\u092e|\u0926\u093e\u0935|\u0915\u0948\u0938\u0947|\u0915\u0939\u093e', re.I)
_COPULA_QUESTION = re.compile(r'\b(?:hai|hain|hota|hoti|milega|milti|milta)\b|\u0939\u0948|\u092e\u093f\u0932\u0924|\u0939\u094b\u0924', re.I)

_NEGATIVE = re.compile(r"\b(?:not|no|never|cannot|can't|nahi|nahin|maybe|perhaps|might|probably|unsure)\b|\u0928\u0939\u0940\u0902", re.I)


def _plain(text):
    return re.sub(r'[*`]', '', text)


def _active(source, reference, doc_type):
    if source.get('doc_type') != doc_type or source.get('status', 'current') != 'current':
        return False
    if not source.get('effective_from'):
        return True
    try:
        return date.fromisoformat(source['effective_from']) <= date.fromisoformat(reference)
    except (TypeError, ValueError):
        return False


def _boolean(value):
    if type(value) is bool:
        return value
    if isinstance(value, str) and value.casefold() in {'true', 'false'}:
        return value.casefold() == 'true'
    return None


def _positive_integer(value):
    if isinstance(value, str) and re.fullmatch(r'\d+', value):
        value = int(value)
    return value if type(value) is int and value > 0 else None


def _fingerprint(source):
    data = {key: source[key] for key in ('id','text','file','doc_type','status','effective_from','version') if key in source}
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _catalog(sources, reference, *, sku=None, query=''):
    rows = []
    for source in sources:
        if not _active(source, reference, 'catalog'):
            continue
        try:
            row = json.loads(source['text'])
        except (ValueError, TypeError):
            continue
        if isinstance(row, dict) and isinstance(row.get('sku'), str):
            rows.append((row, source))
    if sku is not None:
        rows = [(row, source) for row, source in rows if row['sku'] == sku]
    elif len(rows) > 1:
        rows = [(row, source) for row, source in rows if re.search(r'(?<!\w)' + re.escape(row['sku']) + r'(?!\w)', query, re.I)]
    return rows[0] if len(rows) == 1 else None


def _derived(sources, reference, *, sku=None, query=''):
    selected = _catalog(sources, reference, sku=sku, query=query)
    if not selected:
        return {}
    row, catalog_source = selected
    policy = [source for source in sources if _active(source, reference, 'policy')]
    records = {}
    candidates = []
    for source in policy:
        for match in _ASSURANCE.finditer(_plain(source['text'])):
            months = _positive_integer(match['months'])
            flag = _boolean(match['flag'])
            if months is not None and _boolean(row.get('assured')) is flag:
                candidates.append((months, match['name'].strip(), flag, source))
    variants = {(months, name, flag) for months, name, flag, source in candidates}
    if len(variants) == 1:
        months, name, flag = next(iter(variants))
        used = [catalog_source] + [source for _, _, _, source in candidates]
        records['assured'] = {'sku':row['sku'], 'benefit_name':name, 'duration_months':months,
                              'required_assured_flag':flag, 'catalog_assured_flag':_boolean(row.get('assured')),
                              'catalog_brand':row.get('brand',''),
                              'source_ids':sorted({source['id'] for source in used}),
                              'source_sha256':{source['id']:_fingerprint(source) for source in used}}
    brand_sources = [source for source in policy if _BRAND_LINK.search(_plain(source['text']))
                     and _BRAND.search(_plain(source['text']))]
    months = _positive_integer(row.get('warranty_months'))
    if months is not None and brand_sources:
        used = [catalog_source] + brand_sources
        records['brand'] = {'sku':row['sku'], 'brand':row.get('brand',''), 'duration_months':months,
                            'catalog_column':'warranty_months',
                            'source_ids':sorted({source['id'] for source in used}),
                            'source_sha256':{source['id']:_fingerprint(source) for source in used}}
    return records


def warranty_duration_context(query, sources, *, reference_date, sku=None):
    """Select relevant duration facts from supplied current evidence only."""
    values = list(sources.values()) if isinstance(sources, dict) else list(sources)
    actual = [source for source in values if isinstance(source, dict)
              and isinstance(source.get('id'), str) and isinstance(source.get('text'), str)]
    records = _derived(actual, reference_date, query=query, sku=sku)
    selected = {}
    warranty_topic = bool(_WARRANTY.search(query))
    asks_duration = bool(_DURATION.search(query))
    assured_topic = bool(re.search(r'\bassured\b|\u0905\u0936\u094d\u092f\u094b\u0930\u094d\u0921', query, re.I))
    if 'assured' in records:
        name = records['assured']['benefit_name']
        assured_topic = assured_topic or bool(name and re.search(re.escape(name), query, re.I))
        offered = bool(_OFFERED.search(query)) or any(_COPULA_QUESTION.search(clause) and not _ROUTE_QUESTION.search(clause) for clause in re.split(r'[?!.;\u0964\n]+', query))
        if assured_topic and (asks_duration or offered):
            selected['assured'] = records['assured']
    if 'brand' in records:
        explicit_brand = bool(_BRAND.search(query))
        brand = records['brand']['brand']
        if isinstance(brand, str) and brand and warranty_topic and re.search(r'(?<!\w)' + re.escape(brand) + r'(?!\w)', query, re.I):
            explicit_brand = True
        if warranty_topic and asks_duration and (explicit_brand or not assured_topic):
            selected['brand'] = records['brand']
    return {'warranty_duration':selected} if selected else {}


def warranty_duration_constraints(context):
    return [{'kind':'quantity', 'value':record['duration_months'], 'unit':'month',
             'key':'warranty_duration.' + scope + '.duration_months', 'source_ids':record['source_ids']}
            for scope, record in context.get('warranty_duration', {}).items()]


def validate_warranty_duration_constraint(item, facts, sources):
    """A month obligation must rebind its complete entity and catalog evidence."""
    match = re.fullmatch(r'warranty_duration\.(assured|brand)\.duration_months', item.get('key',''))
    if not match or item.get('kind') != 'quantity' or item.get('unit') != 'month':
        raise ValueError('unbound_warranty_duration')
    scope = match[1]
    durations = facts.get('warranty_duration', {})
    record = durations.get(scope) if isinstance(durations, dict) else None
    if not isinstance(record, dict) or type(record.get('duration_months')) is not int:
        raise ValueError('unbound_warranty_duration')
    actual = _derived(sources, facts.get('reference_date'), sku=record.get('sku')).get(scope)
    if (actual != record or type(item.get('value')) is not int or item['value'] != record['duration_months']
            or item.get('source_ids') != record['source_ids']):
        raise ValueError('unbound_warranty_duration')


def warranty_duration_answer_matches(answer, item, facts, sources):
    """Count only an affirmative month quantity associated with its warranty."""
    scope = item['key'].split('.')[1]
    records = facts['warranty_duration']
    record = records[scope]
    names = {records.get('assured', {}).get('benefit_name', '')}
    for source in sources:
        if _active(source, facts.get('reference_date'), 'policy'):
            names.update(match['name'].strip() for match in _ASSURANCE.finditer(_plain(source['text'])))
    names.discard('')
    target_assured = re.compile(r'\bassured\b' + ''.join('|' + re.escape(name) for name in sorted(names)), re.I)
    brand_name = record.get('brand', record.get('catalog_brand', ''))
    brand_pattern = re.compile(re.escape(brand_name) + r'\s+(?:ki\s+)?warranty\b', re.I) if isinstance(brand_name, str) and brand_name else None
    other_entity = bool(_BRAND.search(answer) or (brand_pattern and brand_pattern.search(answer))) if scope == 'assured' else bool(target_assured.search(answer))
    for clause in re.split(r'(?<!\d)\.(?!\d)|[!?;,\u0964\n]+|\b(?:and|but|however|while|whereas|in\s+addition\s+to)\b', answer, flags=re.I):
        if _NEGATIVE.search(clause):
            continue
        if not any(unit in {'month', 'year'} and _quantity_supported((number, unit), {(str(record['duration_months']), 'month')}) for number, unit in _quantities(clause)):
            continue
        assured = bool(target_assured.search(clause))
        brand_name = record.get('brand', record.get('catalog_brand', ''))
        named_brand = bool(isinstance(brand_name, str) and brand_name and re.search(re.escape(brand_name) + r'\s+(?:ki\s+)?warranty\b', clause, re.I))
        brand = bool(_BRAND.search(clause)) or named_brand
        if scope == 'assured' and assured and not brand:
            return True
        if scope == 'brand' and brand and not assured:
            return True
        # A single explicitly requested warranty can use an unambiguous short
        # follow-up such as 'It lasts N months'; two entities need labels.
        implicit = bool(_WARRANTY.search(clause) or re.search(r'^\s*(?:it|this|that|yeh|yah)\b|^\s*\u092f\u0939', clause, re.I))
        if len(records) == 1 and not assured and not brand and implicit and not other_entity:
            return True
    return False
