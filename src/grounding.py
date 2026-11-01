"""Evidence validation and bindings for deterministic operational guards.

These checks reject common unsupported outputs; they are not semantic proof.
Policy replies use the current retrieved source text, not authored plans.
"""
import hashlib
import json
import os
import re
from decimal import Decimal
from datetime import date
import calendar
from pathlib import Path

from .llm import LLMUnavailable
from .normalize import ascii_digits


def fingerprint(source):
    fields = {k: source.get(k, '') for k in ('id', 'text', 'status', 'effective_from', 'version', 'doc_type')}
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def compatible(ids, sources):
    """Every policy dependency must be retrieved and match the reviewed version."""
    bindings = json.loads(Path(__file__).with_name('rule_bindings.json').read_text(encoding='utf-8'))
    by_id = {s['id']: s for s in sources}
    return bool(ids) and all(cid in by_id and (cid.startswith(('products.csv:', 'pincodes.csv:')) or bindings.get(cid) == fingerprint(by_id[cid])) for cid in ids)


# This finite vocabulary catches explicit number words as well as digit forms.
# It does not attempt general natural-language entailment or every numeral form.
_SMALL = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
_SMALL.update(dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10))))
_SMALL.update({'एक': 1, 'दो': 2, 'तीन': 3, 'चार': 4, 'पांच': 5, 'पाँच': 5, 'छह': 6, 'सात': 7, 'आठ': 8, 'नौ': 9, 'दस': 10, 'बीस': 20, 'तीस': 30, 'चालीस': 40, 'पचास': 50, 'साठ': 60, 'सत्तर': 70, 'अस्सी': 80, 'नब्बे': 90})
_SCALES = {'hundred': 100, 'thousand': 1000, 'lakh': 100000, 'crore': 10000000, 'सौ': 100, 'हजार': 1000, 'हज़ार': 1000, 'लाख': 100000, 'करोड़': 10000000}
_NUMBER_WORD = '(?:' + '|'.join(map(re.escape, sorted(_SMALL.keys() | _SCALES.keys(), key=len, reverse=True))) + ')'
_WORD_NUMBERS = re.compile(r'(?<![A-Za-z\u0900-\u097f])' + _NUMBER_WORD + r'(?:[\s-]+(?:and\s+)?' + _NUMBER_WORD + r')*(?![A-Za-z\u0900-\u097f])', re.I)


def _numeric_text(text):
    def replace(match):
        total = current = 0
        for word in re.split(r'[\s-]+', match.group().casefold()):
            if word == 'and':
                continue
            if word in _SMALL:
                current += _SMALL[word]
            elif _SCALES[word] == 100:
                current = max(current, 1) * 100
            else:
                total += max(current, 1) * _SCALES[word]
                current = 0
        return str(total + current)
    return _WORD_NUMBERS.sub(replace, ascii_digits(text).replace(',', ''))


def numbers(text):
    return set(re.findall(r'\d+(?:\.\d+)?', _numeric_text(text)))


_UNITS = {
    'business_day': r'business\s+(?:days?|din)|working\s+(?:days?|din)|कार्य\s*दिवस(?:ों)?|कारोबारी\s+दिन',
    'calendar_day': r'calendar\s+days?|कैलेंडर\s+(?:दिन|दिवस)|calendar\s+din',
    'day': r'days?|दिन|din',
    'hour': r'hours?|hrs?|घंटे?|घण्टे?|ghante?',
    'minute': r'minutes?|mins?|मिनट',
    'money': r'rupees?|inr|रुपये|रुपए|रुपया',
    'year': r'years?|साल|वर्ष',
    'month': r'months?|महीने?|माह|mahina|mahine|mahino(?:n)?',
    'week': r'weeks?|हफ्ते?|सप्ताह',
    'percent': r'percent|per\s+cent|प्रतिशत|%',
}
_UNIT_PATTERN = '(?:' + '|'.join('(?P<' + name + '>' + pattern + ')' for name, pattern in _UNITS.items()) + ')'
_QUANTITIES = re.compile(r'(?P<first>\d+(?:\.\d+)?)(?:\s*(?:to|and|or|[-–]|से|se|तक)\s*(?P<last>\d+(?:\.\d+)?))?\s*-?\s*' + _UNIT_PATTERN + r'(?![A-Za-z\u0900-\u097f])', re.I)


