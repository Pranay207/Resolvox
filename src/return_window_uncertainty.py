"""Finite checks for unqualified personal windows with unresolved placement.

The caller supplies a placement status independently rebound to current source
text. This guard does not establish full answer coverage or semantic entailment.
"""
from datetime import date
import json
import re

_RETURN = re.compile(r'\breturn(?:s|ing|ed)?\b|\b(?:lautane|lautana|wapas|vaapas)\b|लौट|वापस|रिटर्न', re.I)
_REFUND = re.compile(r'\brefund\w*\b|रिफंड|रिफ़ंड|धनवापसी', re.I)
_WINDOW = re.compile(r'\breturn\s+(?:window|deadline|period|duration|time)\b|रिटर्न\s*(?:अवधि|समय|विंडो)', re.I)
_LOGISTICS = re.compile(
    r'\b(?:pick[ -]?up|collect(?:ion|ed)?|shipment|shipping|courier|carrier|warehouse|transit|arriv\w*|reach\w*|god[aou]am|pahunch\w*)\b|'
    r'पिकअप|संग्रह|गोदाम|कूरियर|शिपमेंट|पार्सल|पहुँच|पहुंच', re.I)
_REQUEST = re.compile(
    r'\b(?:request|initiate|raise|submit|apply\s+for)\b.{0,30}\breturn\b|'
    r'\breturn\s+(?:request|eligibility)\b|\byou\b.{0,50}\b(?:to\s+return|can\s+return|may\s+return|must\s+return)\b|'
    r'रिटर्न\s*(?:अनुरोध|करने)|वापस\s*करने|\breturn\s+(?:request|karne)\b', re.I)
_PERSONAL = re.compile(
    r'\b(?:your|you|this\s+(?:item|order|purchase|product|unit))\b|'
    r'आपक[ाीेो]|आप\b|इस\s+(?:वस्तु|सामान|उत्पाद|ऑर्डर)|'
    r'\b(?:aapk[aeio]|aapko|aap|is\s+(?:item|order|product))\b', re.I)
_GENERAL = re.compile(
    r'\b(?:standard|general|ordinary|normal|normally|usually|regular)\b|'
    r'सामान्य|आम\s*तौर|आमतौर|नियमित|\b(?:samanya|saamanya|aam\s+taur)\b', re.I)
_UNCERTAIN = re.compile(
    r"\b(?:cannot|can't|do\s+not|don't|unable\s+to)\s+(?:confirm|know|determine|verify)\b|"
    r'\bnot\s+(?:confirmed|known|determined|verified)\b|'
    r'पुष्टि.{0,15}नहीं|नहीं.{0,15}(?:पता|पुष्टि)|पता\s+नहीं|'
    r'\b(?:confirm|pata).{0,15}\b(?:nahi|nahin)\b|\b(?:nahi|nahin).{0,15}\b(?:pata|confirm)\b', re.I)
_QUESTION = re.compile(
    r'^\s*(?:is|are|can|could|does|do|would|will|what|which|when|whether|kya|kab)\b|^\s*(?:क्या|कब|कौन)', re.I)
_UNIVERSAL = re.compile(
    r'\b(?:regardless|irrespective|whatever|always|only)\b|हमेशा|चाहे|सिर्फ|केवल|'
    r'\b(?:hamesha|chahe|sirf|keval)\b', re.I)
_OTHER = re.compile(r'\b(?:other|another|different|alag|doosr[aei])\b|दूसर|अलग', re.I)
_MONTHS = (
    ('January', 'Jan', 'जनवरी'), ('February', 'Feb', 'फरवरी', 'फ़रवरी'),
    ('March', 'Mar', 'मार्च'), ('April', 'Apr', 'अप्रैल'), ('May', 'मई'),
    ('June', 'Jun', 'जून'), ('July', 'Jul', 'जुलाई'), ('August', 'Aug', 'अगस्त'),
    ('September', 'Sep', 'Sept', 'सितंबर', 'सितम्बर'),
    ('October', 'Oct', 'अक्टूबर', 'अक्तूबर'), ('November', 'Nov', 'नवंबर', 'नवम्बर'),
    ('December', 'Dec', 'दिसंबर', 'दिसम्बर'),
)


def _catalog_names(sources, category, *, different=False):
    """Names count only when actual supplied catalog JSON binds the category."""
    names = set()
    values = sources.values() if isinstance(sources, dict) else sources
    for source in values:
        if (not isinstance(source, dict) or source.get('doc_type') != 'catalog'
                or source.get('status') != 'current'):
            continue
        try:
            row = json.loads(source.get('text', ''))
        except (ValueError, TypeError):
            continue
        if (not isinstance(row, dict) or not isinstance(row.get('return_category'), str)
                or (row['return_category'] == category) == different):
            continue
        title = row.get('title')
        if isinstance(title, str):
            names.update(name.casefold().strip() for name in (title, title.split(',', 1)[0])
                         if len(name.strip()) >= 4)
    return names


