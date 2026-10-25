"""Finite source-derived support for delivery appointment/arrival clock claims.

No policy values or question/source IDs occur here. This is a bounded semantic
contradiction/absence guard, not a scheduling tool or a general entailment proof.
"""
from datetime import date
import hashlib
import json
import re
import unicodedata

_AUTHORITY={'policy':4,'agent_guide':3,'help':2}
_EVENT=re.compile(r'\b(?:deliver(?:y|ies|ed|ing)?|arriv(?:e|es|al)|delivery\s+appointments?)\b|डिलीवरी|वितरण|पहुंच',re.I)
_SLOT=re.compile(r'\b(?:schedul\w*|slots?|appointments?|time[ -]windows?)\b|स्लॉट|समय.{0,12}(?:चुन|तय)|समयावधि',re.I)
_CUTOFF=re.compile(r'\b(?:order(?:ed|ing)?\s+(?:by|before)|place\w*.{0,15}order|cut[ -]?off|cancel\w*|dispatch\w*|ships?|shipping|refund\w*|pickup\w*)\b|रद्द|कैंसल|कटऑफ|ऑर्डर.{0,12}(?:पहले|करने)',re.I)
_AVAILABILITY=re.compile(r'\b(?:available|unavailable|possible|impossible|offered|offer|provide|provided|allowed|permitted|outside|within)\b|\b(?:deliver|delivers|arrives|arrive)\b|उपलब्ध|संभव|मुमकिन|नहीं\s*(?:हो|कर)|हो\s*सक|मिलती|बंद|नहीं.{0,15}(?:मिल|ले|दे)|\b(?:mil\w*|ho\s+sakt\w*|nahi|nahin|band|occurs?|restricted|limited)\b',re.I)
_CAPABILITY=re.compile(r'\b(?:can|cannot|can\x27t)\s+(?:\w+\s+){0,2}(?:deliver|schedule|arrive)\b|^(?:(?:yes|no)[,\s]+)?(?:you|we|it|that|i)\s+(?:can|cannot|can\x27t)[.! ]*$',re.I)
_NEGATIVE=re.compile(r'\b(?:not|no|never|cannot|can\x27t|unavailable|impossible|outside|don\x27t|doesn\x27t)\b|नहीं|नही|बंद|\b(?:nahi|nahin|band)\b',re.I)
_UNCERTAIN=re.compile(r'(?:documents?|sources?|policy|evidence).{0,35}(?:do not|does not|don\x27t|doesn\x27t).{0,15}(?:state|specify|describe|confirm|document)|\b(?:cannot|can\x27t|unable\s+to|do\s+not|don\x27t)\s+(?:confirm|verify|determine|say|know|find|answer)\b|\b(?:not\s+(?:specified|documented)|insufficient\s+(?:evidence|information))\b|पुष्टि.{0,18}नहीं|नहीं.{0,18}पुष्टि|\b(?:confirm|verify|bata).{0,16}(?:nahi|nahin)\b',re.I)
_NAMED={'midnight':0,'noon':720,'मध्यरात्रि':0,'आधी रात':0,'दोपहर':720}
_PERIODS=('morning','afternoon','evening','night','dawn','सुबह','शाम','रात','subah','shaam','raat')
_WORDS={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12}
_CLOCK=re.compile(r'(?<![\w:])(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>am|pm)?(?P<b>\s*(?:बजे|baje))?(?![\w:])',re.I)


def _text(value):
    value=unicodedata.normalize('NFKC',str(value)).casefold().replace('’',"'")
    value=''.join(str(unicodedata.digit(c)) if c.isdigit() else c for c in value)
    value=re.sub(r'\ba\s*\.\s*m\s*\.?','am',value)
    value=re.sub(r'\bp\s*\.\s*m\s*\.?','pm',value)
    for word,num in _WORDS.items():value=re.sub(r'\b'+word+r'(?=\s*(?:am|pm|o\x27clock))',str(num),value)
    return value


def _clauses(text):
    # Do not split decimal clock times, ranges or comma-bound conditions.
    return [x.strip() for x in re.split(r'(?<!\d)[.!?;\n।]+(?!\d)|\b(?:but|however|lekin)\b|लेकिन|मगर',_text(text)) if x.strip()]


