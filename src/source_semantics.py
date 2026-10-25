"""Finite source-derived guards for explicit permissions and benefit conditions.

Derive constraints only from explicit source relationships. No policy identifiers,
amounts, time limits, membership names or prewritten answers are embedded here.
These narrow checks do not establish sentence-level semantic entailment.
"""
import hashlib
import json
from datetime import date
from .config import REFERENCE_DATE
from .kb import AUTHORITY
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



# These are language-level payment and event cues; no policy IDs or values.
_RTO_REFUND_EVENT = re.compile(
    r'\b(?:RTO|returned?[- ]to[- ]origin|refus\w*\s+(?:(?:the|a|this)\s+)?(?:parcel|delivery|package)|'
    r'(?:delivery\s+)?attempt\w*[^.!?;\n]{0,40}fail\w*|fail\w*[^.!?;\n]{0,40}(?:delivery|attempt)|'
    r'not\s+delivered|undelivered)\b|'
    r'\b(?:delivery|parcel|package)\b[^.!?;\n]{0,30}\brefus\w*\b|'
    r'\u0921\u093f\u0932\u0940\u0935\u0930\u0940[^.!?;\n]{0,35}(?:\u0905\u0938\u092b\u0932|\u0928\u0939\u0940\u0902)|'
    r'(?:\u092a\u093e\u0930\u094d\u0938\u0932|\u092a\u0948\u0915\u0947\u091f)[^.!?;\n]{0,35}\u092e\u0928\u093e|'
    r'\b(?:delivery|attempt)\w*[^.!?;\n]{0,30}\b(?:fail|nahi|nahin)\b', re.I)
_REFUND_WORD = re.compile(r'\brefund\w*\b|\u0930\u093f\u092b\u093c?\u0902\u0921', re.I)
_PREPAID_CUE = re.compile(
    r'\bpre[- ]?paid\b|\b(?:paid|payment\s+made)\s+(?:before\s+(?:delivery|shipping)|in\s+advance)\b|'
    r'\b(?:pehle|pahle)\s+(?:se\s+)?(?:paid|payment\s+(?:ki|kiya|ho))\b|'
    r'\u092a\u094d\u0930\u0940\u092a\u0947\u0921|\u092a\u0942\u0930\u094d\u0935\s*\u092d\u0941\u0917\u0924\u093e\u0928|'
    r'\u092a\u0939\u0932\u0947\s*(?:\u0938\u0947\s*)?\u092d\u0941\u0917\u0924\u093e\u0928', re.I)
_PAYMENT_CONDITION_DENIED = re.compile(
    r"\bnot\s+pre[- ]?paid\b|\b(?:need\s+not|not\s+(?:need|require\w*|necessary)|(?:do(?:es)?\s+not|don['\u2019]t|doesn['\u2019]t)\s+need)\b[^.!?;\n]{0,25}\bpre[- ]?paid\b|"
    r'\bpre[- ]?paid\b[^.!?;\n]{0,25}\b(?:not\s+(?:required|necessary)|nahi|nahin)\b|'
    r'\u092a\u094d\u0930\u0940\u092a\u0947\u0921[^.!?;\n]{0,25}(?:\u091c\u0930\u0942\u0930\u0940|\u0906\u0935\u0936\u094d\u092f\u0915)\s*\u0928\u0939\u0940\u0902',re.I)


def _conditional_refund_constraints(records):
    constraints=[]
    for cid, text in records:
        # Bind the qualifier to a marked rule antecedent, not another section
        # or an arbitrary mention of prepaid somewhere in the document.
        for match in re.finditer(r'^\s*[-*]\s+\*\*(?P<when>[^\n]+?):\*\*\s*(?P<then>[^\n]+)',text,re.M):
            when,then=match['when'],match['then']
            if re.search(r'\bprepaid\s+order\b',when,re.I) and _RTO_REFUND_EVENT.search(when):
                heading=text[:match.start()]
                if re.search(r'\brefund\b',heading,re.I):
                    constraints.append({'kind':'conditional_rto_refund','payment_condition':'prepaid',
                                        'source_antecedent':when,'source_consequence':then,'source_ids':[cid]})
    return constraints


