"""Finite checks for explicit date/category/window claims from current policies.

Values and dates are parsed from actual source clauses. This neither authors an
answer nor proves full semantic coverage; unrecognized phrasing is outside scope.
"""
from datetime import date, datetime
import hashlib
import re
from .grounding import _numeric_text

_DATE = r'\d{1,2}\s+[A-Za-z]+\s+\d{4}'
_SOURCE = re.compile(
    r'\bFrom\s+(?P<date>'+_DATE+r'),?\s+the\s+return\s+window\s+for\s+'
    r'(?P<category>[A-Za-z][A-Za-z ,&-]{0,100}?)\s+is\s+'
    r'(?P<days>\d+)\s+(?:calendar\s+)?days?\b', re.I)
_CLAIM = re.compile(
    r'\b(?:as\s+of|from|effective\s+from|starting\s+(?:on|from))\s+'
    r'(?P<date>'+_DATE+r'),?\s+(?:the\s+)?return\s+window\s+for\s+'
    r'(?P<category>[A-Za-z][A-Za-z ,&-]{0,100}?)\s+(?:is|was|will\s+be|became)\s+'
    r'(?:(?:now|only)\s+)?(?P<days>\d+)[ -]+(?:calendar[ -]+)?days?\b', re.I)
_HISTORY = re.compile(
    r'(?P<category>[A-Za-z][A-Za-z ,&-]{0,100}?)\s+delivered\s+before\s+'
    r'(?P<date>'+_DATE+r')\s+keep\s+the\s+(?:earlier|previous)\s+'
    r'(?P<days>\d+)[ -]+(?:calendar[ -]+)?day\s+window',re.I)
_UNIVERSAL_DELIVERY = re.compile(
    r'\b(?:regardless|irrespective)\s+of\s+(?:when|whether)\b.{0,55}\b(?:delivered|received)\b|'
    r'\b(?:regardless|irrespective)\s+of\s+(?:(?:the|its|your|their)\s+)?delivery\s+date\b|'
    r'\bno\s+matter\s+when\b.{0,55}\b(?:delivered|received)\b|'
    r'\bwhatever\s+(?:(?:the|its|your|their)\s+)?delivery\s+date\b',re.I)
_NEGATED_DESCRIPTION = re.compile(r'\b(?:not\s+(?:true|correct)|incorrect|false)\b[^.!?;\n]{0,60}$', re.I)


def _date(value):
    for pattern in ('%d %B %Y', '%d %b %Y'):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    return None


def _category(value):
    words = set(re.findall(r'[a-z]+', value.lower())) - {
        'the', 'and', 'for', 'of', 'category', 'products', 'items'}
    return frozenset(word[:-3]+'y' if word.endswith('ies') else
        word[:-1] if word.endswith('s') else word for word in words)


def _active(source, reference):
    if not isinstance(source, dict) or source.get('doc_type') != 'policy' or source.get('status') != 'current':
        return False
    if not isinstance(source.get('id'), str) or not isinstance(source.get('text'), str):
        return False
    if source.get('effective_from'):
        try:
            if date.fromisoformat(str(source['effective_from'])[:10]) > reference:
                return False
        except ValueError:
            return False
    return True


def check_effective_return_windows(answer, sources, *, reference_date):
    """Reject a recognized explicit transition claim that conflicts with its source."""
    reference = date.fromisoformat(str(reference_date)[:10])
    rules = []
    histories = []
    for source in sources:
        if not _active(source, reference):
            continue
        text = re.sub(r'[*`]', '', source['text'])
        for history in _HISTORY.finditer(text):
            boundary=_date(history['date'])
            if boundary:
                histories.append({'effective_on':boundary.isoformat(),'category':_category(history['category']),'days':int(history['days'])})
        for match in _SOURCE.finditer(text):
            effective = _date(match['date'])
            category = _category(match['category'])
            if effective is None or effective > reference or not category:
                continue
            rules.append({'effective_on': effective.isoformat(), 'category': category,
                'days': int(match['days']), 'source_id': source['id'],
                'source_sha256': hashlib.sha256(source['text'].encode()).hexdigest()})
    answer = _numeric_text(answer)
    checked = []
    for match in _CLAIM.finditer(answer):
        if _NEGATED_DESCRIPTION.search(answer[max(0, match.start()-80):match.start()]):
            continue
        effective = _date(match['date'])
        category = _category(match['category'])
        if effective is None or not category:
            continue
        applicable = [rule for rule in rules if rule['effective_on'] == effective.isoformat()
            and (category <= rule['category'] or rule['category'] <= category)]
        values = {rule['days'] for rule in applicable}
        if len(values) != 1:
            continue  # No arbitrary choice between absent/conflicting authority.
        if int(match['days']) not in values:
            raise ValueError('contradicted_effective_return_window')
        checked.extend({key: value for key, value in rule.items() if key != 'category'} for rule in applicable)
    for clause in re.split(r'[.!?;\n]+',answer):
        universal=_UNIVERSAL_DELIVERY.search(clause)
        if not universal or _NEGATED_DESCRIPTION.search(clause[:universal.start()]):
            continue
        if not re.search(r'\breturn\s+(?:window|period|duration)\b',clause,re.I):
            continue
        words=_category(clause)
        for rule in rules:
            if not (rule['category'] & words):
                continue
            peers=[other for other in rules if other['effective_on']==rule['effective_on'] and other['category']==rule['category']]
            if len({peer['days'] for peer in peers})!=1:
                continue
            earlier={history['days'] for history in histories if history['effective_on']==rule['effective_on'] and history['category'] and (history['category']<=rule['category'] or rule['category']<=history['category'])}
            if len(earlier)!=1 or rule['days'] in earlier:
                continue
            if re.search(r'(?<!\d)'+str(rule['days'])+r'[ -]+(?:calendar[ -]+)?days?\b',clause,re.I):
                raise ValueError('contradicted_effective_return_window')
    return checked