def _times(text):
    text=_text(text);found=[]
    for label,value in _NAMED.items():
        for m in re.finditer(r'(?<!\w)'+re.escape(label)+r'(?!\w)',text):found.append((m.start(),m.end(),value))
    for label in _PERIODS:
        # Period words attached to explicit hours qualify that hour, rather than
        # becoming an independent claim about every hour of the day period.
        for m in re.finditer(r'(?<!\w)'+re.escape(label)+r'(?!\w)',text):
            if not re.search(r'\d.{0,15}(?:बजे|baje|am|pm)|(?:am|pm).{0,8}\d',text[max(0,m.start()-20):m.end()+20]):
                found.append((m.start(),m.end(),'period:'+label))
    for m in _CLOCK.finditer(text):
        if not (m['m'] is not None or m['ap'] or m['b']):continue
        h=int(m['h']);minute=int(m['m'] or 0)
        if h>23 or minute>59:continue
        ap=m['ap'];near=text[max(0,m.start()-12):m.end()+12]
        if not ap:
            if re.search(r'शाम|रात|shaam|raat',near):ap='pm'
            elif re.search(r'सुबह|subah',near):ap='am'
        if ap:
            if not 1<=h<=12:continue
            h=h%12+(12 if ap=='pm' else 0)
        elif m['m'] is None:
            # An unqualified Hindi/Roman hour is ambiguous; retain its lexical
            # identity rather than inventing a morning/evening interpretation.
            found.append((m.start(),m.end(),'hour:'+str(h)));continue
        found.append((m.start(),m.end(),h*60+minute))
    return sorted(found)


def _scopes(clause, times=None):
    times=_times(clause) if times is None else times
    if len(times)==2 and isinstance(times[0][2],int) and isinstance(times[1][2],int):
        between=clause[times[0][1]:times[1][0]]
        before=clause[max(0,times[0][0]-20):times[0][0]]
        after=clause[times[1][1]:times[1][1]+12]
        if re.search(r'\b(?:to|until|through)\b|[-–—]|से|\bse\b',between) or (re.search(r'\bbetween\b',before) and re.search(r'\band\b',between)) or re.search(r'तक|\btak\b',after):
            return [{'kind':'range','start':times[0][2],'end':times[1][2]}]
    return [{'kind':'point','value':value} for _,_,value in times]


def _arrival_scopes(clause):
    times=[]
    for item in _times(clause):
        prefix=clause[:item[0]]
        events=list(_EVENT.finditer(prefix))+list(_SLOT.finditer(prefix))
        cutoffs=list(_CUTOFF.finditer(prefix))
        event_position=max((m.end() for m in events),default=-1)
        cutoff_position=max((m.end() for m in cutoffs),default=-1)
        if cutoff_position>event_position:continue
        times.append(item)
    return _scopes(clause,times)


