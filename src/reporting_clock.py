"""Compare a verified report clock with its actual current source window.

The recorded elapsed hours are authoritative; date-only delivery fields do
not contain enough information to recompute an elapsed-hour measurement.
This check does not authorize a remedy or establish claim verification.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib,json,re
from .grounding import _numeric_text

_TOPIC=re.compile(r'\bdamag\w*\b|\bbroken\b|\bdefect\w*\b|नुकसान|क्षतिग्रस्त|टूट|खराब',re.I)
_RULE=re.compile(r'\breport\b[^.!?;\n]{0,220}\bwithin\s+(\d+(?:\.\d+)?)\s+hours?\s+of\s+delivery\b',re.I)
_SPLIT=re.compile(r'[.!?;।\n]|\b(?:but|however|lekin)\b|लेकिन',re.I)
_CONDITIONAL=re.compile(r'\b(?:if|whether|assuming|agar|yadi|jab|chahe)\b|यदि|अगर|चाहे',re.I)
_UNCERTAIN=re.compile(r"\b(?:cannot|can't|unable\s+to)\s+(?:confirm|verify|say)|\bnot\s+saying|\bnahi\s+keh|पुष्टि\s+नहीं",re.I)
_REPORT=re.compile(r'\breport(?:ed)?\b|रिपोर्ट|शिकायत',re.I)
_PAST=re.compile(r'\breported\b|\b(?:was|has\s+been)\b|\bkiya\b|किया|की\s+गई',re.I)
_LATE=re.compile(r'\blate\b|\boverdue\b|\boutside\s+(?:the\s+)?reporting\s+window\b|\bder\s+se\b|देरी\s+से',re.I)
_WITHIN=re.compile(r'\bwithin\b|\bandar\b|अंदर|भीतर',re.I)
_NEG=re.compile(r'\b(?:not|nahi|nahin)\b|नहीं',re.I)
_COORD=re.compile(r'[,;]|\b(?:and|aur)\b|और',re.I)

def _predicate_scope(clause,match,before,after):
    left=_COORD.split(clause[:match.start()])[-1][-before:]
    right=_COORD.split(clause[match.end():],maxsplit=1)[0][:after]
    return left+match[0]+right


def reporting_clock_inputs(query,facts,sources,reference_date):
    order=facts.get('verified_order') if isinstance(facts,dict) else None
    if not isinstance(order,dict):return None
    if not _TOPIC.search(query) and (facts.get('operational_escalation') or {}).get('reason')!='high_value_damage':return None
    raw=order.get('damage_hours_after_delivery')
    if isinstance(raw,bool) or raw is None:return None
    try:
        elapsed=Decimal(str(raw));today=date.fromisoformat(str(reference_date)[:10])
        if not elapsed.is_finite() or elapsed<0:return None
    except (InvalidOperation,ValueError,TypeError):return None
    rules=[]
    for source in sources:
        if source.get('doc_type')!='policy' or source.get('status')!='current':continue
        try:
            if source.get('effective_from') and date.fromisoformat(source['effective_from'])>today:continue
        except (ValueError,TypeError):continue
        values={Decimal(m) for m in _RULE.findall(_numeric_text(re.sub(r'[*`]', '',source.get('text',''))))}
        if len(values)==1:rules.append((next(iter(values)),source))
    limits={amount for amount,_ in rules}
    if len(limits)!=1:return None
    limit=next(iter(limits))
    if limit<=0:return None
    number=lambda value:int(value) if value==value.to_integral_value() else float(value)
    return {'recorded_elapsed_hours':number(elapsed),'policy_limit_hours':number(limit),
        'within_reporting_window':elapsed<=limit,'value_origin':'verified_order.damage_hours_after_delivery',
        'source_ids':[s['id'] for _,s in rules],
        'source_sha256':{s['id']:hashlib.sha256(json.dumps(s,sort_keys=True,ensure_ascii=False).encode()).hexdigest() for _,s in rules}}

def check_reporting_clock_claim(answer,query,facts,sources,reference_date):
    clock=reporting_clock_inputs(query,facts,sources,reference_date)
    if clock is None:return
    for clause in _SPLIT.split(_numeric_text(answer)):
        if '?' in clause or _CONDITIONAL.search(clause) or _UNCERTAIN.search(clause):continue
        if not _REPORT.search(clause) or not _PAST.search(clause):continue
        late=_LATE.search(clause);within=_WITHIN.search(clause)
        if within:
            local=_predicate_scope(clause,within,45,55)
            claims_within=not bool(_NEG.search(local))
            if claims_within!=clock['within_reporting_window']:raise ValueError('contradicted_reporting_window_status')
        elif late:
            local=_predicate_scope(clause,late,22,18)
            claims_late=not bool(_NEG.search(local))
            if claims_late==clock['within_reporting_window']:raise ValueError('contradicted_reporting_window_status')
