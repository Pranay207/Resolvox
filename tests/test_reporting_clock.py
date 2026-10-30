import copy,json
import pytest
from src.reporting_clock import reporting_clock_inputs,check_reporting_clock_claim
from src.document_answers import document_reply

def evidence(limit):
 return [{'id':'REPORT-X','doc_type':'policy','status':'current','effective_from':'2020-01-01','text':f'Report damaged items within {limit} hours of delivery, with photos of the item and packaging.'}]
def facts(elapsed):return {'verified_order':{'damage_hours_after_delivery':elapsed,'damage_reported_at':'2026-10-17T02:41','damage_photos_attached':False}}

@pytest.mark.parametrize('limit,elapsed,answer',[
 (48,40,'Your damage report was not within 48 hours.'),
 (36,40,'Your damage was reported within 36 hours.'),
 (72,60,'Your damage report was late.'),
 (48,60,'Your damage report was not late.'),
 (48,40,'Damage report 48 ghante ke andar nahi kiya gaya tha.'),
 (36,40,'Damage report 36 ghante ke andar kiya gaya tha.')])
def test_report_verdict_uses_actual_source_limit_and_verified_elapsed_hours(limit,elapsed,answer):
 with pytest.raises(ValueError,match='contradicted_reporting_window_status'):
  check_reporting_clock_claim(answer,'My damaged item report',facts(elapsed),evidence(limit),'2026-10-20')

@pytest.mark.parametrize('limit,elapsed,answer',[
 (48,48,'Your damage was reported within 48 hours.'),
 (36,40,'Your damage report was late.'),
 (72,60,'Your damage report was not late.'),
 (48,40,'If the damage report was not within 48 hours, the other rule applies.'),
 (48,40,'I cannot confirm that the report was late.')])
def test_correct_conditional_and_uncertain_report_statements_remain_valid(limit,elapsed,answer):
 check_reporting_clock_claim(answer,'My damaged item report',facts(elapsed),evidence(limit),'2026-10-20')

def test_comparison_is_not_claim_approval_or_photo_verification():
 value=reporting_clock_inputs('My damaged item report',facts(40),evidence(48),'2026-10-20')
 assert value['within_reporting_window'] is True and value['recorded_elapsed_hours']==40
 assert not any('approv' in key or 'eligib' in key for key in value)

def test_missing_ambiguous_future_and_unrelated_inputs_are_not_guessed():
 assert reporting_clock_inputs('My refund report',facts(40),evidence(48),'2026-10-20') is None
 assert reporting_clock_inputs('My damaged item report',{},evidence(48),'2026-10-20') is None
 assert reporting_clock_inputs('My damaged item report',facts(40),evidence(48)+[{**evidence(36)[0],'id':'CONFLICT-X'}],'2026-10-20') is None
 assert reporting_clock_inputs('My damaged item report',facts(40),[{**evidence(48)[0],'effective_from':'2027-01-01'}],'2026-10-20') is None

def test_generation_receives_derived_clock_and_rejects_then_repairs_false_status():
 bad='Your damage report was not within 48 hours.';good='Your damage was reported within 48 hours; photos of the item and packaging are still required.';answers=iter([bad,good]);calls=[]
 class Client:
  def complete(self,system,user,**options):
   calls.append(json.loads(user));return json.dumps({'answer':next(answers),'covered':True,'needs_clarification':False})
 result=document_reply(Client(),'My damaged item report needs review.','en',evidence(48),facts=facts(40),private=True,context_provenance=True)
 assert result['answer']==good and result['repair_errors']==['contradicted_reporting_window_status']
 assert calls[0]['deterministic_facts']['reporting_time_check']['within_reporting_window'] is True
 assert 'source_sha256' not in calls[0]['deterministic_facts']['reporting_time_check']
 assert result['reporting_time_check']['source_sha256']


def test_missing_photos_do_not_negate_a_timely_report_verdict():
 check_reporting_clock_claim('Your damage report was within 48 hours and photos were not attached.',
  'My damaged item report',facts(40),evidence(48),'2026-10-20')


def test_photo_negation_does_not_hide_a_false_late_report_verdict():
 with pytest.raises(ValueError,match='contradicted_reporting_window_status'):
  check_reporting_clock_claim('Your damage report was late and photos not attached.',
   'My damaged item report',facts(40),evidence(48),'2026-10-20')
