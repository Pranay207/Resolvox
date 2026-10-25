"""Finite role binding for personal refund/paid amounts, never policy answers.

A monetary value appearing in a source fee table is not a customer's transaction
amount. This does not prove arbitrary financial-language entailment or payment
status; it checks explicit currency-linked refund/payment amount attributions.
"""
from decimal import Decimal,InvalidOperation
import hashlib
import re
import unicodedata
from .grounding import _numeric_text

_MONEY=re.compile(r'(?:\u20b9|\binr\b|\brs\.?|\brupees?)\s*(?P<before>\d+(?:\.\d{1,2})?)|(?P<after>\d+(?:\.\d{1,2})?)\s*(?:rupees?|rupaye?|rupay|\u0930\u0941\u092a\u092f\u0947|\u0930\u0941\u092a\u090f|\u0930\u0941\u092a\u092f\u093e|inr\b)',re.I)
_REFUND=re.compile(r'\brefund\w*\b|\u0930\u093f\u092b\u093c?\u0902\u0921|\u0930\u093f\u092b\u0902\u0921',re.I)
_PAID=re.compile(r'\b(?:paid|pay(?:ment)?|bhugtan|bhugataan)\b|\u092d\u0941\u0917\u0924\u093e\u0928|\bpay\s+kiya\b',re.I)
_FEE=re.compile(r'\b(?:fees?|charges?|surcharge|postage)\b|\u0936\u0941\u0932\u094d\u0915|\u092b\u0940\u0938',re.I)
_TOTAL=re.compile(r'\b(?:order\s+(?:total|amount|value)|basket\s+(?:total|amount|value)|total\s+(?:amount|value))\b',re.I)
_PERSONAL=re.compile(r'\b(?:your|you|i|we|my|our|mera|meri|mere|aapka|aapki|aapke|maine|hamara)\b|\u0906\u092a\u0915|\u092e\u0947\u0930|\u092e\u0948\u0902\u0928\u0947',re.I)
_EVENT={'return':re.compile(r'\breturn\w*\b|\u0930\u093f\u091f\u0930\u094d\u0928',re.I),
        'cancellation':re.compile(r'\bcancel\w*\b|\u0915\u0948\u0902\u0938\u093f\u0932',re.I),
        'rto':re.compile(r'\brto\b|return\s+to\s+origin',re.I)}


def _decimal(value):
 if type(value) is bool:return None
 try:amount=Decimal(str(value).replace(',',''))
 except (InvalidOperation,ValueError,TypeError):return None
 return amount if amount.is_finite() and amount>=0 else None

def _number(value):return format(value.normalize(),'f')

def _text(value):
 value=unicodedata.normalize('NFKC',value)
 value=re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))','',value)
 value=re.sub(r'\b(for\s+example|for\s+instance|hypothetically|suppose)\s*,\s*',r'\1 ',value,flags=re.I)
 value=value.replace(',',';')
 value=re.sub(r'\brs\.(?=\s*\d)','Rs',value,flags=re.I)
 return _numeric_text(value).casefold()

def _clauses(text):
 return [part for part in re.split(r'(?<!\d)[.!?]|[.!?](?!\d)|[;\u0964\n]|\b(?:but|however|lekin)\b',_text(text)) if part.strip()]

def _event(text):
 found={key for key,pattern in _EVENT.items() if pattern.search(text)}
 if found=={'return','rto'}:return 'rto'
 return next(iter(found)) if len(found)==1 else None

def _role(part,match):
 # A described policy fee is not automatically the caller's total payment.
 # Conversely an explicit personal past-paid predicate is a real amount claim,
 # even when it says the money was paid as a fee.
 if _PERSONAL.search(part):
  for paid in re.finditer(r'\bpaid\b|\bpay\s+kiya\b',part,re.I):
   between=part[paid.end():match.start()]
   if 0<=match.start()-paid.end()<=40 and not _MONEY.search(between) and not _REFUND.search(between):return 'paid_amount'
 suffix=part[match.end():match.end()+55]
 fee=re.match(r'\s*(?:as\s+(?:(?:a|the)\s+)?)?(?:[a-z-]+\s+){0,4}(?:fee|charge)s?\b',suffix,re.I)
 if fee and not re.search(r'\b(?:including|includes|inclusive|covers|minus|after|before|refund|payment)\b',fee[0],re.I):return 'fee'
 candidates=[]
 for role,pattern in [('fee',_FEE),('refund_amount',_REFUND),('paid_amount',_PAID),('order_total',_TOTAL)]:
  for token in pattern.finditer(part):
   distance=min(abs(token.end()-match.start()),abs(token.start()-match.end()))
   if distance<=65:candidates.append((distance,0 if role=='fee' else 1,role))
 return min(candidates)[2] if candidates else None

