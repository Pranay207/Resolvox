import json
import pytest
from src.document_answers import document_reply

@pytest.mark.parametrize('supported',[True,False])
def test_unknown_personal_date_does_not_force_or_flip_model_source_support(supported):
 sources=[{'id':'ROWS-X','doc_type':'policy','status':'current','effective_from':'2020-01-01',
           'text':'The return window starts at delivery.\n| Garments and bags | 12 days | cloth_x |'},
          {'id':'SALE-Y','doc_type':'policy','status':'current','effective_from':'2020-01-01',
           'text':'Garments and bags from orders placed between 03 April and 11 April 2026 can be returned within 24 days of delivery.'}]
 facts={'reference_date':'2026-10-20','return_policy':{'category':'cloth_x','category_label':'Garments and bags',
        'window_calendar_days':12,'source_ids':['ROWS-X'],'selection':'unresolved_placement_window',
        'placement_date_unavailable':True,'placement_exception':{'placed_from':'2026-04-03','placed_through':'2026-04-11',
        'window_calendar_days':24,'source_ids':['SALE-Y']}}}
 class Client:
  def complete(self,system,user,**options):
   assert 'has_document_support' in options['schema']['required']
   # Preserve the source's date spelling; this test isolates boolean support mapping.
   text=('The standard window is 12 days from delivery. If the order was placed between 03 April and 11 April 2026, the window is 24 days from delivery.' if supported else 'I cannot confirm that from the supplied documents.')
   return json.dumps({'answer':text,'has_document_support':supported,'needs_clarification':False})
 out=document_reply(Client(),'What is the general return window?','en',sources,facts=facts,context_provenance=True)
 assert out['covered'] is supported
 assert out['window_support_contract']['original_model_flags']['has_document_support'] is supported
