'Temporary source-derived business-rule proof; no model or tool requests.'
from pathlib import Path
from types import SimpleNamespace
import copy,importlib.util,json
import pytest
from src import escalation_rules as helper

def source(key,text,kind='policy',**extra):
 return {'id':key,'text':text,'doc_type':kind,'status':'current','effective_from':'2020-01-01','version':'mutation',**extra}
@pytest.fixture
def sources():
 return [source('amount-rule','Claims for items worth more than ₹1,200 are handled by a specialist team. The support agent must create a ticket and hand over; the agent cannot approve these claims.'),
 source('operational-rules','''Hand over at once when any of these is true:
- Damaged, defective or wrong item worth more than ₹1,200.
- Fourth or later contact about the same issue within 9 days.
- Refund more than 2 business days past its maximum timeline.
For the repeat-contact rule, use the `contacts_last_9_days` field returned by order lookup. It counts earlier contacts only, not the current one. Escalate when it is 3 or more.''','agent_guide'),
 source('ticket-process','Create a ticket with create_ticket before handing over. Never promise an outcome.','agent_guide'),
 source('payment-ranges','''Refunds go to the original payment method from refund initiation.
| Payment method | Time to reach you |
| UPI | 2 to 4 business days |
| Credit or debit card | 6 to 8 business days |'''),
 source('business-calendar','A business day is Monday to Friday, excluding the warehouse holidays below.','meta'),
 source('item-record',json.dumps({'sku':'CASE-X','title':'Aster Radio','price_inr':'1201'}),'catalog',file='data/products.csv')]
@pytest.fixture
def data():return SimpleNamespace(holidays={'2026-10-12'})
def derive(sources,data,query='My CASE-X arrived damaged.',order=None,public=None,today='2026-10-15'):
 return helper.derive_escalation(query,sources,data,verified_order=order,public_context=public,reference_date=today)
def row(result,reason):return next(x for x in result['decisions'] if x['reason']==reason)
def refund(**extra):return {'payment_method':'upi','return_refund_method':'upi','return_refund_initiated_on':'2026-10-05',**extra}

@pytest.mark.parametrize('price,applies',[('1199',False),('1200',False),('1201',True)])
def test_actual_high_value_strict_boundary(sources,data,price,applies):
 sources[-1]['text']=json.dumps({'sku':'CASE-X','title':'Aster Radio','price_inr':price})
 decision=row(derive(sources,data),'high_value_damage')
 assert decision['applicable'] is applies
 assert decision['facts']['threshold_inr']=='1200' and decision['facts']['item_value_inr']==price

def test_primary_rule_mutation_recovers_or_suppresses_legacy_route(sources,data):
 sources[0]['text']=sources[0]['text'].replace('1,200','1,300')
 assert row(derive(sources,data),'high_value_damage')['applicable'] is False
 sources[0]['text']=sources[0]['text'].replace('1,300','1,000')
 assert row(derive(sources,data),'high_value_damage')['applicable'] is True

def test_comparison_operator_changes_with_source(sources,data):
 sources[0]['text']=sources[0]['text'].replace('more than','at least')
 sources[-1]['text']=sources[-1]['text'].replace('1201','1200')
 decision=row(derive(sources,data),'high_value_damage')
 assert decision['applicable'] is True and decision['facts']['operator']=='ge'

@pytest.mark.parametrize('query',['My CASE-X is not damaged.',"My CASE-X wasn't damaged.",'If my CASE-X were damaged, what would happen?','Explain damaged item policy for CASE-X.','Do you repair damaged items such as CASE-X?','My CASE-X has no damage.','Is my CASE-X damaged?','My CASE-X is damaged nahi.'])
def test_negative_hypothetical_and_overview_are_not_individual_claims(sources,data,query):
 assert row(derive(sources,data,query),'high_value_damage')['applicable'] is False

