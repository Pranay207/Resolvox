"""Bind explicit public policy choices and matching table rows to real sources.

No business names, amounts, IDs, expected answers or authored replies live here.
Ambiguous/current conflicts leave the ordinary generation path unchanged.
"""
from datetime import date
import re

_CHOICE=re.compile(r'\bFor\s+(?P<scope>[^.;\n]{1,80}?)\s+orders\s*,\s*the\s+customer\s+chooses\s+either\s+(?P<left>[^.;\n]+?)\s+or\s+(?P<right>[^.;\n]+)',re.I)
def _norm(value):return ' '.join(re.findall(r'[^\W_]+',value.casefold()))
def _active(row,reference):
 if row.get('doc_type')!='policy' or row.get('status')!='current':return False
 try:return date.fromisoformat(row['effective_from'])<=reference
 except (KeyError,TypeError,ValueError):return False

def choice_restatement_inputs(query,sources,reference_date):
 """Return exact governing paragraphs and source table fragments, never prose."""
 reference=date.fromisoformat(str(reference_date));available=[r for r in sources if _active(r,reference)]
 query_norm=_norm(query);candidates=[]
 if re.search(r'\b(?:not|never|no|didn t|wasn t|isn t|don t)\b',query_norm):return None
 for row in available:
  for match in _CHOICE.finditer(row['text']):
   scope=_norm(match['scope']);words=scope.split();acronym=''.join(w[0] for w in words)
   if scope not in query_norm and not (len(acronym)>=3 and re.search(r'(?<!\w)'+re.escape(acronym)+r'(?!\w)',query_norm)):continue
   if re.search(r'\bor\b',match['right'],re.I):continue
   options=[re.sub(r'^(?:a|an|the)\s+','',re.sub(r'\([^)]*\)','',match[key]).strip(),flags=re.I) for key in ('left','right')]
   if not all(options):continue
   candidates.append((row,scope,options))
 if len(candidates)!=1:return None
 governing,scope,options=candidates[0];rows=[];values={}
 for source in available:
  lines=source['text'].splitlines();table=[line for line in lines if line.lstrip().startswith('|')]
  if not table:continue
  basis=[m[0].strip() for m in re.finditer(r'[^.!?;\n]*(?:timelines?|times?)\s+are\s+counted[^.!?;\n]*',source['text'],re.I)]
  for line in table[2:]:
   cells=[c.strip() for c in line.strip().strip('|').split('|')]
   if len(cells)!=2 or scope not in _norm(cells[0]):continue
   matched=[option for option in options if _norm(option) in _norm(cells[0])]
   if len(matched)!=1:continue
   key=_norm(matched[0]);value=_norm(cells[1]);values.setdefault(key,set()).add(value)
   rows.append({'source_id':source['id'],'table_header':table[0],'row':line,'time_basis':basis})
 if any(len(v)>1 for v in values.values()):return None
 return {'sources':[governing], 'facts':{'source_choice_rule':{'scope':scope,'options':options,'source_ids':[governing['id']]},'matching_timing_rows':rows}}
