import copy,json,pytest
from test_warranty_duration_guard import staged,sources,build,ScriptedClient
from test_customer_condition_premises import Client, SOURCES, QUERY, facts
from src.document_answers import document_reply
from src.generation_diagnostics import GenerationValidationError

@pytest.mark.parametrize('duration',[17,23])
def test_source_values_follow_document_mutation_without_reasking_navigation_question(staged,sources,duration):
 sources[1]['text']=sources[1]['text'].replace('17-month',str(duration)+'-month')
 value=build(staged,sources);before=copy.deepcopy(value)
 answer=f'ITEM-X has a {duration}-month Helio Secure warranty from delivery. Claims are in the app under My Orders.'
 client=ScriptedClient("Click the 'Wizard' button.",answer)
 result=document_reply(client,'Does ITEM-X have Helio Secure? How do I claim?','en',sources,facts=value,context_provenance=True)
 payload=client.calls[1][0]
 assert 'question' not in payload and 'previous_response' not in payload
 assert payload['deterministic_facts']['answer_constraints']==value['answer_constraints']
 assert result['repair_mode']=='evidence_restatement' and result['answer']==answer
 assert result['repair_context_sources']==payload['source_text'] and value==before

def test_bound_customer_state_and_policy_requirements_remain_separate():
 value=facts();before=copy.deepcopy(value)
 client=Client('Your product is unopened.','You reported opening the product. It does not meet the policy condition requiring unopened products.')
 result=document_reply(client,QUERY,'en',SOURCES,facts=value,context_provenance=True)
 payload=client.calls[1][1]
 assert 'question' not in payload and 'previous_response' not in payload
 assert payload['deterministic_facts']['return_condition_policy']['requirements']['opened'] is False
 assert payload['deterministic_facts']['customer_item_condition_claim']['opened'] is True
 assert payload['deterministic_facts']['customer_item_condition_claim']['input_status']=='customer_provided_unverified'
 assert result['repair_mode']=='source_condition_application' and value==before

@pytest.mark.parametrize('answer',['Click the Magic button.','Helio Secure covers 17 months. View your item details in My Orders.'])
def test_source_restatement_does_not_authorize_new_controls_or_steps(staged,sources,answer):
 client=ScriptedClient("Click the 'Wizard' button.",answer)
 with pytest.raises(GenerationValidationError):document_reply(client,'Does ITEM-X have Helio Secure? How do I claim?','en',sources,facts=build(staged,sources),context_provenance=True)
 assert len(client.calls)==2

def test_reversed_return_rule_still_fails_on_final_attempt():
 client=Client('Your product is unopened.','The policy requires products to be opened.')
 with pytest.raises(GenerationValidationError):document_reply(client,QUERY,'en',SOURCES,facts=facts(),context_provenance=True)
 assert len(client.calls)==2

def test_private_generation_keeps_original_full_context_contract(staged,sources):
 client=ScriptedClient("Click the 'Wizard' button.",'ITEM-X has a 17-month Helio Secure warranty. Claims are in the app under My Orders.')
 result=document_reply(client,'Does ITEM-X have Helio Secure? How do I claim?','en',sources,facts=build(staged,sources),private=True,context_provenance=True)
 assert 'repair_mode' not in result and 'question' in client.calls[1][0]
 assert client.calls[0][1]['cache'] is False and client.calls[1][1]['cache'] is False
