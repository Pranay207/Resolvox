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
            elif re.search(r'\bopened\b', condition, re.I):
                requirements['opened'] = True
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


# A source requirement is not a factual description of this customer's item.

def _premise_is_conditional(prefix):
    local=re.split(r'[,;]|\b(?:and|but|however|then)\b|\u0932\u0947\u0915\u093f\u0928',prefix,flags=re.I)[-1]
    if re.search(r'(?:\b(?:if|unless|assuming|provided|whether|agar|yadi)|\u092f\u0926\u093f|\u0905\u0917\u0930)\s*$',local,re.I):
        return True
    return bool(re.search(
        r'\b(?:cannot|can.t|unable\s+to)\s+(?:confirm|verify|say|determine)\s+(?:that\s+)?$|'
        r'\b(?:policy|rules?|conditions?)\b.{0,45}\b(?:requires?|states?|specif(?:y|ies))\s+(?:that\s+)?$',local,re.I))


def _check_customer_condition_premises(answer, claim, item):
    """Reject a definite item-state premise opposite to the explicit user claim.

    Inputs stay customer-provided and unverified; this is consistency with
    those inputs, never independent verification or complete eligibility.
    Only singular item copular predicates are recognized in this bounded check.
    """
    if claim.get('scope') == 'ambiguous':
        return
    title=re.escape(item['title'])
    subject=rf'(?:\bit\b|\b(?:your|this|the)\s+(?:item|product)\b|{title})'
    patterns=[
        ('opened',re.compile(subject+r'\s+(?:is|was|remains?)\s+(?P<neg>(?:(?:not|never)\s+)?)(?P<state>unopened|opened|open)\b',re.I)),
        ('opened',re.compile(subject+r'\s+(?P<neg>(?:(?:nahi|nahin)\s+)?)(?P<state>unopened|opened|open|khula|khuli|khule|khola|kholi)\s+(?P<postneg>(?:(?:nahi|nahin)\s+)?)(?:hai|hain|tha|thi)\b',re.I)),
        ('opened',re.compile(r'(?:\u092f\u0939|\u0907\u0938\u0947|\u0906\u092a\u0915\u093e\s+(?:\u0909\u0924\u094d\u092a\u093e\u0926|\u0938\u093e\u092e\u093e\u0928)|'+title+r')\s+(?P<neg>(?:\u0928\u0939\u0940\u0902\s+)?)(?P<state>\u0905\u0928\u0916\u0941\u0932[\u093e\u0940\u0947]|\u0916\u0941\u0932[\u093e\u0940\u0947]|\u0916\u094b\u0932[\u093e\u0940\u0947])\s+(?P<postneg>(?:\u0928\u0939\u0940\u0902\s+)?)(?:\u0939\u0948|\u0925\u093e|\u0925\u0940)(?=\s|[.,;!?\u0964]|$)',re.I)),
        ('seal_intact',re.compile(r'\b(?:its|your|the\s+item.s)\s+seal\s+(?:is|was|remains?)\s+(?P<neg>(?:(?:not|never)\s+)?)(?P<state>intact|unbroken|broken)\b',re.I)),
    ]
    for clause in re.split(r'[.!?;\u0964\n]+',answer):
        for key,pattern in patterns:
            if type(claim.get(key)) is not bool:
                continue
            for match in pattern.finditer(clause):
                if _premise_is_conditional(clause[:match.start()]):
                    continue
                state=match['state'].casefold()
                asserted=(state not in {'unopened','intact','unbroken'} and not state.startswith('\u0905\u0928\u0916\u0941\u0932')) if key=='opened' else state in {'intact','unbroken'}
                negations=sum(bool(match.groupdict().get(name,'').strip()) for name in ('neg','postneg'))
                if negations>1:
                    continue
                if negations:asserted=not asserted
                if asserted is not claim[key]:
                    raise ValueError('contradicted_customer_item_premise:'+key)


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
    _check_customer_condition_premises(answer, claim, _catalog(sources, facts.get('reference_date'))[1])
    _check_requirement_polarity(answer, policy, _catalog(sources, facts.get('reference_date'))[1])
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


# Requirement narration is distinct from an already-opened customer item.
_POLARITY_MODAL = re.compile(
    r'\b(?:must|should|needs?\s+to|has\s+to|have\s+to)\s+'
    r'(?P<phrase>(?:(?:not|never)\s+)?(?:be|remain|stay)\s+(?:(?:not|never)\s+)?'
    r'(?P<state>unopened|opened|open))\b', re.I)
_POLARITY_REQUIRED = re.compile(
    r'\b(?:requires?|mandates?|demands?)\s+(?:that\s+)?(?:(?:the|your|this)\s+)?(?:products?|items?|it|they)\s+'
    r'(?P<phrase>(?:to\s+)?(?:be|are|is|remain)\s+(?:(?:not|never)\s+)?(?P<state>unopened|opened|open))\b', re.I)
_POLARITY_ONLY_IF = re.compile(
    r'\b(?:returnable|returned|eligible(?:\s+for\s+return)?)\s+only\s+if\s+'
    r'(?P<phrase>(?:(?:they|it|products?|items?)\s+(?:are|is)\s+)?(?:(?:not|never)\s+)?'
    r'(?P<state>unopened|opened|open))\b', re.I)
