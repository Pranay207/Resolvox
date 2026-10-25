"""Source-bound necessary return conditions; no customer-facing policy prose.

The narrow parser deliberately leaves ambiguous rules and customer statements
unresolved. It checks only ordinary-return contradictions, not total eligibility.
"""
import hashlib
import json
import re
from datetime import date

_RULE = re.compile(
    r'(?P<subject>[^.!?;\n]{1,140}?)\s+(?:are\s+)?'
    r'(?:returnable|can\s+be\s+returned)\s+only\s+if\s+'
    r'(?P<conditions>[^.!?;\n]+)', re.I)
_EXCEPTION = re.compile(
    r'\b(?:damag\w*|defect\w*|expired|wrong|missing|tamper\w*|broken)\b|'
    r'खराब|टूटा|टूटी|गलत|एक्सपायर|गुम|क्षतिग्रस्त|टैम्पर|'
    r'\b(?:kharab|tuta|toota|galat|expired|missing)\b', re.I)
_UNCERTAIN = re.compile(
    r'\b(?:if|suppose|maybe|perhaps|might|not sure|not certain|unsure|whether|planning|will open|may have|could have)\b|'
    r'अगर|यदि|शायद|खोलना|\b(?:agar|shayad|shayed|kholna)\b', re.I)
_PACKAGING = re.compile(r'\b(?:box|carton|packaging|shipping package|outer package)\b|डिब्बा|पैकिंग|कार्टन', re.I)
_SELF = re.compile(r"\b(?:i|i've|we|we've|my|our|maine|mainne|hamne)\b|मैंने|हमने|मेरा|मेरी", re.I)
_PRONOUN = re.compile(r'\b(?:it|this item|the item|my item|this product|the product|my product)\b|इस सामान|यह सामान|इस उत्पाद|मेरे सामान', re.I)
_YES = re.compile(r'^\s*(?:yes|haan|han|हाँ|हां|जी\s*हाँ)(?=\s|[,;:.!?।]|$)', re.I)
_NEGATIVE = re.compile(r"\b(?:not|never|cannot|can't|nahi|nahin)\b|नहीं|नहि", re.I)
_CONDITIONAL = re.compile(r'\b(?:if|provided|assuming|could|were|unless)\b|अगर|यदि|\b(?:agar|yadi)\b', re.I)
_POSITIVE = (
    re.compile(r'\byou\s+(?:can|may)\s+(?:(?:still|now|certainly)\s+){0,2}(?:return|send\s+.{0,15}back)\b', re.I),
    re.compile(r'\b(?:it|(?:your|this|the)\s+(?:item|product))\s+(?:is|remains)\s+(?:still\s+)?(?:eligible|returnable)\b', re.I),
    re.compile(r'\byou\s+are\s+(?:eligible\s+for\s+(?:a\s+)?return|allowed\s+to\s+return)\b', re.I),
    re.compile(r'आप.{0,40}(?:वापस|लौटा|रिटर्न).{0,20}(?:कर\s+सकत[ीे]|हो\s+सकत)', re.I),
    re.compile(r'\baap\b.{0,40}\b(?:return|wapas|vaapas)\b.{0,20}\bkar\s+sakt[ei]\b', re.I),
)


def _sources(sources):
    values = sources.values() if isinstance(sources, dict) else sources
    return [source for source in values if isinstance(source, dict)
            and isinstance(source.get('id'), str) and isinstance(source.get('text'), str)]


def _active(source, reference_date):
    if source.get('status') != 'current':
        return False
    effective = source.get('effective_from')
    if not effective:
        return True
    try:
        return date.fromisoformat(effective) <= date.fromisoformat(reference_date)
    except (TypeError, ValueError):
        return False


