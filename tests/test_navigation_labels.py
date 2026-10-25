"""Finite named-control grounding regressions; no model calls or answer gold."""
import copy,json
import pytest
from src.navigation_labels import derive_navigation_labels,validate_navigation_steps


def source(text='Requests are raised in the app under Service Requests.',**changes):
 return {'id':'UI-SOURCE-X','text':text,'file':'pol_requests.md','doc_type':'policy','status':'current','effective_from':'2020-01-01','version':'1',**changes}

@pytest.mark.parametrize('answer',[
 "Click the 'Claim' option in the app.",
 'Click Claim option in the app.',
 'Tap the Claim button.',
 'Open the Claim tab.',
 'Choose the Claim menu in the app.',
 "Click 'Claim'.",
 'Click claim in the app.',
 "App mein 'Claim' option par click karein.",
 'App mein Claim option par click karein.',
 'Claim option pe tap karo.',
 "App mein 'Claim' par click karein.",
 "\u090f\u092a \u092e\u0947\u0902 'Claim' \u0935\u093f\u0915\u0932\u094d\u092a \u092a\u0930 \u0915\u094d\u0932\u093f\u0915 \u0915\u0930\u0947\u0902\u0964",
 'Click the button named Claim.',
])
def test_invented_named_positive_controls_reject(answer):
 with pytest.raises(ValueError,match='unsupported_navigation_label'):
  validate_navigation_steps(answer,[source()])

@pytest.mark.parametrize('answer',[
 'Raise the request in the app under Service Requests.',
 'Open Service Requests.',
 "Open 'Service Requests'.",
 "App mein 'Service Requests' option par click karein.",
 'Service Requests option pe tap karein.',
 "\u090f\u092a \u092e\u0947\u0902 'Service Requests' \u0935\u093f\u0915\u0932\u094d\u092a \u092a\u0930 \u0915\u094d\u0932\u093f\u0915 \u0915\u0930\u0947\u0902\u0964",
 'Raise a claim in the app.',
 'Claim karein ke liye app mein request raise karein.',
 'Do you see a Claim option in the app?',
 'The supplied documents do not name a Claim button.',
 'Source mein Claim option ka naam nahi diya hai.',
 'Do not click an unknown Claim button.',
 'Claim option par click mat karein.',
 'Open your order and raise a claim.',
 'Choose a pickup slot.',
 'Select a pickup slot in the app.',
 'Choose Wallet or bank transfer as the refund option.',
 'The available options are Wallet and bank transfer.',
])
def test_documented_labels_general_actions_questions_absence_and_choices_remain_allowed(answer):
 validate_navigation_steps(answer,[source()])

@pytest.mark.parametrize('label',['Repair Desk','Request Centre','Warranty Review','Account Tasks'])
def test_actual_source_label_mutation_controls_allowed_navigation(label):
 docs=[source('Requests are raised in the app under '+label+'.')]
 assert {row['label'] for row in derive_navigation_labels(docs)}=={label.casefold()}
 validate_navigation_steps("Click the '"+label+"' option in the app.",docs)
 with pytest.raises(ValueError,match='unsupported_navigation_label'):
  validate_navigation_steps("Click the 'Service Requests' option in the app.",docs)

@pytest.mark.parametrize('body,answer,label',[
 ("In the app tap the 'Create Case' button.","Click the 'Create Case' button.",'create case'),
 ('In the app tap service requests option.','Tap service requests option.','service requests'),
 ('In the app tap the button named Start Review.','Click the Start Review button.','start review'),
 ('Hold the case button until its light flashes.','Press the case button.','case'),
])
def test_actual_explicit_named_controls_are_preserved(body,answer,label):
 docs=[source(body)]
 assert label in {row['label'] for row in derive_navigation_labels(docs)}
 validate_navigation_steps(answer,docs)

@pytest.mark.parametrize('changes',[{'status':'superseded'},{'effective_from':'2099-01-01'},{'doc_type':'marketing'},{'doc_type':'catalog'},{'doc_type':'unknown'}])
def test_inactive_or_non_rule_text_cannot_authorize_an_invented_control(changes):
 docs=[source("In the app click the 'Claim' button.",**changes)]
 assert not derive_navigation_labels(docs)
 with pytest.raises(ValueError,match='unsupported_navigation_label'):
  validate_navigation_steps("Click the 'Claim' button.",docs)


def test_negative_source_control_mention_does_not_authorize_positive_step():
 docs=[source('The app does not have a Claim button.')]
 assert not derive_navigation_labels(docs)
 with pytest.raises(ValueError,match='unsupported_navigation_label'):
  validate_navigation_steps('Click the Claim button in the app.',docs)


def test_quoted_catalog_flag_and_general_warranty_verbs_are_not_ui_names():
 validate_navigation_steps("The catalog assured flag is 'True'. Raise a claim in the app.",[source()])


def test_actual_first_fresh_response_invents_a_control_beyond_actual_policy_route():
 from src.kb import KnowledgeBase
 docs=[c.public() for c in KnowledgeBase().require('WAR-2')]
 assert 'my orders' in {row['label'] for row in derive_navigation_labels(docs)}
 with pytest.raises(ValueError,match='unsupported_navigation_label'):
  validate_navigation_steps("Claim karein ke liye app mein 'My Orders' par jaayein, order ke baad 'Claim' option par click karein.",docs)
 validate_navigation_steps("Claim app mein 'My Orders' ke under raise karein.",docs)

class Client:
 def __init__(self,values):self.values=iter(values);self.calls=[];self.last_metrics={}
 def complete(self,system,user,**options):
  self.calls.append(json.loads(user));return json.dumps(next(self.values))

def response(answer):return {'answer':answer,'covered':True,'needs_clarification':False}


