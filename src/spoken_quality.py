"""Reject exposed host labels and repeated answer sentences; never rewrite claims."""
import re
_INTERNAL=re.compile(r'\b(?:return_deadline|standard_fee_inr|minimum_business_days|maximum_business_days|refund_arrival_policy|timing_anchor)\b',re.I)
def check_spoken_quality(answer):
 if _INTERNAL.search(answer):raise ValueError('internal_metadata_in_answer')
 seen=set()
 for clause in re.split(r'[.!?;।\n]+',answer):
  key=' '.join(clause.casefold().split())
  if len(key)>=24 and len(key.split())>=5:
   if key in seen:raise ValueError('repeated_answer_sentence')
   seen.add(key)
