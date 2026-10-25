"""Absence of a source reference cannot itself justify a policy denial."""
import json
import pytest
from src.document_answers import document_reply,_check_absence_causal_denial,CONTEXT_SYSTEM,CONTEXT_LANGUAGE
from src.llm import LLMUnavailable

SOURCE={'id':'orchid-general','text':'Orchid service supports requests in the app.','doc_type':'policy','status':'current'}
BAD='An Aster pass is not available because the policy contains no reference to it.'
SAFE='I cannot confirm that information from the supplied documents.'

@pytest.mark.parametrize('answer',[
    BAD,
    'You will not receive an Aster pass because the documents do not mention it.',
    'Because the policy does not mention Aster passes, they are not available.',
    'The policy has no reference to Aster passes, so they are not offered.',
    'The documents do not state anything about Aster passes; therefore they are not available.',
    'Aster pass nahi milega, kyunki policy mein koi reference nahi hai.',
    'Policy mein koi jaankari nahi hai, isliye Aster pass nahi milega.',
    '\u092f\u0939 \u0938\u0947\u0935\u093e \u0909\u092a\u0932\u092c\u094d\u0927 \u0928\u0939\u0940\u0902 \u0939\u0948 \u0915\u094d\u092f\u094b\u0902\u0915\u093f \u0928\u0940\u0924\u093f \u092e\u0947\u0902 \u0907\u0938\u0915\u093e \u0909\u0932\u094d\u0932\u0947\u0916 \u0928\u0939\u0940\u0902 \u0939\u0948\u0964',
    'I cannot confirm other details, but an Aster pass is not offered because the sources have no information about it.',
])
def test_explicit_absence_cannot_become_a_prohibition(answer):
    with pytest.raises(ValueError,match='absence_causal_policy_denial'):_check_absence_causal_denial(answer)

@pytest.mark.parametrize('answer',[
    SAFE,
    'Because the policy does not mention it, I cannot confirm whether an Aster pass is available.',
    'The policy has no information about Aster passes, so I cannot determine availability.',
    'An Aster pass is not available because the policy explicitly excludes it.',
    'An Aster pass is not returnable because the policy says it cannot be returned.',
    'The policy does not mention one topic. A separate policy expressly excludes Aster passes.',
    'Gift cards are not returnable, and I cannot confirm other details because the documents contain no reference to them.',
    'Do not conclude that a pass is not available because the policy contains no reference.',
    'The policy contains no reference; that does not mean a pass is not available.',
    'Policy mein jaankari nahi hai, isliye main confirm nahi kar sakta.',
    '\u0928\u0940\u0924\u093f \u092e\u0947\u0902 \u0909\u0932\u094d\u0932\u0947\u0916 \u0928\u0939\u0940\u0902 \u0939\u0948, \u0907\u0938\u0932\u093f\u090f \u092e\u0948\u0902 \u092a\u0941\u0937\u094d\u091f\u093f \u0928\u0939\u0940\u0902 \u0915\u0930 \u0938\u0915\u0924\u093e\u0964',
])
def test_uncertainty_and_actual_negative_policy_explanations_are_preserved(answer):
    _check_absence_causal_denial(answer)

class Client:
    def __init__(self,*values):self.values=list(values);self.calls=[]
    def complete(self,system,user,**kwargs):
        self.calls.append((system,json.loads(user),kwargs));assert self.values
        value=self.values.pop(0)
        if isinstance(value,Exception):raise value
        return json.dumps(value)

def value(answer=BAD,**flags):return {'answer':answer,'covered':True,'needs_clarification':False,**flags}
def run(client,sources=None):return document_reply(client,'Explain the Aster pass policy.','en',[SOURCE] if sources is None else sources,context_provenance=True)

def test_one_strict_uncertainty_repair_preserves_original_evidence_and_primary_prompt():
    client=Client(value(),value(SAFE,covered=False))
    out=run(client)
    assert out['generation_attempts']==2 and out['repair_attempted']
    assert out['covered'] is False and out['source_ids']==[] and out['citations']==[]
    assert out['reply_kind']=='uncertainty' and out['evidence_status']=='insufficient_evidence'
    assert out['repair_errors']==['absence_causal_policy_denial']
    first,second=client.calls
    assert first[0]==second[0]==CONTEXT_SYSTEM+'\n'+CONTEXT_LANGUAGE['en']
    assert set(first[1])=={'source_text','deterministic_facts','reference_date','language','question'}
    assert first[1]['source_text']==second[1]['source_text']==[SOURCE]
    assert 'repair_instruction' not in first[1]
    assert second[1]['repair_validation_error']=='absence_causal_policy_denial'
    assert 'Set covered false and needs_clarification false' in second[1]['repair_instruction']
    assert first[2]['cache'] is True and second[2]['cache'] is False

@pytest.mark.parametrize('repair',[
    value(SOURCE['text']),
    value('Which membership do you mean?',covered=False,needs_clarification=True),
    value(SAFE,covered='false'),
    value(SAFE,covered=False,needs_clarification='false'),
    {'answer':SAFE,'covered':False,'decision':'refuse'},
])
def test_repair_cannot_relabel_the_denial_or_change_to_a_policy_answer(repair):
    client=Client(value(),repair)
    with pytest.raises(ValueError,match='absence_repair_requires_uncertainty'):run(client)
    assert len(client.calls)==2

@pytest.mark.parametrize('repair',[
    'I cannot confirm the 99-day deadline.',
    'I cannot confirm more information. Your refund has been issued.',
    'I cannot confirm more information; contact aster@example.com.',
    'I cannot confirm availability, but Aster passes are not offered.',
])
def test_uncertainty_repair_still_passes_numeric_action_privacy_and_policy_checks(repair):
    client=Client(value(),value(repair,covered=False))
    with pytest.raises(ValueError):run(client)
    assert len(client.calls)==2

def test_normal_supported_answer_and_context_stay_unchanged():
    client=Client(value(SOURCE['text']))
    out=run(client)
    assert out['answer']==SOURCE['text'] and out['covered'] is True
    assert out['generation_attempts']==1 and not out['repair_attempted']
    assert out['source_ids']==['orchid-general']

def test_source_mutation_is_passed_through_without_business_answer_constants():
    source={**SOURCE,'id':'violet-current','text':'Violet service does not include Aster passes.'}
    client=Client(value(source['text']))
    assert run(client,[source])['answer']==source['text']
    assert client.calls[0][1]['source_text']==[source]

def test_provider_failure_during_repair_propagates_without_third_attempt():
    client=Client(value(),LLMUnavailable('offline'))
    with pytest.raises(LLMUnavailable):run(client)
    assert len(client.calls)==2