def _quantity_date_spans(text):
    """Recognize valid full calendar spans, never partial numeric tokens."""
    months = {name.casefold(): number for names in (calendar.month_name, calendar.month_abbr)
              for number, name in enumerate(names) if number and name}
    named = re.compile(r'(?<![\w.+/-])(\d{1,2})(?:st|nd|rd|th)?\s+('
        + '|'.join(map(re.escape, sorted(months, key=len, reverse=True)))
        + r')\s+(\d{4})(?![\w.+/-])', re.I)
    iso = re.compile(r'(?<![\w.+/-])\d{4}-\d{2}-\d{2}(?![\w.+/-])')
    spans = []
    for pattern in (named, iso):
        for match in pattern.finditer(text):
            if re.match(r'\s*[-+/.]\s*\d', text[match.end():]):
                continue
            try:
                parsed = (date(int(match[3]), months[match[2].casefold()], int(match[1]))
                          if pattern is named else date.fromisoformat(match[0]))
            except ValueError:
                continue
            spans.append(match.span())
    return spans

def _quantities(text):
    normalized = _numeric_text(re.sub(r'(?<!\d),|,(?!\d)', ';', text))
    values = set()
    date_spans = _quantity_date_spans(normalized)
    for match in _QUANTITIES.finditer(normalized):
        unit = next(name for name in _UNITS if match.group(name) is not None)
        if unit == 'day':
            # A tightly bound explicit unit can precede a range in ordinary
            # Hinglish. Never promote an explicit calendar-day quantity or
            # carry a unit across punctuation/an unrelated clause.
            prefix = normalized[max(0, match.start()-70):match.start()]
            bound_unit = re.search(r'(?<![\w-])(?:business\s+(?:days?|din)|working\s+(?:days?|din))'
                         r'\s+(?:(?:(?:ko|mein|me|ke|ki|ka|are|is)\s+){0,2}|(?:range|window|period)\s+of\s+)$', prefix, re.I)
            if bound_unit and not re.search(r'\b(?:not|non|nahi|nahin)\s*[- ]*(?:(?:a|an)\s+)?$', prefix[:bound_unit.start()], re.I):
                unit = 'business_day'
        # A date's trailing year/day is not a duration range endpoint.
        # Require a real following quantity; bare date+unit stays checked.
        date_endpoint = match.group('last') and any(
            begin <= match.start('first') and match.end('first') <= end
            and not (begin <= match.start('last') and match.end('last') <= end)
            for begin, end in date_spans)
        if not date_endpoint:
            values.add((match.group('first'), unit))
        if match.group('last'):
            values.add((match.group('last'), unit))
    for match in re.finditer(r'(?:₹|\bINR\s*)\s*(\d+(?:\.\d+)?)', normalized, re.I):
        values.add((match.group(1), 'money'))
    return values


def _fact_quantities(facts):
    """Collect typed scalar quantities recursively, including catalog lists."""
    values = set()
    if isinstance(facts, (list, tuple)):
        for child in facts:
            if isinstance(child, (dict, list, tuple)):
                values.update(_fact_quantities(child))
        return values
    if not isinstance(facts, dict):
        return values
    for key, value in facts.items():
        if isinstance(value, (dict, list, tuple)):
            values.update(_fact_quantities(value))
            continue
        name = key.casefold()
        unit = ('money' if 'inr' in name or 'amount' in name else
                'business_day' if 'business' in name and 'day' in name else
                'calendar_day' if 'return_days' in name or 'calendar' in name else
                'hour' if 'hour' in name else
                'month' if 'month' in name else
                'year' if 'year' in name else None)
        if unit and isinstance(value, str) and re.fullmatch(r'\d+(?:\.\d+)?', value):
            value = float(value) if '.' in value else int(value)
        if unit and isinstance(value, (int, float)) and not isinstance(value, bool):
            values.add((str(value), unit))
    return values