_POLARITY_ONLY_ITEMS = re.compile(
    r'\bonly\s+(?P<phrase>(?P<state>unopened|opened|open))\s+(?:products?|items?)\s+'
    r'(?:are\s+)?(?:returnable|eligible|can\s+be\s+returned)\b', re.I)
_POLARITY_HI = re.compile(
    r'(?P<phrase>(?:(?:\u0928\u0939\u0940\u0902|\u0928)\s+)?'
    r'(?P<state>\u0905\u0928\u0916\u0941\u0932[\u093e\u0940\u0947]|\u0916\u0941\u0932[\u093e\u0940\u0947]|\u0916\u094b\u0932[\u093e\u0940\u0947])'
    r'(?:\s+(?:\u0928\u0939\u0940\u0902|\u0928))?(?:\s+\u0917[\u090f\u092f\u0940])?'
    r'(?:\s+(?:\u0928\u0939\u0940\u0902|\u0928))?\s+'
    r'(?P<norm>\u0939\u094b\u0928[\u093e\u0947]\s+\u091a\u093e\u0939\u093f\u090f|\u0930\u0939\u0928[\u093e\u0947]\s+\u091a\u093e\u0939\u093f\u090f|\u0939\u094b\u0902))', re.I)
_POLARITY_ROMAN = re.compile(
    r'\b(?P<phrase>(?:(?:nahi|nahin|na)\s+)?(?P<state>unopened|opened|open|khula|khuli|khule|khola|kholi|khole)'
    r'(?:\s+(?:nahi|nahin|na))?(?:\s+(?:hua|hue|gaye))?'
    r'(?:\s+(?:nahi|nahin|na))?\s+(?P<norm>(?:hona|hone|rahna|rehna)\s+chahiye|hon))\b', re.I)
_POLARITY_REPORT = re.compile(
    r'\b(?:policy|rules?|conditions?|requirements?)\b.{0,50}\b(?:say|says|state|states|require|requires|specify|specifies)\b|'
    r'(?:\u0936\u0930\u094d\u0924[\u0947\u094b]\u0902?|\u0928\u093f\u092f\u092e|\u092a\u0949\u0932\u093f\u0938\u0940).{0,45}'
    r'(?:\u0915\u0939\u0924[\u0940\u0947\u093e]|\u092c\u0924\u093e\u0924[\u0940\u0947\u093e])|'
    r'\b(?:policy|shartein|sharten|niyam)\b.{0,45}\b(?:kehti|kehte|kehta|bolti|bolta)\b', re.I)
_POLARITY_NEGATION = re.compile(
    r'(?<![A-Za-z\u0900-\u097f])(?:not|never|nahi|nahin|na|\u0928\u0939\u0940\u0902|\u0928)(?![A-Za-z\u0900-\u097f])', re.I)
_POLARITY_PRODUCT = re.compile(
    r'\b(?:products?|items?|it|they)\b|\u0909\u0924\u094d\u092a\u093e\u0926|\u0938\u093e\u092e\u093e\u0928|\u092a\u094d\u0930\u094b\u0921\u0915\u094d\u091f|\u0935\u0938\u094d\u0924\u0941', re.I)
_POLARITY_OTHER_SUBJECT = re.compile(
    r'\b(?:packaging|box|carton|app|portal|screen|page|window)\b|\u0921\u093f\u092c\u094d\u092c\u093e|\u092a\u0948\u0915\u093f\u0902\u0917|\u0910\u092a', re.I)


def _polarity_product_subject(prefix, item):
    products = [match.end() for match in _POLARITY_PRODUCT.finditer(prefix)]
    if item.get('title') and item['title'].casefold() in prefix.casefold():
        products.append(prefix.casefold().rfind(item['title'].casefold()) + len(item['title']))
    if not products:
        return False
    others = [match.end() for match in _POLARITY_OTHER_SUBJECT.finditer(prefix)]
    return not others or max(products) > max(others)


def _polarity_hypothetical_requirement(clause, match, pattern):
    """An opening predicate may be hypothetical; another condition is not it."""
    prefix = clause[:match.start()]
    report = _POLARITY_REPORT.search(prefix)
    if report:
        prefix = prefix[report.end():]
        prefix = re.sub(r'^\s*(?:(?:hai|hain|\u0939\u0948|\u0939\u0948\u0902)\s+)?(?:(?:that|ki|\u0915\u093f)\s+)?', '', prefix, flags=re.I)
    opener = (r'(?:if|suppose|hypothetically|agar|yadi|\u092f\u0926\u093f|\u0905\u0917\u0930|\u0915\u093e\u0936)')
    subject = (r'(?:(?:the|your|this|these|those)\s+)?(?:products?|items?|it|they)|'
               r'(?:(?:yeh|yah|ye|aapka|aapki)\s+)?(?:products?|items?)|'
               r'(?:(?:\u092f\u0939|\u092f\u0947|\u0906\u092a\u0915\u093e)\s+)?(?:\u0909\u0924\u094d\u092a\u093e\u0926|\u0938\u093e\u092e\u093e\u0928|\u0935\u0938\u094d\u0924\u0941)')
    # A separate predicate, comma or conjunction before this match closes the
    # condition. Permit only the item subject and counterfactual linking verbs.
    if re.fullmatch(r'\s*' + opener + r'\s+(?:' + subject + r')\s*(?:(?:were|was|are|is|had\s+to)\s*)?', prefix, re.I):
        return True
    return pattern is _POLARITY_ONLY_ITEMS and bool(re.fullmatch(r'\s*' + opener + r'\s*', prefix, re.I))


