"""Extract minimal unverified public event dates, without company policy values."""
from datetime import date, timedelta
import re
from .normalize import ascii_digits
from .grounding import _NUMBER_WORD, _numeric_text

_MONTHS = {}
for _number, _name in enumerate(('january','february','march','april','may','june','july','august','september','october','november','december'),1):
    _MONTHS[_name]=_number
    _MONTHS[_name[:3]]=_number
for _number, _name in enumerate(('\u091c\u0928\u0935\u0930\u0940','\u092b\u0930\u0935\u0930\u0940','\u092e\u093e\u0930\u094d\u091a','\u0905\u092a\u094d\u0930\u0948\u0932','\u092e\u0908','\u091c\u0942\u0928','\u091c\u0941\u0932\u093e\u0908','\u0905\u0917\u0938\u094d\u0924','\u0938\u093f\u0924\u0902\u092c\u0930','\u0905\u0915\u094d\u091f\u0942\u092c\u0930','\u0928\u0935\u0902\u092c\u0930','\u0926\u093f\u0938\u0902\u092c\u0930'),1):
    _MONTHS[_name]=_number
_MONTHS['\u092b\u093c\u0930\u0935\u0930\u0940']=2
_MONTH_RE='|'.join(re.escape(x) for x in sorted(_MONTHS,key=len,reverse=True))
_NAMED = re.compile(r'(?<!\d)(\d{1,2})(?:st|nd|rd|th)?\s+('+_MONTH_RE+r')(?![A-Za-z\u0900-\u097f])(?:\s*,?\s+(\d{4})(?!\d))?',re.I)
_ISO = re.compile(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)')
_RELATIVE = re.compile(r'(?<![\w.+,-])(?:today|yesterday|(?P<days>\d+|' + _NUMBER_WORD +
    r'(?:[ -]+(?:and\s+)?' + _NUMBER_WORD + r')*)\s+days?\s+ago)(?![\w])', re.I)
_CUES = {
    'placement': re.compile(
        r'\b(?:placed|ordered|bought|purchased)\b|\border\s+(?:kiya|diya|place(?:d)?)(?:\s+(?:tha|thi|hai))?\b|'
        r'\b(?:order|placement|purchase)\s+date\s+(?:is|was|:)\b|'
        r'(?:\u0911\u0930\u094d\u0921\u0930|\u0906\u0930\u094d\u0921\u0930)\s*(?:\u0915\u093f\u092f\u093e|\u0926\u093f\u092f\u093e)|'
        r'\u0916\u0930\u0940\u0926[\u093e\u0940]?|\u092e\u0902\u0917\u093e\u092f[\u093e\u0940]',re.I),
    'delivery': re.compile(
        r'\b(?:delivered|received|reached|arrived)\b|\bdelivery\s+(?:hua|hui|ho\s+gayi)\b|'
        r'\bdelivery(?:\s+date)?\s*(?::|(?:is|was|happened|occurred)\b)|\u0921\u093f\u0932\u0940\u0935\u0930|\u0921\u093f\u0932\u0940\u0935\u0930|'
        r'\u0935\u093f\u0924\u0930\u093f\u0924|\u092a\u0939\u0941\u0902\u091a[\u093e\u0940]',re.I),
}
_UNCERTAIN = re.compile(r"\b(?:if|assuming|suppose|maybe|perhaps|whether|not|never|nahi|nahin|agar|yadi)\b|"
                        r"\b(?:didn['\u2019]?t|wasn['\u2019]?t|hasn['\u2019]?t|haven['\u2019]?t|hadn['\u2019]?t|weren['\u2019]?t)\b|"
                        r'\u092f\u0926\u093f|\u0905\u0917\u0930|\u0936\u093e\u092f\u0926|\u0928\u0939\u0940\u0902?',re.I)
_SPLIT_SCOPE = re.compile(r'[,;]|\b(?:and|but|then|aur|lekin)\b|\u0914\u0930|\u0932\u0947\u0915\u093f\u0928',re.I)
_MONEY = re.compile(r'\b(?:refund|money|payment|wallet|bank)\b|\bpaise?\b|\u092a\u0948\u0938|\u0930\u093f\u092b',re.I)
_GOODS = re.compile(r'\b(?:item|product|parcel|package|order|goods|purchase)\b|\u0938\u093e\u092e\u093e\u0928|\u0909\u0924\u094d\u092a\u093e\u0926',re.I)
_OTHER_EVENT = re.compile(r'\b(?:refund|payment|transfer)\b.{0,35}\b(?:started|initiated|began|received|credited|completed|arrived|reached|shuru)\b|\b(?:shipped|dispatched|cancelled|canceled|inspected|picked\s+up)\b',re.I)


