"""Finite source-bound prerequisites for definite recipient remedy claims.

This does not authorize a remedy or claim that verification was performed.
Authenticated identity is distinct from claim verification/inspection/approval.
"""
from datetime import date
import hashlib,json,re,unicodedata

_AUTHORITY={'policy':4,'agent_guide':3,'help':2}
_RECIPIENT=re.compile(r'\b(?:you|customer|customers|buyer|buyers|aapko|aap|grahak|customer\s+ko)\b|आपको|आप\b|ग्राहक',re.I)
_ENTITLED=re.compile(r'\b(?:gets?|receiv\w*|entitled|eligible|qualif\w*|mile\w*|milt\w*|mil\s+jay\w*)\b|मिले|मिलत|मिल\s*जाए|पात्र|हकदार|प्राप्त',re.I)
_REMEDIES={'refund':re.compile(r'\brefund\w*\b|रिफ़?ंड|धनवापसी',re.I),
 'replacement':re.compile(r'\breplace\w*\b|रिप्लेसमेंट|प्रतिस्थापन|बदलाव',re.I)}
_CONDITIONS={'verification':re.compile(r'\b(?:verif\w*|validation|validated|validate)\b|सत्यापन|सत्यापित|पुष्टि',re.I),
 'inspection':re.compile(r'\binspect\w*\b|निरीक्षण|जाँच|जांच',re.I),
 'approval':re.compile(r'\bapprov\w*\b|मंजूरी|अनुमोदन|स्वीकृति',re.I)}
_RELATION=re.compile(r'\b(?:after|following|upon|once|subject\s+to|baad)\b|के\s*बाद|होने\s*पर',re.I)
_NEGATIVE=re.compile(r'\b(?:not|no|never|cannot|can\x27t|won\x27t|nahi|nahin)\b|नहीं|नही',re.I)
_TENTATIVE=re.compile(r'\b(?:may|might|could|possibly|consider\w*|sakt\w*)\b|सकता|सकती|संभव',re.I)
_QUESTION=re.compile(r'^\s*(?:can|could|would|will|what|which|whether|क्या|kya)\b',re.I)
_SCOPE_ALIASES={
 'damage':r'\b(?:damag\w*|torn|ripped|broken|defect\w*|expired|toot\w*|tut\w*|phat\w*)\b|फट|टूट|खराब|क्षतिग्रस्त|दोषपूर्ण|एक्सपायर',
 'wrong':r'\b(?:wrong|incorrect|mismatch\w*|galat)\b|गलत',
 'missing':r'\b(?:missing|absent|gayab|gaayab)\b|गायब|लापता'}
_ALLOWED_TAIL=re.compile(r'^[\s,:()\-]*(?:(?:is|was|has|have|been|be|successfully|complete|completed|done|passed|of|the|your|a|an|claim|damage|item|identity|account|payment|quality|customer|order|verification|inspection|approval|hone|ke|baad|ho|jaane|gaya|hai|की|के|का|बाद|होने|पर|पूरा|पूरी|है|हो|गया|दावे|दावा|पहचान|जाँच|जांच|सत्यापन|मंजूरी)\b[\s,:()\-]*)*$',re.I)


_TAIL_WORDS=frozenset('is was has have been be successfully complete completed done passed of the your a an claim damage item identity account payment quality customer order verification inspection approval hone ke baad ho jaane gaya hai की के का बाद होने पर पूरा पूरी है हो गया दावे दावा पहचान जाँच जांच सत्यापन मंजूरी'.split())

def _tail_allowed(text):
 return all(word in _TAIL_WORDS for word in re.findall(r'[^\s,:()\-]+',text))

def _norm(value):return ' '.join(unicodedata.normalize('NFKC',str(value)).casefold().replace('’',"'").split())
def _parts(value):return [x.strip() for x in re.split(r'[.!?;।\n]+',str(value)) if x.strip()]
def _role(text):
 text=_norm(text)
 if re.search(r'\b(?:identity|authentication|account)\b|पहचान',text):return 'identity'
 if re.search(r'\b(?:damage|damaged|claim)\b|दाव[ेा]|नुकसान',text):return 'claim'
 if re.search(r'\b(?:quality|qc)\b|गुणवत्ता',text):return 'quality'
 if re.search(r'\bpayment\b|भुगतान',text):return 'payment'
 return 'unspecified'