def test_verified_unit_price_overrides_catalog_and_line_total(sources,data):
 order={'items':[{'sku':'CASE-X','unit_price_inr':'1100','line_total_inr':'3300','quantity':'3'}]}
 decision=row(derive(sources,data,order=order),'high_value_damage')
 assert decision['applicable'] is False and decision['facts']['value_origin']=='verified_order.items.unit_price_inr'
 assert 'item-record' not in decision['source_ids']

def test_unattributed_multiple_items_remain_unresolved(sources,data):
 order={'items':[{'sku':'A','unit_price_inr':'1100'},{'sku':'B','unit_price_inr':'2000'}]}
 decision=row(derive(sources[:-1],data,'My item arrived damaged.',order=order),'high_value_damage')
 assert decision['applicable'] is None and 'one_unambiguous_item_value' in decision['missing_inputs']

@pytest.mark.parametrize('count,applies',[(2,False),(3,True),(4,True)])
def test_repeat_earlier_count_and_dynamic_period(sources,data,count,applies):
 decision=row(derive(sources,data,'My order issue remains.',order={'contacts_last_9_days':str(count)}),'repeat_contact')
 assert decision['applicable'] is applies
 assert decision['facts']['window_calendar_days']==9 and decision['facts']['current_contact_excluded'] is True

def test_repeat_threshold_period_and_field_change_together(sources,data):
 sources[1]['text']=sources[1]['text'].replace('Fourth','Sixth').replace('9 days','12 days').replace('last_9_days','last_12_days').replace('3 or more','5 or more')
 assert row(derive(sources,data,'My refund issue remains.',order={'contacts_last_12_days':'5'}),'repeat_contact')['applicable'] is True
 assert row(derive(sources,data,'My refund issue remains.',order={'contacts_last_9_days':'5'}),'repeat_contact')['applicable'] is None

def test_conflicting_current_contact_semantics_fail_closed(sources,data):
 sources[1]['text']=sources[1]['text'].replace('Fourth','Fifth')
 decision=row(derive(sources,data,'My refund issue remains.',order={'contacts_last_9_days':'8'}),'repeat_contact')
 assert decision['applicable'] is None and decision['binding_status']=='ambiguous'

@pytest.mark.parametrize('order,query',[(None,'My order issue remains.'),({'contacts_last_9_days':'9'},'Hello there.')])
def test_repeat_needs_corresponding_record_and_topic(sources,data,order,query):
 decision=row(derive(sources,data,query,order=order),'repeat_contact')
 assert decision['applicable'] is False and decision['binding_status']=='not_relevant'

@pytest.mark.parametrize('today,applies,elapsed',[('2026-10-13',False,1),('2026-10-14',False,2),('2026-10-15',True,3)])
def test_overdue_uses_real_range_calendar_and_strict_tolerance(sources,data,today,applies,elapsed):
 decision=row(derive(sources,data,'My refund has not arrived.',order=refund(),today=today),'refund_overdue')
 assert decision['applicable'] is applies
 assert decision['facts']['maximum_date']=='2026-10-09' and decision['facts']['tolerance_boundary_date']=='2026-10-14'
 assert decision['facts']['elapsed_business_days_past_maximum']==elapsed
 assert {'payment-ranges','business-calendar','data/holidays.csv'}<=set(decision['source_ids'])

def test_changed_method_range_suppresses_old_overdue_route(sources,data):
 sources[3]['text']=sources[3]['text'].replace('2 to 4','2 to 6')
 decision=row(derive(sources,data,'My refund has not arrived.',order=refund()),'refund_overdue')
 assert decision['facts']['maximum_date']=='2026-10-14' and decision['applicable'] is False

def test_changed_tolerance_recovers_route(sources,data):
 sources[1]['text']=sources[1]['text'].replace('more than 2 business','more than 1 business')
 assert row(derive(sources,data,'My refund has not arrived.',order=refund(),today='2026-10-14'),'refund_overdue')['applicable'] is True

