"""Source review rejects invented requirements and preserves original evidence."""
import json
import pytest
from src.claim_audit import SYSTEM as AUDIT_SYSTEM, assess_claims
from src.document_answers import document_reply
from src.generation_diagnostics import GenerationValidationError

SOURCE={'id':'REPORT-NEW','doc_type':'policy','status':'current','effective_from':'2020-01-01','file':'reporting.md',
        'text':'Report a damaged item within 72 hours of delivery, with photos of the item and packaging.'}
GOOD='Report the damaged item within 72 hours of delivery, with photos of the item and packaging.'
BAD=GOOD+' Send the report in writing.'

class Client:
    def __init__(self,answers,verdicts):self.answers=iter(answers);self.verdicts=iter(verdicts);self.calls=[];self.last_metrics={};self.last_provider='scripted'
    def complete(self,system,user,**options):
        payload=json.loads(user);self.calls.append((system,payload,options));self.last_metrics={'cache_hit':False}
        if system==AUDIT_SYSTEM:return json.dumps(next(self.verdicts))
        flag='has_document_support' if 'has_document_support' in options['schema']['properties'] else 'covered'
        return json.dumps({'answer':next(self.answers),flag:True,'needs_clarification':False})


def test_unsupported_requirement_is_repaired_with_original_evidence(monkeypatch):
    monkeypatch.setenv('RAG_CLAIM_AUDIT','true')
    client=Client([BAD,GOOD],[{'supported':False,'unsupported_claims':['Written format is not required by the supplied source.']},{'supported':True,'unsupported_claims':[]}])
    out=document_reply(client,'How do I report a damaged item?','en',[SOURCE],context_provenance=True)
    assert out['answer']==GOOD and out['repair_errors']==['unsupported_answer_claim']
    assert len(client.calls)==4 and len(out['claim_audits'])==2
    assert [a['supported'] for a in out['claim_audits']]==[False,True]
    for _,payload,_ in client.calls:
        assert payload['source_text'][0]['id']=='REPORT-NEW'
        assert payload['source_text'][0]['text']==SOURCE['text']
    audits=[call for call in client.calls if call[0]==AUDIT_SYSTEM]
    assert all(call[2]['cache'] is False for call in audits)
    assert 'claim_audit_feedback' in client.calls[2][1]


def test_repeated_unsupported_requirement_never_becomes_a_customer_reply(monkeypatch):
    monkeypatch.setenv('RAG_CLAIM_AUDIT','true')
    verdict={'supported':False,'unsupported_claims':['The written-format requirement is unsupported.']}
    client=Client([BAD,BAD],[verdict,verdict])
    with pytest.raises(GenerationValidationError,match='unsupported_answer_claim'):
        document_reply(client,'How do I report a damaged item?','en',[SOURCE],context_provenance=True)
    assert len(client.calls)==4


def test_private_generation_and_audit_both_disable_output_caching(monkeypatch):
    monkeypatch.setenv('RAG_CLAIM_AUDIT','true')
    client=Client([GOOD],[{'supported':True,'unsupported_claims':[]}])
    out=document_reply(client,'How do I report a damaged item?','en',[SOURCE],private=True,context_provenance=True)
    assert out['answer']==GOOD and len(client.calls)==2
    assert all(call[2]['cache'] is False for call in client.calls)


def test_malformed_positive_verdict_cannot_approve_an_answer():
    client=Client([], [{'supported':'true','unsupported_claims':[]}])
    result=assess_claims(client,GOOD,'How do I report damage?','en',[SOURCE],{},'2026-10-20')
    assert result['supported'] is False
    assert result['unsupported_claims']


def test_claim_failure_diagnostics_do_not_expose_dynamic_details():
    from src.generation_diagnostics import validation_code
    assert validation_code('unsupported_answer_claim:private-draft-detail')=='unsupported_answer_claim'


def test_source_review_works_through_the_real_read_only_model_probe(monkeypatch):
    from src.agent import ModelCallProbe
    monkeypatch.setenv('RAG_CLAIM_AUDIT','true')
    probe=ModelCallProbe(Client([GOOD],[{'supported':True,'unsupported_claims':[]}]))
    out=document_reply(probe,'How do I report a damaged item?','en',[SOURCE],context_provenance=True)
    assert out['answer']==GOOD and probe.calls==2
    assert out['claim_audits'][0]['supported'] is True