def _fingerprint(source):
 fields={k:source.get(k) for k in ('id','text','file','doc_type','status','effective_from','version')}
 return hashlib.sha256(json.dumps(fields,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def _condition_occurrences(text):
 text=_norm(text);result=[]
 for kind,pattern in _CONDITIONS.items():
  for match in pattern.finditer(text):
   before=text[max(0,match.start()-70):match.start()];after=text[match.end():match.end()+80]
   # Both ordinary English and Hindi/Roman postpositions are finite forms.
   if _RELATION.search(before) or re.match(r'\s*(?:ke\s+baad|के\s*बाद|होने\s*पर)',after):
    prefix=list(_RELATION.finditer(before))
    begin=max(0,match.start()-70)+(prefix[-1].start() if prefix else len(before))
    result.append({'kind':kind,'role':_role(text[begin:match.end()+35]),'start':match.start(),'end':match.end(),
      'relation_start':begin})
 return sorted(result,key=lambda x:x['start'])

def _recipient_claims(text):
 text=_norm(text);recipients=list(_RECIPIENT.finditer(text));claims=[]
 for index,recipient in enumerate(recipients):
  end=recipients[index+1].start() if index+1<len(recipients) else len(text)
  window=text[recipient.start():min(end,recipient.end()+180)]
  verb=_ENTITLED.search(window)
  if not verb:continue
  remedies=[kind for kind,pattern in _REMEDIES.items() if pattern.search(window)]
  if not remedies:continue
  claims.append({'start':recipient.start(),'end':end,'window':window,'remedies':remedies,
    'negative':bool(_NEGATIVE.search(window[:max(verb.end(),next((m.end() for p in _REMEDIES.values() if (m:=p.search(window))),verb.end()))])),
    'tentative':bool(_TENTATIVE.search(window[:verb.end()+12]))})
 return claims

def derive_remedy_prerequisites(sources, *, reference_date=None):
 """Return only actual attached verification/inspection/approval conditions."""
 today=date.fromisoformat(str(reference_date)[:10]) if reference_date is not None else None
 result=[]
 for source in sources:
  if not isinstance(source,dict) or source.get('status','current')!='current' or source.get('doc_type') not in _AUTHORITY:continue
  if not isinstance(source.get('id'),str) or not isinstance(source.get('text'),str):continue
  if source.get('effective_from'):
   try:effective=date.fromisoformat(str(source['effective_from'])[:10])
   except ValueError:continue
   if today is None or effective>today:continue
  topic=_norm(str(source.get('file') or '')+' '+str(source.get('title') or ''))
  scope=[key for key in _SCOPE_ALIASES if re.search(r'\b'+key+r'\w*\b',topic.replace('_',' '))]
  for original in _parts(source['text']):
   text=_norm(re.sub(r'[*`]', '',original));claims=_recipient_claims(text)
   if not claims:continue
   for condition in _condition_occurrences(text):
    for claim in claims:
     # The relation and remedy predicate must share this source clause. A
     # different recipient/action between them is not a bound prerequisite.
     if condition['end']<=claim['start']:
      tail=text[condition['end']:claim['start']]
      if not _tail_allowed(tail):continue
     elif condition['start']>=claim['start']:
      # Suffix prerequisites belong only to the current recipient predicate.
      if condition['relation_start']<claim['start'] or condition['start']>=claim['end']:continue
     else:continue
     result.append({'kind':'remedy_prerequisite','condition_kind':condition['kind'],
       'condition_role':condition['role'],'remedies':claim['remedies'],'scope_topics':scope,
       'source_ids':[source['id']],'source_sha256':{source['id']:_fingerprint(source)},
       'source_clause':original,'authority':source['doc_type'],'priority':_AUTHORITY[source['doc_type']]})
 return result

def _qualified(text,claim,rule):
 for condition in _condition_occurrences(text):
  if condition['kind']!=rule['condition_kind']:continue
  expected=rule['condition_role'];actual=condition['role']
  if actual!='unspecified' and actual!=expected:continue
  if condition['end']<=claim['start']:
   if _tail_allowed(text[condition['end']:claim['start']]):return True
  elif claim['start']<=condition['relation_start']<condition['start']<claim['end']:
   return True
 return False

def _actual_proof(rule,facts):
 # This application documents an authenticated identity boundary only. It does
 # not document a tool proof for generic/claim/quality/payment verification or
 # claim approval. Photos, customer assertions and arbitrary damage statuses
 # never become a claim-verification result here.
 return (rule['condition_kind']=='verification' and rule['condition_role']=='identity'
         and isinstance(facts.get('verified_order'),dict) and bool(facts['verified_order']))

def _uncertain_prefix(text,claim):
 prefix=text[:claim['start']]
 matches=list(re.finditer(r"\b(?:cannot|can't|unable to)\s+(?:confirm|verify|determine|say)\b|confirm\s+(?:nahi|nahin)(?:\s+kar\s+sakt\w*)?|पुष्टि\s+नहीं\s+कर\s+सकत[ाी]",prefix,re.I))
 if not matches:return False
 tail=prefix[matches[-1].end():].strip(' ,:')
 return all(word in {'whether','if','that','the','ki','कि'} for word in tail.split())


def check_remedy_prerequisites(answer,query,sources, *, facts=None,reference_date=None):
 """Check definite recipient entitlement, not fee-only or neutral options.

 Finite vocabulary/scope; not a general conditional entailment certificate.
 """
 rules=derive_remedy_prerequisites(sources,reference_date=reference_date);facts=facts or {}
 topic=_norm(query+' '+answer)
 applicable=[r for r in rules if not r['scope_topics'] or any(re.search(_SCOPE_ALIASES[key],topic,re.I) for key in r['scope_topics'])]
 for original in _parts(answer):
  text=_norm(original)
  if _QUESTION.search(text):continue
  for claim in _recipient_claims(text):
   if claim['negative'] or claim['tentative'] or _uncertain_prefix(text,claim):continue
   for remedy in claim['remedies']:
    candidates=[r for r in applicable if remedy in r['remedies']]
    if not candidates:continue
    priority=max(r['priority'] for r in candidates)
    for rule in candidates:
     if rule['priority']!=priority:continue
     if not _actual_proof(rule,facts) and not _qualified(text,claim,rule):
      raise ValueError('missing_remedy_prerequisite:'+rule['condition_kind'])
 return applicable
