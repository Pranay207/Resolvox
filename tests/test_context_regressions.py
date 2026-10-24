from src.normalize import order_id,proof_value
from src.agent import Agent,Resources


def test_literal_entities_are_not_merged_with_speech_homophones():
    assert order_id('Please check order 35061733 for me')=='35061733'
    assert order_id('Please check order 3506 1733 for me')=='35061733'
    assert proof_value('1234 for verification')=='1234'


def test_safety_warning_survives_a_troubleshooting_followup():
    a=Agent(Resources(dense=False),compose=False)
    a.respond('The battery is swollen')
    out=a.respond('Should I try charging it again?')
    assert out['decision']=='escalate'
    assert 'Stop using' in out['answer']
