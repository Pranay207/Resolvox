"""Typed source-derived business handover inputs; never render policy answers.

Current sources and public/verified records are the only knowledge inputs.
This finite parser declines missing/conflicting rule structure. Independent
protective or user-requested handover remains the caller's responsibility.
"""
from datetime import date,timedelta
from decimal import Decimal,InvalidOperation
import hashlib
import json
import re

_RANK={'policy':0,'agent_guide':1}
_FIELDS=('id','text','file','doc_type','status','effective_from','version')
_DAYS={name:index for index,name in enumerate(('monday','tuesday','wednesday','thursday','friday','saturday','sunday'))}
_ORDINAL={name:index for index,name in enumerate(('first','second','third','fourth','fifth','sixth','seventh','eighth','ninth','tenth'),1)}
_DAMAGE=re.compile(r'\b(?:damaged?|defective|broken|crack(?:ed|s)?|torn|wrong\s+(?:item|product|goods))\b|खराब|टूट[ाी]|क्षतिग्रस्त|गलत\s*(?:सामान|उत्पाद)|\b(?:kharab|toota|tuta|galat\s+(?:item|product))\b',re.I)
_REFUND=re.compile(r'\brefund\w*\b|रिफ़?ंड|रिफंड',re.I)
_CASE_TOPIC=re.compile(r'\b(?:refund\w*|deliver\w*|shipment|parcel|damag\w*|defect\w*|return\w*|issue|unresolved|contact\w*|again)\b|रिफ़?ंड|डिलीवरी|समस्या|खराब|संपर्क',re.I)
_UNCERTAIN=re.compile(r"\b(?:if|suppose|assuming|hypothetical|whether|not|never|no|without|nahi|nahin|agar|yadi)\b|नहीं|अगर|यदि",re.I)


