"""Bind a refund-arrival range to a known method and actual current table.

Finite validation and evidence selection only; never render a policy answer.
"""
from datetime import date
import hashlib
import re
from .grounding import _numeric_text, _UNITS

_REFUND = re.compile(r"refund|रिफ़?ंड|धनवापसी", re.I)
_DURATION = re.compile(r"\b(?:days?|long|soon|when|time|kab|kitn\w*)\b|दिन|कब|समय", re.I)
_RECEIPT = re.compile(r"\b(?:arriv\w*|receiv\w*|reach\w*|get|aay\w*|aeg\w*|mil\w*)\b|आए|आय|मिल", re.I)
_START = re.compile(r"\b(?:initiat\w*|start\w*|begin\w*|shuru)\b|शुरू|शुरुआत|आरंभ|प्रारंभ", re.I)
_COMPOUND = re.compile(r"\b(?:compare|all|each|every|warrant\w*|return\s+(?:window|deadline)|pick.?up\s+(?:cost|fee)|RRN)\b|तुलना|सभी|वारंटी|शुल्क", re.I)
# These questions need the original context, not a future-arrival-only view.
_REFUND_DETAILS = re.compile(
 r'\b(?:coupon\w*|discount\w*|partial|amount\w*|deduct\w*|fees?|charg\w*)\b|'
 r'\bhow\s+much\s+(?:money|refund)\b|\bkitn\w*\s+(?:paise|paisa|rak[am]+)\b|'
 r'कूपन|कुपन|छूट|राशि|रकम|आंशिक|शुल्क|कटौती|कितन[^।?!]{0,15}पैस', re.I)
_PAST_REFUND_EVENT = re.compile(
 r'\b(?:was|were|did|has|have|had)\b[^.!?;]{0,80}\b(?:complet\w*|settled|credited|arriv\w*|receiv\w*)\b|'
 r'(?:पूरा|पूर्ण)[^।?!]{0,12}(?:हुआ|हुई)|'
 r'\b(?:complete\w*|settle\w*|credit\w*)\s+(?:ho\s+)?(?:hua|hui|ho\s+gaya|ho\s+chuka)\b', re.I)
_METHODS = {
 'upi': r'\bupi\b|यूपीआई',
 'card': r'\b(?:(?:credit|debit)\s+)?cards?\b|कार्ड',
 'netbanking': r'\bnet\s*bank(?:ing)?\b|नेट\s*बैंक',
 'wallet': r'\bwallet\b|वॉलेट',
 'cod_bank': r'\bneft\b|\bbank\s+transfer\b',
}

def mentioned_methods(text):
 return {key for key,pattern in _METHODS.items() if re.search(pattern,text,re.I)}

def _recorded_completion(order):
 """A verified completion date takes precedence over an arrival estimate."""
 for event in ('return', 'cancellation', 'rto'):
  value=order.get(event+'_refund_completed_on')
  if not isinstance(value,str):continue
  try:date.fromisoformat(value[:10])
  except ValueError:continue
  return True
 return False


def refund_timeline_binding(query, facts, sources, reference_date):
 if _PAST_REFUND_EVENT.search(query) or _recorded_completion(facts.get('verified_order') or {}):return None
 if (not _REFUND.search(query) or not _DURATION.search(query) or _COMPOUND.search(query)
     or (_START.search(query) and not _RECEIPT.search(query))): return None
 from .document_context import _payment, _rows
 order=facts.get('verified_order') or {}
 recorded={_payment(order.get(event+'_refund_method')) for event in ('return','cancellation','rto') if order.get(event+'_refund_method')}
 known=recorded or {_payment(order.get('payment_method'))}
 if not order:
  known={_payment((facts.get('public_context') or {}).get('payment_method')),
         _payment((facts.get('customer_provided_refund_claim') or {}).get('payment_method'))}
 known.discard(None)
 explicit=mentioned_methods(query)
 if explicit and known and explicit != known: return None
 known=known or explicit
 if len(known)!=1:return None
 method=next(iter(known)); found=[]
 for source in sources:
  if source.get('doc_type')!='policy' or source.get('status')!='current':continue
  try:
   if source.get('effective_from') and date.fromisoformat(source['effective_from'])>date.fromisoformat(str(reference_date)[:10]):continue
  except (ValueError,TypeError):continue
  text=source.get('text','')
  if not (re.search(r'payment\s+method',text,re.I) and re.search(r'after\s+initiation|from[^.\n]{0,70}initiat',text,re.I)):continue
  for cells in _rows(source):
   if len(cells)!=2 or _payment(cells[0])!=method:continue
   span=re.fullmatch(r'\s*(\d+)\s+(?:to|-)\s+(\d+)\s+business\s+days?\s*',cells[1],re.I)
   if method=='wallet':
    hours=re.fullmatch(r'\s*(?:instant,?\s*)?within\s+(\d+)\s+hours?\s*',cells[1],re.I)
    if not hours:return None
    found.append((0,int(hours[1]),source,cells))
   else:
    if not span or int(span[1])>int(span[2]):return None
    found.append((int(span[1]),int(span[2]),source,cells))
 if not found or len({(r[0],r[1]) for r in found})!=1:return None
 low,high,_,cells=found[0]
 if method=='wallet':
  return {'payment_method':method,'source_payment_label':cells[0],'maximum_hours':high,
          'timing_unit':'hour','timing_anchor':'after_refund_initiation',
          'source_ids':sorted({r[2]['id'] for r in found}),
          'source_sha256':{r[2]['id']:hashlib.sha256(r[2]['text'].encode('utf-8')).hexdigest() for r in found}}
 return {'payment_method':method,'source_payment_label':cells[0],'minimum_business_days':low,
         'maximum_business_days':high,'timing_anchor':'after_refund_initiation',
         'source_ids':sorted({r[2]['id'] for r in found}),
         'source_sha256':{r[2]['id']:hashlib.sha256(r[2]['text'].encode('utf-8')).hexdigest() for r in found}}