def _duration_months(quantity):
    number, unit = quantity
    return Decimal(number) * (12 if unit == 'year' else 1) if unit in {'month', 'year'} else None


def _quantity_supported(quantity, support):
    number, unit = quantity
    if quantity in support or (unit == 'day' and (number, 'calendar_day') in support):
        return True
    duration = _duration_months(quantity)
    return duration is not None and any(_duration_months(candidate) == duration for candidate in support)


def _duration_numeric_validation_text(answer, support):
    # Exact year/month conversion changes only numeric validation text.
    # Each replacement uses an actual supported quantity, never a new allowance.
    def replace(match):
        unit = 'year' if match.group('year') is not None else 'month' if match.group('month') is not None else None
        if unit is None:
            return match[0]
        terms = [match['first']] + ([match['last']] if match['last'] else [])
        replaced = []
        for number in terms:
            quantity = (number, unit)
            if quantity in support:
                candidate = quantity
            else:
                duration = _duration_months(quantity)
                candidates = sorted(candidate for candidate in support if _duration_months(candidate) == duration)
                if not candidates:
                    return match[0]
                candidate = candidates[0]
            replaced.append(candidate[0] + ' ' + candidate[1])
        return ' and '.join(replaced)
    return _QUANTITIES.sub(replace, _numeric_text(answer))


_COMPLETED = r'(?:cancelled|canceled|approved|issued|processed|booked|created|raised|refunded|initiated|scheduled|credited|transferred|completed)'
_NEGATION = re.compile(r"\b(?:no|not|never|without|cannot|can['’]?t|doesn['’]?t|isn['’]?t|excluded|nahi|nahin)\b|नहीं|नहि", re.I)
_CONCEPTS = {
    'return': r'return|रिटर्न|वापस|लौटा', 'refund': r'refund|रिफंड|रिफ़ंड',
    'cancel': r'cancel|रद्द|कैंसिल|कैंसल', 'ship': r'ship|dispatch|शिप|भेज',
    'wallet': r'wallet|वॉलेट', 'bank': r'bank|बैंक',
    'pickup': r'pick.?up|collection|पिकअप', 'fee': r'fee|charge|शुल्क|फीस|फ़ीस',
    'warranty': r'warranty|वारंटी', 'assured': r'assured|अश्योर्ड',
    'marketplace': r'marketplace|seller|मार्केटप्लेस|विक्रेता',
    'compensation': r'compensation|मुआवजा|मुआवज़ा', 'credit': r'credit|क्रेडिट',
}


def _english_pronoun_prerequisite_view(answer):
    """Recognize only a complete generic present policy-clock answer.

    Any other clause/prose declines masking, preserving every consequent or
    neighboring claim without a lexical list of claim paraphrases.
    """
    operation = r'(?:refund|payment|return|pickup|request|order|ticket)'
    route = r'(?:[ \t]+(?:to|via|through)[ \t]+(?P<route>[A-Za-z]{1,32}))?'
    number = r'(?:\d+(?:\.\d+)?|' + _NUMBER_WORD + r'(?:[ -]+' + _NUMBER_WORD + r')*)'
    duration = (r'(?:(?:from|between)[ \t]+)?' + number
        + r'(?:(?:[ \t]+(?:to|and|through)[ \t]+|[ \t]*[-–][ \t]*)' + number + r')?'
        + r'[ \t]+(?:(?:business|working|calendar)[ \t]+)?(?:minutes?|hours?|days?|weeks?)')
    clock = re.compile(
        r'(?P<matrix>\s*(?:a|an)[ \t]+' + operation + route
        + r'[ \t]+takes[ \t]+' + duration + r'[ \t]+)'
        + r'after[ \t]+it[ \t]+is[ \t]+' + _COMPLETED
        + r'(?P<ending>[ \t]*[.!?।]?\s*)', re.I)
    match = clock.fullmatch(answer)
    if not match:
        return answer
    non_generic = re.compile(
        r'\b(?:I|we|my|our|you|your|me|us|he|she|his|her|they|their|its|'
        r'is|are|was|were|had|has|have|already|now|today|yesterday|earlier|previously|currently|on|at|since|during|'
        r'done|complete|guarantee(?:d)?)\b|\b[A-Za-z]+ed\b', re.I)
    if non_generic.search(match['route'] or ''):
        return answer
    return match['matrix'] + 'after a generic prerequisite' + match['ending']