def _date_pattern(value, normalizer):
    parsed = date.fromisoformat(value)
    forms = [value]
    for month in _MONTHS[parsed.month - 1]:
        forms.extend((f'{parsed.day} {month} {parsed.year}', f'{parsed.day:02d} {month} {parsed.year}',
                      f'{parsed.day} {month}', f'{parsed.day:02d} {month}'))
    return '(?:' + '|'.join(re.escape(normalizer(form.casefold())) for form in forms) + ')'


def _ordinary_placement_condition(clause, status, normalizer):
    """Recognize a local condition selecting outside the actual source range."""
    if _OTHER.search(clause) or _UNIVERSAL.search(clause):
        return False
    conditional = re.search(r'\b(?:if|provided|assuming|when|whether|unless|agar|yadi)\b|यदि|अगर', clause, re.I)
    if not conditional:
        return False
    condition = clause[conditional.start():]
    years = set(re.findall(r'(?<!\d)\d{4}(?!\d)', condition))
    if not years <= {status['placed_from'][:4], status['placed_through'][:4]}:
        return False
    placement = r'(?:\b(?:placed|ordered|order\s+(?:kiya|kiyaa|hua)|place\s+(?:hua|kiya))\b|ऑर्डर.{0,25}(?:किया|दिया)|ऑर्डर.{0,25}प्लेस)'
    if not re.search(placement, condition, re.I):
        return False
    begin = _date_pattern(status['placed_from'], normalizer)
    end = _date_pattern(status['placed_through'], normalizer)
    if conditional.group().casefold() == 'unless':
        # The ordinary branch excludes the actual source range. Do not
        # accept a reversed range, outside condition or negated placement.
        if re.search(r'\b(?:not|no|never|outside|before|after|nahi|nahin)\b|नहीं', condition, re.I):
            return False
        bounded = r'\b(?:placed|ordered)\s+between\s+' + begin + r'\s+(?:and|to)\s+' + end
        return bool(re.search(bounded, condition, re.I))
    before = re.search(r'(?:\bbefore\s+' + begin + r'|' + begin + r'\s*(?:से\s*पहले|se\s+pehle))', condition, re.I)
    after = re.search(r'(?:\bafter\s+' + end + r'|' + end + r'\s*(?:के\s*बाद|ke\s+baad))', condition, re.I)
    if re.search(r'\bnot\b|नहीं|\b(?:nahi|nahin)\b', condition, re.I):
        before = after = None
    outside = re.search(r'\b(?:outside|not\s+(?:placed|ordered)\s+(?:between|during))\b|के\s*बाहर|से\s*बाहर|\bbahar\b', condition, re.I)
    exact_range = re.search(begin, condition, re.I) and re.search(end, condition, re.I)
    deictic_range = re.search(r'\b(?:this|that|the|stated|exception)\s+(?:period|range|window)\b|इस\s*अवधि|\bis\s+(?:period|avadhi|range)\b', condition, re.I)
    explicit_date = re.search(r'\b\d{4}\b|\d{1,2}\s+(?:' + '|'.join(re.escape(name.casefold()) for names in _MONTHS for name in names) + ')', condition, re.I)
    return bool(before or after or (outside and (exact_range or (deictic_range and not explicit_date))))


_MISSING_PLACEMENT = re.compile(
    r"\b(?:order|placement|purchase)\s+date\b.{0,65}\b(?:unknown|unavailable|missing|not\s+(?:provided|supplied|given|known)|isn['’]t\s+(?:provided|given|known))\b|"
    r'\b(?:unknown|missing|unavailable)\s+(?:(?:order|purchase)\s+)?(?:placement|order|purchase)\s+date\b|'
    r'\bwithout\s+(?:(?:the|your|an?)\s+)?(?:order|placement|purchase)\s+date\b|'
    r'ऑर्डर\s*(?:की\s*)?(?:तारीख|तिथि|डेट).{0,40}(?:नहीं|अज्ञात|उपलब्ध\s*नहीं)|'
    r'\border\s+(?:ki\s+)?date\b.{0,40}\b(?:nahi|nahin|unknown|missing)\b', re.I)
_BRANCH_CHOICE = re.compile(
    r'\b(?:appl(?:y|ies|ied)|us(?:e|ing)|select\w*|default\w*|assum\w*)\b|'
    r'लागू|मान\s*(?:ले|लें)|\b(?:lagega|lagu|maan\s+le)\b', re.I)
_CAUSAL_CHOICE = re.compile(r'^\s*(?:therefore|so|hence|thus|because|since)\b|^\s*(?:इसलिए|इसीलिए|kyunki|isliye)\b', re.I)


