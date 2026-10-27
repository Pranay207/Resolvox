"""Finite source-bound UI-label check; never authors navigation instructions.

General claim verbs, payment-method choices, neutral questions and statements of
missing documentation are outside this named-control guard. It is not a full
procedure/entailment checker or a model of an application's actual interface.
"""
from datetime import date
import hashlib
import json
import re
import unicodedata
from .config import REFERENCE_DATE
from .kb import AUTHORITY

_TYPE=re.compile(r'\b(?:buttons?|options?|tabs?|menus?|forms?)\b|\u092c\u091f\u0928|\u0935\u093f\u0915\u0932\u094d\u092a|\u091f\u0948\u092c|\u092e\u0947\u0928\u0942|\u092b\u0949\u0930\u094d\u092e|\u092b\u093e\u0930\u094d\u092e',re.I)
_QUOTES=r"[\"'`\u2018\u2019\u201c\u201d]"
_QUOTED=re.compile(_QUOTES+r'([^\"\'`\u2018\u2019\u201c\u201d\n]{1,70})'+_QUOTES)
_CAPITAL=r'[A-Z][A-Za-z0-9_-]*(?:\s+[A-Z][A-Za-z0-9_-]*){0,5}'
_STRONG_ACTION=re.compile(r'\b(?:click|tap|press|hold)\b|\u0915\u094d\u0932\u093f\u0915|\u091f\u0948\u092a|\u0926\u092c\u093e',re.I)
_UI_CONTEXT=re.compile(r'\b(?:app|application|screen|interface|navigate|navigation|click|tap)\b|\u090f\u092a|\u0905\u092a\u094d\u092a|\u0938\u094d\u0915\u094d\u0930\u0940\u0928|\u0915\u094d\u0932\u093f\u0915|\u091f\u0948\u092a',re.I)
_STOP=frozenset('the a an this that these those one another any available appropriate desired corresponding app application screen button buttons option options tab tabs menu menus form forms on to par pe mein me karein karen karo kijiye click tap press hold select choose open go'.split())
_NEG=re.compile(r"\b(?:no|not|never|cannot|can't|doesn't|does\s+not|nahi|nahin)\b|\u0928\u0939\u0940\u0902",re.I)
_DOC=re.compile(r'\b(?:source|document|policy|evidence|text|information|provided|supplied)\w*\b|\u0926\u0938\u094d\u0924\u093e\u0935\u0947\u091c|\u0938\u094d\u0930\u094b\u0924|\u0928\u0940\u0924\u093f|\u091c\u093e\u0928\u0915\u093e\u0930\u0940',re.I)

def _norm(value):
 return ' '.join(unicodedata.normalize('NFKC',value).casefold().strip(' \t\r\n.:,;\"\'`').split())

def _parts(text):return re.findall(r'[^.!?;\u0964\n]+[.!?;\u0964\n]?',text)

def _neutral(part):
 if '?' in part:return True
 # A negative/absence clause must not hide a later positive instruction.
 positive_tail=re.search(r'(?:,|\b(?:and|but|then|however|phir|lekin)\b)\s*(?:you\s+(?:can|should|must)\s+)?(?:click|tap|select|open|choose|fill|complete|view|see|review|check)\b',part,re.I)
 if positive_tail:return False
 return (bool(_DOC.search(part) and _NEG.search(part))
         or bool(re.search(r"\b(?:do\s+not|don't|never|cannot|can't)\s+(?:\w+\s+){0,2}(?:click|tap|select|open|press|view|see|review|check)\b|\b(?:click|tap)\s+(?:mat|nahi|nahin)\b",part,re.I)))

def _candidates(prefix,*,source=False):
 prefix=prefix.rstrip()
 quoted=list(_QUOTED.finditer(prefix))
 if quoted and not prefix[quoted[-1].end():].strip(' :,-'):
  return [_norm(quoted[-1][1])]
 capital=re.search(r'('+_CAPITAL+r')\s*$',prefix)
 if capital:return [_norm(capital[1])]
 # Ordinary lowercase labels may have multiple words. Source extraction uses
 # the nearest explicit action/determiner; answers offer bounded suffixes only
 # for matching an actual source-derived label, never for inventing a name.
 segment=re.split(r'\b(?:click|tap|press|hold|select|choose|open|use|the|a|an|called|named|labelled|labeled)\b',prefix,flags=re.I)[-1]
 words=re.findall(r'[^\W_][\w-]*',segment,flags=re.UNICODE)[-6:]
 while words and _norm(words[0]) in _STOP:words.pop(0)
 if not words or all(_norm(word) in _STOP for word in words):return []
 values=[' '.join(words)] if source else [' '.join(words[-length:]) for length in range(1,len(words)+1)]
 return list(dict.fromkeys(_norm(value) for value in values if _norm(value) not in _STOP))