def _hindi_generic_prerequisite_view(answer):
    """Mask only a bounded prerequisite with a closed predicate grammar.

    Extra modifiers, recipients and dates do not fit this finite grammar.
    Other completion/person cues decline masking to preserve anaphoric claims.
    """
    subject = r'(?:ऑर्डर|आदेश|रिफ़ंड|रिफंड|भुगतान|पिकअप|पार्सल|टिकट|रिटर्न)'
    perfective = r'(?:गया|गई|गए|चुका|चुकी|चुके)'
    passive = r'(?:गया|गई|गए)'
    state = r'(?:शिप|पूरा|पूर्ण|बंद|रद्द|जारी|कैंसिल|कैंसल)'
    operation = r'(?:पूरा|पूर्ण|बंद|रद्द|जारी|कैंसिल|कैंसल)'
    predicate = (r'(?:(?:' + state + r'\s+)?हो\s+' + perfective
        + r'|' + operation + r'\s+(?:किया|की|किए)\s+' + passive
        + r'|(?:बनाया|बन)\s+' + passive + r'|(?:रद्द|जारी)\s+(?:हुआ|हुई|है))')
    grammar = re.compile(r'(?:(?:कोई(?:\s+भी)?|एक)\s+)?' + subject
        + r'\s+' + predicate + r'(?:\s+(?:है|हैं))?', re.I)
    person = re.compile(r'मैं|हम|आपने|तुमने|उसने|इसने|उन्होंने|इन्होंने|\b(?:I|we|you)\b', re.I)
    other_completed = re.compile(
        r'कर\s*(?:दिया|दी|दिए)|हो\s*(?:गया|गई|गए|चुका|चुकी|चुके)|'
        r'बना(?:या)?\s*(?:दिया|गया|गई|गए)|(?:किया|की|किए)\s*(?:गया|गई|गए)|'
        r'(?:रद्द|जारी)\s*(?:है|हुआ|हुई)|पूरा|पूर्ण|सम्पन्न')
    clauses = re.compile(
        r'(?P<lead>(?:^|(?<=[,;.!?।\n]))[ \t]*(?:अगर|यदि)[ \t]+)'
        r'(?P<condition>[^,;.!?।\n]{1,120}?)'
        r'(?P<boundary>[ \t]+तो(?=$|[ \t,;.!?।\n])|(?=[,;.!?।\n]))')

    def replace(match):
        if not grammar.fullmatch(match['condition'].strip()):
            return match[0]
        outside = answer[:match.start('condition')] + answer[match.end('condition'):]
        if person.search(outside) or other_completed.search(outside):
            return match[0]
        return match['lead'] + 'सामान्य शर्त' + match['boundary']

    return clauses.sub(replace, answer)