def _negated_amount(part,match):
 prefix=part[max(0,match.start()-25):match.start()]
 return bool(re.search(r'\b(?:not|never|nahi|nahin)\s*(?:(?:exactly|around|about)\s*)?$',prefix,re.I))

def _conditional_amount(part,match,role):
 prefix=part[:match.start()]
 if re.search(r'\b(?:for\s+example|for\s+instance|hypothetically|suppose|assuming|maan\s+lijiye|udaharan)\b[^;]{0,80}$',prefix,re.I):return True
 if re.search(r'\b(?:if|agar|yadi)\b[^;]{0,70}$|(?:\u0905\u0917\u0930|\u092f\u0926\u093f)[^;]{0,70}$',prefix,re.I):
  if role=='refund_amount':
   premise=r'(?:refund(?:\s+amount)?|\u0930\u093f\u092b\u093c?\u0902\u0921)\s*(?:(?:is|were|was|equals|of|hai|ho)\s*)?$'
  else:premise=r'(?:paid|pay|payment|\u092d\u0941\u0917\u0924\u093e\u0928)\s*(?:(?:is|were|was|of|kiya)\s*)?$'
  if re.search(premise,prefix,re.I):return True
  if re.search(r'\b(?:if|agar|yadi)\s*$|(?:\u0905\u0917\u0930|\u092f\u0926\u093f)\s*$',prefix,re.I):return True
 if re.search(r'\b(?:a|an)\s*$',prefix,re.I) and not _PERSONAL.search(prefix):return True
 if re.search(r'\bfor\s+(?:a|an)\b[^;]{0,45}$',prefix,re.I) and not _PERSONAL.search(prefix):return True
 return False

def _generic(part,match,role):
 if _PERSONAL.search(part):return False
 if re.search(r'\b(?:refunds|refund\s+amounts|payment\s+amounts)\b',part,re.I):return True
 if role=='paid_amount' and re.search(r'\b(?:customers|members|shoppers)\s+(?:pay|are\s+charged)\b',part,re.I):return True
 return False

def _amount_question(prefix):
 subject=r'(?:(?:my|your|the|this)\s+)?(?:refund|payment)(?:\s+amount)?'
 return bool(re.search(r'^\s*(?:is|are)\s+'+subject+r'\s*(?:of|equal\s+to)?\s*$|'
                       r'^\s*(?:will|would|can|could)\s+'+subject+r'\s+(?:be|equal|amount\s+to)\s*$|'
                       r'\b(?:whether|if)\s+'+subject+r'\s+(?:is|will\s+be|equals)\s*$|'
                       r'^\s*does\s+'+subject+r'\s+equal\s*$|'
                       r'^\s*(?:did|have|had)\s+(?:i|you|we)\s+(?:pay|paid)\s*$',prefix,re.I))


def _mentions(text):
 result=[]
 for part in _clauses(text):
  for match in _MONEY.finditer(part):
   amount=_decimal(match['before'] or match['after']);role=_role(part,match)
   if amount is None or role is None or _negated_amount(part,match):continue
   result.append({'amount':_number(amount),'role':role,'event':_event(part),
                  'conditional':_conditional_amount(part,match,role),'generic':_generic(part,match,role),
                  'uncertain_amount':bool('?' in text and _amount_question(part[:match.start()]))})
 return result