def test_one_source_bound_repair_has_only_derived_labels_and_preserves_supported_reply():
 from src.document_answers import document_reply
 docs=[source()];c=Client([response("Click the 'Claim' button."),response('Raise the request in the app under Service Requests.')])
 out=document_reply(c,'How do I submit a request?','en',docs,facts={},context_provenance=True)
 assert len(c.calls)==2 and out['repair_attempted'] is True
 assert out['repair_errors']==['unsupported_navigation_label']
 labels=c.calls[1]['documented_navigation_labels']
 assert {row['label'] for row in labels}=={'service requests'}
 assert all(row['source_ids']==['UI-SOURCE-X'] and row['source_sha256'] for row in labels)
 assert 'invented' in c.calls[1]['repair_instruction'] and out['answer'].startswith('Raise the request')


def test_repeated_invented_control_is_rejected_after_one_repair():
 from src.document_answers import document_reply
 c=Client([response('Click the Claim button.'),response('Click the Claim button.')])
 with pytest.raises(ValueError,match='document_generation_failed:unsupported_navigation_label'):
  document_reply(c,'How do I submit a request?','en',[source()],facts={},context_provenance=True)
 assert len(c.calls)==2


@pytest.mark.parametrize('answer',[
 'In the app select your item.',
 'App mein woh item select karein.',
 'App mein order select karein.',
 'In the app fill in the warranty claim form.',
 'Warranty claim form mein details bharein.',
 'Complete the form in the app.',
])
def test_undocumented_record_selection_and_form_completion_reject(answer):
 with pytest.raises(ValueError,match='unsupported_navigation_(?:procedure|label)'):
  validate_navigation_steps(answer,[source()])


@pytest.mark.parametrize('answer',[
 'Choose an item that suits the stated requirements.',
 'Select a product for comparison.',
 'Do you need to fill in a claim form?',
 'The supplied policy does not describe a warranty claim form.',
 'Please do not select your item in the app.',
])
def test_general_selection_and_neutral_form_questions_are_not_ui_inventions(answer):
 validate_navigation_steps(answer,[source()])


def test_actual_source_explicit_record_selection_and_form_step_authorize_only_that_object():
 from src.navigation_labels import derive_navigation_procedures
 docs=[source("In the app select the item, then fill in the 'Repair Request' form.")]
 steps=derive_navigation_procedures(docs)
 assert {(row['operation'],row['object']) for row in steps}=={('select_record','item'),('complete_form','form')}
 validate_navigation_steps("In the app select your item, then fill in the 'Repair Request' form.",docs)
 with pytest.raises(ValueError,match='unsupported_navigation_procedure'):
  validate_navigation_steps('In the app select your order.',docs)


def test_actual_new_fresh_item_and_form_instruction_is_unsupported():
 from src.kb import KnowledgeBase
 docs=[c.public() for c in KnowledgeBase().require('WAR-2')]
 answer="Claim karein ke liye app mein 'My Orders' mein jaayein, phir woh item select karein aur warranty claim form mein details dinay mein."
 with pytest.raises(ValueError,match='unsupported_navigation_(?:procedure|label)'):
  validate_navigation_steps(answer,docs)


def test_source_form_name_mutation_preserves_the_actual_new_name_only():
 docs=[source("In the app fill in the 'Case Form' form.")]
 names={row['label'] for row in derive_navigation_labels(docs)}
 assert 'case form' in names and 'case' not in names
 validate_navigation_steps("Fill in the 'Case Form' form in the app.",docs)
 with pytest.raises(ValueError,match='unsupported_navigation_label'):
  validate_navigation_steps("Fill in the 'Wrong Form' form in the app.",docs)


def test_source_authority_prevents_help_overriding_explicit_policy_control_prohibition():
 docs=[source('The app does not have a Claim button.'),source('In the app click the Claim button.',id='HELP-Y',doc_type='help')]
 assert 'claim' not in {row['label'] for row in derive_navigation_labels(docs)}
 with pytest.raises(ValueError,match='unsupported_navigation_label'):
  validate_navigation_steps('Click the Claim button in the app.',docs)


def test_same_priority_control_conflict_does_not_authorize_positive_step():
 docs=[source('The app does not have a Claim button.'),source('In the app click the Claim button.',id='OTHER-Z')]
 with pytest.raises(ValueError,match='unsupported_navigation_label'):
  validate_navigation_steps('Click the Claim button in the app.',docs)


def test_conflicting_duplicate_source_id_is_not_accepted_as_navigation_proof():
 docs=[source(),source('In the app click the Claim button.')]
 with pytest.raises(ValueError,match='conflicting_navigation_source_id'):
  derive_navigation_labels(docs)


def test_primary_payload_is_unchanged_and_procedure_facts_are_added_only_on_repair():
 from src.document_answers import document_reply
 docs=[source()];c=Client([response('In the app select your item.'),response('Raise the request in the app under Service Requests.')])
 out=document_reply(c,'How do I submit a request?','en',docs,facts={},context_provenance=True)
 assert out['repair_errors']==['unsupported_navigation_procedure']
 assert 'documented_navigation_steps' not in c.calls[0] and 'documented_navigation_labels' not in c.calls[0]
 assert c.calls[1]['documented_navigation_steps']==[]
 assert c.calls[0]['source_text']==c.calls[1]['source_text']


@pytest.mark.parametrize('answer',[
 'The policy does not cover damage, but click the Claim button in the app.',
 'The documents do not mention a Claim button, and click the Claim button.',
 'Do not click random buttons, then click the Claim button in the app.',
])
def test_neutral_prefix_cannot_hide_a_later_positive_ui_step(answer):
 with pytest.raises(ValueError,match='unsupported_navigation_label'):
  validate_navigation_steps(answer,[source()])
