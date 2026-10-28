import copy,pytest
from src.policy_choices import choice_restatement_inputs

RULE={'id':'novel-choice','text':'For parcel-pay orders, the customer chooses either Nimbus Wallet (instant) or a bank transfer. Bank transfers start only after account details are verified, then take 11 to 14 business days.','doc_type':'policy','status':'current','effective_from':'2020-01-01'}
TABLE={'id':'novel-times','text':'Timelines are counted in business days from the day the refund is initiated.\n| Method | Timeline |\n| --- | --- |\n| Nimbus Wallet for parcel-pay orders | Instant, within 9 hours |\n| Bank transfer for parcel-pay orders | 11 to 14 business days |\n| Credit card | 99 days |','doc_type':'policy','status':'current','effective_from':'2020-01-01'}
def read(query='I used parcel-pay for my order.',sources=None):return choice_restatement_inputs(query,sources or [RULE,TABLE],'2026-10-20')

def test_only_explicit_matching_order_class_choices_and_exact_table_rows_are_selected():
 original=copy.deepcopy([RULE,TABLE]);result=read()
 assert result['sources']==[RULE]
 assert result['facts']['source_choice_rule']['options']==['Nimbus Wallet','bank transfer']
 rows=result['facts']['matching_timing_rows'];assert len(rows)==2
 assert all(row['row'] in TABLE['text'] for row in rows)
 assert all('99 days' not in row['row'] for row in rows)
 assert rows[0]['time_basis']==['Timelines are counted in business days from the day the refund is initiated']
 assert [RULE,TABLE]==original

@pytest.mark.parametrize('query',['I used another method.','I did not use parcel-pay.','I never used parcel-pay.'])
def test_missing_or_negated_class_does_not_select_a_rule(query):assert read(query) is None

@pytest.mark.parametrize('change',[{'status':'superseded'},{'effective_from':'2099-01-01'},{'doc_type':'faq'},{'effective_from':None}])
def test_only_current_effective_policy_can_establish_choices(change):assert read(sources=[{**RULE,**change},TABLE]) is None

def test_conflicting_current_choices_and_timelines_decline_specialized_repair():
 assert read(sources=[RULE,{**RULE,'id':'other','text':RULE['text'].replace('bank transfer','paper cheque')},TABLE]) is None
 other={**TABLE,'id':'other-times','text':TABLE['text'].replace('9 hours','17 hours')}
 assert read(sources=[RULE,TABLE,other]) is None

def test_changed_source_names_and_values_are_copied_without_business_constants():
 changed=[dict(r,text=r['text'].replace('Nimbus Wallet','Aster Credit').replace('9 hours','17 hours')) for r in [RULE,TABLE]]
 result=read(sources=changed)
 assert result['facts']['source_choice_rule']['options']==['Aster Credit','bank transfer']
 assert '17 hours' in result['facts']['matching_timing_rows'][0]['row']