def _check_missing_date_default(answer, status, duration, normalizer):
    text = normalizer(re.sub(r'[-\u2010-\u2015]', ' ', answer.casefold()))
    if not _MISSING_PLACEMENT.search(text):
        return
    for fragment in re.split(r'[.!?;।\n]+|\b(?:but|however|yet)\b|लेकिन|परन्तु|परंतु|\blekin\b', text):
        if not (_MISSING_PLACEMENT.search(fragment) or _CAUSAL_CHOICE.search(fragment)):
            continue
        if not duration.search(fragment):
            continue
        if _REFUND.search(fragment) and not _WINDOW.search(fragment):
            continue
        if _LOGISTICS.search(fragment) and not (_WINDOW.search(fragment) or _REQUEST.search(fragment)):
            continue
        if not (_RETURN.search(fragment) or re.search(r'\bwindow\b|अवधि', fragment) or _RETURN.search(text)):
            continue
        if _ordinary_placement_condition(fragment, status, normalizer):
            continue
        for choice in _BRANCH_CHOICE.finditer(fragment):
            prefix = re.split(r'[,;]|\b(?:and|so|therefore|hence|thus|then|isliye|kyunki)\b|इसलिए|इसीलिए', fragment[:choice.start()])[-1]
            if _UNCERTAIN.search(prefix):
                continue
            raise ValueError('unsupported_placement_exception_personal_window')


def check_unknown_placement_window(answer, status, sources, *, category, normalizer, query=None):
    """Reject unqualified individual standard durations while placement is unknown."""
    if not status or status.get('applicability') != 'unknown' or status.get('input_origin') != 'missing':
        return
    standard, alternate = status.get('standard_window_calendar_days'), status.get('window_calendar_days')
    if type(standard) is not int or type(alternate) is not int or standard == alternate:
        return
    names = _catalog_names(sources, category)
    other_names = _catalog_names(sources, category, different=True)
    duration = re.compile(r'(?<!\d)' + re.escape(str(standard)) +
                          r'\s*-?\s*(?:calendar\s*|कैलेंडर\s*)?(?:days?|din(?:on)?|दिन(?:ों|ो)?)(?![A-Za-z\u0900-\u097f])', re.I)
    _check_missing_date_default(answer, status, duration, normalizer)
    if query and _RETURN.search(query) and not _GENERAL.search(query):
        asks_duration = re.search(r'\b(?:window|period|duration|days?|how\s+long|kitn\w*\s+din)\b|कितन|दिन|अवधि', query, re.I)
        normalized = normalizer(re.sub(r'[-\u2010-\u2015]', ' ', answer.casefold()))
        alternate_duration = re.compile(r'(?<!\d)' + re.escape(str(alternate)) +
            r'\s*(?:calendar\s*|कैलेंडर\s*)?(?:days?|din(?:on)?|दिन(?:ों|ो)?)(?![A-Za-z\u0900-\u097f])', re.I)
        asks_date = re.search(r'(?:when|which\s+date|what\s+date).{0,50}(?:placed|ordered|purchase)|ऑर्डर.{0,30}कब|कब.{0,30}ऑर्डर|\b(?:order|place).{0,25}\bkab\b', answer, re.I)
        if asks_duration and duration.search(normalized) and not alternate_duration.search(normalized) and not asks_date:
            raise ValueError('unsupported_placement_exception_personal_window')
    for original in re.findall(r'[^.!?;।\n]+[.!?;।\n]?', answer):
        clause = normalizer(original.casefold().replace(',', ';'))
        if '?' in original and _QUESTION.search(original.casefold()):
            continue
        for fragment in re.split(r'\b(?:but|however|yet)\b|लेकिन|परंतु|\b(?:lekin|magar)\b', clause):
            for span in duration.finditer(fragment):
                split = r';|\b(?:and|aur)\b|और'
                left = re.split(split, fragment[:span.start()])[-1]
                right = re.split(split, fragment[span.end():], maxsplit=1)[0]
                local = left + span.group() + right
                if not _RETURN.search(local):
                    continue
                if _REFUND.search(local) and not _WINDOW.search(local):
                    continue
                # Collection and transport clocks do not determine how long a
                # customer has to request a return.
                if _LOGISTICS.search(local) and not (_WINDOW.search(local) or _REQUEST.search(local)):
                    continue
                named = any(re.search(r'(?<![\w])' + re.escape(name) + r'(?![\w])', local, re.I) for name in names)
                other_named = any(re.search(r'(?<![\w])' + re.escape(name) + r'(?![\w])', local, re.I) for name in other_names)
                if other_named and not named:
                    continue
                if not (_PERSONAL.search(local) or named):
                    continue
                # This narrow check preserves explicitly general/standard
                # explanations without proving full branch coverage.
                if _GENERAL.search(local) and not _UNIVERSAL.search(local):
                    continue
                if _UNCERTAIN.search(local):
                    continue
                if _ordinary_placement_condition(fragment, status, normalizer):
                    continue
                raise ValueError('unsupported_placement_exception_personal_window')
