import pytest
from src.document_answers import document_reply
from src.generation_diagnostics import GenerationValidationError
from test_customer_condition_premises import Client,SOURCES,QUERY,facts

@pytest.mark.parametrize('answer',[
 'Your seal is broken. This does not meet the ordinary return condition.',
 'The seal is intact. This does not meet the ordinary return condition.',
 'आपके कहने के अनुसार सील नहीं है। इसलिए आम वापसी की शर्त पूरी नहीं होती।',
])
def test_a_report_of_opening_does_not_establish_seal_state(answer):
 client=Client('Your product is unopened.',answer)
 with pytest.raises(GenerationValidationError):document_reply(client,QUERY,'hi' if 'सील' in answer else 'en',SOURCES,facts=facts(),context_provenance=True)

def test_policy_seal_requirement_remains_distinct_from_customer_state():
 client=Client('Your product is unopened.','You reported opening it, which does not meet the unopened condition. The seal must be intact.')
 result=document_reply(client,QUERY,'en',SOURCES,facts=facts(),context_provenance=True)
 assert result['answer'].endswith('The seal must be intact.')
 assert client.calls[1][1]['unreported_customer_attributes']==['seal_intact']

def test_an_explicit_customer_seal_report_can_be_repeated():
 question='I opened Aster Tint and broke the seal. Can I return it?'
 client=Client('Your product is unopened.','You reported opening the item and its seal is broken. This does not meet the ordinary return condition.')
 result=document_reply(client,question,'en',SOURCES,facts=facts(question),context_provenance=True)
 assert result['covered'] is True and client.calls[1][1]['unreported_customer_attributes']==[]
