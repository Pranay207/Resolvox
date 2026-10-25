"""Candidate-flow contracts only; fake embeddings, no answer gold/model calls."""
from types import SimpleNamespace
import json
import numpy as np
import pytest
from src.kb import Chunk,KnowledgeBase
from src.retrieval import Retriever


def chunk(i,status='current',kind='policy'):
 return Chunk('DOC-'+str(i),'## [DOC-'+str(i)+'] Scope\nActual supplied evidence.','pol_public.md',kind,status,'2026-01-01','1','Scope')


def controlled(monkeypatch,*,dense=False):
 docs=[chunk(i) for i in range(30)]
 kb=SimpleNamespace(chunks={c.id:c for c in docs},allowed=lambda c,historical=False:c.status=='current')
 r=Retriever(kb,dense=False)
 monkeypatch.setattr(r,'_bm25',lambda q:np.array([40-i for i in range(30)],dtype=float))
 monkeypatch.setattr(r,'_dependencies',lambda *a:{i:float(50-i) for i in range(20,30)})
 if dense:
  class Model:
   def encode(self,texts):return np.ones((len(texts),1),dtype=np.float32)
  r.model=Model()
  monkeypatch.setattr(r,'_similarities',lambda e:np.array([.9-i*.01 for i in range(30)],dtype=float))
 return r


@pytest.mark.parametrize('k',[1,4,6,8,12,20])
@pytest.mark.parametrize('dense',[False,True])
def test_all_direct_results_survive_bounded_dependency_append(monkeypatch,k,dense):
 r=controlled(monkeypatch,dense=dense);rows=r.search('neutral evidence request',k=k)
 direct=[x for x in rows if x['retrieval_role']=='direct'];extra=[x for x in rows if x['retrieval_role']=='dependency']
 assert [x['chunk'].id for x in direct]==['DOC-'+str(i) for i in range(k)]
 assert [x['direct_rank'] for x in direct]==list(range(1,k+1))
 assert len(extra)==min(4,max(0,k-6))
 assert len(rows)==k+len(extra)
 assert all(x['direct_rank'] is None and x['dependency_weight']>0 for x in extra)
 assert all(x['returned_count']==len(rows) and x['requested_direct_k']==k and x['candidate_limit']==k+min(4,max(0,k-6)) for x in rows)
 assert len({x['chunk'].id for x in rows})==len(rows)
 assert [x['score'] for x in rows]==sorted((x['score'] for x in rows),reverse=True)


@pytest.mark.parametrize('dense',[False,True])
def test_rank_twelve_actual_evidence_is_not_evicted(monkeypatch,dense):
 r=controlled(monkeypatch,dense=dense);rows=r.search('different wording never mapped to a section',k=12)
 assert rows[11]['chunk'] is r.kb.chunks['DOC-11']
 assert rows[11]['retrieval_role']=='direct' and rows[11]['direct_rank']==12
 assert [x['chunk'].id for x in rows[12:]]==['DOC-20','DOC-21','DOC-22','DOC-23']


def test_overlapping_dependencies_never_duplicate_direct_sources(monkeypatch):
 r=controlled(monkeypatch)
 monkeypatch.setattr(r,'_dependencies',lambda *a:{0:50,11:49,20:48})
 rows=r.search('neutral evidence request',k=12)
 assert len(rows)==13 and rows[-1]['chunk'].id=='DOC-20'
 assert rows[0]['retrieval_role']=='direct' and rows[0]['dependency_weight']==50


def test_no_dependencies_adds_no_unrelated_fill(monkeypatch):
 r=controlled(monkeypatch);monkeypatch.setattr(r,'_dependencies',lambda *a:{})
 assert len(r.search('neutral evidence request',k=12))==12


def test_actual_source_authority_remains_in_direct_fusion():
 body='Same actual public eligibility clause.'
 low=Chunk('LOW-1',body,'faq_public.md','faq','current','2026-01-01','1','Eligibility')
 high=Chunk('HIGH-1',body,'pol_public.md','policy','current','2026-01-01','1','Eligibility')
 kb=SimpleNamespace(chunks={c.id:c for c in (low,high)},allowed=lambda c,historical=False:True)
 assert Retriever(kb,dense=False).search('eligibility',k=1)[0]['chunk'] is high


def test_superseded_reference_never_enters_appended_dependencies():
 direct=Chunk('NEW-1','## [NEW-1] Eligibility\nPublic eligibility requires OLD-2.','pol_public.md','policy','current','2026-01-01','1','Eligibility')
 old=Chunk('OLD-2','## [OLD-2] Obsolete eligibility\nOutdated public rule.','pol_old.md','policy','superseded','2025-01-01','1','Obsolete eligibility')
 kb=SimpleNamespace(chunks={c.id:c for c in (direct,old)},allowed=lambda c,historical=False:c.status=='current')
 assert {x['chunk'].id for x in Retriever(kb,dense=False).search('eligibility',k=12)}=={'NEW-1'}


def test_real_public_generation_logs_actual_direct_and_dependency_counts():
 from src.agent import Agent
 from src.answering import Policy
 from src.data import Data
 class Client:
  last_metrics={}
  def complete(self,*a,**kw):return json.dumps({'answer':'The supplied sources do not establish that information.','covered':False,'needs_clarification':False})
 class Tools:
  def lookup(self,*a,**kw):raise AssertionError('Public query must not access private records')
  def ticket(self,*a,**kw):raise AssertionError('No ticket action requested')
 kb=KnowledgeBase();data=Data();r=SimpleNamespace(kb=kb,data=data,policy=Policy(kb,data),retriever=Retriever(kb,dense=False),llm=Client(),tools=Tools())
 out=Agent(r,compose=True).respond('Which jurisdictions can you ship purchases to?',language_hint='en')
 candidates=out['retrieval_candidates']
 assert out['retrieval_k']==out['retrieval_direct_k']==12
 assert out['retrieval_returned_count']==len(candidates)
 assert out['retrieval_direct_count']==sum(c['retrieval_role']=='direct' for c in candidates)==12
 assert out['retrieval_dependency_count']==sum(c['retrieval_role']=='dependency' for c in candidates)<=4
 assert out['retrieval_candidate_limit']==16 and out['retrieval_dependency_limit']==4
 for row in candidates:assert row['id'] in kb.chunks
