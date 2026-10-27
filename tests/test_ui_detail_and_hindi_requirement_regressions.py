"""Reject observed unsupported claims without changing source-derived policy."""
import copy
import pytest
from src.navigation_labels import validate_navigation_steps,derive_navigation_procedures
from test_customer_condition_premises import check, SOURCES

UI=[{'id':'route-novel','text':'Claims are raised in the app under Service Requests.',
     'doc_type':'policy','status':'current','effective_from':'2020-01-01'}]

@pytest.mark.parametrize('answer',[
 'In the app check your order details, then raise a claim.',
 'View your item details in Service Requests.',
 'App mein order details dekhne ke baad claim karein.',
 'App mein order dikhayein aur claim karein.',
])
def test_record_detail_steps_need_explicit_document_support(answer):
 with pytest.raises(ValueError,match='unsupported_navigation_procedure'):
  validate_navigation_steps(answer,UI)

@pytest.mark.parametrize('answer',[
 'Claims are raised in the app under Service Requests.',
 'Do not view your item details in the app.',
 'Do you need to check your order details in the app?',
 'The supplied source does not describe viewing order details in the app.',
])
def test_location_statements_questions_and_negative_instructions_remain_allowed(answer):
 validate_navigation_steps(answer,UI)

def test_explicit_source_step_authorizes_only_its_record_type():
 docs=[dict(UI[0],text='In the app view your item details under Service Requests.')]
 assert ('view_record_details','item') in {(r['operation'],r['object']) for r in derive_navigation_procedures(docs)}
 validate_navigation_steps('View your item details in the app under Service Requests.',docs)
 with pytest.raises(ValueError,match='unsupported_navigation_procedure'):
  validate_navigation_steps('View your order details in the app.',docs)

@pytest.mark.parametrize('answer',[
 'उत्पाद खुले रहने की आवश्यकता होती है।',
 'वापसी के लिए उत्पाद खुले रहने की आवश्यकता है।',
 'उत्पाद खुले रहने की जरूरत है।',
 'उत्पाद खुले रहने की ज़रूरत है।',
 'उत्पाद खुले रहना जरूरी है।',
])
def test_hindi_requirement_narration_cannot_reverse_unopened_condition(answer):
 with pytest.raises(ValueError,match='contradicted_return_condition_polarity:opened'):
  check(answer)

@pytest.mark.parametrize('answer',[
 'उत्पाद अनखुले रहने की आवश्यकता होती है।',
 'उत्पाद अनखुले रहने की आवश्यकता है।',
 'उत्पाद खुले नहीं रहने की जरूरत है।',
 'उत्पाद खुले रहने की आवश्यकता नहीं है।',
 'बाहरी पैकिंग खुले रहने की आवश्यकता होती है।',
])
def test_correct_negation_and_unrelated_packaging_subject_are_preserved(answer):
 check(answer)

def test_hindi_requirement_check_follows_changed_document_polarity():
 changed=copy.deepcopy(SOURCES);changed[0]['text']=changed[0]['text'].replace('unopened','opened')
 check('उत्पाद खुले रहने की आवश्यकता होती है।',sources=changed)
 with pytest.raises(ValueError,match='contradicted_return_condition_polarity:opened'):
  check('उत्पाद अनखुले रहने की आवश्यकता होती है।',sources=changed)