def _dates(text,reference):
    result=[]
    for match in _ISO.finditer(text):
        try: parsed=date.fromisoformat(match[0])
        except ValueError: continue
        result.append((match.start(),match.end(),parsed))
    for match in _NAMED.finditer(text):
        if any(a<=match.start()<b for a,b,_ in result): continue
        # An invalid/long explicit year must not fall back to an inferred year.
        if match[3] is None and re.match(r'\s*,?\s*\d{4,}',text[match.end():]): continue
        try: parsed=date(int(match[3]) if match[3] else reference.year,_MONTHS[match[2].casefold()],int(match[1]))
        except ValueError: continue
        # Do not guess a previous year for a yearless future date in a past claim.
        if match[3] is None and parsed>reference: continue
        if match[3] is None and re.search(r'\b(?:last|previous|next)\s+year\b|\b(?:pichle|agle)\s+saal\b|\u092a\u093f\u091b\u0932\u0947\s*\u0938\u093e\u0932',text[max(0,match.start()-20):match.end()+25],re.I): continue
        result.append((match.start(),match.end(),parsed))
    for match in _RELATIVE.finditer(text):
        if text[match.end():].casefold().startswith((chr(39)+'s',chr(8217)+'s')): continue
        before=text[max(0,match.start()-20):match.start()]
        after=_SPLIT_SCOPE.split(text[match.end():])[0][:65]
        # Nested calendar arithmetic and approximate quantities are not an
        # exact occurrence of this relative-day expression.
        if re.search(r'\b(?:about|around|roughly|approximately|approx|nearly|almost|over|under|up\s+to|at\s+least|at\s+most|more\s+than|less\s+than|something\s+like|give\s+or\s+take|maybe|perhaps)\b',before,re.I): continue
        if re.search(r'\b(?:before|after|from|since|until|till|ago|or)\s*(?:(?:just|exactly|right|only)\s+)*$|\b(?:days?|weeks?|months?|years?)\s+ago\b[^.!?;,]{0,20}$',before,re.I): continue
        if re.match(r'\s*(?:plus|minus|before|after|from|ago|or|ish|approximately|roughly|give\s+or\s+take)\b',after,re.I): continue
        if re.match(r'\s*(?:\d+|[a-z]+(?:[ -]+[a-z]+){0,4})\s+(?:days?|weeks?|months?|years?)\s+(?:ago|before|after|from)\b',after,re.I): continue
        if re.search(r'[-+]\s*$|\b(?:minus|negative|point|in|next)\s*$',before,re.I): continue
        try:
            days=(int(_numeric_text(match['days'])) if match['days'] else
                  1 if match[0].casefold()=='yesterday' else 0)
            parsed=reference-timedelta(days=days)
        except (ValueError,OverflowError): continue
        result.append((match.start(),match.end(),parsed))
    return sorted(result)


def event_date(text,event,reference_date):
    """Bind one asserted event to a nearby date on either side, or decline.

    Yearless day/month claims use the supplied reference year only. Ambiguous,
    negated, hypothetical, unbound or competing event dates return None. This
    reads no orders and does not verify the customer's statement.
    """
    if event not in _CUES: raise ValueError('unsupported_event_kind')
    if not isinstance(text,str) or not isinstance(reference_date,date): return None
    text=ascii_digits(text); values=set()
    for clause in re.split(r'[!?;\u0964\n]+',text):
        dates=_dates(clause,reference_date)
        if not dates: continue
        if len(dates)>1 and re.search(r'\b(?:or|ya)\b|(?<![\u0900-\u097f])\u092f\u093e(?![\u0900-\u097f])',clause[dates[0][0]:dates[-1][1]],re.I): continue
        cues=[]
        for kind,pattern in _CUES.items():
            for cue in pattern.finditer(clause):
                prefix=_SPLIT_SCOPE.split(clause[:cue.start()])[-1][-55:]
                suffix=_SPLIT_SCOPE.split(clause[cue.end():])[0][:20]
                if _UNCERTAIN.search(prefix) or _UNCERTAIN.search(suffix): continue
                if re.match(r'^\s*(?:did|was|were|whether|has|have|had|may|is|are|can|could|would|will)\b',prefix,re.I): continue
                # Modal/future descriptions are not completed event inputs.
                if re.search(r'\b(?:will|would|could|might|can|must|should|shall)\b|\bgoing\s+to\b',prefix,re.I): continue
                # May is a modal here unless it belongs to a named-date span.
                named_dates=list(_NAMED.finditer(prefix))
                if any(not any(named.start()<=modal.start()<named.end() for named in named_dates)
                       for modal in re.finditer(r'\bmay\b',prefix,re.I)): continue
                local=prefix + cue[0] + suffix
                if re.search(r'\b(?:is|was)\s+(?:expected|scheduled|planned|due)\b',local,re.I): continue
                if kind=='delivery' and _MONEY.search(local): continue
                cues.append((cue.start(),cue.end(),kind))
        # Other explicit dated events are barriers, never placement/delivery
        # inputs. This prevents transferring a refund or shipping date merely
        # because the requested event was mentioned nearby without a date.
        cues.extend((cue.start(),cue.end(),'other') for cue in _OTHER_EVENT.finditer(clause))
        for begin,end,parsed in dates:
            distances=[]
            for left,right,kind in cues:
                distance=max(left-end,begin-right,0)
                if distance<=65: distances.append((distance,kind,left,right))
            if not distances: continue
            nearest=min(x[0] for x in distances)
            winners=[x for x in distances if x[0]==nearest]
            if len({x[1] for x in winners})!=1: continue
            winner=winners[0]
            # Alternatives beside the dated event are not an asserted input.
            local=clause[min(begin,winner[2]):max(end,winner[3])]
            before=clause[max(0,begin-15):begin]
            if re.search(r'\b(?:or|ya)\b|(?<![\u0900-\u097f])\u092f\u093e(?![\u0900-\u097f])',local,re.I) or re.search(r'\d+\s+(?:or|ya)\s*$',before,re.I): continue
            if winner[1]==event: values.add(parsed)
    return next(iter(values)) if len(values)==1 else None
