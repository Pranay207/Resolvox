"""Typed quantities follow safe nested fact records and preserve units."""
import pytest
from src.grounding import _fact_quantities, validate_generated


def test_nested_catalog_numeric_string_is_typed():
    assert ('17', 'month') in _fact_quantities({'catalog': [{'warranty_months': '17'}]})


def test_recursive_mixed_collections():
    facts = {'rows': ({'amount_inr': '395'}, [{'maximum_business_days': 9}]),
             'return_policy': {'window_calendar_days': 23}}
    assert {('395','money'),('9','business_day'),('23','calendar_day')} <= _fact_quantities(facts)


@pytest.mark.parametrize('value', [True, False, '17 months', 'unknown', '', None])
def test_untyped_or_invalid_values_cannot_authorize_quantities(value):
    assert not _fact_quantities({'rows': [{'warranty_months': value}]})


def test_untyped_scalar_in_list_is_not_inferred():
    assert not _fact_quantities({'catalog': [17, '17', True]})


def test_real_catalog_warranty_unit_supported_but_other_unit_rejected():
    source = {'id': 'product', 'text': 'This catalog item has a warranty.', 'status': 'current'}
    value = {'covered': True, 'answer': 'The brand warranty is 17 months.',
             'citations': [{'id':'product','quote':source['text']}]}
    facts = {'catalog':[{'warranty_months':'17'}]}
    assert validate_generated(value, [source], facts=facts)[0] == value['answer']
    value['answer'] = 'The refund takes 17 business days.'
    with pytest.raises(ValueError, match='unsupported_quantity_unit'):
        validate_generated(value, [source], facts=facts)
