"""Finite source-derived guards for explicit permissions and benefit conditions.

Derive constraints only from explicit source relationships. No policy identifiers,
amounts, time limits, membership names or prewritten answers are embedded here.
These narrow checks do not establish sentence-level semantic entailment.
"""
import hashlib
import re
import unicodedata


def _plain(text):
    return re.sub(r'[*\x60]', '', text)


def _norm(text):
    return ' '.join(re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', text).casefold()))


def _clauses(text):
    return [part.strip() for part in re.split(
        r'[.!?;।\n,]+|\b(?:but|however)\b|लेकिन|मगर', _plain(text), flags=re.I)
            if part.strip()]


_NEG = re.compile(r"\b(?:not|no|never|cannot|can't|can’t|nahi|nahin)\b|नहीं|मत", re.I)
_REFUSE = re.compile(r'\b(?:refuse|decline|reject)\b|रिफस|रिफ्यू[जज़]|रिफ़्यू[जज़]|मना', re.I)
_PARCEL = re.compile(r'\b(?:parcel|package|shipment|delivery|packet)\b|पार्सल|पैकेट|डिलीवरी', re.I)
_REFUSE_DENIED = re.compile(
    r"\b(?:cannot|can't|can’t|may not|must not|not allowed to)\s+(?:\w+\s+){0,2}(?:refuse|decline|reject)\b|"
    r'(?:refuse|decline|reject|रिफस|रिफ्यू[जज़]|रिफ़्यू[जज़]|मना)[^.;।\n]{0,28}(?:\bnot\b|\bnahi\b|\bnahin\b|नहीं)', re.I)
_BRAND = re.compile(
    r"\b(?:(?:brand|manufacturer(?:'s)?)\s+warrant(?:y|ies)|both\s+warranties)\b|"
    r'(?:ब्रांड|निर्माता|दोनों)\s*(?:की\s*)?वारंट[ीियां]+|'
    r'\b(?:brand|manufacturer|dono)\s+(?:ki\s+)?warrant(?:y|ies)\b', re.I)
_START = re.compile(
    r'\b(?:from|on)\s+(?:the\s+)?(?P<event>delivery|purchase|invoice|activation)(?:\s+date)?\b|'
    r'(?P<hi>डिलीवरी|खरीद|इनवॉइस|सक्रियण)(?:\s+की\s+तारीख)?\s+से|'
    r'\b(?P<roman>delivery|purchase|invoice|activation)\s+se\b', re.I)
_COVER = re.compile(r'\b(?:covers?|protects?\s+against)\b|कवर\s+कर(?:ता|ती|ते)|कवरेज', re.I)
_EVENT = {'डिलीवरी': 'delivery', 'खरीद': 'purchase',
          'इनवॉइस': 'invoice', 'सक्रियण': 'activation'}
_CREDIT = re.compile(r'\bcredit(?:ed)?\b|क्रेडिट', re.I)
_FEE_EN = r'(?:fees?|charges?)'
_PAID_EN = r'(?:paid|charged|collected|billed|pay kiya|pay ki|diya|di|bhara|bhari|chukaya|chukai)'
_FEE_HI = r'(?:फ़ीस|फीस|शुल्क)'
_PAID_HI = r'(?:चुकाया|चुकाई|चुकाए|भरा|भरी|भरे|दिया|दी|दिए|लिया|ली|लिए|लगा|लगी|लगे|वसूला|वसूली|वसूले)'
_PAID = re.compile(
    r'\b' + _FEE_EN + r'\b[^.;।\n]{0,70}\b' + _PAID_EN + r'\b|'
    r'\b' + _PAID_EN + r'\b[^.;।\n]{0,50}\b' + _FEE_EN + r'\b|'
    + _FEE_HI + r'[^.;।\n]{0,55}' + _PAID_HI + r'|'
    + _PAID_HI + r'[^.;।\n]{0,55}' + _FEE_HI, re.I)


def _brand_attributes(text):
    """Associate attributes with their subject, not a later brand reference."""
    starts, coverages = set(), set()
    for clause in _clauses(text):
        if _NEG.search(clause):
            continue
        for entity in _BRAND.finditer(clause):
            # A cue before 'in addition to [any] brand warranty' belongs to
            # the earlier store warranty, even when the comma is omitted.
            tail = clause[entity.end():]
            tail = re.split(
                r'\bin addition to\b|\b(?:and|plus)\s+(?:an?\s+)?additional\b',
                tail, maxsplit=1, flags=re.I)[0]
            next_entity = _BRAND.search(tail)
            if next_entity:
                tail = tail[:next_entity.start()]
            start = _START.search(tail)
            if start:
                event = next((part for part in start.groups() if part), '')
                starts.add(_EVENT.get(event, event.casefold()))
            coverage = _COVER.search(tail)
            if coverage:
                value = _norm(tail[coverage.end():])
                if value:
                    coverages.add(value)
            prefix = clause[:entity.start()]
            passive = re.search(
                r'(?P<scope>.+?)\s+(?:is|are)\s+covered\s+(?:by|under)\s+(?:the\s+)?$',
                prefix, re.I)
            if passive:
                coverages.add(_norm(passive['scope']))
    return starts, coverages


_COVERAGE_FILLER = frozenset((
    'a', 'an', 'the', 'in', 'of', 'and', 'or', 'for', 'due', 'to',
    'only', 'from', 'against', 'are', 'is', 'covered'))
_COVERAGE_ALIASES = {'defects': 'defect', 'faults': 'defect', 'fault': 'defect',
                     'materials': 'material'}


def _coverage_tokens(text):
    return {_COVERAGE_ALIASES.get(token, token)
            for token in _norm(text).split() if token not in _COVERAGE_FILLER}


def _coverage_supported(candidate, documented):
    """Allow reordered/subset scopes without inventing a new positive scope."""
    wanted = _coverage_tokens(candidate)
    if not wanted:
        return False
    for phrase in documented:
        known = _coverage_tokens(phrase)
        modifiers = known.difference({'defect'})
        if wanted.issubset(known) and (not modifiers or wanted.intersection(modifiers)):
            return True
    return False


def _paid_fee_mention(answer):
    return any(_PAID.search(clause) and not _NEG.search(clause)
               for clause in _clauses(answer))


def derive_source_constraints(sources):
    """Return inspectable source-bound constraints, not authored replies."""
    records = []
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get('id'), str) or not isinstance(source.get('text'), str):
            raise ValueError('invalid_semantic_source')
        records.append((source['id'], source['text']))
    constraints = []
    for cid, raw_text in records:
        text = _plain(raw_text)
        direct = re.search(
            r'\b(?:the\s+)?(?:customer|you)\s+(?:can|may)\s*:?\s*(?:[-*]\s*)?'
            r'(?:refuse|decline)\s+(?:(?:the|a|this)\s+)?(?:parcel|package|shipment|delivery)\b', text, re.I)
        if direct:
            constraints.append({'kind': 'explicit_permission',
                                'action': 'refuse_parcel', 'source_ids': [cid]})
        fee_paid = re.search(
            r'\b' + _FEE_EN + r'\b[^.;\n]{0,90}\b' + _PAID_EN + r'\b[^.;\n]{0,90}\bcredit(?:ed)?\b', text, re.I)
        group = re.search(
            r'(?P<label>[A-Za-z][A-Za-z -]{0,60})\s+members\s*,?\s*(?:who\s+)?'
            r'pay\s+no\s+[^.;\n]{0,30}\b' + _FEE_EN + r'\b[^.;\n]{0,80}'
            r'\b(?:get|receive)\s+no\s+credit\b', text, re.I)
        if fee_paid and group:
            constraints.append({'kind': 'fee_paid_credit',
                                'excluded_membership': group['label'].strip(),
                                'source_ids': [cid]})
    brand_sources = [(cid, text) for cid, text in records if _BRAND.search(_plain(text))]
    if brand_sources:
        starts, coverages = set(), set()
        for _, text in brand_sources:
            source_starts, source_coverages = _brand_attributes(text)
            starts.update(source_starts)
            coverages.update(source_coverages)
        constraints.append({'kind': 'brand_warranty_attributes',
                            'documented_start_events': sorted(starts),
                            'documented_positive_coverages': sorted(coverages),
                            'source_ids': [cid for cid, _ in brand_sources]})
    actual = dict(records)
    for item in constraints:
        item['source_sha256'] = {
            cid: hashlib.sha256(actual[cid].encode('utf-8')).hexdigest()
            for cid in item['source_ids']}
    return constraints