def test_changed_calendar_and_holidays_update_binding(sources,data):
 first=derive(sources,data,'My refund has not arrived.',order=refund(),today='2026-10-14')
 sources[4]['text']=sources[4]['text'].replace('Friday','Saturday')
 second=derive(sources,data,'My refund has not arrived.',order=refund(),today='2026-10-14')
 assert row(first,'refund_overdue')['applicable'] is False and row(second,'refund_overdue')['applicable'] is True
 data.holidays=set()
 third=derive(sources,data,'My refund has not arrived.',order=refund(),today='2026-10-14')
 assert row(second,'refund_overdue')['source_sha256']['data/holidays.csv']!=row(third,'refund_overdue')['source_sha256']['data/holidays.csv']

@pytest.mark.parametrize('change',['range','calendar','rule','future','superseded','workflow'])
def test_missing_or_stale_input_blocks_automatic_business_action(sources,data,change):
 if change=='range':sources.pop(3)
 elif change=='calendar':sources.pop(4)
 elif change=='rule':sources.pop(1)
 elif change=='future':sources[1]['effective_from']='2099-01-01'
 elif change=='superseded':sources[1]['status']='superseded'
 else:sources.pop(2)
 result=derive(sources,data,'My refund has not arrived.',order=refund())
 assert row(result,'refund_overdue')['applicable'] is None and result['recommended_reason'] is None

@pytest.mark.parametrize('extra',[{'return_refund_completed_on':'2026-10-08'},{'return_refund_initiated_on':''}])
def test_no_active_refund_has_no_overdue_action(sources,data,extra):
 assert row(derive(sources,data,'My refund has not arrived.',order=refund(**extra)),'refund_overdue')['applicable'] is False

def test_competing_active_events_remain_unresolved(sources,data):
 decision=row(derive(sources,data,'My refund has not arrived.',order=refund(cancellation_refund_initiated_on='2026-10-02')),'refund_overdue')
 assert decision['applicable'] is None and decision['binding_status']=='ambiguous'

def test_public_date_claim_cannot_trigger_verified_record_business_action(sources,data):
 assert row(derive(sources,data,'My UPI refund started 5 October 2026 and has not arrived.'),'refund_overdue')['applicable'] is False

def test_actual_source_fingerprints_resolve_every_comparison_input(sources,data):
 result=derive(sources,data,'My refund has not arrived.',order=refund())
 actual={s['id']:s for s in result['selected_sources']}
 for decision in result['decisions']:
  assert set(decision['source_ids'])<=actual.keys()
  assert decision['source_sha256']=={key:helper.source_fingerprint(actual[key]) for key in decision['source_ids']}
  for calc in decision['calculations']:assert set(calc['source_ids'])<=actual.keys()
 assert not {'answer','en','policy_summary'}&result.keys()

@pytest.mark.parametrize('index,reason,old,new,query,order',[(0,'high_value_damage','1,200','1,500','My CASE-X arrived damaged.',None),(3,'refund_overdue','2 to 4','4 to 9','My refund has not arrived.',refund())])
def test_same_authority_conflicts_are_ambiguous(sources,data,index,reason,old,new,query,order):
 extra=copy.deepcopy(sources[index]);extra['id']='conflicting-source';extra['text']=extra['text'].replace(old,new)
 decision=row(derive(sources+[extra],data,query,order=order),reason)
 assert decision['applicable'] is None and decision['binding_status']=='ambiguous'


@pytest.mark.parametrize('query',['My CASE-X received yesterday has a crack.','The CASE-X I received has a crack.','My CASE-X arrived cracked.'])
def test_noun_and_adjective_damage_claims_use_the_same_source_rule(sources,data,query):
 assert row(derive(sources,data,query),'high_value_damage')['applicable'] is True

