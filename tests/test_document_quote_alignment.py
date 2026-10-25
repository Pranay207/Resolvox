import json
import pytest
from src.document_answers import document_reply

class Client:
    def __init__(self,quote,answer):self.quote=quote;self.answer=answer
    def complete(self,*args,**kwargs):
        return json.dumps({'answer':self.answer,'decision':'answer','citations':[{'id':'D-1','quote':self.quote}]})

def test_format_only_quote_is_restored_to_the_actual_source_span():
    source={'id':'D-1','text':'Report within **48 hours** of delivery, with photos.'}
    out=document_reply(Client('Report within 48 hours of delivery, with photos.','Report within 48 hours of delivery, with photos.'),'What should I do?','en',[source])
    assert out['citations'][0]['quote']==source['text']

@pytest.mark.parametrize('quote,answer',[
    ('Report within 72 hours of delivery, with photos.','Report within 72 hours of delivery.'),
    ('Report within 48 business days of delivery, with photos.','Report within 48 business days of delivery.'),
    ('No photos are needed within 48 hours.','No photos are needed within 48 hours.'),
])
def test_alignment_never_changes_words_numbers_units_or_conditions(quote,answer):
    source={'id':'D-1','text':'Report within **48 hours** of delivery, with photos.'}
    with pytest.raises(ValueError,match='unsupported_citation'):
        document_reply(Client(quote,answer),'What should I do?','en',[source])


def test_an_uncited_resolution_cannot_be_supported_by_only_a_reporting_quote():
    sources=[{'id':'D-1','text':'Report damage within 48 hours, with photos.'},
             {'id':'D-2','text':'After verification a free replacement or full refund includes delivery fees.'}]
    with pytest.raises(ValueError,match='uncited_policy_claim'):
        document_reply(Client(sources[0]['text'],'Report damage within 48 hours. After verification, a free replacement or full refund includes delivery fees.'),'What do I do?','en',sources)