def _completed_action(answer):
    # A passive modifier naming a calculated value is not a performed order,
    # refund or ticket operation. Preserve the value and adjacent action text.
    answer = re.sub(r'गणना\s+की\s+गई\s+((?:अंतिम\s+)?(?:तारीख|तिथि|समयसीमा|राशि))',r'गणितीय \1',answer)
    answer = _english_pronoun_prerequisite_view(answer)
    # Completed operational outcomes are rendered by deterministic tool/state
    # code. Even a true-looking model assertion falls back for review there.
    # A generic prerequisite describes when a policy clock starts, rather than
    # asserting that this customer's action was performed. Remove only that
    # bounded clause; any completed claim in the following clause is checked.
    conditional = (r'\b(?:after|once|when|if)\s+(?:(?:the|a|an)\s+)?'
                   r'(?:refund|payment|return|pickup|request|order|ticket)s?\s+'
                   r'(?:is|are|has\s+been|have\s+been)\s+'
                   r'(?:(?:already|successfully)\s+)*' + _COMPLETED + r'\b')
    # A conditional generic policy consequence is not an assertion that the
    # assistant performed the action. Mask only this indefinite present-tense
    # predicate; actor-specific, past/perfect and other action claims remain.
    def generic_consequence(match):
        clause = match.group()
        antecedent = clause.split(',', 1)[0]
        if re.search(r'\b(?:was|were|had|has|have|already|yesterday|earlier|previously|failed|chose)\b', antecedent, re.I):
            return clause
        clause = re.sub(r'\ba refund is initiated\b(?!\s+(?:already|now|today|yesterday|on\s+\d))',
                        'refund initiation occurs', clause, flags=re.I)
        return re.sub(r'\b(?:a|the) refund is (?:initiated|processed)\b'
                      r'(?=\s+(?:within|in)\s+(?:\d|' + _NUMBER_WORD + r'))',
                      'refund timing applies', clause, flags=re.I)
    conditional_view = re.sub(r'\b(?:If|When)\b[^.!?;\n]{1,240},[^.!?;\n]{0,400}',
                              generic_consequence, _hindi_generic_prerequisite_view(answer), flags=re.I)
    text = re.sub(conditional, '', conditional_view, flags=re.I)
    text = re.sub(r"\b(?:has|have|had|is|are|was|were)\s+not\s+(?:yet\s+)?(?:been\s+)?" + _COMPLETED, '', text, flags=re.I)
    patterns = [
        r'\b(?:I|we)\s+(?:(?:have|had|already|just|now|successfully)\s+)*' + _COMPLETED,
        r'\b(?:has|have|had|is|are|was|were)\s+(?:(?:been|already|just|now|successfully)\s+)*' + _COMPLETED,
        r'\b(?:order|refund|return|replacement|pickup|ticket|request|cancellation|booking)\s+(?:(?:now|already|successfully)\s+)*(?:complete(?:d)?|done|' + _COMPLETED + r')\b',
        r'\bguarantee(?:d)?\b',
        r'(?:ऑर्डर|रिफंड|रिफ़ंड|टिकट|रिटर्न(?!ेबल)|भुगतान|पिकअप|रद्द|कैंसिल|कैंसल|मंजूर|मंज़ूर|जारी).{0,45}(?:कर\s*(?:दिया|दी|दिए)|हो\s*(?:गया|गई|गए|चुका|चुकी)|बना(?:या)?\s*(?:दिया|गया|गई)|(?:किया|की|किए)\s*(?:गया|गई|गए)|रद्द\s*(?:है|हुआ)|जारी\s*(?:है|हुआ))',
        r'\b(?:order|refund|return|ticket|replacement|pickup|payment|cancel|approve|book|issue|process)\w*.{0,45}\b(?:kar\s*diya|kar\s*di|ho\s*gaya|ho\s*gayi|ho\s*chuka|ho\s*chuki)\b',
    ]
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def _preserve_negatives(answer, required_text):
    clauses = re.split(r'[.!?;।]', answer)
    for required in re.split(r'[.!?;।]', required_text):
        if not _NEGATION.search(required):
            continue
        concepts = {name for name, pattern in _CONCEPTS.items() if re.search(pattern, required, re.I)}
        if not any(_NEGATION.search(clause) and all(re.search(_CONCEPTS[name], clause, re.I) for name in concepts) for clause in clauses):
            raise ValueError('omitted_negative_condition')