def validate_source_semantics(answer, sources):
    """Reject only the explicitly represented relationships; return provenance.

    Invoke before language validation for a covered answer, with one existing
    retry owned by document_reply. Never use this as an answer renderer.
    """
    constraints = derive_source_constraints(sources)
    clauses = _clauses(answer)
    for item in constraints:
        if item['kind'] == 'explicit_permission':
            if any(_PARCEL.search(clause) and _REFUSE_DENIED.search(clause) for clause in clauses):
                raise ValueError('source_permission_reversed')
        elif item['kind'] == 'brand_warranty_attributes':
            starts, coverages = _brand_attributes(answer)
            if starts.difference(item['documented_start_events']):
                raise ValueError('unsupported_brand_warranty_start')
            if any(not _coverage_supported(scope, item['documented_positive_coverages']) for scope in coverages):
                raise ValueError('unsupported_brand_warranty_coverage')
        elif item['kind'] == 'fee_paid_credit':
            positive_credit = any(
                _CREDIT.search(clause) and not _NEG.search(clause) for clause in clauses)
            if not positive_credit:
                continue
            if not _paid_fee_mention(answer):
                raise ValueError('source_credit_paid_fee_condition_missing')
            label = _norm(item['excluded_membership'])
            label_tokens = label.split()
            # A source-specified membership label can omit its brand prefix,
            # but the no-credit statement must still identify that membership.
            labels = {label}
            if len(label_tokens) == 2:
                labels.add(label_tokens[-1])
            exclusion = any(
                _CREDIT.search(clause) and _NEG.search(clause)
                and any(re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', _norm(clause))
                        for name in labels)
                for clause in clauses)
            if not exclusion:
                raise ValueError('source_credit_membership_exclusion_missing')
    return constraints
