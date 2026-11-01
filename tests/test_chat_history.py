import json
import sqlite3

import pytest

from src.agent import State
from src.chat_history import LocalHistory, HistoryError, restore_state


def entry(text='Where is my order?', audio=None):
    return {'output': {'transcript': text, 'answer': 'Please provide your order ID.',
        'intent': 'delivery', 'decision': 'clarify', 'language': 'en',
        'retrieved_chunk_ids': ['IDV-1'], 'sources': [], 'tool_calls': []},
        'audio': audio, 'audio_error': None}


def test_history_survives_restarting_store_and_retains_reply_audio(tmp_path):
    path=tmp_path/'history.sqlite3'
    store=LocalHistory(path)
    state=State(language='hi', turn=3, public_context={'category':'fashion'})
    chat_id,rev=store.save(None,state,[entry(audio=b'reply-audio')])
    reopened=LocalHistory(path).load(chat_id)
    assert reopened['revision']==rev
    assert reopened['messages'][0]['audio']==b'reply-audio'
    restored=restore_state(reopened['state'])
    assert restored.language=='hi' and restored.public_context=={'category':'fashion'}


def test_history_excludes_credentials_full_order_and_provider_diagnostics(tmp_path):
    store=LocalHistory(tmp_path/'history.sqlite3')
    state=State(order_id='89782837', order={'order_id':'89782837','phone':'private-phone'},
                attempts={'89782837':1},safe_history=[{'user':'[verification value redacted]',
                'intent':'verification','decision':'answer'}])
    message=entry('[verification value redacted]')
    message['output'].update({'facts':{'phone':'private-phone'},
        'llm':{'api_key':'private-provider-secret'},
        'sources':[{'id':'ORDER-1','doc_type':'record','text':'private-phone'},
                   {'id':'IDV-1','doc_type':'policy','text':'Verify first.'}],
        'tool_calls':[{'name':'lookup_order','arguments':{'order_id':'89782837','phone_last4':'4533'},
                       'result':{'verified':True,'order':{'phone':'private-phone'}}}]})
    chat_id,_=store.save(None,state,[message])
    with sqlite3.connect(store.path) as db:
        raw=db.execute('SELECT payload FROM conversations').fetchone()[0]
    assert all(secret not in raw for secret in ('private-phone','private-provider-secret','4533','phone_last4'))
    loaded=store.load(chat_id)
    restored=restore_state(loaded['state'])
    assert restored.order is None and restored.order_id=='89782837'
    assert restored.attempts=={'89782837':1}
    assert [source['id'] for source in loaded['messages'][0]['output']['sources']]==['IDV-1']


def test_stale_tab_cannot_overwrite_a_newer_saved_conversation(tmp_path):
    store=LocalHistory(tmp_path/'history.sqlite3')
    chat_id,rev=store.save(None,State(),[entry()])
    store.save(chat_id,State(turn=2),[entry(),entry('A follow-up')],rev)
    with pytest.raises(HistoryError,match='newer version'):
        store.save(chat_id,State(),[entry('Stale tab')],rev)
    assert len(store.load(chat_id)['messages'])==2


def test_remove_is_recoverable_and_does_not_resurrect_on_save(tmp_path):
    store=LocalHistory(tmp_path/'history.sqlite3')
    chat_id,rev=store.save(None,State(),[entry(audio=b'audio')])
    store.delete(chat_id)
    assert store.list()==[]
    with pytest.raises(HistoryError):store.load(chat_id)
    with pytest.raises(HistoryError):store.save(chat_id,State(),[entry()],rev)
    store.undo_delete(chat_id)
    assert store.load(chat_id)['messages'][0]['audio']==b'audio'


def test_oversized_save_preserves_the_previous_record(tmp_path):
    store=LocalHistory(tmp_path/'history.sqlite3')
    chat_id,rev=store.save(None,State(),[entry()])
    with pytest.raises(HistoryError):
        store.save(chat_id,State(),[entry(audio=b'x'*10_000_001)],rev)
    assert store.load(chat_id)['revision']==rev


def test_restored_ticket_reference_prevents_losing_confirmed_case_context(tmp_path):
    store=LocalHistory(tmp_path/'history.sqlite3')
    state=State(tickets={('order-a','human'):{'created':True,'ticket_id':'T-1'}})
    chat_id,_=store.save(None,state,[entry()])
    restored=restore_state(store.load(chat_id)['state'])
    assert restored.tickets[('order-a','human')]=={'created':True,'ticket_id':'T-1'}


def test_malformed_history_is_a_safe_read_failure(tmp_path):
    store=LocalHistory(tmp_path/'history.sqlite3')
    chat_id,_=store.save(None,State(),[entry()])
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE conversations SET payload=? WHERE id=?', ('not-json',chat_id))
    with pytest.raises(HistoryError,match='could not be read'):
        store.load(chat_id)
