"""Runner CLI/mode/provenance checks use synthetic clients, never inference."""
import json
import sys
from types import SimpleNamespace

import pytest

import eval_adversarial


@pytest.fixture
def runner(tmp_path,monkeypatch):
    (tmp_path/'src').mkdir();(tmp_path/'tests').mkdir()
    (tmp_path/'src/agent.py').write_text('# synthetic runtime\n')
    (tmp_path/'src/rule_bindings.json').write_text('{}')
    (tmp_path/'tests/adversarial_cases.json').write_text(json.dumps([
        {'id':'SYNTHETIC1','question':'Synthetic source question','decision':'answer','contains':'supplied evidence'},
    ]))
    resources=SimpleNamespace(
        llm=SimpleNamespace(provider='mock',model='actual-test-model'),
        tools=SimpleNamespace(module=SimpleNamespace(
            _ORDERS={'one':{'order_id':'11112222','customer_id':'c1'}},
            _CUSTOMERS={'c1':{'phone':'+910000008723'}},
        )))
    instances=[]
    class FakeAgent:
        callback=None
        single_answer='From supplied evidence.'
        def __init__(self,resources,compose):
            self.compose=compose;self.attempts=0;instances.append(self)
        def respond(self,text):
            callback=type(self).callback
            if callback:
                type(self).callback=None;callback()
            if text=='Synthetic source question':
                return {'answer':self.single_answer,'decision':'answer','verified':False,'tool_calls':[],
                        'composition':'grounded_llm' if self.compose else 'document_excerpts'}
            if text.startswith('Order '):
                return {'answer':'Please verify.','decision':'clarify','verified':False,
                        'tool_calls':[],'composition':'deterministic_guardrail'}
            correct=text.endswith('8723') and self.attempts<2
            if not correct:self.attempts+=1
            return {'answer':'Verification response.','decision':'answer' if correct else ('clarify' if self.attempts==1 else 'refuse'),
                    'verified':correct,'tool_calls':[],'composition':'deterministic_guardrail'}
    monkeypatch.setattr(eval_adversarial,'ROOT',tmp_path)
    monkeypatch.setattr(eval_adversarial,'Resources',lambda:resources)
    monkeypatch.setattr(eval_adversarial,'Agent',FakeAgent)
    monkeypatch.setattr(sys,'argv',['eval_adversarial.py'])
    return tmp_path,instances,FakeAgent


def report(root,name):
    return json.loads((root/'sample_outputs'/name).read_text(encoding='utf-8'))


def test_default_remains_explicit_offline_for_single_and_stateful_agents(runner):
    root,instances,_=runner
    assert eval_adversarial.main()==0
    data=report(root,'eval_adversarial.json')
    assert instances and all(agent.compose is False for agent in instances)
    assert data['mode']=='offline_compose_false'
    assert data['summary']['composition_counts']=={'document_excerpts':1,'deterministic_guardrail':2}
    assert data['summary']['total']==data['summary']['planned']==3


def test_live_default_is_separate_and_all_agents_generate_with_provenance(runner,monkeypatch):
    root,instances,_=runner
    (root/'sample_outputs').mkdir()
    historical=root/'sample_outputs/eval_adversarial.json'
    historical.write_bytes(b'preserve historical bytes')
    fixture=(root/'tests/adversarial_cases.json').read_bytes()
    monkeypatch.setattr(sys,'argv',['eval_adversarial.py','--live'])
    assert eval_adversarial.main()==0
    data=report(root,'eval_adversarial_live_current.json')
    assert all(agent.compose is True for agent in instances)
    assert historical.read_bytes()==b'preserve historical bytes'
    assert (root/'tests/adversarial_cases.json').read_bytes()==fixture
    assert data['configuration']['llm_model']=='actual-test-model'
    assert data['mode']=='live_compose_true' and data['complete'] is True
    assert data['validation_passed'] is True
    assert 'src/rule_bindings.json' in data['runtime_source_sha256']
    assert data['runtime_source_sha256']==data['runtime_source_sha256_finished']
    assert data['source_runtime_unchanged'] is True
    assert data['summary']['composition_counts']=={'grounded_llm':1,'deterministic_guardrail':2}
    assert data['results'][0]['expected']=={'decision':'answer','contains':'supplied evidence'}


def test_output_argument_controls_live_result_location(runner,monkeypatch):
    root,_,_=runner
    target=root/'custom/live.json'
    monkeypatch.setattr(sys,'argv',['eval_adversarial.py','--live','--output',str(target)])
    assert eval_adversarial.main()==0
    assert target.exists()
    assert not (root/'sample_outputs/eval_adversarial.json').exists()


def test_live_cannot_overwrite_historical_result(runner,monkeypatch):
    root,instances,_=runner
    target=root/'sample_outputs/eval_adversarial.json'
    monkeypatch.setattr(sys,'argv',['eval_adversarial.py','--live','--output',str(target)])
    with pytest.raises(SystemExit) as error:eval_adversarial.main()
    assert error.value.code==2 and instances==[]


def test_runtime_change_retains_actual_scores_but_invalidates_run(runner):
    root,_,agent=runner
    agent.callback=lambda:(root/'src/agent.py').write_text('# changed during synthetic run\n')
    assert eval_adversarial.evaluate(live=True)==2
    data=report(root,'eval_adversarial_live_current.json')
    assert data['summary']['passed']==3 and data['summary']['failed']==0
    assert data['status']=='invalid_runtime_changed'
    assert data['complete'] is False and data['validation_passed'] is False
    assert data['source_runtime_unchanged'] is False


def test_judgment_failure_is_preserved_and_returns_failure(runner):
    root,_,agent=runner
    agent.single_answer='No matching marker.'
    assert eval_adversarial.evaluate(live=True)==1
    data=report(root,'eval_adversarial_live_current.json')
    assert data['complete'] is True and data['validation_passed'] is False
    assert data['summary']['failed']==1 and data['results'][0]['passed'] is False


def test_help_does_not_instantiate_resources_or_agents(runner,monkeypatch):
    _,instances,_=runner
    monkeypatch.setattr(eval_adversarial,'Resources',lambda:pytest.fail('Help must not initialize inference resources'))
    monkeypatch.setattr(sys,'argv',['eval_adversarial.py','--help'])
    with pytest.raises(SystemExit) as error:eval_adversarial.main()
    assert error.value.code==0 and instances==[]
