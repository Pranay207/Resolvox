"""Finite consistency check for a leading yes and the first permission statement.

This checks wording consistency, not document entailment or policy truth.
Negative questions, later exceptions and an assistant's inability to act are
kept separate from a customer's requested permission.
"""
import re

_YES = re.compile(r'^(?:yes|yeah|haan|han|हाँ|हां)(?:\s*[,;:!।]\s*|\s+)', re.I)
_NEGATIVE_QUERY = re.compile(r"\b(?:not|cannot|can['’]t|isn['’]t|aren['’]t|nahi|nahin)\b|नहीं|नहि", re.I)
_BINARY = re.compile(r'(?:^|[.!?;।,]\s*)(?:can|could|may)\s+(?:i|we|you|it|this|that|the|my)\b|क्या|\bkya\b', re.I)
_ACTIONS = {
    'cancel': r'(?:\bcancel(?:s|l?ed|lations?|l?ing)?\b|कैंसिल|कैंसल|रद्द)',
    'return': r'(?:\breturn(?:s|ed|ing)?\b|रिटर्न|लौटा(?:या|ना)?|वापस)',
    'refund': r'(?:\brefund(?:s|ed|ing)?\b|रिफंड|रिफ़ंड)',
    'claim': r'(?:\bclaim(?:s|ed|ing)?\b|क्लेम|दावा)',
    'replace': r'(?:\breplac(?:e|ed|ements?)\b|बदला)',
}


def _positions(pattern, text):
    return [match.start() for match in re.finditer(pattern, text, re.I)]


def check_answer_acknowledgment(answer, query):
    if not isinstance(query, str) or not _BINARY.search(query) or _NEGATIVE_QUERY.search(query):
        return
    if query.count('?') > 1 or re.search(r'\b(?:how|help|assist|madad)\b|\bkaise\b|कैसे|मदद', query, re.I):
        return
    opening = _YES.match(answer.strip())
    if not opening:
        return
    body = answer.strip()[opening.end():]
    body = re.split(r'[.!?;।\n]|\b(?:but|however|otherwise|else|lekin|magar|varna)\b|लेकिन|मगर|अन्यथा', body, flags=re.I)[0]
    for action in _ACTIONS.values():
        if not re.search(action, query, re.I):
            continue
        negative = []
        for pattern in (
            r"\b(?:cannot|can['’]t|may\s+not)\s+be\s+" + action,
            r"\byou\s+(?:cannot|can['’]t|may\s+not)\s+(?:(?:get|receive|request|a|an|the)\s+){0,3}" + action,
            action + r'\s+(?:is|are)\s+not\s+(?:allowed|permitted|possible)\b',
            r'\bnot\s+(?:possible|allowed|permitted)\s+to\s+' + action,
            action + r'\s+नहीं\s+(?:(?:किया|की|किए|लौटाया|लिया|ली)\s+जा|हो)\s+सकत[ाीे]',
            r'(?:आप|तुम)\s+[^.!?;।]{0,32}' + action + r'\s+नहीं\s+(?:कर|ले|दे)\s+सकत[ाीे]',
            action + r'\s+(?:nahi|nahin)\s+(?:(?:kiya|ki|kiye|liya|diya)\s+ja|ho)\s+sakt[aei]\b',
            r'\b(?:aap|tum)\s+[^.!?;।]{0,32}' + action + r'\s+(?:nahi|nahin)\s+(?:kar|le|de)\s+sakt[aei]\b',
        ):
            negative.extend(_positions(pattern, body))
        if not negative:
            continue
        positive = []
        for pattern in (
            r'\bcan\s+(?:be\s+)?' + action,
            action + r'\s+(?:is|are)\s+(?:allowed|permitted|possible)\b',
            action + r'\s+(?:(?:किया|की|किए|कर|हो|जा|ले|दे)\s+){0,4}सकत[ाीे]',
            action + r'\s+(?:(?:kiya|ki|kiye|kar|ho|ja|le|de)\s+){0,4}sakt[aei]\b',
        ):
            positive.extend(_positions(pattern, body))
        if not positive or min(negative) <= min(positive):
            raise ValueError('contradictory_answer_acknowledgment')


def normalize_answer_acknowledgment(value, query):
    """Remove only a contradictory conversational prefix; never insert a claim.

    The unchanged suffix still requires every normal source and safety check.
    This is a recorded presentation edit, not another model generation.
    """
    if (not isinstance(value, dict)
            or set(value) != {'answer', 'covered', 'needs_clarification'}
            or value['covered'] is not True or value['needs_clarification'] is not False
            or not isinstance(value['answer'], str)):
        return value, None
    answer = value['answer'].strip()
    try:
        check_answer_acknowledgment(answer, query)
    except ValueError as error:
        if str(error) != 'contradictory_answer_acknowledgment':
            raise
        opening = _YES.match(answer)
        if opening is not None:
            edited = dict(value, answer=answer[opening.end():])
            return edited, {'kind': 'remove_contradictory_opening_acknowledgment',
                            'removed_prefix': answer[:opening.end()],
                            'inserted_text': '', 'remaining_text_unchanged': True}
    return value, None