def _fingerprint(source):
    fields={k:source.get(k) for k in ('id','text','file','doc_type','status','effective_from','version')}
    return hashlib.sha256(json.dumps(fields,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def derive_delivery_clock_constraints(sources, *, reference_date=None):
    """Read only explicit current arrival/appointment availability statements."""
    today=date.fromisoformat(str(reference_date)[:10]) if reference_date is not None else None
    result=[]
    for source in sources:
        if not isinstance(source,dict) or source.get('status','current')!='current':continue
        kind=source.get('doc_type');priority=_AUTHORITY.get(kind)
        if priority is None or not isinstance(source.get('id'),str) or not isinstance(source.get('text'),str):continue
        effective=source.get('effective_from')
        if effective:
            try:effective=date.fromisoformat(str(effective)[:10])
            except ValueError:continue
            if today is None or effective>today:continue
        for clause in _clauses(source['text']):
            if not _EVENT.search(clause) or _CUTOFF.search(clause) or _UNCERTAIN.search(clause):continue
            # A non-event clock, e.g. a cutoff before a next-day ETA, never
            # authorizes a time-of-day arrival/scheduling claim.
            scopes=_scopes(clause)
            general_slots=bool(_SLOT.search(clause) and not scopes and re.search(r'\b(?:all|any|no)\b|किसी|सभी|\b(?:koi|sabhi)\b',clause))
            if not scopes and not general_slots:continue
            if not _AVAILABILITY.search(clause) and not re.search(r'\b(?:delivery|arrival)\s+hours\s*:',clause):continue
            if re.search(r'\b(?:if|unless|except|provided|when)\b|यदि|अगर|जब|\b(?:agar|jab)\b',clause):
                # Do not strip an eligibility antecedent to manufacture an
                # unconditional scheduling policy. Unsupported structure fails
                # closed rather than guessing its application.
                continue
            qualifiers=re.findall(r'\b(?:express|standard|grocery)\b',clause)
            result.append({'kind':'delivery_clock_availability','source_ids':[source['id']],
              'source_sha256':{source['id']:_fingerprint(source)},'evidence':clause,
              'authority':kind,'priority':priority,'available':not bool(_NEGATIVE.search(clause)),
              'exclusive':bool(re.search(r'\bonly\b|केवल|सिर्फ|\bsirf\b|\b(?:delivery|arrival)\s+hours\s*:',clause)),
              'scopes':scopes,'all_scheduling':general_slots,'service_qualifiers':sorted(set(qualifiers))})
    return result


def _contains(scope,target):
    if target['kind']=='range':
        if scope['kind']!='range':return False
        def segments(item):
            start,end=item['start'],item['end']
            return [(start,end)] if start<=end else [(start,24*60-1),(0,end)]
        return all(any(a<=x<=y<=b for a,b in segments(scope)) for x,y in segments(target))
    value=target['value']
    if scope['kind']=='point':return scope['value']==value
    if not isinstance(value,int):return False
    start,end=scope['start'],scope['end']
    return start<=value<=end if start<=end else value>=start or value<=end


def _answer_parts(sentence):
    result=[]
    for part in re.split(r',',sentence):
        # An earlier uncertainty sentence cannot authorize a later independent
        # availability predicate. Range conjunctions stay intact unless this is
        # specifically an uncertainty-prefixed clause.
        result.extend(re.split(r'\b(?:and|aur)\b|और',part) if _UNCERTAIN.search(part) else [part])
    return [part.strip() for part in result if part.strip()]


def check_delivery_clock_answer(answer,query,sources, *, reference_date=None):
    """Reject unsupported positive AND negative arrival/slot availability.

    Returns the evaluated source-derived rules for host audit. Absence is never
    interpreted as a prohibition. Ordinary business-day delivery ETAs are outside
    this finite guard's scope.
    """
    rules=derive_delivery_clock_constraints(sources,reference_date=reference_date)
    question=_text(query);qscopes=_scopes(question)
    query_clock=bool((_EVENT.search(question) or _SLOT.search(question)) and qscopes)
    claims=[]
    for sentence in _clauses(answer):
      for clause in _answer_parts(sentence):
        if _UNCERTAIN.search(clause):continue
        all_scopes=_scopes(clause)
        scopes=_arrival_scopes(clause)
        # Bind clock mentions to their local event. A nearby order/cancel cutoff
        # cannot authorize an arrival time, or hide a later arrival assertion.
        if all_scopes and not scopes and _CUTOFF.search(clause):continue
        if _CUTOFF.search(clause) and not scopes and not re.search(
                r'(?:deliver\w*|arriv\w*|डिलीवरी|वितरण).{0,45}'
                r'(?:available|unavailable|possible|impossible|outside|उपलब्ध|संभव|मुमकिन)',clause):continue
        event=bool(_EVENT.search(clause) or query_clock)
        if not event or not (_AVAILABILITY.search(clause) or _CAPABILITY.search(clause)):continue
        if not scopes and not query_clock:continue
        negative=bool(_NEGATIVE.search(clause));targets=scopes or qscopes
        applicable=[r for r in rules if not r['service_qualifiers'] or all(re.search(r'\b'+re.escape(x)+r'\b',clause) for x in r['service_qualifiers'])]
        supported=[]
        for target in targets:
            evidence=[]
            for rule in applicable:
                inside=rule['all_scheduling'] or any(_contains(scope,target) for scope in rule['scopes'])
                if inside:evidence.append((rule['priority'],rule['available'],rule))
                elif rule['exclusive'] and rule['available'] and target['kind']=='point':
                    evidence.append((rule['priority'],False,rule))
            if not evidence:raise ValueError('unsupported_delivery_clock_availability')
            best=max(item[0] for item in evidence)
            governing=[item for item in evidence if item[0]==best]
            directions={item[1] for item in governing}
            if directions!={not negative}:raise ValueError('unsupported_delivery_clock_availability')
            supported.extend(item[2] for item in governing)
        claims.extend(supported)
    # Keep full evaluated rules independently of whether this answer asserted a
    # clock claim. No host-generated business reply is introduced here.
    return rules
