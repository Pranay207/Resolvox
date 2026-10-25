"""Selected numeric/date facts bind answers without authored policy wording."""
import copy
import json

import pytest

from src.document_answers import document_reply

RET = {'id':'RET-2','text':'Electronics allow 7 calendar days. Fashion allows 15 calendar days.',
       'doc_type':'policy','status':'current'}
OLD = {'id':'RET-3','text':'Earlier deliveries keep a 10-calendar-day window.',
       'doc_type':'policy','status':'current'}
REF = {'id':'REF-2','text':'Card refunds take 5 to 7 business days after initiation.',
       'doc_type':'policy','status':'current'}
CAL = {'id':'KB-00.3','text':'Business days run Monday to Saturday excluding supplied holidays.',
       'doc_type':'meta','status':'current'}
DEL = {'id':'DEL-3','text':'Delivery has 3 attempts before return to sender.',
       'doc_type':'policy','status':'current'}


class Client:
    def __init__(self,*answers):
        self.answers=list(answers); self.calls=[]
    def complete(self,system,user,json_mode=False,**options):
        self.calls.append({'system':system,'payload':json.loads(user),'options':options})
        assert self.answers
        return json.dumps(self.answers.pop(0))


def value(answer,decision='answer',covered=True):
    return {'answer':answer,'decision':decision,'covered':covered}


def quantity(days=15,sid='RET-2'):
    return {'return_policy':{'window_calendar_days':days},
            'answer_constraints':[{'kind':'quantity','value':days,'unit':'calendar_day',
                                   'key':'return_policy.window_calendar_days','source_ids':[sid]}]}


def dates(day=27):
    iso=f'2026-10-{day:02d}'
    return {'reference_date':'2026-10-20','date_labels':{iso:f'{day} October 2026'},
            'calculations':[{'operation':'refund_business_date_range',
                             'source_ids':['REF-2','KB-00.3','data/holidays.csv'],
                             'result':{'latest_date':iso}}],
            'answer_constraints':[{'kind':'date','value':iso,'key':'refund.latest_date',
                                   'source_ids':['REF-2','KB-00.3'],'calculation_index':0}]}


def reply(client,facts,sources,language='en',query='What is the applicable policy?'):
    return document_reply(client,query,language,sources,facts=facts,context_provenance=True)


def reject(answer,facts,sources,language='en'):
    client=Client(value(answer),value(answer))
    with pytest.raises(ValueError,match='answer_constraint_missing'):
        reply(client,facts,sources,language)
    assert len(client.calls)==2
    assert client.calls[1]['options']['cache'] is False


@pytest.mark.parametrize('answer,language',[
    ('Fashion returns allow 15 calendar days.','en'),
    ('Fashion returns allow fifteen days.','en'),
    ('डिलीवरी से पंद्रह दिन में रिटर्न करना होगा।','hi'),
    ('Return window pandrah din ki hai.','hi-en'),
])
def test_selected_quantity_accepts_relevant_multilingual_units(answer,language):
    out=reply(Client(value(answer)),quantity(),[RET],language)
    assert out['answer']==answer


@pytest.mark.parametrize('answer',[
    'Fashion returns allow 7 calendar days.',
    'Fashion returns allow 15 business days.',
])
def test_matching_an_unrelated_table_number_or_wrong_unit_is_not_enough(answer):
    reject(answer,quantity(),[RET])


def test_source_selected_historical_value_overrides_unrelated_current_window():
    out=reply(Client(value('The applicable window is 10 calendar days.')),
              quantity(10,'RET-3'),[RET,OLD])
    assert '10 calendar days' in out['answer']
    reject('The applicable window is 7 calendar days.',quantity(10,'RET-3'),[RET,OLD])


def test_a_changed_source_value_is_used_without_matching_a_known_answer():
    changed=dict(RET,text='This selected category allows 23 calendar days.')
    out=reply(Client(value('This return allows 23 days.')),quantity(23),[changed])
    assert '23 days' in out['answer']


def test_targeted_repair_contains_only_validated_source_bound_constraint():
    client=Client(value('The window is 7 calendar days.'),value('The window is 15 calendar days.'))
    out=reply(client,quantity(),[RET])
    repair=client.calls[1]['payload']
    assert out['generation_attempts']==2
    assert repair['repair_constraints']==quantity()['answer_constraints']
    assert 'calculated deadline' in repair['repair_instruction']
    assert 'verified_rule_summary' not in repair and 'expected_answer' not in repair