@pytest.mark.parametrize('index,old,new,reason,query,order',[
 (0,'must create a ticket and hand over','must not create a ticket and hand over','high_value_damage','My CASE-X arrived damaged.',None),
 (1,'Escalate when it is','Never escalate when it is','repeat_contact','My order issue remains.',{'contacts_last_9_days':'9'}),
 (1,'Refund more than','Do not hand over if refund more than','refund_overdue','My refund has not arrived.',refund()),
 (2,'Create a ticket','Do not create a ticket','refund_overdue','My refund has not arrived.',refund()),
])
def test_negated_source_action_cannot_authorize_business_tool_effect(sources,data,index,old,new,reason,query,order):
 sources[index]['text']=sources[index]['text'].replace(old,new)
 assert row(derive(sources,data,query,order=order),reason)['applicable'] is None


@pytest.mark.parametrize('query',[
 'Explain the standard refund options generally. This is a different question, not my previous issue.',
 'This is a separate issue about delivery options.',
 'I have a new question about refunds.',
 'Tell me about refund policy in general.',
 'Explain general refund information.',
 'Yeh alag issue hai, refund options batao.',
 'यह अलग समस्या है, रिफंड के नियम बताइए।',
])
def test_explicit_other_or_general_topic_does_not_inherit_same_issue_contact_count(sources,data,query):
 result=derive(sources,data,query,order={'contacts_last_9_days':'9'})
 assert row(result,'repeat_contact')['applicable'] is False
 assert result['recommended_reason'] is None

@pytest.mark.parametrize('query',[
 'The same refund issue remains unresolved.',
 'My refund has still not arrived; generally what are my options?',
 'This is not a different issue. The same refund problem remains.',
 'My refund issue is unresolved again.',
])
def test_actual_same_unresolved_issue_keeps_verified_repeat_handover(sources,data,query):
 result=derive(sources,data,query,order={'contacts_last_9_days':'3'})
 assert row(result,'repeat_contact')['applicable'] is True
 assert result['recommended_reason']=='repeat_contact'


@pytest.mark.parametrize('prefix', ['Maine', 'Humne', 'मैंने', 'हमने'])
def test_reported_damage_identifies_named_verified_line_without_asking_for_colour(sources,data,prefix):
 order={'items':[{'sku':'CASE-X','title':'Aster Radio, Blue','unit_price_inr':'800'},
                 {'sku':'TV-X','title':'Aster Vista 43-inch Smart TV, Grey','unit_price_inr':'1500'}]}
 decision=row(derive(sources,data,prefix+' Aster Vista 43 inch Smart TV damage report kiya tha. Replacement approve karo?',order=order),'high_value_damage')
 assert decision['applicable'] is True
 assert decision['facts']['item_sku']=='TV-X' and decision['facts']['item_value_inr']=='1500'
 assert decision['facts']['value_origin']=='verified_order.items.unit_price_inr'


def test_same_named_family_in_two_order_lines_remains_ambiguous(sources,data):
 order={'items':[{'sku':'TV-A','title':'Aster Vista Smart TV, Grey','unit_price_inr':'1500'},
                 {'sku':'TV-B','title':'Aster Vista Smart TV, Blue','unit_price_inr':'1600'}]}
 decision=row(derive(sources,data,'Maine Aster Vista Smart TV damage report kiya tha.',order=order),'high_value_damage')
 assert decision['applicable'] is None and 'one_unambiguous_item_value' in decision['missing_inputs']


def test_verified_named_line_uses_mutated_source_threshold(sources,data):
 sources[0]['text']=sources[0]['text'].replace('1,200','1,600')
 order={'items':[{'sku':'CASE-X','title':'Aster Radio, Blue','unit_price_inr':'800'},
                 {'sku':'TV-X','title':'Aster Vista Smart TV, Grey','unit_price_inr':'1500'}]}
 decision=row(derive(sources,data,'Maine Aster Vista Smart TV damage report kiya tha.',order=order),'high_value_damage')
 assert decision['applicable'] is False and decision['facts']['threshold_inr']=='1600'