# Only the reviewed answer plan contributes required aspects. A retrieved
# section may mention unrelated policies; those must not become new obligations.
# Synonym families permit ordinary paraphrases/translations without exact-text
# copying. This finite coverage filter is not a semantic entailment model.
_ASPECTS = {
    'brand_cover': r'\b(?:brand|manufacturer|maker)\b|ब्रांड|निर्माता',
    'assured_cover': r'assured|अश्योर्ड',
    'additional_cover': r'in addition|additional|on top of|supplement|separate|extra cover|अतिरिक्त|अलग|दोनों|alag|dono',
    'service_centre': r'service cent(?:re|er)|manufacturer.{0,25}(?:support|service)|repair cent(?:re|er)|सर्विस सेंटर|सेवा केंद्र',
    'order_self_service': r'my orders|order (?:page|section|history)|ऑर्डर (?:पेज|सेक्शन|विभाग)|मेरे ऑर्डर',
    'seal_condition': r'\bseal(?:ed|s)?\b|सील',
    'unopened_condition': r'\bunopened\b|not.{0,12}opened|बंद|बिना खोल|khola nahi',
    'unused_condition': r'\bunused\b|not.{0,12}used|बिना इस्तेमाल|इस्तेमाल नहीं|use nahi',
    'packaging': r'packag(?:e|es|ing)|packing|पैकिंग|पैकेज',
    'tags': r'\btags?\b|टैग',
    'accessories': r'accessor(?:y|ies)|एक्सेसरी|सहायक सामान',
    'free_gifts': r'\bgifts?\b|उपहार|तोहफ',
    'photos': r'photo|picture|image|फ़ोटो|फोटो|तस्वीर',
    'quality_check': r'quality (?:check|inspection)|\bqc\b|inspection|गुणवत्ता जाँच|क्वालिटी चेक',
    'initiation': r'initiat|\bstart|\bbegin|commenc|शुरू|आरंभ|प्रारंभ|shuru',
    'stock': r'\bstock\b|inventory|स्टॉक|उपलब्धता',
    'refund_reference': r'\brrn\b|refund reference|tracking reference|रिफंड संदर्भ|रिफ़ंड संदर्भ|संदर्भ संख्या|reference number',
    'bank_trace': r'\btrac(?:e|ing)\b|बैंक.{0,30}(?:जाँच|पता)|bank.{0,25}(?:check|track)|bank se.{0,25}(?:pata|jaanch)',
    'payment_method': r'payment.method|mode of payment|भुगतान.{0,15}(?:तरीक|माध्यम)',
    'sale_condition': r'festive|\bsale\b|promotion|त्योहार|सेल|बिक्री',
    'placement_date': r'\b(?:placed|placement)\b|order(?:ing|ed)? date|ऑर्डर.{0,15}(?:तारीख|दिया|किया)|\bplac(?:e|ed|ement)\b',
}
# Relations are checked with separate detection/response vocabularies so a
# paraphrase such as "identical return rules" can preserve "same policy".
_RELATIONS = {
    'seller_policy_equivalence': (
        r'(?:same|identical).{0,35}(?:polic|return)|(?:all|every).{0,25}seller',
        r'(?:same|identical|uniform|common).{0,40}(?:polic|rules?|return)|(?:all|every).{0,30}seller|समान.{0,25}(?:नीति|नियम)|एक.{0,15}(?:नीति|नियम)|same.{0,30}(?:policy|rule|return)'),
    'policy_precedence': (
        r'current policy|supersed|outrank|specific.{0,25}polic|policy.{0,25}(?:overrid|precedence)',
        r'current|supersed|outrank|overrid|govern|takes precedence|specific.{0,25}(?:polic|rule)|वर्तमान|मौजूदा|प्राथमिकता|पुरान'),
}

