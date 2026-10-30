"""Script equivalence must not turn a translated label into a new category."""
import json
import pytest
from src.category_labels import check_policy_category_labels


def catalog(code):
    return dict(id='changed-item-source',doc_type='catalog',status='current',text=json.dumps({'return_category':code}))


@pytest.mark.parametrize('code,label',[
    ('fashion','फैशन'),('fashion','फ़ैशन'),('electronics','इलेक्ट्रॉनिक्स'),
    ('electronics','इलेक्ट्रोनिक्स'),('grocery','ग्रोसरी'),('innerwear','इनरवियर'),('digital','डिजिटल'),
])
def test_same_technical_term_is_valid_in_hindi_script_only_when_source_contains_it(code,label):
    check_policy_category_labels(f'यह {label} श्रेणी में शामिल है।',[catalog(code)],'2026-10-20')


@pytest.mark.parametrize('source_code,label',[
    ('fashion_x','फैशन'),('books_media','फैशन'),('grocery','ग्रीन'),('digital','ग्रोसरी'),
])
def test_wrong_terms_and_mutated_source_identities_are_still_rejected(source_code,label):
    with pytest.raises(ValueError,match='unsupported_category_label'):
        check_policy_category_labels(f'यह {label} श्रेणी में शामिल है।',[catalog(source_code)],'2026-10-20')


def test_faithful_transliteration_does_not_supply_a_category_absent_from_policy():
    source=dict(id='new-table',doc_type='policy',status='current',text='| Novel Group | 31 days | novel_group |')
    with pytest.raises(ValueError,match='unsupported_category_label'):
        check_policy_category_labels('यह फैशन श्रेणी में शामिल है।',[source],'2026-10-20')
