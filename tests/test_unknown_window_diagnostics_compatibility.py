"""Actual-import compatibility between a bound-window guard and safe diagnostics."""
import copy
import json
import socket
import pytest
import requests
from src.document_answers import document_reply
from src.generation_diagnostics import GenerationValidationError,failure_diagnostics


def test_terminal_bound_unknown_window_failure_retains_safe_code_and_metrics(monkeypatch):
    def denied(*a,**k): raise AssertionError('No network permitted')
    monkeypatch.setattr(socket,'create_connection',denied)
    monkeypatch.setattr(requests.sessions.Session,'request',denied)
    sources=[{'id':'SYNTHETIC-TABLE','text':'| Garments and bags | 12 days | cloth_x |','doc_type':'policy','status':'current','effective_from':'2030-01-01'},
             {'id':'SYNTHETIC-EXCEPTION','text':'Garments and bags from orders placed between 3 April and 11 April 2031 can be returned within 24 days of delivery.','doc_type':'policy','status':'current','effective_from':'2030-01-01'}]
    facts={'reference_date':'2031-05-01','return_policy':{'category':'cloth_x','window_calendar_days':12,'source_ids':['SYNTHETIC-TABLE'],'selection':'standard_window','placement_date_unavailable':True,
           'placement_exception':{'placed_from':'2031-04-03','placed_through':'2031-04-11','window_calendar_days':24,'source_ids':['SYNTHETIC-EXCEPTION']}}}
    originals=copy.deepcopy((sources,facts))
    class Client:
        calls=0
        last_metrics={}
        def complete(self,*a,**k):
            self.calls+=1
            assert self.calls<=2
            self.last_metrics={'cache_hit':False,'http_attempts':self.calls,'wall_ms':self.calls,'headers':{'Authorization':'PRIVATE_SENTINEL'}}
            return json.dumps({'answer':'You have 12 days to return it.','covered':True,'needs_clarification':False})
    client=Client()
    with pytest.raises(GenerationValidationError) as raised:
        document_reply(client,'What is the return window?','en',sources,facts=facts,context_provenance=True)
    code='unsupported_placement_exception_personal_window'
    out=failure_diagnostics(raised.value)
    assert out['repair_errors']==[code,code] and out['validation_error']==code
    assert out['generation_attempts']==client.calls==2
    assert [m['http_attempts'] for m in out['attempt_metrics']]==[1,2]
    assert 'PRIVATE_SENTINEL' not in json.dumps(out) and 'Authorization' not in json.dumps(out)
    assert (sources,facts)==originals
