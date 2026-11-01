"""Source-bound completeness for an authenticated return awaiting initiation.

No policy values or customer-facing answers are embedded here. This finite
check requires the prerequisite only when the verified record and current
policy establish the corresponding refund phase.
"""
from datetime import date
from .grounding import _numeric_text, _UNITS
import hashlib
import re

_QUALITY = re.compile(r'\bquality\s+(?:check|inspection|review)\b|\bQC\b|गुणवत्ता\s*(?:जाँच|जांच|निरीक्षण)|क्वालिटी\s*(?:चेक|जाँच|जांच)|\bquality\s+(?:ki\s+)?(?:jaanch|janch)\b',re.I)
_REFUND = re.compile(r'\brefund\w*\b|रिफ़?ंड|धनवापसी',re.I)


def pending_refund_requirement(query, facts, sources, reference_date):
    order=facts.get('verified_order') or {}
    if (not _REFUND.search(query) or order.get('is_plus') is not False
            or not order.get('return_pickup_on') or order.get('return_qc_passed_on')
            or order.get('return_refund_initiated_on') or order.get('return_refund_completed_on')
            or order.get('return_status') not in {'picked_up','qc_pending'}):
        return None
    reference=date.fromisoformat(str(reference_date)[:10])
    used=[]
    for source in sources:
        if source.get('doc_type')!='policy' or source.get('status')!='current':continue
        if source.get('effective_from'):
            try:
                if date.fromisoformat(source['effective_from'])>reference:continue
            except (ValueError,TypeError):continue
        text=re.sub(r'[*`]', '',source.get('text',''))
        for line in re.split(r'[.!?;\n]+',text):
            quality=_QUALITY.search(line)
            if not quality:continue
            before,after=line[:quality.start()],line[quality.end():]
            refund_before=_REFUND.search(before) and re.search(r'\b(?:after|once|following)\b',before,re.I)
            returned_rule=re.search(r'\breturned\s+item\b.{0,35}\bafter\b',before,re.I)
            if refund_before or returned_rule:
                used.append(source)
                break
    if not used:return None
    clocks=[]
    for source in used:
        text=re.sub(r'[*`]', '', source['text'])
        for match in re.finditer(r'refund\s+is\s+initiated\s+within\s+(\d+)\s+business\s+days\s+(?:of|after|from)\s+pick[ -]?up',text,re.I):
            clocks.append({'source_id':source['id'],'business_days':int(match[1]),'start_event':'pickup','prerequisite':'quality_check_pass'})
    return {'initiation_clocks':clocks,'kind':'pending_return_quality_condition','source_ids':sorted({s['id'] for s in used}),
            'source_sha256':{s['id']:hashlib.sha256(s['text'].encode('utf-8')).hexdigest() for s in used},
            'scope':'verified_return_picked_up_without_recorded_QC_pass_or_refund_initiation'}


def check_pending_refund_answer(answer, query, facts, sources, reference_date):
    requirement=pending_refund_requirement(query,facts,sources,reference_date)
    if requirement and not _QUALITY.search(answer):
        raise ValueError('missing_pending_refund_condition')
    if requirement:
        for clock in requirement.get('initiation_clocks', []):
            duration=r'(?<![\d.])'+str(clock['business_days'])+r'\s*(?:'+_UNITS['business_day']+r')(?![A-Za-z\u0900-\u097f])'
            for clause in re.split(r'[.!?;।\n]+',_numeric_text(answer)):
                if re.search(duration,clause,re.I) and not re.search(r'\bpick[ -]?up\b|पिक[ -]?अप|पिकअप',clause,re.I):
                    raise ValueError('missing_refund_initiation_anchor')
    return requirement
