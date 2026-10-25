"""Offline fake-client checks for the normal Hinglish schema proposal."""
import copy
import json
import re
import pytest
from src.document_answers import CONTEXT_SCHEMA, SCHEMA, _generation_schema, document_reply


def sources():
    return [{'id':'REF-test','text':'Credit card refunds take 5 to 7 business days.',
             'status':'current','doc_type':'policy'}]


def response(answer, covered=True, needs=False):
    return {'answer':answer,'covered':covered,'needs_clarification':needs}


class FakeClient:
    last_metrics={}
    def __init__(self, answers):
        self.answers=list(answers)
        self.calls=[]
    def complete(self,system,payload,**kwargs):
        self.calls.append({'system':system,'payload':json.loads(payload),'kwargs':copy.deepcopy(kwargs)})
        answer=self.answers[min(len(self.calls)-1,len(self.answers)-1)]
        return json.dumps(answer,ensure_ascii=False)


def pattern():
    return _generation_schema('hi-en',True)['properties']['answer']['pattern']


@pytest.mark.parametrize('language',['en','hi'])
def test_other_normal_languages_keep_exact_existing_schema(language):
    assert _generation_schema(language,True) is CONTEXT_SCHEMA
    assert 'pattern' not in _generation_schema(language,True)['properties']['answer']


@pytest.mark.parametrize('language',['en','hi','hi-en'])
def test_strict_compatibility_api_remains_unchanged(language):
    assert _generation_schema(language,False) is SCHEMA


def test_schema_is_copied_and_preserves_fields_flags_and_lengths():
    previous=copy.deepcopy(CONTEXT_SCHEMA)
    schema=_generation_schema('hi-en',True)
    assert schema is not CONTEXT_SCHEMA
    assert schema['required']==previous['required']
    assert schema['additionalProperties'] is False
    assert schema['properties']['covered']=={'type':'boolean'}
    assert schema['properties']['needs_clarification']=={'type':'boolean'}
    assert schema['properties']['answer']['minLength']==1
    assert schema['properties']['answer']['maxLength']==1800
    del schema['properties']['answer']['pattern']
    assert schema==previous==CONTEXT_SCHEMA


@pytest.mark.parametrize('text',[
    'Refund 5 to 7 business days mein aa sakta hai.',
    'SKU ELE-0012 par Assured hai.',
    'Aapka charge \u20b979 hai.',
    'Yeh Zo\u00eb brand ka item hai.',
    'Aapki supplied date 17 October 2026 hai.',
])
def test_pattern_accepts_latin_hinglish_product_codes_dates_and_unicode_symbols(text):
    assert re.fullmatch(pattern(),text)


@pytest.mark.parametrize('text',[
    '\u0930\u093f\u092b\u0902\u0921 5 \u0938\u0947 7 \u0926\u093f\u0928 \u092e\u0947\u0902 \u0906\u090f\u0917\u093e',
    'Refund \u0939\u0948',
    '\u0967\u0968 din hai',
    'Naam "quoted" hai.',
    r'Escaped \u0930 text hai.',
    'path\\name hai',
    'Line\nnext hai',
    'Tab\there hai',
    'Control '+chr(0),
    'DEL '+chr(127),
    '',
    'a'*1801,
])
def test_pattern_blocks_devanagari_json_delimiters_escapes_controls_and_bad_lengths(text):
    assert re.fullmatch(pattern(),text) is None


def test_pattern_keeps_exact_existing_length_boundaries():
    assert re.fullmatch(pattern(),'a')
    assert re.fullmatch(pattern(),'a'*1800)


def test_only_normal_hinglish_format_changes_the_existing_schema_cache_input():
    original=json.dumps(CONTEXT_SCHEMA,sort_keys=True)
    assert json.dumps(_generation_schema('en',True),sort_keys=True)==original
    assert json.dumps(_generation_schema('hi',True),sort_keys=True)==original
    assert json.dumps(_generation_schema('hi-en',True),sort_keys=True)!=original


def test_document_reply_forwards_pattern_without_changing_boolean_contract():
    value=response('Card refund 5 to 7 business days mein aa sakta hai.')
    client=FakeClient([value])
    result=document_reply(client,'Card refund kab milega?','hi-en',sources(),context_provenance=True)
    schema=client.calls[0]['kwargs']['schema']
    assert schema['properties']['answer']['pattern']==pattern()
    assert result['decision']=='answer'
    assert result['model_flags']=={'covered':True,'needs_clarification':False}
    assert result['generation_attempts']==1


def test_host_still_repairs_provider_that_ignores_script_pattern_once():
    client=FakeClient([
        response('\u0930\u093f\u092b\u0902\u0921 5 to 7 business days \u092e\u0947\u0902 \u0906\u090f\u0917\u093e'),
        response('Refund 5 to 7 business days mein aa sakta hai.'),
    ])
    result=document_reply(client,'Refund kab milega?','hi-en',sources(),context_provenance=True)
    assert result['generation_attempts']==2
    assert result['repair_errors']==['wrong_output_language']
    assert len(client.calls)==2
    assert client.calls[0]['kwargs']['cache'] is True
    assert client.calls[1]['kwargs']['cache'] is False
    assert client.calls[0]['kwargs']['schema']==client.calls[1]['kwargs']['schema']


@pytest.mark.parametrize('answer,error',[
    ('Maine aapka refund kar diya hai.','unsupported_action'),
    ('Refund 999 business days mein aayega.','unsupported_number'),
    ('Refund 5 to 7 din mein aayega.','unsupported_quantity_unit'),
    ('Email customer@example.com hai.','private_identifier'),
    ('The refund takes 5 to 7 business days.','wrong_output_language'),
])
def test_script_constraint_does_not_bypass_existing_guards_or_add_repairs(answer,error):
    client=FakeClient([response(answer)])
    with pytest.raises(ValueError,match='document_generation_failed:'+error):
        document_reply(client,'Card refund kab milega?','hi-en',sources(),context_provenance=True)
    assert len(client.calls)==2


def test_bad_science_days_and_unattributed_operation_remain_rejected():
    client=FakeClient([response('Refund 5 to 7 vigyan din mein aayega; refund ho gaya hai.')])
    with pytest.raises(ValueError,match='document_generation_failed:unsupported_action'):
        document_reply(client,'Card refund kab milega?','hi-en',sources(),context_provenance=True)
    assert len(client.calls)==2