def _fingerprint(source):
    bound = {key: source.get(key, '') for key in
             ('id', 'text', 'doc_type', 'status', 'effective_from', 'version')}
    return hashlib.sha256(json.dumps(bound, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _catalog(sources, reference_date):
    rows = []
    for source in sources:
        if source.get('doc_type') != 'catalog' or not _active(source, reference_date):
            continue
        try:
            row = json.loads(source['text'])
        except (ValueError, TypeError):
            continue
        if isinstance(row, dict) and all(isinstance(row.get(key), str) and row[key]
                                        for key in ('sku', 'title', 'return_category')):
            rows.append((source, row))
    # Multi-item attribution is deliberately unresolved in the first version.
    return rows[0] if len(rows) == 1 else None


def _derive_policy(sources, reference_date):
    selected = _catalog(sources, reference_date)
    if not selected:
        return None
    catalog_source, item = selected
    category = item['return_category']
    tokens = set(re.findall(r'[a-z]+', category.casefold())) - {'sealed', 'unopened', 'unused'}
    if not tokens:
        return None
    rules = []
    for source in sources:
        if source.get('doc_type') != 'policy' or not _active(source, reference_date):
            continue
        for match in _RULE.finditer(source['text']):
            subject = set(re.findall(r'[a-z]+', match['subject'].casefold()))
            if not tokens <= subject:
                continue
            condition = match['conditions']
            if re.search(r"\b(?:not|never|no|cannot|can't|isn't|aren't)\b",
                         match['subject'] + ' ' + condition, re.I):
                return None
            if re.search(r'\b(?:or|unless|except|despite|whether)\b', condition, re.I):
                return None
            requirements = {}
            if re.search(r'\bunopened\b', condition, re.I):
                requirements['opened'] = False
            if re.search(r'\bseals?\s+(?:is\s+)?(?:intact|unbroken)\b', condition, re.I):
                requirements['seal_intact'] = True
            if not requirements:
                return None
            rules.append((source, requirements))
    if not rules or any(rule != rules[0][1] for _, rule in rules):
        return None
    bound = {source['id']: source for source, _ in rules}
    bound[catalog_source['id']] = catalog_source
    return {'category': category, 'item_sku': item['sku'], 'requirements': rules[0][1],
            'scope': 'ordinary_return_only', 'source_ids': sorted(bound),
            'source_sha256': {sid: _fingerprint(source) for sid, source in sorted(bound.items())}}


def _has_exception(text):
    """Only explicit local negation removes an exception signal; ambiguity stays."""
    for match in _EXCEPTION.finditer(text):
        prefix = text[max(0, match.start()-30):match.start()]
        suffix = text[match.end():match.end()+15]
        if re.search(r"\b(?:not|never|isn't|wasn't)\s+(?:(?:physically|visibly|actually)\s+)?$", prefix, re.I):
            continue
        if re.search(r'(?:\u0928\u0939\u0940\u0902|\bnahi\b|\bnahin\b)\s*$', prefix, re.I):
            continue
        if re.match(r'\s*(?:\u0928\u0939\u0940\u0902|nahi\b|nahin\b)', suffix, re.I):
            continue
        return True
    return False


def _claim(query, item):
    query = ' '.join(query.split())
    scope = 'possible_exception' if _has_exception(query) else 'ordinary_return'
    if _UNCERTAIN.search(query):
        scope = 'ambiguous'
    values = {'opened': set(), 'seal_intact': set()}
    for clause in re.split(r'[.!?;।\n,]+', query):
        if _PACKAGING.search(clause):
            continue
        target = item['title'].casefold() in clause.casefold() or _PRONOUN.search(clause)
        if target and _SELF.search(clause):
            if re.search(r'\bunopened\b|\b(?:not|never|haven.t|didn.t)\b.{0,20}\bopen(?:ed)?\b|'
                         r'नहीं.{0,20}(?:खोल|खोला|खोली)|(?:खोल|खोला|खोली).{0,12}नहीं|'
                         r'\bnahi\b.{0,15}\bkhol|\bkhol.{0,15}\bnahi\b', clause, re.I):
                values['opened'].add(False)
            elif re.search(r'\b(?:opened|unsealed)\b|खोल\s*(?:लिया|ली|दिया|दी)|'
                           r'\bkhol\s*(?:liya|li|diya|di)\b', clause, re.I):
                values['opened'].add(True)
        # Seal-only statements need the named item elsewhere in this question.
        item_known = target or item['title'].casefold() in query.casefold()
        if item_known and re.search(r'\bseal\b|सील', clause, re.I):
            if re.search(r'\bseal\s+(?:is\s+)?intact\b|सील\s+(?:सही|सलामत|बरकरार)|'
                         r'\bseal\s+intact\s+hai\b', clause, re.I):
                values['seal_intact'].add(True)
            if (_SELF.search(clause) and not re.search(
                    r'\b(?:not|never|didn.t|nahi)\b.{0,20}(?:break|broke|tod)|\u0928\u0939\u0940\u0902.{0,12}\u0924\u094b\u0921\u093c|\u0924\u094b\u0921\u093c.{0,12}\u0928\u0939\u0940\u0902',
                    clause, re.I) and re.search(r'\bbroke\s+(?:the\s+)?seal\b|सील\s*तोड़|'
                                                  r'\bseal\s*tod\b', clause, re.I)):
                values['seal_intact'].add(False)
    if any(len(states) > 1 for states in values.values()):
        scope = 'ambiguous'
    claim = {'item_sku': item['sku'], 'input_status': 'customer_provided_unverified', 'scope': scope}
    if scope != 'ambiguous':
        claim.update({key: next(iter(states)) for key, states in values.items() if len(states) == 1})
    return claim


def _evaluate(policy, claim):
    violated = [key for key, required in policy['requirements'].items()
                if type(claim.get(key)) is bool and claim[key] is not required]
    status = ('not_satisfied' if violated else 'unresolved') if claim['scope'] == 'ordinary_return' else 'unresolved'
    return {'status': status, 'violated_requirements': violated if status == 'not_satisfied' else [],
            'scope': 'ordinary_return_only', 'source_ids': policy['source_ids']}


def return_condition_context(query, sources, *, reference_date):
    """Add necessary facts only; never choose final eligibility or reply text."""
    if not re.search(r'\breturn\w*\b|\bsend.{0,15}back\b|\b(?:wapas|vaapas|lauta\w*)\b|\u0935\u093e\u092a\u0938|\u0932\u094c\u091f\u093e|\u0930\u093f\u091f\u0930\u094d\u0928', query, re.I):
        return {}
    sources = _sources(sources)
    policy = _derive_policy(sources, reference_date)
    if not policy:
        return {}
    _, item = _catalog(sources, reference_date)
    claim = _claim(query, item)
    return {'return_condition_policy': policy, 'customer_item_condition_claim': claim,
            'ordinary_return_condition_check': _evaluate(policy, claim)}


def check_return_condition_answer(answer, facts, sources):
    """Reject positive customer eligibility inconsistent with a necessary fact."""
    keys = {'return_condition_policy', 'customer_item_condition_claim', 'ordinary_return_condition_check'}
    if not keys & set(facts):
        return
    if not keys <= set(facts):
        raise ValueError('unbound_return_condition')
    sources = _sources(sources)
    policy = _derive_policy(sources, facts.get('reference_date'))
    if not policy or facts['return_condition_policy'] != policy:
        raise ValueError('unbound_return_condition')
    claim = facts['customer_item_condition_claim']
    if (not isinstance(claim, dict) or claim.get('item_sku') != policy['item_sku']
            or claim.get('input_status') != 'customer_provided_unverified'
            or claim.get('scope') not in {'ordinary_return', 'ambiguous', 'possible_exception'}
            or set(claim) - {'item_sku', 'input_status', 'scope', 'opened', 'seal_intact'}
            or any(type(value) is not bool for key, value in claim.items() if key in {'opened', 'seal_intact'})):
        raise ValueError('unbound_return_condition')
    check = _evaluate(policy, claim)
    if check != facts['ordinary_return_condition_check']:
        raise ValueError('unbound_return_condition')
    if check['status'] != 'not_satisfied':
        return
    first_statement = re.split(r'[.!?;\u0964\n]', answer, maxsplit=1)[0].strip(' ,')
    if _YES.fullmatch(first_statement):
        raise ValueError('contradicted_return_condition')
    clauses = re.split(r'[.!?;।\n]+|\bbut\b|\bhowever\b|लेकिन|परंतु', answer)
    for clause in clauses:
        if _CONDITIONAL.search(clause) or _has_exception(clause):
            continue
        for pattern in _POSITIVE:
            for match in pattern.finditer(clause):
                local = clause[max(0, match.start()-12):match.end()]
                if not _NEGATIVE.search(local):
                    raise ValueError('contradicted_return_condition')
