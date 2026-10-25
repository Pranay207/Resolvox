"""Evidence wording must follow saved completion and composition, not filenames."""
import copy

import pytest

from scripts.finalize_evidence import (composition_text, live_complete, live_narrative,
    live_result_text, regional_preview_text, select_current_live, update_readiness)
from scripts import build_report


def live(total=2,planned=2,complete=True,passed=None):
    return {'configuration':{'evaluation_mode':'live_compose_true','llm_model':'mock'},
        'complete':complete,
        'summary':{'total':total,'passed':total if passed is None else passed,'planned':planned,
            'complete':complete,'errors':0,
            'composition_counts':{'grounded_llm':1,'evidence_validated_fallback':1}},
        'results':[{'prediction':{}} for _ in range(total)]}


def test_live_completion_requires_all_recorded_boundaries_agree():
    assert live_complete(live())
    for change in ('planned','row_count','flag','top_flag'):
        data=live()
        if change=='planned':data['summary']['planned']=3
        elif change=='row_count':data['results'].pop()
        elif change=='flag':data['summary']['complete']=False
        else:data['complete']=False
        assert not live_complete(data)


def test_current_artifact_is_selected_without_promoting_old_partial():
    old=live(total=1,planned=2,complete=False)
    fresh=live()
    fixtures={'eval_step2_live_postfix_partial.json':old,'eval_step2_live_current.json':fresh}
    name,data=select_current_live(2,lambda name:fixtures.get(name,{}))
    assert name=='eval_step2_live_current.json' and data is fresh
    fixtures.pop(name)
    assert select_current_live(2,lambda name:fixtures.get(name,{}))[1]=={}


def test_an_offline_file_cannot_be_mislabeled_live_by_its_name():
    data=live();data['configuration']['evaluation_mode']='offline_compose_false'
    assert select_current_live(2,lambda name:data)[1]=={}


def test_question_and_conversation_completion_remain_independent():
    text=live_narrative(live(),live(total=1,planned=3,complete=False))
    assert 'grounded questions: 2/2 planned; 2 evaluated; complete=True' in text
    assert 'conversation turns: 1/3 planned; 1 evaluated; complete=False' in text
    assert 'does not mean every reply was freshly generated' in text
    assert 'pending' in live_result_text({})


def test_generated_fallback_guard_and_abstention_counts_are_separate():
    data=live()
    data['summary']['composition_counts']={'grounded_llm':6,'evidence_validated_fallback':19,
        'deterministic_guardrail':2,'evidence_validated_rules':1,'abstained_missing_evidence':4}
    text=composition_text(data)
    assert 'generated 6' in text and 'checked fallbacks 19' in text
    assert 'guards 2' in text and 'rules 1' in text and 'abstentions 4' in text


def test_readme_removes_obsolete_current_32_claim_only_in_favor_of_actual_new_status():
    text='Intro\n\nThe implementation includes query-first hybrid retrieval, old current32 claim.\n\nKeep this section.'
    stages={2:{'summary':{'passed':52,'total':52}},3:{'summary':{'passed':96,'total':96}}}
    hold={'summary':{'passed':91,'evaluated':91,'failed':0}}
    completed=update_readiness(text,stages,live(52,52),live(96,96),hold,337)
    assert 'complete=True' in completed and 'old current32 claim' not in completed
    assert '**337/337**' in completed and 'Offline practice remains 52/52' in completed
    partial=update_readiness(text,stages,live(32,52,False),{},hold,338)
    assert '32/52 planned; 32 evaluated; complete=False' in partial
    assert 'conversation turns: pending' in partial
    assert 'Keep this section.' in partial


def test_failed_regional_preview_never_becomes_ten_languages_working():
    text=regional_preview_text({'summary':{'voice_passed':5,'planned':11,'failed':6,'pending':0}})
    assert 'experimental' in text and '5/11' in text and '6 failed' in text
    assert 'does not establish all ten languages as working' in text


def test_report_import_helpers_do_not_author_pdf_and_keep_partial_marker():
    # Importing/report text selection is safe while evaluation is still running.
    # PDF authoring remains an explicit final operation after evaluation/QA.
    assert build_report.pass_text(live(2,3,False))=='2/2 (partial)'
    assert build_report.select_current_live is select_current_live
    assert build_report.live_complete(live())