def check_refund_timeline_answer(answer, query, facts, sources, reference_date):
 binding=refund_timeline_binding(query,facts,sources,reference_date)
 if facts.get('refund_arrival_policy') is not None and facts['refund_arrival_policy']!=binding:
  raise ValueError('unbound_refund_arrival_policy')
 if not binding:return None
 if binding['payment_method']=='wallet':
  maximum=binding['maximum_hours']
  if not re.search(r'(?<![\d.])'+str(maximum)+r'\s*(?:hours?|hrs?|ghant\w*|घंटे|घंटों)(?![A-Za-z\u0900-\u097f])',_numeric_text(answer),re.I):
   raise ValueError('missing_refund_arrival_range')
  if not (_START.search(answer) and re.search(r'\b(?:after|following|from|once)\b|के\s*(?:बाद|पश्चात)|ke\s+baad',answer,re.I)):
   raise ValueError('missing_refund_initiation_anchor')
  if mentioned_methods(answer)-{'wallet'}:raise ValueError('wrong_refund_payment_method')
  order=facts.get('verified_order') or {}
  if not any(order.get(event+'_refund_initiated_on') for event in ('return','cancellation','rto')):
   from .document_answers import _date_mentions
   if _date_mentions(answer):raise ValueError('unsupported_refund_arrival_date')
  return binding
 low=binding['minimum_business_days']; high=binding['maximum_business_days']
 unit=_UNITS['business_day']
 # Require one ordered range with its unit, not stray matching digits.
 pattern=(r'(?<![\d.])'+str(low)+r'\s*(?:'+unit+r')?\s*(?:to|[-–]|से|se|and|और|तक)\s*'
          +str(high)+r'\s*(?:'+unit+r')(?![A-Za-z\u0900-\u097f])')
 if not re.search(pattern,_numeric_text(answer),re.I):raise ValueError('missing_refund_arrival_range')
 if not (_START.search(answer) and re.search(r'\b(?:after|following|from|once)\b|के\s*(?:बाद|पश्चात)|ke\s+baad',answer,re.I)):
  raise ValueError('missing_refund_initiation_anchor')
 methods=mentioned_methods(answer)
 if methods and methods!={binding['payment_method']}:raise ValueError('wrong_refund_payment_method')
 return binding

def refund_timeline_inputs(query, facts, sources, reference_date):
 binding=refund_timeline_binding(query,facts,sources,reference_date)
 if not binding or facts.get('operational_escalation') or facts.get('refund_arrival_policy')!=binding:return None
 # Leave the complete original sources/facts available for every requested facet.
 if _REFUND_DETAILS.search(query):return None
 ids=set(binding['source_ids'])
 for source in sources:
  text=source.get('text','')
  if source.get('status')!='current':continue
  # Keep original initiation/QC/membership prerequisites and calendar definitions.
  if ((source.get('doc_type')=='policy' and re.search(r'refund',text,re.I)
       and re.search(r'quality\s+check|does\s+not\s+change',re.sub(r'[*`]', '', text),re.I))
      or (source.get('doc_type')=='meta' and re.search(r'A business day is',text,re.I))):ids.add(source['id'])
 selected=[s for s in sources if s['id'] in ids]
 if sum(len(s['text']) for s in selected)>5000:return None
 order=facts.get('verified_order') or {}
 view={'refund_arrival_policy':binding,'verified_order':{k:order[k] for k in
       ('payment_method','is_plus','return_status','return_pickup_on','return_qc_passed_on',
        'return_refund_initiated_on','return_refund_method','cancellation_refund_method','rto_refund_method') if k in order}}
 for key in ('customer_provided_refund_claim','public_context','pending_refund_requirement','calculations','date_labels'):
  if facts.get(key):view[key]=facts[key]
 from .inference_facts import project_inference_facts
 return {'sources':selected,'facts':project_inference_facts(view)}
