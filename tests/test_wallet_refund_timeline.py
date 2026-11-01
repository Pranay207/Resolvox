import copy
import pytest
from types import SimpleNamespace
from src.document_context import build_context
from src.refund_timeline import check_refund_timeline_answer,refund_timeline_inputs,refund_timeline_binding

def context(hours=17):
 sources=[{'id':'wallet-clock','doc_type':'policy','status':'current','text':f'Refund timelines after initiation.\n| Payment method | Time |\n| --- | --- |\n| ZentroMart Wallet | Instant, within {hours} hours |\n| ZentroMart Wallet for cash-on-delivery orders | Instant, within {hours} hours |'}]
 facts=build_context('Refund kitne din mein aayega?',sources,SimpleNamespace(products={},holidays=set()),verified_order={'payment_method':'wallet','is_plus':True})
 return facts,sources

def test_wallet_reads_actual_hours_and_duplicate_equivalent_rows():
 facts,sources=context();assert facts['refund_arrival_policy']['maximum_hours']==17
 assert refund_timeline_inputs('Refund kitne din mein aayega?',facts,sources,'2026-10-20')
 check_refund_timeline_answer('Refund shuru hone ke baad wallet mein 17 ghante ke andar aayega.','Refund kitne din mein aayega?',facts,sources,'2026-10-20')

@pytest.mark.parametrize('answer',['Wallet refund takes 17 business days after initiation.','Wallet refund takes 2 hours after initiation.','Wallet refunds arrive within 17 hours.','After initiation, wallet refunds arrive within 17 hours on 20 October 2026.'])
def test_wrong_wallet_unit_number_anchor_or_unsupported_date_rejected(answer):
 facts,sources=context()
 with pytest.raises(ValueError):check_refund_timeline_answer(answer,'Refund kitne din mein aayega?',facts,sources,'2026-10-20')

def test_changed_wallet_row_cannot_reuse_old_binding():
 facts,sources=context();changed=copy.deepcopy(sources);changed[0]['text']=changed[0]['text'].replace('17 hours','19 hours')
 with pytest.raises(ValueError,match='unbound'):check_refund_timeline_answer('After initiation, wallet refunds arrive within 17 hours.','Refund kitne din mein aayega?',facts,changed,'2026-10-20')

def test_conflicting_wallet_rows_do_not_choose_one():
 facts,sources=context();sources[0]['text']=sources[0]['text']+'\n| ZentroMart Wallet | Instant, within 19 hours |'
 assert refund_timeline_binding('Refund kitne din mein aayega?',facts,sources,'2026-10-20') is None


@pytest.mark.parametrize('query',[
    'How fast are refunds to the ZentroMart Wallet?',
    'How quickly do wallet refunds arrive?',
    'Wallet refund ki speed kya hai?',
    'Wallet refund kitni jaldi aayega?',
    'वॉलेट में रिफंड कितनी जल्दी आएगा?',
])
def test_speed_wording_binds_public_refund_to_actual_source_clock(query):
    _,sources=context(hours=19)
    facts=build_context(query,sources,SimpleNamespace(products={},holidays=set()))
    assert facts['refund_arrival_policy']['maximum_hours']==19
    assert refund_timeline_inputs(query,facts,sources,'2026-10-20')
    check_refund_timeline_answer('After initiation, wallet refunds arrive within 19 hours.',query,facts,sources,'2026-10-20')
    with pytest.raises(ValueError,match='missing_refund_initiation_anchor'):
        check_refund_timeline_answer('Wallet refunds arrive within 19 hours.',query,facts,sources,'2026-10-20')


def test_fast_initiation_question_keeps_full_context_instead_of_arrival_projection():
    query='How fast do you initiate a wallet refund?'
    _,sources=context()
    facts=build_context(query,sources,SimpleNamespace(products={},holidays=set()))
    assert 'refund_arrival_policy' not in facts
    assert refund_timeline_inputs(query,facts,sources,'2026-10-20') is None