def _positive_refund_statement(sentence):
    if not _REFUND_WORD.search(sentence):
        return False
    # Pure denials/uncertainty do not promise a refund. A later positive clause
    # remains eligible for checking even if an earlier sentence has a denial.
    negative=re.search(r"\b(?:does\s+not\s+mean\s+(?:a\s+)?refund|no\s+refund|cannot\s+(?:confirm|promise|guarantee)\s+(?:a\s+)?refund|refund\w*\s+(?:is\s+)?not\s+(?:due|promised|guaranteed))\b|"
                       r'\u0930\u093f\u092b\u093c?\u0902\u0921[^.!?;\n]{0,20}\u0928\u0939\u0940\u0902',sentence,re.I)
    return not negative or bool(re.search(r'\b(?:but|however|later|once|will|initiated|starts?)\b',sentence[negative.end():],re.I))


def _payment_condition_scope(text):
    """Accept an explicit hypothetical/generic condition, not a personal guess."""
    cues=list(_PREPAID_CUE.finditer(text))
    if not cues:
        return False
    for match in cues:
        before=text[:match.start()]
        after=text[match.end():]
        if re.search(r'\b(?:not|never|nahi|nahin)\s*$',before,re.I) or re.search(r'(?:\u0928\u0939\u0940\u0902)\s*$',before):
            continue
        if _PAYMENT_CONDITION_DENIED.search(text):
            continue
        # A purported individual cause is not evidence that an order was paid.
        if re.search(r'\b(?:since|because|as)\b[^.!?;\n]{0,60}\b(?:your|the|this)\s+order\b',before,re.I):
            continue
        if re.search(r'\b(?:if|for|provided|assuming|when)\b[^.!?;\n]{0,60}$',before,re.I):
            return True
        if re.search(r'\b(?:orders|purchases|shipments)\b',after,re.I) and not re.search(r'\b(?:your|this|the)\s*$',before,re.I):
            return True
        if re.search(r'\b(?:agar|yadi)\b[^.!?;\n]{0,60}$',before,re.I) or re.search(r'(?:\u092f\u0926\u093f|\u0905\u0917\u0930)[^.!?;\n]{0,60}$',before):
            return True
        if re.search(r'\b(?:to|ke\s+liye)\b',after,re.I) or re.search(r'\u0915\u0947\s*(?:\u0932\u093f\u090f|\u092e\u093e\u092e\u0932\u0947)',after):
            return True
    return False


def _check_conditional_refund(answer,item):
    sentences=[part.strip() for part in re.split(r'[.!?;\u0964\n]+',_plain(answer)) if part.strip()]
    for index,sentence in enumerate(sentences):
        if not _positive_refund_statement(sentence):
            continue
        context=sentence
        if not _RTO_REFUND_EVENT.search(context) and index:
            # A directly following continuation can refer to the prior event;
            # unrelated QC/cancellation rules are independent antecedents.
            if re.search(r'^(?:then|once|after\s+that|the\s+refund|a\s+refund|refund|it\s+will)\b',sentence,re.I):
                context=sentences[index-1]+' '+sentence
        if not _RTO_REFUND_EVENT.search(context):
            continue
        payment_context=context
        if index and _payment_condition_scope(sentences[index-1]):
            # Permit a generic scoped rule to be stated across two sentences;
            # a negated/current non-prepaid statement cannot inherit it.
            payment_context=sentences[index-1]+' '+context
        if _PAYMENT_CONDITION_DENIED.search(context) or not _payment_condition_scope(payment_context):
            raise ValueError('source_refund_condition_missing:prepaid')


