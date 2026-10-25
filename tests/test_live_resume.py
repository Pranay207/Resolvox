"""Checkpoint/resume invariants with fake agents; no live inference is run."""
import json
from pathlib import Path

import pytest

from scripts.resume_live_practice import run_evaluation


def gold(ident,conversation=None,turn=None):
    value={'id':ident,'question':ident,'expected_decision':'answer','must_include':'supported',
        'must_not_include':'','gold_evidence':'','expected_tool_calls':''}
    if conversation:
        value.update(conversation_id=conversation,turn=str(turn),customer_message=ident)
    return value


def deps():
    calls=[]
    class Fake:
        def __init__(self,resources,compose):
            assert compose is True
            self.turn=0
        def respond(self,text):
            self.turn+=1;calls.append((text,self.turn))
            return {'transcript':text,'answer':'supported','decision':'answer','tool_calls':[],
                'retrieved_chunk_ids':[],'retrieval_candidates':[],'composition':'fake_only','llm':{}}
    return calls,Fake


def run(step,path,data,agent,**kwargs):
    return run_evaluation(step,path,dataset=data,resources_factory=lambda:object(),
        agent_factory=agent,provenance_factory=lambda step:{'step':step,'source':'fixed'},**kwargs)


def test_single_question_resume_keeps_saved_predictions_and_runs_only_remaining(tmp_path):
    calls,agent=deps();path=tmp_path/'live.json';data=[gold('one'),gold('two'),gold('three')]
    first=run(2,path,data,agent,max_new_units=1)
    saved=json.loads(path.read_text())['results'][0]
    assert not first['complete'] and first['total']==1 and first['planned']==3
    done=run(2,path,data,agent)
    assert done['complete'] and done['passed']==3
    assert calls==[('one',1),('two',1),('three',1)]
    assert json.loads(path.read_text())['results'][0]==saved
    # A finished artifact does not construct resources or issue more requests.
    assert run(2,path,data,agent)==done and len(calls)==3


def test_conversation_checkpoints_preserve_whole_sessions_and_reset_next_session(tmp_path):
    calls,agent=deps();path=tmp_path/'conversation.json'
    data=[gold('a1','A',1),gold('a2','A',2),gold('b1','B',1),gold('b2','B',2)]
    part=run(3,path,data,agent,max_new_units=1)
    assert part['total']==2 and not part['complete']
    done=run(3,path,data,agent)
    assert done['complete'] and done['total']==4
    assert calls==[('a1',1),('a2',2),('b1',1),('b2',2)]


def test_runtime_change_refuses_resume_before_creating_agent(tmp_path):
    calls,agent=deps();path=tmp_path/'live.json';data=[gold('one'),gold('two')]
    run(2,path,data,agent,max_new_units=1)
    before=path.read_bytes()
    with pytest.raises(ValueError,match='settings changed'):
        run_evaluation(2,path,dataset=data,resources_factory=lambda:pytest.fail('must not initialize'),
            agent_factory=agent,provenance_factory=lambda step:{'step':step,'source':'changed'})
    assert path.read_bytes()==before and calls==[('one',1)]


def test_partial_conversation_cannot_resume_with_missing_state(tmp_path):
    calls,agent=deps();path=tmp_path/'conversation.json'
    data=[gold('a1','A',1),gold('a2','A',2),gold('b1','B',1)]
    run(3,path,data,agent,max_new_units=1)
    saved=json.loads(path.read_text());saved['results']=saved['results'][:1]
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError,match='complete conversation'):
        run(3,path,data,agent)


def test_checkpoint_does_not_overwrite_historical_artifacts(tmp_path):
    calls,agent=deps();path=tmp_path/'eval_step2_live_postfix_partial.json'
    path.write_text('historical proof')
    with pytest.raises(ValueError,match='historical'):
        run(2,path,[gold('one')],agent)
    assert path.read_text()=='historical proof' and not calls


def test_midrun_source_change_keeps_last_completed_checkpoint(tmp_path):
    calls,agent=deps();path=tmp_path/'live.json';counter=[0]
    def snapshot(step):
        counter[0]+=1
        return {'step':step,'source':'fixed' if counter[0]<=3 else 'changed'}
    with pytest.raises(ValueError,match='changed during'):
        run_evaluation(2,path,dataset=[gold('one'),gold('two')],resources_factory=lambda:object(),
            agent_factory=agent,provenance_factory=snapshot)
    saved=json.loads(path.read_text())
    assert len(saved['results'])==1 and not saved['complete']
    assert calls==[('one',1)]


def test_transient_windows_checkpoint_lock_retries_only_the_rename(tmp_path):
    from scripts.resume_live_practice import _replace_checkpoint
    source=tmp_path/'pending.json';target=tmp_path/'live.json'
    source.write_text('new result');target.write_text('old checkpoint')
    calls=[];sleeps=[]
    def replace(source,target):
        calls.append(True)
        if len(calls)<3:raise PermissionError('temporary Windows sharing violation')
        source.replace(target)
    _replace_checkpoint(source,target,replace=replace,sleep=sleeps.append)
    assert len(calls)==3 and len(sleeps)==2
    assert target.read_text()=='new result' and not source.exists()


def test_permanent_checkpoint_lock_is_bounded_and_retains_both_files(tmp_path):
    from scripts.resume_live_practice import _replace_checkpoint
    source=tmp_path/'pending.json';target=tmp_path/'live.json'
    source.write_text('new result');target.write_text('old checkpoint')
    calls=[];sleeps=[]
    def replace(source,target):
        calls.append(True)
        raise PermissionError('permanent lock')
    with pytest.raises(PermissionError):
        _replace_checkpoint(source,target,replace=replace,sleep=sleeps.append)
    assert len(calls)==12 and len(sleeps)==11 and sum(sleeps)<3
    assert target.read_text()=='old checkpoint' and source.read_text()=='new result'