def _preserve_aspects(answer, required_text):
    """Reject omitted salient plan aspects, including those without numbers."""
    for name, pattern in _ASPECTS.items():
        if re.search(pattern, required_text, re.I) and not re.search(pattern, answer, re.I):
            raise ValueError('omitted_policy_aspect:' + name)
    for name, (required_pattern, answer_pattern) in _RELATIONS.items():
        if re.search(required_pattern, required_text, re.I) and not re.search(answer_pattern, answer, re.I):
            raise ValueError('omitted_policy_aspect:' + name)


def validate_generated(value, sources, required_ids=(), facts=None, required_text=''):
    """Reject unsupported citations/quantities and common forged outcomes.

    These conservative lexical checks allow paraphrases but do not establish
    arbitrary semantic entailment, actor identity, or every policy condition.
    A rejection triggers a bounded generation repair and then honest abstention.
    """
    if not isinstance(value, dict) or value.get('covered') is not True:
        raise ValueError('not_covered')
    answer = value.get('answer')
    citations = value.get('citations')
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 1800:
        raise ValueError('invalid_answer')
    if not isinstance(citations, list) or not citations:
        raise ValueError('missing_citations')
    by_id = {s['id']: s for s in sources}
    used, quotes = [], []
    for citation in citations:
        if not isinstance(citation, dict):
            raise ValueError('invalid_citation')
        cid, quote = citation.get('id'), citation.get('quote')
        if not isinstance(cid, str) or cid not in by_id or not isinstance(quote, str) or len(quote.strip()) < 8 or quote not in by_id[cid]['text']:
            raise ValueError('unsupported_citation')
        used.append(cid)
        quotes.append(quote)
    if not set(required_ids).issubset(used):
        raise ValueError('incomplete_policy_coverage')
    evidence = '\n'.join(quotes)
    # Unquoted numbers elsewhere in a cited section cannot authorize a claim.
    allowed = numbers(evidence + '\n' + json.dumps(facts or {}, ensure_ascii=False))
    quantity_support = _quantities(evidence) | _fact_quantities(facts)
    if not numbers(_duration_numeric_validation_text(answer, quantity_support)).issubset(allowed):
        raise ValueError('unsupported_number')
    if any(not _quantity_supported(quantity, quantity_support) for quantity in _quantities(answer)):
        raise ValueError('unsupported_quantity_unit')
    if required_text and not numbers(required_text).issubset(numbers(answer)):
        raise ValueError('omitted_numeric_constraint')
    answer_quantities = _quantities(answer)
    if any(not _quantity_supported(quantity, answer_quantities) for quantity in _quantities(required_text)):
        raise ValueError('omitted_quantity_constraint')
    if _completed_action(answer):
        raise ValueError('unsupported_action')
    if re.search(r'\b\d{10,}\b|[\w.+-]+@[\w.-]+\.[a-z]{2,}', ascii_digits(answer), re.I):
        raise ValueError('private_identifier')
    _preserve_negatives(answer, required_text)
    _preserve_aspects(answer, required_text)
    return answer.strip(), list(dict.fromkeys(used))

def generate(client, query, language, sources, plan=None, *, private=False):
    """Compatibility adapter; authored plans never enter document generation."""
    from .document_answers import document_reply
    result=document_reply(client,query,language,sources,private=private)
    return result['answer'],result['source_ids']


def abstention(language):
    return {'en': "I don't have enough supported information in the retrieved documents. I can help you reach a human colleague.",
            'hi': 'मिले हुए दस्तावेज़ों में पर्याप्त जानकारी नहीं है। मैं मानव सहयोगी से संपर्क करने में मदद कर सकती हूँ।',
            'hi-en': 'Documents mein is bare mein jaankari nahi hai. Human colleague se connect karne mein help kar sakti hoon.'}[language]
