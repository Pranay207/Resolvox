"""Source-bound status context for a picked-up return without recorded QC/initiation."""
import re
from .refund_status import pending_refund_requirement,_QUALITY
from .inference_facts import project_inference_facts
from .refund_timeline import _REFUND_DETAILS

def pending_status_inputs(query,facts,sources,reference_date):
 requirement=pending_refund_requirement(query,facts,sources,reference_date)
 if (not requirement or _REFUND_DETAILS.search(query)
     or re.search(r'\b(?:warrant\w*|deliver\w*|cancel\w*|replac\w*|RRN)\b|वारंटी|डिलीवरी|रद्द',query,re.I)):
  return None
 ids=set(requirement['source_ids'])
 for source in sources:
  if source.get('status')=='current' and source.get('doc_type')=='meta' and re.search(r'A business day is',source.get('text',''),re.I):ids.add(source['id'])
 selected=[s for s in sources if s['id'] in ids]
 if sum(len(s['text']) for s in selected)>3500:return None
 order=facts['verified_order']
 view={'verified_order':{k:order[k] for k in ('is_plus','return_status','return_pickup_on','return_qc_passed_on','return_refund_initiated_on','return_refund_completed_on','return_rrn') if k in order},'pending_refund_requirement':requirement,'reference_date':facts.get('reference_date',str(reference_date)[:10])}
 return {'sources':selected,'facts':project_inference_facts(view)}

def check_pending_record_claims(answer,query,facts,sources,reference_date):
 if not pending_refund_requirement(query,facts,sources,reference_date):return
 for clause in re.split(r'[.!?;।\n]+',answer):
  recorded=bool(re.search(r'\b(?:not|no)\b.{0,60}\b(?:recorded|listed|shown)\b|\brecord\w*\b.{0,18}(?:does\s+not|do\s+not|doesn.t).{0,12}(?:show|list|contain)|दर्ज\s*नहीं|उल्लेख\s*नहीं',clause,re.I))
  conditional=bool(re.search(r'\b(?:if|until|once|after|unless|when)\b|जब|यदि|अगर|के बाद|hone ke baad',clause,re.I))
  if _QUALITY.search(clause) and not recorded and not conditional:
   if re.search(r'\b(?:failed|passed|has\s+not\s+passed)\b|पास\s*(?:नहीं\s*)?(?:हुई|हुआ|हो\s*गई|हो\s*गया)|fail\s*(?:hua|hui)',clause,re.I):
    raise ValueError('unrecorded_refund_quality_claim')
  if not recorded and not conditional and re.search(r'refund[^.!?;।]{0,35}(?:has not|not yet|is not)[^.!?;।]{0,15}(?:start|initiat)|रिफ़?ंड[^।]{0,30}शुरू\s*नहीं\s*हुआ',clause,re.I):
   raise ValueError('unrecorded_refund_initiation_claim')
  if not facts['verified_order'].get('return_rrn') and re.search(r'\bRRN\b|refund reference|रिफरेंस|रेफरेंस',clause,re.I):
   if re.search(r'\b(?:use|share|trace|provide|give)\b|उपयोग|इस्तेमाल|साझा|देना|बैंक[^।]{0,50}जानकारी',clause,re.I) and not re.search(r'\b(?:no|not|without)\b|नहीं|न\s+करें',clause,re.I):
    raise ValueError('unrecorded_refund_reference_advice')
