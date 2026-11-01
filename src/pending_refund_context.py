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
 view['record_evidence']={'quality_check_pass':'not_recorded','refund_initiation':'not_recorded','prerequisite_satisfaction':'unknown'}
 return {'sources':selected,'facts':project_inference_facts(view)}

def check_pending_record_claims(answer,query,facts,sources,reference_date):
 if not pending_refund_requirement(query,facts,sources,reference_date):return
 for clause in re.split(r'[.!?;।\n]+',answer):
  recorded=bool(re.search(r'\b(?:not|no)\b.{0,60}\b(?:recorded|listed|shown)\b|\brecord\w*\b.{0,18}(?:does\s+not|do\s+not|doesn.t).{0,12}(?:show|list|contain)|दर्ज\s*नहीं|उल्लेख\s*नहीं',clause,re.I))
  conditional=bool(re.search(r'\b(?:if|until|once|after|unless|when)\b|जब|यदि|अगर|के बाद|hone ke baad',clause,re.I))
  unfulfilled=re.search(
   r'\b(?:conditions?|prerequisites?|requirements?)\b.{0,40}\b(?:not\s+(?:been\s+)?(?:met|satisfied|fulfilled)|unfulfilled|unsatisfied)\b|'
   r'(?:शर्तें|शर्तों|आवश्यकताएं|आवश्यकताएँ).{0,24}(?:पूरी|पूर्ण).{0,8}नहीं.{0,8}(?:हुई|हुए|है|हैं)|'
   r'\b(?:shart\w*|conditions?|requirements?)\b.{0,25}\b(?:poori|puri|complete)\s+(?:nahi|nahin)\b',clause,re.I)
  if unfulfilled and not recorded and not conditional:
   raise ValueError('unrecorded_refund_quality_claim')
  if _QUALITY.search(clause) and not recorded and not conditional:
   if re.search(r'\b(?:failed|passed|has\s+not\s+passed)\b|पास\s*(?:नहीं\s*)?(?:हुई|हुआ|हो\s*गई|हो\s*गया)|fail\s*(?:hua|hui)',clause,re.I):
    raise ValueError('unrecorded_refund_quality_claim')
  if not recorded and not conditional and re.search(r'refund[^.!?;।]{0,35}(?:has not|not yet|is not)[^.!?;।]{0,15}(?:start|initiat)|रिफ़?ंड[^।]{0,30}शुरू\s*नहीं\s*हुआ',clause,re.I):
   raise ValueError('unrecorded_refund_initiation_claim')
  if not facts['verified_order'].get('return_rrn') and re.search(r'\bRRN\b|refund reference|रिफरेंस|रेफरेंस',clause,re.I):
   if re.search(r'\b(?:use|share|trace|provide|give)\b|उपयोग|इस्तेमाल|साझा|देना|बैंक[^।]{0,50}जानकारी',clause,re.I) and not re.search(r'\b(?:no|not|without)\b|नहीं|न\s+करें',clause,re.I):
    raise ValueError('unrecorded_refund_reference_advice')



def check_unverified_return_reason(answer,query,facts):
    fee=facts.get('return_pickup_policy', {})
    if fee.get('personal_charge_confirmed') is not False:return
    reason=str(facts.get('verified_order', {}).get('return_reason') or '')
    changed=r'change[ -]of[ -]mind|changed[_ -]mind|मन\s*बदल|mann?\s*badal'
    if re.search(changed,query+' '+reason,re.I):return
    for clause in re.split(r'[.!?;।\n]+',answer):
        if re.search(r'\b(?:if|for|agar|yadi)\b|यदि|अगर|के\s*लिए',clause,re.I):continue
        personal=re.search(r'\b(?:your|this|the)\s+return\s+is\b.{0,35}change[ -]of[ -]mind|(?:यह|आपका|ये).{0,50}मन\s*बदलने.{0,20}(?:का|की)\s*रिटर्न\s*है',clause,re.I)
        if personal:raise ValueError('unverified_return_reason')


def check_unconfirmed_staff_review(answer, facts):
    """A queued escalation is not evidence that staff are actively reviewing it."""
    if not facts.get('operational_escalation'):
        return
    activity = re.compile(
        r'\b(?:is|are|was|were|has\s+been|have\s+been)\s+'
        r'(?:(?:currently|already|actively|now)\s+)*'
        r'(?:being\s+reviewed|under\s+(?:active\s+)?review)\b|'
        r'\b(?:team|staff|agent|specialist|support)\b.{0,35}\b(?:is|are)\s+'
        r'(?:(?:currently|already|actively|now)\s+)*reviewing\b|'
        r'\breview\s+(?:(?:kiya|kiye)\s+ja\s+rah[aei]+|ho\s+rah[aei]+)\b|'
        r'समीक्षा\s*(?:की\s*जा\s*रही|हो\s*रही)|समीक्षाधीन\s*(?:है|हैं)', re.I)
    uncertain = re.compile(
        r"\b(?:cannot|can't|could\s+not|unable\s+to|do\s+not|don't)\s+(?:confirm|verify|know)\b|"
        r'\b(?:unknown|unconfirmed|not\s+(?:yet\s+)?known|not\s+confirmed)\b|'
        r'\b(?:nahi|nahin)\s+pata\b|\bpata\s+(?:nahi|nahin)\b|'
        r'पता\s*नहीं|पुष्टि\s*नहीं|नहीं\s*(?:जान|कह)')
    conditional = re.compile(r'\b(?:if|unless|assuming|whether|agar|yadi)\b|यदि|अगर', re.I)
    for clause in re.split(r'[.!?;।\n]+|,\s*|\b(?:but|however|yet|and|aur)\b|लेकिन|परंतु|और', answer, flags=re.I):
        for match in activity.finditer(clause):
            prefix = clause[:match.start()]
            # Scope qualifications to this predicate, never the next contrastive clause.
            if uncertain.search(prefix) or conditional.search(prefix):
                continue
            suffix = clause[match.end():match.end()+60]
            if re.search(r'^\s*(?:hai\s+)?ya\s+(?:nahi|nahin)\b',suffix,re.I):
                continue
            if re.search(r'\b(?:nahi|nahin)\b|नहीं', suffix, re.I):
                continue
            raise ValueError('unconfirmed_active_staff_review')
