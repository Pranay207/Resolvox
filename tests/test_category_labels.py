from datetime import date
import pytest
from src.category_labels import check_policy_category_labels

SOURCES=[{'id':'TABLE-X','doc_type':'policy','status':'current','effective_from':'2020-01-01','text':'| Home, kitchen and furniture | 16 days | home_x |\n| Books and stationery | 9 days | reading_x |\n| Grocery and perishables | Not returnable | grocery_x |'}]
TODAY=date(2026,10,20)

@pytest.mark.parametrize('text',[
    'It falls under the home_x category.',
    'It belongs to the Home, kitchen and furniture category.',
    'यह Home, kitchen and furniture की श्रेणी में शामिल है।',
    'The return window is 16 days from delivery.',
    'यह 16 दिन के भीतर लौटाया जा सकता है।'])
def test_actual_names_and_answers_without_a_category_assertion_are_preserved(text):
    check_policy_category_labels(text,SOURCES,TODAY)

@pytest.mark.parametrize('text',[
    'It falls under the Food and furniture category.',
    'यह घर, खाना और फर्नीचर के श्रेणी में शामिल है।',
    'यह बुक्स एंड स्टेशनरी कैटेगरी में शामिल है।'])
def test_unsourced_taxonomy_translations_are_not_treated_as_formal_labels(text):
    with pytest.raises(ValueError,match='unsupported_category_label'):
        check_policy_category_labels(text,SOURCES,TODAY)

def test_example_names_are_read_from_actual_source_examples():
    sources=[{'id':'REPORT-X','doc_type':'policy','status':'current','text':'This applies to every category, including grocery and other non-returnable items.'}]
    check_policy_category_labels('This covers every category, including grocery.',sources,TODAY)
    with pytest.raises(ValueError,match='unsupported_category_label'):
        check_policy_category_labels('यह सभी श्रेणियों, जैसे ग्रीन और अन्य वस्तुओं पर लागू है।',sources,TODAY)

def test_changed_source_labels_are_honoured_without_a_compiled_category_dictionary():
    source={**SOURCES[0],'text':'| Alpine equipment | 21 days | alpine_new |'}
    check_policy_category_labels('It falls under the alpine_new category.',[source],TODAY)
    with pytest.raises(ValueError,match='unsupported_category_label'):
        check_policy_category_labels('It falls under the home_x category.',[source],TODAY)



def test_catalog_category_code_is_an_actual_technical_label_even_without_a_window_table():
    import json
    sources=[{'id':'PRODUCT-Z','doc_type':'catalog','status':'current','text':json.dumps({'return_category':'portable_new'})},
             {'id':'REPORT-Z','doc_type':'policy','status':'current','text':'Every category is covered, including grocery.'}]
    check_policy_category_labels('It falls under the portable_new category.',sources,TODAY)