def _attribute_authority(source):
    """Use actual source metadata; metadata/catalog rows are not policy rules."""
    if any(key in source and not isinstance(source[key],str) for key in ('doc_type','status','effective_from')):
        raise ValueError('invalid_semantic_source_authority')
    if source.get('status', 'current') != 'current':
        return None
    kind = source.get('doc_type')
    if kind not in AUTHORITY or kind in {'meta', 'catalog'}:
        return None
    effective = source.get('effective_from')
    if effective:
        try:
            if date.fromisoformat(effective) > REFERENCE_DATE:
                return None
        except (TypeError, ValueError):
            raise ValueError('invalid_semantic_source_authority')
    return AUTHORITY[kind]


def _semantic_fingerprint(source):
    fields = {key: source[key] for key in ('id','text','file','doc_type','status','effective_from','version') if key in source}
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _brand_negative_attributes(text):
    """Read only explicit negative brand attributes, retaining their subject."""
    starts, coverages = set(), set()
    for clause in _clauses(text):
        for entity in _BRAND.finditer(clause):
            tail = re.split(r'\bin addition to\b|\b(?:and|plus)\s+(?:an?\s+)?additional\b',
                            clause[entity.end():], maxsplit=1, flags=re.I)[0]
            next_entity = _BRAND.search(tail)
            if next_entity:
                tail = tail[:next_entity.start()]
            start = _START.search(tail)
            if start and _NEG.search(tail[:start.start()]):
                before = tail[:start.start()]
                if (re.search(r'\b(?:start\w*|begin\w*|valid|effective)\b', before, re.I)
                        or re.fullmatch(r'\s*(?:is\s+)?(?:not|never|nahi|nahin)\s*', before, re.I)):
                    event = next((part for part in start.groups() if part), '')
                    starts.add(_EVENT.get(event, event.casefold()))
            coverage = _COVER.search(tail)
            if coverage and _NEG.search(tail[:coverage.start()]):
                scope = _norm(tail[coverage.end():])
                if scope:
                    coverages.add(scope)
    return starts, coverages


def _catalog_brand_scope(sources):
    brands = set()
    for source in sources:
        if source.get('doc_type') != 'catalog' or source.get('status', 'current') != 'current':
            continue
        try:
            row = json.loads(source['text'])
        except (TypeError, ValueError):
            continue
        if isinstance(row, dict) and isinstance(row.get('sku'), str) and isinstance(row.get('brand'), str):
            if row['brand'].strip():
                brands.add(_norm(row['brand']))
    return next(iter(brands)) if len(brands) == 1 else None


def _bound_brand_text(text, catalog_brand):
    """Do not transfer an explicitly named brand clause to another item.

    Generic brand/manufacturer policy remains generic. Direct proper-name
    qualifiers need a unique matching actual catalog brand; unresolved named
    scope is not promoted to a universal attribute. This is a finite cue check,
    not a full named-entity resolver.
    """
    generic = {'the','a','an','our','your','this','both','any','each','every'}
    bound = []
    for clause in _clauses(text):
        applicable = True
        for entity in _BRAND.finditer(clause):
            prefix = clause[:entity.start()]
            named = re.search(r"(?P<name>[A-Z][A-Za-z0-9_'\u2019-]*(?:\s+[A-Z][A-Za-z0-9_'\u2019-]*){0,3})\s*$", prefix)
            if not named:
                continue
            words = named['name'].split()
            while words and words[0].casefold() in generic:
                words.pop(0)
            if not words:
                continue
            name = re.sub(r"['\u2019]s$", '', ' '.join(words), flags=re.I)
            if catalog_brand is None or _norm(name) != catalog_brand:
                applicable = False
                break
        if applicable:
            bound.append(clause)
    return '. '.join(bound)


