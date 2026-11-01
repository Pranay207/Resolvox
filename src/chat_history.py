"""Local, single-laptop conversation history. No shared-user authentication.

Only presentation data and redacted conversation context are retained. Order
verification is deliberately not restored. SQLite writes are atomic and use
revisions to prevent one browser tab overwriting another tab's newer messages.
"""
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid


class HistoryError(Exception):
    """A safe history-storage failure; provider details never belong here."""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _output(value):
    out = {key: value.get(key, '') for key in
           ('transcript', 'answer', 'intent', 'decision', 'language')}
    if not all(isinstance(v, str) for v in out.values()):
        raise HistoryError('Invalid conversation text')
    out['retrieved_chunk_ids'] = list(value.get('retrieved_chunk_ids', []))
    out['sources'] = [{k: source[k] for k in
        ('id', 'title', 'doc_type', 'text', 'path', 'version', 'effective_date', 'authority')
        if k in source} for source in value.get('sources', [])
        if source.get('doc_type') in {'policy', 'help', 'faq'}]
    out['tool_calls'] = []
    for call in value.get('tool_calls', []):
        name = call.get('name')
        if name not in {'lookup_order', 'create_ticket'}:
            continue
        result = call.get('result', {})
        out['tool_calls'].append({
            'name': name,
            'arguments': {'order_id': call.get('arguments', {}).get('order_id')},
            'result': {key: result[key] for key in ('verified', 'created', 'ticket_id') if key in result},
        })
    return out


def capture(state, messages):
    """Do not save raw tool arguments, authenticated orders or model diagnostics."""
    if not messages or len(messages) > 500:
        raise HistoryError('Conversation size is not supported')
    context = {name: getattr(state, name) for name in (
        'order_id', 'attempts', 'language', 'turn', 'pending_issue', 'pending_intent',
        'last_intent', 'safe_history', 'public_context', 'source_input_workflow')}
    context['tickets'] = [
        {'order_id': key[0], 'reason': key[1],
         'result': {'created': True, 'ticket_id': value['ticket_id']}}
        for key, value in state.tickets.items()
        if value.get('created') is True and value.get('ticket_id')]
    entries = [{'output': _output(entry['output']),
                'audio_error': 'speech_unavailable' if entry.get('audio_error') else None}
               for entry in messages]
    value = {'version': 1, 'state': context, 'messages': entries}
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError) as error:
        raise HistoryError('Conversation could not be serialized') from error
    if len(encoded.encode('utf-8')) > 2_000_000:
        raise HistoryError('Conversation is too large to save')
    return encoded


def restore_state(value):
    """Restore conversational context, always starting without order access."""
    from .agent import State
    state = State()
    for name in ('order_id', 'attempts', 'language', 'turn', 'pending_issue',
                 'pending_intent', 'last_intent', 'safe_history', 'public_context',
                 'source_input_workflow'):
        if name in value:
            setattr(state, name, value[name])
    state.order = None
    state.tickets = {(item['order_id'], item['reason']): item['result']
                     for item in value.get('tickets', [])
                     if item.get('result', {}).get('created') is True
                     and item['result'].get('ticket_id')}
    return state


class LocalHistory:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with closing(self._connect()) as db, db:
            db.execute('PRAGMA journal_mode=WAL')
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise HistoryError('History format is not supported')
            db.execute("""CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, revision INTEGER NOT NULL,
                payload TEXT NOT NULL, deleted_at TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS reply_audio (
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                ordinal INTEGER NOT NULL, content BLOB NOT NULL,
                PRIMARY KEY (conversation_id, ordinal))""")
            db.execute('PRAGMA user_version=1')

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=3)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def list(self):
        with closing(self._connect()) as db:
            rows = db.execute("""SELECT id,title,updated_at,revision FROM conversations
                WHERE deleted_at IS NULL ORDER BY updated_at DESC LIMIT 100""").fetchall()
        return [dict(row) for row in rows]

    def save(self, conversation_id, state, messages, revision=None):
        payload = capture(state, messages)
        title = next((e['output']['transcript'] for e in messages
                      if e['output'].get('transcript') and
                      e['output']['transcript'] != '[verification value redacted]'),
                     'Support conversation')
        title = ' '.join(title.split())[:64]
        audio = [(i, bytes(e['audio'])) for i, e in enumerate(messages) if e.get('audio')]
        if any(len(content) > 10_000_000 for _, content in audio) or sum(len(c) for _, c in audio) > 32_000_000:
            raise HistoryError('Reply audio is too large to save')
        now = _now()
        with closing(self._connect()) as db, db:
            # The write lock covers the revision check and the whole snapshot.
            db.execute('BEGIN IMMEDIATE')
            if conversation_id is None:
                conversation_id = uuid.uuid4().hex
                new_revision = 1
                db.execute('INSERT INTO conversations VALUES (?,?,?,?,?,?,NULL)',
                           (conversation_id, title, now, now, new_revision, payload))
            else:
                row = db.execute('SELECT revision,deleted_at FROM conversations WHERE id=?',
                                 (conversation_id,)).fetchone()
                if row is None or row['deleted_at'] is not None:
                    raise HistoryError('This saved conversation is no longer available')
                if revision != row['revision']:
                    raise HistoryError('A newer version of this conversation is already saved')
                new_revision = row['revision'] + 1
                db.execute('UPDATE conversations SET title=?,updated_at=?,revision=?,payload=? WHERE id=?',
                           (title, now, new_revision, payload, conversation_id))
            db.execute('DELETE FROM reply_audio WHERE conversation_id=?', (conversation_id,))
            db.executemany('INSERT INTO reply_audio VALUES (?,?,?)',
                           [(conversation_id, i, content) for i, content in audio])
        return conversation_id, new_revision

    def load(self, conversation_id):
        with closing(self._connect()) as db:
            row = db.execute('SELECT * FROM conversations WHERE id=? AND deleted_at IS NULL',
                             (conversation_id,)).fetchone()
            if row is None:
                raise HistoryError('Saved conversation is not available')
            try:
                value = json.loads(row['payload'])
                if value.get('version') != 1 or not isinstance(value.get('state'), dict):
                    raise ValueError('invalid format')
                messages = value['messages']
                if not isinstance(messages, list) or not messages or len(messages) > 500:
                    raise ValueError('invalid messages')
                messages = [{'output': _output(e['output']), 'audio': None,
                             'audio_error': e.get('audio_error')} for e in messages]
                restore_state(value['state'])  # Validate the restoration before opening it.
            except (KeyError, TypeError, ValueError, AttributeError) as error:
                raise HistoryError('Saved conversation could not be read') from error
            for audio in db.execute('SELECT ordinal,content FROM reply_audio WHERE conversation_id=?',
                                    (conversation_id,)):
                if 0 <= audio['ordinal'] < len(messages):
                    messages[audio['ordinal']]['audio'] = bytes(audio['content'])
        return {'id': row['id'], 'revision': row['revision'],
                'state': value['state'], 'messages': messages}

    def delete(self, conversation_id):
        with closing(self._connect()) as db, db:
            db.execute('UPDATE conversations SET deleted_at=? WHERE id=? AND deleted_at IS NULL',
                       (_now(), conversation_id))

    def undo_delete(self, conversation_id):
        with closing(self._connect()) as db, db:
            db.execute('UPDATE conversations SET deleted_at=NULL WHERE id=?', (conversation_id,))