def source_fingerprint(source):
    public={key:source[key] for key in _FIELDS if key in source}
    return hashlib.sha256(json.dumps(public,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def _date(value):
    if isinstance(value,date):return value
    if isinstance(value,str):
        try:return date.fromisoformat(value[:10])
        except ValueError:pass
    return None


def _amount(value):
    if type(value) is bool:return None
    try:result=Decimal(str(value).replace(',',''))
    except (InvalidOperation,ValueError,TypeError):return None
    return result if result.is_finite() and result>=0 else None


def _int(value):
    if type(value) is int:return value if value>=0 else None
    return int(value) if isinstance(value,str) and re.fullmatch(r'\d+',value) else None


def _plain(text):return re.sub(r'[*`]', '',text)


def _active(source,reference):
    if source.get('status')!='current':return False
    effective=source.get('effective_from')
    return not effective or bool((parsed:=_date(effective)) and parsed<=reference)


def _sources(sources,reference):
    values=sources.values() if isinstance(sources,dict) else sources
    actual={}
    for source in values:
        if not isinstance(source,dict) or not isinstance(source.get('id'),str) or not isinstance(source.get('text'),str):
            raise ValueError('invalid_escalation_source')
        if source['id'] in actual and source_fingerprint(source)!=source_fingerprint(actual[source['id']]):
            raise ValueError('conflicting_escalation_source_id')
        if _active(source,reference):actual[source['id']]=source
    return list(actual.values())


def _choose(candidates):
    if not candidates:return None,'unbound',[]
    rank=min(rank for rank,value,source in candidates)
    best=[(value,source) for level,value,source in candidates if level==rank]
    distinct={json.dumps(value,sort_keys=True) for value,source in best}
    if len(distinct)!=1 or any(isinstance(value,dict) and 'invalid' in value for value,source in best):return None,'ambiguous',[source for value,source in best]
    return best[0][0],'bound',[source for value,source in best]


def _positive_rule(text,match):
    line=text[text.rfind('\n',0,match.start())+1:text.find('\n',match.end()) if '\n' in text[match.end():] else len(text)]
    prefix=re.split(r'[.!?;]',text[:match.start()])[-1]
    if re.search(r"\b(?:no|not|never|cannot|can't)\b",prefix,re.I):return False
    return not re.search(r"\b(?:not|never|cannot|can't)\s+(?:\w+\s+){0,3}(?:create|hand\s*over|handover|escalat\w*|handled?)\b",line,re.I)


def _workflow(sources):
    candidates=[]
    pattern=re.compile(r'\bcreate\s+(?:a\s+)?ticket\b.{0,50}\bbefore\s+handing\s+over\b',re.I)
    for source in sources:
        if source.get('doc_type') not in _RANK:continue
        text=_plain(source['text'])
        for match in pattern.finditer(text):candidates.append((_RANK[source['doc_type']],_positive_rule(text,match),source))
    value,status,used=_choose(candidates)
    return used if value is True and status=='bound' else []


def _row(reason,applicable,status,used=(),facts=None,calculations=(),missing=()):
    unique={s['id']:s for s in used}
    return {'reason':reason,'applicable':applicable,'binding_status':status,
            'source_ids':sorted(unique),'source_sha256':{key:source_fingerprint(unique[key]) for key in sorted(unique)},
            'facts':facts or {},'calculations':list(calculations),'missing_inputs':list(missing)}


def _high_value_rule(sources):
    candidates=[]
    pattern=re.compile(r'\bitems?\s+worth\s+(?P<operator>more\s+than|above|over|at\s+least)\s*(?:₹|INR\s*|Rs\.?\s*|rupees?\s*)(?P<value>\d[\d,]*(?:\.\d+)?)',re.I)
    for source in sources:
        if source.get('doc_type') not in _RANK:continue
        text=_plain(source['text'])
        if not re.search(r'hand\s*over|handover|escalat',text,re.I):continue
        for match in pattern.finditer(text):
            amount=_amount(match['value'])
            if amount is not None:
                value={'threshold_inr':str(amount),'operator':'ge' if re.fullmatch(r'at\s+least',match['operator'],re.I) else 'gt'} if _positive_rule(text,match) else {'invalid':'negated_rule_action'}
                candidates.append((_RANK[source['doc_type']],value,source))
    return _choose(candidates)


def _asserted_damage(query):
    for clause in re.split(r'[.!?;।\n]+|\b(?:but|however|lekin)\b',query,flags=re.I):
        for match in _DAMAGE.finditer(clause):
            prefix=clause[max(0,match.start()-65):match.start()]
            suffix=clause[match.end():match.end()+18]
            if _UNCERTAIN.search(prefix) or re.search(r"\b(?:isn.t|wasn.t|aren.t|weren.t)\b",prefix,re.I) or re.match(r'\s*(?:nahi|nahin|नहीं)',suffix,re.I):continue
            # Generic policy-overview questions are not individual claims.
            if re.search(r'\b(?:rules?|policy|threshold|hypothetic\w*)\b',clause,re.I) and not re.search(r'\b(?:my|our|mera|meri|hamara)\b|मेरा|मेरी',clause,re.I):continue
            asserted=re.search(r'\b(?:my|our|i|we|mera|meri|maine|humne|mujhe|hamara|received|arrived|came|got|delivered)\b|मेरा|मेरी|मैंने|हमने|मुझे|मिला|मिली|आया',clause,re.I)
            if not asserted or re.match(r'^\s*(?:is|was|are|were|did|does|would|could)\b',clause,re.I):continue
            return True
    return False


def _catalog_prices(query,sources,public):
    rows=[]
    for source in sources:
        if source.get('doc_type')!='catalog':continue
        try:value=json.loads(source['text'])
        except (TypeError,ValueError):continue
        if not isinstance(value,dict) or not isinstance(value.get('sku'),str):continue
        amount=_amount(value.get('price_inr'))
        if amount is not None:rows.append((value,amount,source))
    sku=public.get('sku')
    if sku:rows=[row for row in rows if row[0]['sku']==sku]
    else:
        matched=[row for row in rows if re.search(r'(?<!\w)'+re.escape(row[0]['sku'])+r'(?!\w)',query,re.I) or (row[0].get('title') and row[0]['title'].casefold() in query.casefold())]
        rows=matched or rows
    unique={row[0]['sku']:row for row in rows}
    return next(iter(unique.values())) if len(unique)==1 else None


def _damage(query,sources,order,public,workflow):
    reason='high_value_damage'
    if not _asserted_damage(query):return _row(reason,False,'not_relevant'),[]
    rule,status,used=_high_value_rule(sources)
    if not rule:return _row(reason,None,status,used,missing=['current_high_value_rule']),used
    selected=_catalog_prices(query,sources,public)
    amount=None;origin=None;sku=public.get('sku')
    if order:
        items=[item for item in order.get('items',[]) if isinstance(item,dict)]
        exact=[item for item in items if item.get('sku') and re.search(r'(?<!\w)'+re.escape(item['sku'])+r'(?!\w)',query,re.I)]
        def title_key(text):
            text=re.sub(r'(?<=[0-9])(?=[a-z])|(?<=[a-z])(?=[0-9])',' ',str(text).casefold())
            return ' '.join(re.findall(r'\w+',text))
        query_key=' '+title_key(query)+' '
        named=[]
        for item in items:
            core=title_key(str(item.get('title') or '').split(',')[0])
            if len(core)>=8 and ' '+core+' ' in query_key:named.append(item)
        if exact:items=exact
        elif named:items=named
        elif sku:items=[item for item in items if item.get('sku')==sku]
        elif selected:items=[item for item in items if item.get('sku')==selected[0]['sku']]
        if len(items)==1:
            amount=_amount(items[0].get('unit_price_inr'));sku=items[0].get('sku');origin='verified_order.items.unit_price_inr'
    elif selected:
        record,amount,source=selected;sku=record['sku'];origin='public_catalog.price_inr';used=used+[source]
    facts={**rule,'item_sku':sku,'item_value_inr':str(amount) if amount is not None else None,'value_origin':origin}
    if amount is None:return _row(reason,None,'bound',used,facts,missing=['one_unambiguous_item_value']),used
    applies=amount>=Decimal(rule['threshold_inr']) if rule['operator']=='ge' else amount>Decimal(rule['threshold_inr'])
    local_action=any(re.search(r'\bmust\s+create\s+(?:a\s+)?ticket\s+and\s+hand\s+over\b',_plain(s['text']),re.I) for s in used)
    if applies and not (workflow or local_action):return _row(reason,None,'unbound',used,facts,missing=['ticket_before_handover_workflow']),used
    used=used+workflow if applies else used
    return _row(reason,applies,'bound',used,facts),used


def _repeat_rule(sources):
    candidates=[]
    for source in sources:
        if source.get('doc_type') not in _RANK:continue
        text=_plain(source['text'])
        field=re.search(r'\b(contacts_last_(\d+)_days)\b',text,re.I)
        threshold=re.search(r'\bEscalate\s+when\s+it\s+is\s+(\d+)\s+or\s+more\b',text,re.I)
        earlier=re.search(r'counts\s+earlier\s+contacts\s+only\s*,?\s*not\s+the\s+current\s+one',text,re.I)
        if not(field and threshold and earlier):continue
        if not _positive_rule(text,threshold):
            candidates.append((_RANK[source['doc_type']],{'invalid':'negated_rule_action'},source));continue
        period=int(field[2]);minimum=int(threshold[1])
        ordinal=re.search(r'\b('+('|'.join(_ORDINAL))+r'|\d+(?:st|nd|rd|th))\s+or\s+later\s+contact\b.{0,55}?\bwithin\s+(\d+)\s+days\b',text,re.I)
        if ordinal:
            count=_ORDINAL.get(ordinal[1].casefold()) or int(re.sub(r'\D','',ordinal[1]))
            if count!=minimum+1 or int(ordinal[2])!=period:
                candidates.append((_RANK[source['doc_type']],{'invalid':'conflicting_earlier_contact_semantics'},source));continue
        candidates.append((_RANK[source['doc_type']],{'record_field':field[1],'earlier_contact_threshold':minimum,'window_calendar_days':period,'current_contact_excluded':True},source))
    rule,status,used=_choose(candidates)
    if rule and 'invalid' in rule:return None,'ambiguous',used
    return rule,status,used


def _different_or_general_issue(query):
    """Do not apply a same-issue contact count to an explicitly other topic."""
    for match in re.finditer(r'\b(?:different|separate|new|another|unrelated)\s+(?:question|issue|problem|topic|concern)\b|अलग\s*(?:प्रश्न|सवाल|मुद्दा|समस्या)|\b(?:alag|naya|nayi)\s+(?:question|issue|problem|sawal)\b',query,re.I):
        prefix=query[max(0,match.start()-25):match.start()]
        if not re.search(r"\b(?:not|isn't|wasn't|nahi|nahin)\s+(?:(?:a|an|the)\s+)?$|नहीं\s*$",prefix,re.I):
            return True
    if re.search(r'\bnot\s+(?:(?:about|related\s+to|the|my|our|a|an)\s+)*(?:(?:previous|earlier|same|old)\s+)?(?:issue|question|problem|concern)\b',query,re.I):
        return True
    general=re.search(r'\b(?:generally|in\s+general|general\s+(?:[a-z]+\s+){0,2}(?:policy|question|information|options)|policy\s+overview)\b|सामान्य\s*(?:जानकारी|नियम|प्रश्न)|\b(?:aam|general)\s+(?:jaankari|niyam|sawal)\b',query,re.I)
    same=re.search(r'\bsame\b.{0,35}\b(?:issue|problem|concern)\b|\b(?:my|our|mera|meri|mujhe)\b.{0,90}\b(?:still|again|missing|unresolved|not\s+(?:arrived|received|resolved)|hasn.t\s+(?:arrived|resolved))\b|उसी\s*(?:मुद्दे|समस्या)|अभी\s*भी',query,re.I)
    return bool(general and not same)


def _same_issue_call(query):
    """Resolve explicit call-about-this anaphora without a policy threshold."""
    contact = re.compile(
        r'\b(?:call(?:ing|ed)?|phon(?:e|ed|ing))\b[^.!?;\n]{0,65}'
        r'(?:\babout\s+(?:this|that|it)\b|\b(?:isi|usi)\s+(?:baare|bare|mudde)\b)|'
        r'(?:कॉल|फ़ोन|फोन)[^.!?;।\n]{0,65}(?:इसी|उसी)\s*(?:बारे|मुद्दे|समस्या)|'
        r'(?:इसी|उसी)\s*(?:बारे|मुद्दे|समस्या)[^.!?;।\n]{0,65}(?:कॉल|फ़ोन|फोन)', re.I)
    return any(contact.search(clause) and not _UNCERTAIN.search(clause)
               for clause in re.split(r'[.!?;।\n]+',query))


def _repeat(query,sources,order,workflow):
    reason='repeat_contact'
    if not order or not (_CASE_TOPIC.search(query) or _same_issue_call(query)) or _different_or_general_issue(query):return _row(reason,False,'not_relevant'),[]
    rule,status,used=_repeat_rule(sources)
    if not rule:return _row(reason,None,status,used,missing=['current_repeat_contact_rule']),used
    count=_int(order.get(rule['record_field']))
    facts={**rule,'earlier_contact_count':count,'value_origin':'verified_order.'+rule['record_field']}
    if count is None:return _row(reason,None,'bound',used,facts,missing=[rule['record_field']]),used
    applies=count>=rule['earlier_contact_threshold']
    if applies and not workflow:return _row(reason,None,'unbound',used,facts,missing=['ticket_before_handover_workflow']),used
    used=used+workflow if applies else used
    return _row(reason,applies,'bound',used,facts),used


def _method(value):
    text=re.sub(r'[_-]',' ',str(value or '')).casefold()
    if 'neft' in text or ('bank' in text and ('cod' in text or 'cash' in text)):return 'cod_bank'
    if 'wallet' in text and ('cod' in text or 'cash' in text):return 'cod_wallet'
    if 'upi' in text:return 'upi'
    if 'card' in text:return 'card'
    if 'net' in text and 'bank' in text:return 'netbanking'
    if 'wallet' in text:return 'wallet'
    return None


def _refund_rule(sources):
    candidates=[]
    pattern=re.compile(r'\brefund\s+(?P<operator>more\s+than|at\s+least)\s+(?P<days>\d+)\s+business\s+days?\s+(?:past|beyond|after)\s+(?:its\s+|the\s+)?maximum\s+(?:timeline|date|deadline)',re.I)
    for source in sources:
        if source.get('doc_type') not in _RANK:continue
        text=_plain(source['text'])
        if not re.search(r'hand\s*over|handover|escalat',text,re.I):continue
        for match in pattern.finditer(text):
            value={'tolerance_business_days':int(match['days']),'operator':'ge' if re.fullmatch(r'at\s+least',match['operator'],re.I) else 'gt'} if _positive_rule(text,match) else {'invalid':'negated_rule_action'}
            candidates.append((_RANK[source['doc_type']],value,source))
    return _choose(candidates)


def _refund_range(sources,method):
    candidates=[]
    for source in sources:
        if source.get('doc_type')!='policy':continue
        text=_plain(source['text'])
        if not re.search(r'\brefund\w*\b',text,re.I) or not re.search(r'\binitiat\w*\b',text,re.I):continue
        for line in text.splitlines():
            cells=[cell.strip() for cell in line.strip().strip('|').split('|')]
            if len(cells)!=2 or _method(cells[0])!=method:continue
            span=re.fullmatch(r'(\d+)\s+(?:to|[-–])\s+(\d+)\s+business\s+days?',cells[1],re.I)
            if span and int(span[1])<=int(span[2]):candidates.append((0,{'minimum_business_days':int(span[1]),'maximum_business_days':int(span[2]),'payment_method':method},source))
    return _choose(candidates)


def _calendar(sources,data):
    candidates=[]
    for source in sources:
        if source.get('doc_type') not in {'meta','policy'}:continue
        text=_plain(source['text'])
        match=re.search(r'\bbusiness\s+day\s+is\s+('+('|'.join(_DAYS))+r')\s+to\s+('+('|'.join(_DAYS))+r')\s*,?\s*excluding\s+(?:the\s+)?warehouse\s+holidays',text,re.I)
        if match:
            first,last=_DAYS[match[1].casefold()],_DAYS[match[2].casefold()]
            weekdays=[(first+offset)%len(_DAYS) for offset in range((last-first)%len(_DAYS)+1)]
            candidates.append((0,{'business_weekdays':weekdays},source))
    rule,status,used=_choose(candidates)
    if not rule:return None,status,used
    values=getattr(data,'holidays',None)
    if not isinstance(values,(set,frozenset,list,tuple)):return None,'unbound',used
    parsed=[_date(value) for value in values]
    if any(value is None for value in parsed):return None,'ambiguous',used
    holidays=sorted({value.isoformat() for value in parsed})
    public={'id':'data/holidays.csv','file':'data/holidays.csv','text':json.dumps({'warehouse_holidays':holidays},sort_keys=True,separators=(',',':')),'doc_type':'catalog','status':'current'}
    return {**rule,'holidays':holidays},'bound',used+[public]


def _business_add(start,count,calendar):
    current=start;remaining=count;holidays=set(calendar['holidays']);weekdays=set(calendar['business_weekdays'])
    while remaining:
        current+=timedelta(days=1)
        if current.weekday() in weekdays and current.isoformat() not in holidays:remaining-=1
    return current


def _business_elapsed(start,end,calendar):
    current=start;count=0;holidays=set(calendar['holidays']);weekdays=set(calendar['business_weekdays'])
    while current<end:
        current+=timedelta(days=1)
        count+=current.weekday() in weekdays and current.isoformat() not in holidays
    return count


def _refund(query,sources,data,order,reference,workflow):
    reason='refund_overdue'
    if not order or not _REFUND.search(query):return _row(reason,False,'not_relevant'),[]
    events=[]
    for name in ('return','cancellation','rto'):
        started=_date(order.get(name+'_refund_initiated_on'))
        if started and not order.get(name+'_refund_completed_on'):
            events.append((name,started,_method(order.get(name+'_refund_method') or order.get('payment_method'))))
    if not events:return _row(reason,False,'not_relevant',facts={'active_recorded_refund_count':0}),[]
    if len(events)!=1:return _row(reason,None,'ambiguous',facts={'active_recorded_refund_count':len(events)},missing=['one_unambiguous_active_refund']),[]
    event,started,method=events[0]
    if method is None:return _row(reason,None,'bound',facts={'refund_event':event},missing=['recorded_refund_method']),[]
    tolerance,status,used=_refund_rule(sources)
    if not tolerance:return _row(reason,None,status,used,missing=['current_refund_overdue_rule']),used
    span,status,range_sources=_refund_range(sources,method);used+=range_sources
    if not span:return _row(reason,None,status,used,missing=['current_payment_method_range']),used
    calendar,status,calendar_sources=_calendar(sources,data);used+=calendar_sources
    if not calendar:return _row(reason,None,status,used,missing=['current_business_calendar']),used
    if started>reference:return _row(reason,None,'ambiguous',used,missing=['past_recorded_initiation']),used
    first=_business_add(started,span['minimum_business_days'],calendar)
    maximum=_business_add(started,span['maximum_business_days'],calendar)
    elapsed=_business_elapsed(maximum,reference,calendar)
    threshold=_business_add(maximum,tolerance['tolerance_business_days'],calendar)
    facts={**tolerance,**span,'refund_event':event,'initiated_on':started.isoformat(),'reference_date':reference.isoformat(),'earliest_date':first.isoformat(),'maximum_date':maximum.isoformat(),'elapsed_business_days_past_maximum':elapsed,'tolerance_boundary_date':threshold.isoformat(),'value_origin':'verified_order.'+event+'_refund_initiated_on'}
    applies=elapsed>=tolerance['tolerance_business_days'] if tolerance['operator']=='ge' else elapsed>tolerance['tolerance_business_days']
    if reference<maximum:applies=False
    ids=sorted({s['id'] for s in used})
    calculation={'operation':'source_refund_overdue_comparison','source_ids':ids,'inputs':{'initiated_on':started.isoformat(),'reference_date':reference.isoformat(),**span,**tolerance,**calendar},'result':{'earliest_date':first.isoformat(),'maximum_date':maximum.isoformat(),'tolerance_boundary_date':threshold.isoformat(),'elapsed_business_days_past_maximum':elapsed,'escalation_required':applies}}
    if applies and not workflow:return _row(reason,None,'unbound',used,facts,[calculation],['ticket_before_handover_workflow']),used
    used=used+workflow if applies else used
    return _row(reason,applies,'bound',used,facts,[calculation]),used


def derive_escalation(query,sources,data,*,verified_order=None,public_context=None,reference_date=None):
    """Derive before business tool effects. True/False/None is not spoken text.

    ``selected_sources`` contains every actual source used, plus a serialized
    public holiday-table input if calendar arithmetic is needed. Recompute this
    function at the action boundary and compare canonical fingerprints; do not
    treat a previous result or legacy Plan as authority.
    """
    reference=_date(reference_date)
    if reference is None:raise ValueError('explicit_reference_date_required')
    if not isinstance(query,str):raise ValueError('invalid_escalation_query')
    if verified_order is not None and not isinstance(verified_order,dict):raise ValueError('invalid_verified_order')
    if public_context is not None and not isinstance(public_context,dict):raise ValueError('invalid_public_context')
    actual=_sources(sources,reference);order=verified_order or {};public=public_context or {};workflow=_workflow(actual)
    rows=[_damage(query,actual,order,public,workflow),_repeat(query,actual,order,workflow),_refund(query,actual,data,order,reference,workflow)]
    decisions=[row for row,used in rows];selected={source['id']:source for row,used in rows for source in used}
    priority=('repeat_contact','high_value_damage','refund_overdue')
    recommended=next((reason for reason in priority if any(row['reason']==reason and row['applicable'] is True for row in decisions)),None)
    return {'decisions':decisions,'recommended_reason':recommended,'source_ids':sorted(selected),'selected_sources':[selected[key] for key in sorted(selected)],'facts':{row['reason']:row['facts'] for row in decisions if row['facts']},'calculations':[calc for row in decisions for calc in row['calculations']]}