@pytest.mark.parametrize('answer,language',[
    ('The latest expected date is 2026-10-27.','en'),
    ('The latest expected date is 27 October 2026.','en'),
    ('The latest expected date is October 27, 2026.','en'),
    ('अंतिम अनुमानित तारीख २७ अक्टूबर २०२६ है।','hi'),
    ('Antim tareekh sattais October 2026 hai.','hi-en'),
])
def test_full_calculated_date_is_accepted_in_normal_language_forms(answer,language):
    out=reply(Client(value(answer)),dates(),[REF,CAL],language)
    assert out['answer']==answer


@pytest.mark.parametrize('answer',[
    'The expected date is 20 October 2026.',
    'The expected date is 27.',
    'The expected date is 27 October.',
])
def test_reference_date_or_bare_day_does_not_satisfy_calculated_deadline(answer):
    reject(answer,dates(),[REF,CAL])


def test_changed_calculation_date_is_not_frozen_to_the_practice_answer():
    out=reply(Client(value('The expected date is 28 October 2026.')),dates(28),[REF,CAL])
    assert '28 October 2026' in out['answer']


def test_required_delivery_attempt_count_is_not_omitted_before_rto_explanation():
    facts={'delivery_policy':{'delivery_attempt_limit':3},
           'answer_constraints':[{'kind':'number','value':3,
                                  'key':'delivery_policy.delivery_attempt_limit','source_ids':['DEL-3']}]}
    reject('The parcel returns to sender if delivery fails.',facts,[DEL])
    out=reply(Client(value('After three delivery attempts, the parcel returns to sender.')),facts,[DEL])
    assert 'three delivery attempts' in out['answer']


@pytest.mark.parametrize('change',[
    'foreign_source','missing_fact','wrong_source_value','wrong_calculation','self_proof',
])
def test_constraints_require_actual_context_and_independent_typed_proof(change):
    facts=quantity()
    sources=[RET]
    if change=='foreign_source':
        facts['answer_constraints'][0]['source_ids']=['MADE-UP']
    elif change=='missing_fact':
        facts.pop('return_policy')
    elif change=='wrong_source_value':
        facts=quantity(99)
    elif change=='wrong_calculation':
        facts=dates()
        facts['calculations'][0]['result']['latest_date']='2026-10-20'
        sources=[REF,CAL]
    else:
        facts['answer_constraints'][0]['key']='answer_constraints.value'
    client=Client()
    with pytest.raises(ValueError):
        reply(client,facts,sources)
    assert client.calls==[]


def test_unqueried_scalar_facts_are_not_automatically_required_in_an_answer():
    facts={'return_policy':{'window_calendar_days':15}}
    out=reply(Client(value('Electronics allow 7 calendar days.')),facts,[RET])
    assert '7 calendar days' in out['answer']


def test_valid_uncovered_clarification_does_not_have_to_assert_a_policy_quantity():
    candidate=value('Which product category would you like to return?','clarify',False)
    out=reply(Client(candidate),quantity(),[RET])
    assert out['covered'] is False


@pytest.mark.parametrize('query,echo,language',[
    ('How long is the return window?','  How long is the return window!!! ','en'),
    ('कितने दिन में वापस करना होगा?','कितने दिन में वापस करना होगा।','hi'),
])
def test_echoed_question_is_repaired_or_rejected(query,echo,language):
    good='Fashion allows 15 calendar days.' if language=='en' else 'डिलीवरी से 15 कैलेंडर दिन मिलते हैं।'
    client=Client(value(echo),value(good))
    out=reply(client,quantity(),[RET],language,query)
    assert out['answer']==good
    assert client.calls[1]['payload']['repair_validation_error']=='echoed_question'
    assert 'Do not repeat it' in client.calls[1]['payload']['repair_instruction']


def test_strict_helper_does_not_apply_context_answer_constraints():
    strict={'answer':'Electronics allow 7 calendar days.','decision':'answer',
            'citations':[{'id':RET['id'],'quote':RET['text']}]}
    client=Client(strict)
    out=document_reply(client,'What is the return window?','en',[RET],facts=quantity())
    assert out['answer']==strict['answer']
