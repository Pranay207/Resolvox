"""Retrieval regressions use new utterances and source contracts, not answer plans."""
from types import SimpleNamespace

import numpy as np
import pytest

from src.kb import Chunk, KnowledgeBase
from src.retrieval import Retriever, tokenize


@pytest.fixture(scope='module')
def retriever():
    return Retriever(KnowledgeBase(), dense=False)


@pytest.mark.parametrize('query,expected', [
    ('The courier has skipped collecting my parcel twice. What happens next?', 'RVP-2'),
    ('Could I swap these trainers for a larger size?', 'RET-9'),
    ('Why is my returned money waiting for an inspection?', 'RET-7'),
    ('Can I use a voucher alongside another coupon?', 'CPN-1'),
    ('Cash refund sent to my wallet: can it be moved into my savings account?', 'PAY-4'),
    ('Does joining Plus extend the deadline for sending something back?', 'PLS-2'),
    ('paise wallet mein aa gaye, bank mein bhej sakte ho?', 'PAY-4'),
    ('Can I cancel just one item from the basket and keep the others?', 'CAN-4'),
    ('Please tell me whether the failed UPI debit reverses without a support request.', 'PAY-3'),
    ('मेरे ऑर्डर को शिप होने के बाद कैंसिल कर सकते हैं?', 'CAN-2'),
    ('How much time does the UPI refund need once initiated?', 'REF-2'),
])
def test_unseen_customer_phrasings(retriever, query, expected):
    assert expected in {row['chunk'].id for row in retriever.search(query, k=8)}


def test_devanagari_words_preserve_vowel_marks():
    words = tokenize('ऑर्डर कैंसिल रिफ़ंड')
    assert words == ['ऑर्डर', 'कैंसिल', 'रिफ़ंड']


def test_intent_hint_cannot_replace_query(retriever):
    query = 'Cash refund sent to my wallet: can it be moved into my savings account?'
    assert retriever.search(query, k=1, intent='damage')[0]['chunk'].id == 'PAY-4'


def test_historical_flag_never_reopens_obsolete_pickup_fee(retriever):
    query = 'Earlier electronics returns policy version 3 return windows and free reverse pickup'
    normal = {row['chunk'].id for row in retriever.search(query, 100)}
    historical = {row['chunk'].id for row in retriever.search(query, 100, historical=True)}
    assert 'RETv3-2' not in normal
    assert 'RETv3-2' in historical
    assert 'RETv3-6' not in normal | historical


@pytest.mark.parametrize('query,k', [('', 8), ('   ', 8), ('refund', 0), ('refund', -1)])
def test_empty_search(retriever, query, k):
    assert retriever.search(query, k) == []


def test_results_keep_source_metadata_and_score_contract(retriever):
    rows = retriever.search('When does an initiated card refund arrive?', k=8)
    assert 1 <= len(rows) <= 8
    assert len({row['chunk'].id for row in rows}) == len(rows)
    assert [row['score'] for row in rows] == sorted((row['score'] for row in rows), reverse=True)
    for row in rows:
        assert set(row) == {'chunk', 'score', 'dense_score'}
        assert row['chunk'] is retriever.kb.chunks[row['chunk'].id]
        assert row['chunk'].text.startswith('## [')


def make_chunk(ident, title, body, kind='policy', file='pol_refunds.md', status='current'):
    return Chunk(ident, f'## [{ident}] {title}\n{body}', file, kind, status,
                 '2026-01-01', '1.0', title)


def make_kb(*chunks):
    return SimpleNamespace(chunks={c.id: c for c in chunks},
                           allowed=lambda chunk, historical=False: chunk.status == 'current')


def test_current_policy_outranks_identical_faq_copy():
    policy = make_chunk('NEW-1', 'Refund timeline', 'Card refund takes business days.')
    faq = make_chunk('OLD-1', policy.title, 'Card refund takes business days.', kind='faq')
    r = Retriever(make_kb(faq, policy), dense=False)
    assert r.search('Card refund timeline', k=1)[0]['chunk'] == policy


def test_dependencies_follow_new_source_ids_and_respect_scope():
    policy = make_chunk('NEW-1', 'Parcel compensation',
                        'A priority delayed parcel receives an adjustment; see DEP-9.')
    dependency = make_chunk('DEP-9', 'Adjustment calculation', 'An adjustment uses a verified ledger.')
    obsolete = make_chunk('DEP-8', 'Earlier adjustment', 'Unlimited parcel compensation.', status='superseded')
    policy = make_chunk('NEW-1', policy.title, policy.text + ' Old wording: DEP-8.')
    others = [make_chunk(f'ALT-{i}', f'Parcel compensation {i}', 'Delayed parcel compensation adjustment.') for i in range(8)]
    r = Retriever(make_kb(policy, dependency, obsolete, *others), dense=False)
    rows = r.search('priority delayed parcel compensation', k=8, historical=True)
    ids = [row['chunk'].id for row in rows]
    assert ids[0] != 'DEP-9'
    assert 'DEP-9' in ids
    assert 'DEP-8' not in ids


def test_dense_channels_keep_raw_query_separate(monkeypatch, tmp_path):
    from src import retrieval
    model_dir = tmp_path / 'model'
    model_dir.mkdir()
    (model_dir / 'model.onnx').touch()
    seen = []

    class Model:
        def encode(self, texts):
            seen.append(list(texts))
            return np.tile(np.array([[1., 0.]], dtype=np.float32), (len(texts), 1))

    monkeypatch.setattr(retrieval, 'MODEL_DIR', model_dir)
    monkeypatch.setattr(retrieval, 'CACHE', tmp_path)
    monkeypatch.setattr(retrieval, 'dense_model', lambda: Model())
    chunk = make_chunk('NEW-1', 'Refund timeline', 'Refunds reach the original payment method.')
    r = Retriever(make_kb(chunk), dense=True)
    query = 'When does my refund arrive?'
    r.search(query)
    assert seen[-1][0] == query
    assert len(seen[-1]) > 1
    assert all(not text.startswith('## [') for batch in seen for text in batch)


def test_no_documents():
    assert Retriever(make_kb(), dense=False).search('refund') == []