def _safe_record_bindings(facts,private):
 if not private:return []
 record=facts.get('verified_order',{})
 if not isinstance(record,dict):raise ValueError('invalid_personal_money_record')
 result=[]
 for key,value in record.items():
  if re.fullmatch(r'(?:return|cancellation|rto)_refund_amount_inr',key):role='refund_amount';event=key.split('_refund_',1)[0]
  elif key in {'paid_amount_inr','amount_paid_inr'}:role='paid_amount';event=None
  elif key in {'total_inr','order_total_inr'}:role='order_total';event=None
  else:continue
  amount=_decimal(value)
  if amount is not None:result.append({'amount':_number(amount),'currency':'INR','role':role,'event':event,'origin':'verified_record','path':'verified_order.'+key})
 return result

def derive_personal_money_bindings(query,facts,sources,*,private=False):
 """Safe typed premises, never raw questions, records, identifiers or proofs."""
 if not isinstance(query,str) or not isinstance(facts,dict):raise ValueError('invalid_personal_money_inputs')
 values=[row for row in _mentions(query) if row['role'] in {'refund_amount','paid_amount','order_total'} and not row['conditional'] and not row['generic'] and not row['uncertain_amount']]
 public=[]
 for role in ('refund_amount','paid_amount','order_total'):
  grouped={row['amount'] for row in values if row['role']==role}
  if len(grouped)==1:
   amount=next(iter(grouped));events={row['event'] for row in values if row['role']==role and row['event']}
   public.append({'amount':amount,'currency':'INR','role':role,'event':next(iter(events)) if len(events)==1 else None,'origin':'customer_provided_unverified','path':'question.explicit_currency_premise'})
 verified=_safe_record_bindings(facts,private)
 # Source-backed calculations may carry forward independently bound monetary
 # inputs. A source fee alone, a forged key or an unrelated scalar never binds
 # an unknown transaction amount, even if its number appears in source text.
 bound=verified+public;calculation_inputs=[]
 by_id={row['id']:row for row in sources if isinstance(row,dict) and isinstance(row.get('id'),str)}
 hashes=facts.get('calculation_source_sha256',{})
 calculations=facts.get('calculations',[])
 for index,calc in enumerate(calculations if isinstance(calculations,list) else []):
  if not isinstance(calc,dict):continue
  ids=calc.get('source_ids');inputs=calc.get('inputs')
  if not isinstance(ids,list) or not ids or not isinstance(inputs,dict) or any(sid not in by_id for sid in ids):continue
  if any(hashes.get(sid)!=hashlib.sha256(by_id[sid]['text'].encode()).hexdigest() for sid in ids):continue
  for key,value in inputs.items():
   role='refund_amount' if re.fullmatch(r'(?:return_|cancellation_|rto_)?refund_amount_inr',key) else 'paid_amount' if key in {'paid_amount_inr','amount_paid_inr'} else 'order_total' if key in {'order_amount_inr','order_total_inr','total_inr'} else None
   amount=_decimal(value)
   if role and amount is not None and any(row['role']==role and _decimal(row['amount'])==amount for row in bound):
    calculation_inputs.append({'amount':_number(amount),'currency':'INR','role':role,'event':None,'origin':'source_backed_calculation_input','path':f'calculations[{index}].inputs.{key}','source_ids':ids})
 return {'amount_bindings':bound,'calculation_inputs':calculation_inputs,'policy_fee_values_are_not_personal_amounts':True}

def validate_personal_money(answer,query,facts,sources,*,private=False):
 bindings=derive_personal_money_bindings(query,facts,sources,private=private)
 known=bindings['amount_bindings']
 query_event=_event(query)
 for claim in _mentions(answer):
  if claim['role'] not in {'refund_amount','paid_amount'} or claim['conditional'] or claim['generic']:continue
  role=claim['role'];event=claim['event'] or query_event
  applicable=[row for row in known if row['role']==role and (not event or row['event'] in {None,event})]
  # A verified field outranks an inconsistent public amount. Distinct active
  # refund fields cannot silently choose the customer's intended event.
  verified=[row for row in applicable if row['origin']=='verified_record']
  if verified:applicable=verified
  if len({row['amount'] for row in applicable})!=1 or claim['amount'] not in {row['amount'] for row in applicable}:
   raise ValueError('unsupported_personal_money_amount')
 return bindings