def _after_target(tail):
 quoted=_QUOTED.match(tail.lstrip())
 if quoted:return [_norm(quoted[1])]
 if re.match(r'^\s*(?:your|this|that|its)\s+',tail,re.I):return []
 tail=re.split(r'\b(?:and|then|to|for|with|on|par|pe|karein|karen|karo|kijiye|button|option|tab|menu|form)\b|[>,;.!?\u0964]|\u092a\u0930|\u092a\u0947|\u0915\u0930\u0947\u0902',tail,maxsplit=1,flags=re.I)[0]
 tail=re.sub(r'^(?:(?:on|to|the|a|an)\s+)+','',tail,flags=re.I).strip()
 words=re.findall(r'[^\W_][\w-]*',tail,flags=re.UNICODE)
 if not 1<=len(words)<=6:return []
 value=_norm(' '.join(words))
 return [value] if value not in _STOP else []

def _named_controls(part,*,source=False):
 found=[]
 quoted_spans=[(match.start(),match.end()) for match in _QUOTED.finditer(part)]
 path_spans=[match.span(1) for match in re.finditer(r'\b(?:under|from|to|in)\s+('+_CAPITAL+r')',part)]
 action_spans=[match.span(1) for match in re.finditer(r'\b(?:click|tap|select|open)\s+(?:(?:on|to|the)\s+)*('+_CAPITAL+r')',part)]
 for match in _TYPE.finditer(part):
  if any(begin<=match.start()<end for begin,end in quoted_spans+path_spans+action_spans):continue
  # Option is also a normal payment/remedy choice, not necessarily an app UI.
  if re.fullmatch(r'options?|\u0935\u093f\u0915\u0932\u094d\u092a',match[0],re.I) and not _UI_CONTEXT.search(part):
   continue
  prefix=part[:match.start()].rsplit(',',1)[-1]
  values=_candidates(prefix,source=source)
  if values:found.append(values)
  named=re.match(r'\s+(?:named|called|labelled|labeled)\s+',part[match.end():],re.I)
  if named:
   values=_after_target(part[match.end()+named.end():])
   if values:found.append(values)
 for match in re.finditer(r'\b(?:click|tap|select|open)\s+(?:(?:on|to|the)\s+)*',part,re.I):
  tail=part[match.end():]
  if match[0].casefold().startswith(('select','open')) and not (_QUOTED.match(tail) or re.match(_CAPITAL,tail)):
   continue
  values=_after_target(tail)
  if values:found.append(values)
 for match in re.finditer(r'(?:\b(?:par|pe)\b|\u092a\u0930|\u092a\u0947)\s*(?:click|tap|\u0915\u094d\u0932\u093f\u0915|\u091f\u0948\u092a)',part,re.I):
  prefix=part[:match.start()].rstrip()
  preceding=list(_TYPE.finditer(prefix))
  if preceding and not prefix[preceding[-1].end():].strip():prefix=prefix[:preceding[-1].start()]
  values=_candidates(prefix,source=source)
  if values:found.append(values)
 return found

def _active(source):
 if source.get('doc_type') not in {'policy','help','agent_guide'} or source.get('status')!='current':return False
 try:return not source.get('effective_from') or date.fromisoformat(source['effective_from'])<=REFERENCE_DATE
 except (TypeError,ValueError):return False

def _fingerprint(source):
 fields={key:source[key] for key in ('id','text','file','doc_type','status','effective_from','version') if key in source}
 return hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def _actual_sources(sources):
 values=sources.values() if isinstance(sources,dict) else sources
 seen={}
 for source in values:
  if not isinstance(source,dict) or not isinstance(source.get('id'),str) or not isinstance(source.get('text'),str):continue
  digest=_fingerprint(source)
  if source['id'] in seen and digest!=_fingerprint(seen[source['id']]):raise ValueError('conflicting_navigation_source_id')
  seen[source['id']]=source
 return [source for source in seen.values() if _active(source)]

def _bind_names(contributions,*,procedure=False):
 rows=[]
 for key,items in sorted(contributions.items()):
  rank=min(AUTHORITY[source['doc_type']] for positive,source in items)
  chosen=[(positive,source) for positive,source in items if AUTHORITY[source['doc_type']]==rank]
  # A same/higher-authority prohibition cannot authorize a positive UI step.
  if not chosen or any(not positive for positive,source in chosen):continue
  row=({'operation':key[0],'object':key[1]} if procedure else {'label':key})
  used={source['id']:source for positive,source in chosen}
  row.update(source_ids=sorted(used),source_sha256={sid:_fingerprint(used[sid]) for sid in sorted(used)})
  rows.append(row)
 return rows

