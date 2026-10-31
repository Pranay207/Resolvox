import copy,json
import pytest
from test_refund_context_scope import context,Client
from src.refund_timeline import completed_refund_record_inputs
from src.document_answers import document_reply

def setup(query='When was my refund completed?'):
 return context(query=query,return_status='refunded',return_refund_completed_on='2026-10-17')

def test_record_view_supplies_actual_date_without_other_transaction_facts():
 facts,sources=setup();before=copy.deepcopy(facts);view=completed_refund_record_inputs('When was my refund completed?',facts,sources)
 assert view['facts']['verified_order']=={'return_refund_completed_on':'2026-10-17'} and facts==before
 assert all(s in sources for s in view['sources'])

@pytest.mark.parametrize('query',['When will my refund arrive?','When was my refund completed and what amount was paid?','When was the partial refund completed?'])
def test_other_facets_or_nonhistorical_questions_keep_full_context(query):
 facts,sources=setup(query)
 assert completed_refund_record_inputs(query,facts,sources) is None

def test_record_reading_uses_small_prompt_and_all_original_guards():
 facts,sources=setup();good='The verified order record shows refund completed on 17 October 2026.';client=Client(good)
 result=document_reply(client,'When was my refund completed?','en',sources,facts=facts,private=True,context_provenance=True)
 assert result['answer']==good and result['repair_mode']=='verified_completion_record_reading'
 assert client.calls[0][1]['deterministic_facts']['verified_order']=={'return_refund_completed_on':'2026-10-17'}
 assert client.calls[0][2]['cache'] is False and client.calls[0][2]['max_tokens']==200
 bad=good.replace('17 October','18 October')
 with pytest.raises(ValueError):document_reply(Client(bad,bad),'When was my refund completed?','en',sources,facts=facts,private=True,context_provenance=True)

def test_assistant_action_is_still_rejected_even_with_correct_record_date():
 facts,sources=setup();bad='The record lists refund completed on 17 October 2026. I have issued your refund.'
 with pytest.raises(ValueError):document_reply(Client(bad,bad),'When was my refund completed?','en',sources,facts=facts,private=True,context_provenance=True)