def _polarity_inspection_exception(clause, match):
    """Skip only a positive damage-item exception with a local inspection aim."""
    prefix = clause[:match.start()]
    local = re.split(r'[,;]|\b(?:and|but|however|yet|then)\b', clause[match.end():], maxsplit=1, flags=re.I)[0]
    local_prefix = re.split(r'[,;]|\b(?:and|but|however|yet|then)\b', prefix, flags=re.I)[-1]
    if re.search(r'\b(?:ordinary|normal|standard)\b|\u0938\u093e\u092e\u093e\u0928\u094d\u092f', local_prefix + ' ' + local, re.I):
        return False
    header = re.split(r'[,;]|\b(?:then|to)\b|\u0924\u094b', prefix, maxsplit=1, flags=re.I)[0]
    if not re.match(r'^\s*(?:for\b|if\b|when\b|in\s+(?:the\s+)?case\s+of\b|agar\b|yadi\b|\u092f\u0926\u093f|\u0905\u0917\u0930)', header, re.I):
        return False
    if not _has_exception(header):
        return False
    # An article cannot obscure a negated exception: 'not a damaged item'.
    for event in _EXCEPTION.finditer(header):
        before = header[max(0,event.start()-45):event.start()]
        after = header[event.end():event.end()+20]
        if re.search(r"\b(?:not|never|isn't|wasn't|nahi|nahin)\s+(?:(?:a|an|the|physically|visibly|actually)\s+)*$", before, re.I):
            return False
        if re.search(r'(?:\u0928\u0939\u0940\u0902)\s*$', before) or re.match(r'\s*(?:nahi\b|nahin\b|\u0928\u0939\u0940\u0902)', after, re.I):
            return False
    return bool(re.search(r'\b(?:for|during)\s+(?:an?\s+)?(?:inspection|testing|assessment)\b|'
                          r'\b(?:inspection|testing|assessment)\s+ke\s+liye\b|'
                          r'(?:\u091c\u093e\u0902\u091a|\u0928\u093f\u0930\u0940\u0915\u094d\u0937\u0923)\s+\u0915\u0947\s+\u0932\u093f\u090f', local, re.I))


def _check_requirement_polarity(answer, policy, item):
    expected = policy['requirements'].get('opened')
    if type(expected) is not bool:
        return
    for clause in re.split(r'[.!;\u0964\n]+', answer):
        if '?' in clause:
            continue
        for pattern in (_POLARITY_MODAL, _POLARITY_REQUIRED, _POLARITY_ONLY_IF,
                        _POLARITY_ONLY_ITEMS, _POLARITY_HI, _POLARITY_ROMAN):
            for match in pattern.finditer(clause):
                prefix = clause[:match.start('state')]
                local_prefix = re.split(r'[,;]|\b(?:and|but|however|yet|then)\b', prefix, flags=re.I)[-1]
                modal_prefix = re.split(r'[,;]|\b(?:and|but|however|yet|then)\b', clause[:match.start()], flags=re.I)[-1]
                if pattern is _POLARITY_MODAL and re.search(r"(?:\b(?:not|never)|don't|doesn't|cannot|can't)\s*$", modal_prefix, re.I):
                    continue
                if _polarity_hypothetical_requirement(clause, match, pattern):
                    continue
                if _polarity_inspection_exception(clause, match):
                    continue
                if re.search(r"\b(?:do\s+not|does\s+not|don't|doesn't|never)\s+(?:say|state|require|mandate)\b|"
                             r'(?:\u0928\u0939\u0940\u0902|\bnahi\b|\bnahin\b).{0,12}(?:\u0915\u0939|\bkeht)', local_prefix, re.I):
                    continue
                if not _polarity_product_subject(prefix[-160:], item):
                    # In 'only opened items...', the product subject follows.
                    if pattern is not _POLARITY_ONLY_ITEMS:
                        continue
                if pattern in (_POLARITY_HI, _POLARITY_ROMAN) and match['norm'] in ('\u0939\u094b\u0902', 'hon'):
                    report = _POLARITY_REPORT.search(prefix)
                    if not report:
                        continue
                state = match['state'].casefold()
                required = not (state == 'unopened' or state.startswith('\u0905\u0928\u0916\u0941\u0932'))
                negations = list(_POLARITY_NEGATION.finditer(match['phrase']))
                if len(negations) > 1:
                    continue
                if negations:
                    required = not required
                if required is not expected:
                    raise ValueError('contradicted_return_condition_polarity:opened')