def derive_navigation_labels(sources):
 """Return only explicit navigation/control names with actual source authority."""
 labels={}
 for source in _actual_sources(sources):
  for part in _parts(re.sub(r'[*`]', '',source['text'])):
   groups=_named_controls(part,source=True)
   if _UI_CONTEXT.search(part) or re.search(r'\b(?:raise|raised|claim\w*|guide\w*)\b',part,re.I):
    for match in re.finditer(r'\b(?:under|from|to|in)\s+('+_CAPITAL+r')',part):groups.append([_norm(match[1])])
   for candidates in groups:
    for label in candidates:labels.setdefault(label,[]).append((not bool(_NEG.search(part)),source))
 return _bind_names(labels)

_RECORD_WORDS=r'(?:orders?|items?|products?|purchases?|records?|entries|entry|\u0911\u0930\u094d\u0921\u0930|\u0906\u0930\u094d\u0921\u0930|\u0906\u0907\u091f\u092e|\u0935\u0938\u094d\u0924\u0941|\u0909\u0924\u094d\u092a\u093e\u0926)'

def _record_object(word):
 word=_norm(word)
 if word in {'\u0911\u0930\u094d\u0921\u0930','\u0906\u0930\u094d\u0921\u0930'}:return 'order'
 if word in {'\u0906\u0907\u091f\u092e','\u0935\u0938\u094d\u0924\u0941'}:return 'item'
 if word=='\u0909\u0924\u094d\u092a\u093e\u0926':return 'product'
 if word=='entries':return 'entry'
 return word[:-1] if word.endswith('s') else word

def _procedure_mentions(part):
 steps=set()
 patterns=[r'\b(?:select|choose)\s+(?:(?:the|your|this|that|an?|desired|specific|relevant|corresponding)\s+){0,3}(?P<object>'+_RECORD_WORDS+r')\b',
           r'(?P<object>'+_RECORD_WORDS+r')(?:\s+(?:ko|ka|par|pe|mein|me|\u0915\u094b))?\s*(?:select|choose|\u091a\u0941\u0928\u0947\u0902|\u091a\u092f\u0928\s*\u0915\u0930\u0947\u0902)\b']
 for pattern in patterns:
  for match in re.finditer(pattern,part,re.I):steps.add(('select_record',_record_object(match['object'])))
 # Viewing a record is a distinct interaction from a documented location.
 # Bind only explicit record/detail verbs; payment or product choices remain
 # outside this typed procedure check.
 details=[r'\b(?:view|see|review|check|open)\s+(?:(?:the|your|this|that|an?|specific|relevant)\s+){0,3}(?P<object>'+_RECORD_WORDS+r')\s+(?:details|information)\b',
          r'(?P<object>'+_RECORD_WORDS+r')\s+(?:ki\s+)?details\s+(?:ko\s+)?(?:dekhne|dekhein|dekhen|dekho)\b']
 for pattern in details:
  for match in re.finditer(pattern,part,re.I):steps.add(('view_record_details',_record_object(match['object'])))
 for match in re.finditer(r'(?P<object>'+_RECORD_WORDS+r')\s+(?:ko\s+)?(?:dikhayein|dikhaayein|dekhein|dekhen|dekho)\b',part,re.I):
  steps.add(('view_record',_record_object(match['object'])))
 form=r'(?:\bforms?\b|\u092b\u0949\u0930\u094d\u092e|\u092b\u093e\u0930\u094d\u092e)'
 fill=r'(?:\b(?:fill|complete|bharein|bharen|bharo|bharna)\b|\u092d\u0930\u0947\u0902|\u092d\u0930\u093f\u090f)'
 if re.search(fill+r'[^.!?;\n]{0,70}'+form+'|'+form+r'[^.!?;\n]{0,70}'+fill,part,re.I):steps.add(('complete_form','form'))
 return steps

def derive_navigation_procedures(sources):
 """Typed explicit record-selection/form steps; no inferred intermediate UI."""
 contributions={}
 for source in _actual_sources(sources):
  for part in _parts(re.sub(r'[*`]', '',source['text'])):
   for step in _procedure_mentions(part):contributions.setdefault(step,[]).append((not bool(_NEG.search(part)),source))
 return _bind_names(contributions,procedure=True)

def validate_navigation_steps(answer,sources):
 """Reject invented positive named-control steps; return auditable source names."""
 # Materialize once so generators cannot consume the source-binding input.
 actual=list(sources.values() if isinstance(sources,dict) else sources)
 documented=derive_navigation_labels(actual);allowed={row['label'] for row in documented}
 procedures=derive_navigation_procedures(actual);steps={(row['operation'],row['object']) for row in procedures}
 ui_context=bool(_UI_CONTEXT.search(answer) or _TYPE.search(answer) or any(row['label'] in _norm(answer) for row in documented))
 for part in _parts(answer):
  if _neutral(part):continue
  if ui_context and any(step not in steps for step in _procedure_mentions(part)):raise ValueError('unsupported_navigation_procedure')
  for candidates in _named_controls(part):
   if not any(label in allowed for label in candidates):raise ValueError('unsupported_navigation_label')
 return documented
