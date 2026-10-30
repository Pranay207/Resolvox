"""Source-bound completeness for an authenticated return awaiting initiation.

No policy values or customer-facing answers are embedded here. This finite
check requires the prerequisite only when the verified record and current
policy establish the corresponding refund phase.
"""
from datetime import date
import hashlib
import re

_QUALITY = re.compile(r'\bquality\s+(?:check|inspection|review)\b|\bQC\b|गुणवत्ता\s*(?:जाँच|जांच|निरीक्षण)|\bquality\s+(?:ki\s+)?(?:jaanch|janch)\b',re.I)
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
    return {'kind':'pending_return_quality_condition','source_ids':sorted({s['id'] for s in used}),
            'source_sha256':{s['id']:hashlib.sha256(s['text'].encode('utf-8')).hexdigest() for s in used},
            'scope':'verified_return_picked_up_without_recorded_QC_pass_or_refund_initiation'}


def check_pending_refund_answer(answer, query, facts, sources, reference_date):
    requirement=pending_refund_requirement(query,facts,sources,reference_date)
    if requirement and not _QUALITY.search(answer):
        raise ValueError('missing_pending_refund_condition')
    return requirement