def _brand_authority_constraint(sources):
    """Select authority independently for starts and positive/negative coverage.

    An unrelated store attribute cannot outrank a brand attribute. A source
    that merely mentions brand warranty does not erase another attribute.
    Conflicting same-priority starts authorize no start value. Coverage must be
    supported by every governing positive source and violate no governing
    explicit exclusion; this is intentionally cautious about ambiguous scope.
    """
    actual = {}
    for source in sources:
        ident = source['id']
        if ident in actual and _semantic_fingerprint(actual[ident]) != _semantic_fingerprint(source):
            raise ValueError('conflicting_semantic_source_identity')
        actual[ident] = source
    brand = [source for source in actual.values() if _BRAND.search(_plain(source['text']))]
    if not brand:
        return None
    catalog_brand = _catalog_brand_scope(sources)
    candidates = {'start': [], 'coverage': []}
    for source in brand:
        priority = _attribute_authority(source)
        if priority is None:
            continue
        applicable_text = _bound_brand_text(source['text'], catalog_brand)
        starts, coverages = _brand_attributes(applicable_text)
        denied_starts, denied_coverages = _brand_negative_attributes(applicable_text)
        for attribute, positive, negative in (('start', starts, denied_starts),
                                               ('coverage', coverages, denied_coverages)):
            if positive or negative:
                candidates[attribute].append((priority, source['id'], positive, negative))
    governing = {}
    for attribute, entries in candidates.items():
        best = min((entry[0] for entry in entries), default=None)
        governing[attribute] = [entry for entry in entries if entry[0] == best]
    starts = set().union(*(row[2] for row in governing['start'])) if governing['start'] else set()
    denied_starts = set().union(*(row[3] for row in governing['start'])) if governing['start'] else set()
    conflict = len(starts) > 1 or bool(starts & denied_starts)
    coverages = set().union(*(row[2] for row in governing['coverage'])) if governing['coverage'] else set()
    denied_coverages = set().union(*(row[3] for row in governing['coverage'])) if governing['coverage'] else set()
    positive_groups = [{'source_ids':[row[1]], 'documented_positive_coverages':sorted(row[2])}
                       for row in governing['coverage'] if row[2]]
    ids = [source['id'] for source in brand]
    return {'kind':'brand_warranty_attributes',
            'documented_start_events':sorted(starts) if not conflict else [],
            'documented_positive_coverages':sorted(coverages),
            'prohibited_start_events':sorted(denied_starts),
            'prohibited_positive_coverages':sorted(denied_coverages),
            'start_authority_conflict':conflict,
            'governing_start_source_ids':[row[1] for row in governing['start']],
            'governing_coverage_source_ids':[row[1] for row in governing['coverage']],
            'governing_positive_coverage_groups':positive_groups,
            'source_ids':ids,
            'source_authority':{sid:{key:actual[sid][key] for key in ('doc_type','status','effective_from','version') if key in actual[sid]} for sid in ids},
            'source_provenance_sha256':{sid:_semantic_fingerprint(actual[sid]) for sid in ids}}


def _brand_coverage_allowed(scope, item):
    if not _coverage_supported(scope, item['documented_positive_coverages']):
        return False
    for group in item.get('governing_positive_coverage_groups', []):
        if not _coverage_supported(scope, group['documented_positive_coverages']):
            return False
    wanted = _coverage_tokens(scope)
    for excluded in item.get('prohibited_positive_coverages', []):
        denied = _coverage_tokens(excluded)
        if denied and denied.issubset(wanted):
            return False
    return True


def derive_source_constraints(sources):
    """Return inspectable source-bound constraints, not authored replies."""
    actual_sources = list(sources)
    records = []
    for source in actual_sources:
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
    constraints.extend(_conditional_refund_constraints(records))
    brand_constraint = _brand_authority_constraint(actual_sources)
    if brand_constraint:
        constraints.append(brand_constraint)
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
        elif item['kind'] == 'conditional_rto_refund':
            _check_conditional_refund(answer, item)
        elif item['kind'] == 'brand_warranty_attributes':
            starts, coverages = _brand_attributes(answer)
            if starts.difference(item['documented_start_events']):
                raise ValueError('unsupported_brand_warranty_start')
            if any(not _brand_coverage_allowed(scope, item) for scope in coverages):
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
