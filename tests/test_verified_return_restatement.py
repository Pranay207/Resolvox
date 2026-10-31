"""Focused verified-return retries keep actual original evidence and validators."""
import copy,json
import pytest
from test_return_pickup_fee_context import context
from src.repair_contexts import verified_return_restatement_inputs
from src.document_answers import document_reply


def test_focus_keeps_rebound_cost_deadline_and_original_policy_sections():
    facts,sources=context();before=copy.deepcopy(facts)
    view=verified_return_restatement_inputs('Can I return this jacket?',facts,sources,'2026-10-20')
    assert view and view['facts']['return_deadline']=='2026-10-31'
    assert view['facts']['return_pickup_policy']['standard_fee_inr']==23
    assert all(row in sources for row in view['sources'])
    assert facts==before


@pytest.mark.parametrize('mutation',['fee','deadline','source'])
def test_forged_or_changed_binding_cannot_enter_focused_mode(mutation):
    facts,sources=context()
    if mutation=='fee':facts['return_pickup_policy']['standard_fee_inr']=29
    elif mutation=='deadline':facts['calculations'][0]['result']['deadline']='2026-11-01'
    else:sources[1]['text']=sources[1]['text'].replace('23','29')
    assert verified_return_restatement_inputs('Can I return this jacket?',facts,sources,'2026-10-20') is None


@pytest.mark.parametrize('query',['Can I return this and when will the refund arrive?','Can I return it and what brand warranty applies?','Which category does this return belong to?'])
def test_unrelated_requested_topics_are_not_dropped_from_a_compound_query(query):
    facts,sources=context()
    assert verified_return_restatement_inputs(query,facts,sources,'2026-10-20') is None


class Client:
    def __init__(self,*answers):self.answers=list(answers);self.calls=[]
    def complete(self,system,user,**options):
        self.calls.append((system,json.loads(user),options))
        return json.dumps(dict(answer=self.answers.pop(0),covered=True,needs_clarification=False))


def test_repair_uses_the_smaller_bound_view_and_still_rejects_invented_cost():
    facts,sources=context();query='Can I return this jacket?'
    good='You may request a return by 31 October 2026 if the item conditions are satisfied. A change-of-mind return has a reverse pickup fee of 23 rupees unless a documented waiver applies.'
    client=Client('You can request a return within the window.',good)
    result=document_reply(client,query,'en',sources,facts=facts,private=True,context_provenance=True)
    assert result['answer']==good and result['repair_mode']=='source_verified_return_restatement'
    assert client.calls[1][1]['deterministic_facts']['return_deadline']=='2026-10-31'
    assert client.calls[1][2]['cache'] is False
    client=Client('You can request a return within the window.',good.replace('23 rupees','29 rupees'))
    with pytest.raises(ValueError):document_reply(client,query,'en',sources,facts=facts,private=True,context_provenance=True)


def test_simple_verified_return_starts_with_bound_small_context_without_a_failed_draft():
 facts,sources=context()
 sources=sources+[{'id':'unrelated-topic','doc_type':'help','status':'current','text':'Contact support for other questions.'}]
 good='You may request a return by 31 October 2026 if the item conditions are satisfied. A change-of-mind return has a reverse pickup fee of 23 rupees unless a documented waiver applies.'
 client=Client(good)
 result=document_reply(client,'Can I return this jacket?','en',sources,facts=facts,private=True,context_provenance=True)
 assert len(client.calls)==1 and result['repair_attempted'] is False
 assert 'unrelated-topic' not in {row['id'] for row in client.calls[0][1]['source_text']}
 assert client.calls[0][1]['deterministic_facts']['return_deadline']=='2026-10-31'
