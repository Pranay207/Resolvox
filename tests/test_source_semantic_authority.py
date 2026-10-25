"""Authority is source metadata, selected per brand attribute, never answer text."""
import copy
import hashlib
import json
import pytest
from src.source_semantics import derive_source_constraints,validate_source_semantics


def source(ident,text,kind='policy',**metadata):
    return dict(id=ident,text=text,doc_type=kind,status='current',effective_from='2025-01-01',**metadata)


def brand_constraint(sources):
    return next(x for x in derive_source_constraints(sources) if x['kind']=='brand_warranty_attributes')

@pytest.mark.parametrize('lower',['agent_guide','help','faq','marketing'])
def test_current_policy_start_outranks_conflicting_lower_source(lower):
    docs=[source('policy-a','The brand warranty starts from the invoice date.'),
          source('other-b','The brand warranty starts from the delivery date.',lower)]
    assert brand_constraint(docs)['documented_start_events']==['invoice']
    assert brand_constraint(docs)['governing_start_source_ids']==['policy-a']
    validate_source_semantics('The brand warranty starts from invoice.',docs)
    with pytest.raises(ValueError,match='unsupported_brand_warranty_start'):
        validate_source_semantics('The brand warranty starts from delivery.',docs)

@pytest.mark.parametrize('lower',['agent_guide','help','faq','marketing'])
def test_current_policy_coverage_outranks_conflicting_lower_source(lower):
    docs=[source('policy-a','The brand warranty covers material defects.'),
          source('other-b','The brand warranty covers motor defects.',lower)]
    assert brand_constraint(docs)['governing_coverage_source_ids']==['policy-a']
    validate_source_semantics('The brand warranty covers material defects.',docs)
    with pytest.raises(ValueError,match='unsupported_brand_warranty_coverage'):
        validate_source_semantics('The brand warranty covers motor defects.',docs)


def test_each_attribute_selects_its_own_best_actual_source():
    docs=[source('start','The brand warranty starts from invoice.'),
          source('coverage','The brand warranty covers workmanship faults.','help')]
    item=brand_constraint(docs)
    assert item['governing_start_source_ids']==['start']
    assert item['governing_coverage_source_ids']==['coverage']
    validate_source_semantics('The brand warranty starts from invoice. The brand warranty covers workmanship faults.',docs)


def test_store_attribute_does_not_become_higher_priority_brand_attribute():
    docs=[source('store','Marked items carry an additional store warranty from delivery covering battery defects in addition to any brand warranty.'),
          source('brand','The brand warranty starts from invoice. The brand warranty covers motor defects.','help')]
    item=brand_constraint(docs)
    assert item['governing_start_source_ids']==['brand']
    assert item['governing_coverage_source_ids']==['brand']
    validate_source_semantics('The brand warranty starts from invoice.',docs)
    with pytest.raises(ValueError,match='unsupported_brand_warranty_start'):
        validate_source_semantics('The brand warranty starts from delivery.',docs)


def test_same_priority_conflicting_start_events_authorize_no_start_claim():
    docs=[source('a','The brand warranty starts from invoice.'),source('b','The brand warranty starts from delivery.')]
    item=brand_constraint(docs)
    assert item['start_authority_conflict'] is True
    assert item['documented_start_events']==[]
    assert set(item['governing_start_source_ids'])=={'a','b'}
    for value in ['invoice','delivery']:
        with pytest.raises(ValueError,match='unsupported_brand_warranty_start'):
            validate_source_semantics('The brand warranty starts from '+value+'.',docs)
    validate_source_semantics('I cannot confirm the brand warranty start event from these conflicting sources.',docs)


def test_same_priority_agreement_remains_supported():
    docs=[source('a','The brand warranty starts from activation.'),source('b','The manufacturer warranty begins from activation.')]
    assert not brand_constraint(docs)['start_authority_conflict']
    validate_source_semantics('The brand warranty starts from activation.',docs)


def test_ambiguous_same_priority_positive_coverage_is_not_blindly_unioned():
    docs=[source('a','The brand warranty covers only battery defects.'),source('b','The brand warranty covers only motor defects.')]
    for scope in ['battery defects','motor defects','battery and motor defects']:
        with pytest.raises(ValueError,match='unsupported_brand_warranty_coverage'):
            validate_source_semantics('The brand warranty covers '+scope+'.',docs)


def test_common_supported_coverage_subset_survives_governing_sources():
    docs=[source('a','The brand warranty covers defects in materials and workmanship.'),source('b','The brand warranty covers material defects.')]
    validate_source_semantics('The brand warranty covers material defects.',docs)
    with pytest.raises(ValueError,match='unsupported_brand_warranty_coverage'):
        validate_source_semantics('The brand warranty covers workmanship defects.',docs)


def test_policy_explicit_coverage_exclusion_is_not_overridden_by_help():
    docs=[source('a','The brand warranty does not cover physical damage.'),source('b','The brand warranty covers physical damage.','help')]
    assert brand_constraint(docs)['prohibited_positive_coverages']==['physical damage']
    with pytest.raises(ValueError,match='unsupported_brand_warranty_coverage'):
        validate_source_semantics('The brand warranty covers physical damage.',docs)


def test_same_priority_positive_and_negative_coverage_conflict_rejects_claim():
    docs=[source('a','The brand warranty covers battery defects.'),source('b','The brand warranty does not cover battery defects.')]
    with pytest.raises(ValueError,match='unsupported_brand_warranty_coverage'):
        validate_source_semantics('The brand warranty covers battery defects.',docs)


def test_policy_explicit_start_denial_is_not_overridden_by_help():
    docs=[source('a','The brand warranty does not start from delivery.'),source('b','The brand warranty starts from delivery.','help')]
    assert brand_constraint(docs)['prohibited_start_events']==['delivery']
    with pytest.raises(ValueError,match='unsupported_brand_warranty_start'):
        validate_source_semantics('The brand warranty starts from delivery.',docs)

@pytest.mark.parametrize('field,value',[('status','superseded'),('effective_from','2038-01-01')])
def test_inactive_policy_cannot_override_actual_current_help(field,value):
    a=source('a','The brand warranty starts from invoice.');a[field]=value
    docs=[a,source('b','The brand warranty starts from delivery.','help')]
    assert brand_constraint(docs)['governing_start_source_ids']==['b']
    validate_source_semantics('The brand warranty starts from delivery.',docs)


def test_inactive_only_source_does_not_authorize_a_current_attribute():
    a=source('a','The brand warranty starts from invoice.');a['status']='superseded'
    assert brand_constraint([a])['documented_start_events']==[]
    with pytest.raises(ValueError,match='unsupported_brand_warranty_start'):
        validate_source_semantics('The brand warranty starts from invoice.',[a])


def test_missing_authority_metadata_cannot_outrank_current_policy():
    a={'id':'unknown','text':'The brand warranty starts from delivery.'}
    docs=[source('p','The brand warranty starts from invoice.'),a]
    assert brand_constraint(docs)['governing_start_source_ids']==['p']
    with pytest.raises(ValueError,match='unsupported_brand_warranty_start'):
        validate_source_semantics('The brand warranty starts from delivery.',docs)


def test_actual_doc_type_mutation_changes_governing_event_and_provenance():
    a=source('a','The brand warranty starts from invoice.');b=source('b','The brand warranty starts from delivery.','help')
    first=brand_constraint([a,b]);a['doc_type']='faq';second=brand_constraint([a,b])
    assert first['documented_start_events']==['invoice'] and second['documented_start_events']==['delivery']
    assert first['source_sha256']==second['source_sha256']
    assert first['source_provenance_sha256']['a']!=second['source_provenance_sha256']['a']
    assert second['source_authority']['a']['doc_type']=='faq'

@pytest.mark.parametrize('field,value',[('doc_type','help'),('status','superseded'),('effective_from','2025-02-01'),('version','9.1'),('file','new.md')])
def test_authority_provenance_binds_actual_metadata_without_altering_text_hash(field,value):
    a=source('a','The brand warranty starts from invoice.');first=brand_constraint([a]);a[field]=value;second=brand_constraint([a])
    assert first['source_sha256']==second['source_sha256']
    assert first['source_provenance_sha256']['a']!=second['source_provenance_sha256']['a']
    assert second['source_sha256']['a']==hashlib.sha256(a['text'].encode()).hexdigest()

@pytest.mark.parametrize('field,value',[('doc_type',{}),('status',True),('effective_from','not-a-date')])
def test_invalid_authority_metadata_fails_closed(field,value):
    a=source('a','The brand warranty starts from invoice.');a[field]=value
    with pytest.raises(ValueError,match='invalid_semantic_source_authority'):
        derive_source_constraints([a])


def test_duplicate_id_cannot_mix_source_authority_or_text():
    a=source('same','The brand warranty starts from invoice.');b=source('same','The brand warranty starts from delivery.','help')
    with pytest.raises(ValueError,match='conflicting_semantic_source_identity'):
        derive_source_constraints([a,b])


def test_catalog_brand_duration_remains_bound_to_catalog_and_linking_policy():
    from src.warranty_durations import warranty_duration_context
    docs=[source('catalog-link','The brand warranty period is listed in the warranty_months column of the product catalog.'),
          source('help-start','The brand warranty starts from delivery.','help'),
          {'id':'catalog-row','text':json.dumps({'sku':'ITEM-Q','brand':'Aster','warranty_months':'23','assured':'True'}),'doc_type':'catalog','status':'current'}]
    result=warranty_duration_context('How long is the brand warranty?',docs,reference_date='2026-10-20')
    record=result['warranty_duration']['brand']
    assert record['duration_months']==23
    assert set(record['source_ids'])=={'catalog-row','catalog-link'}
    assert brand_constraint(docs)['governing_start_source_ids']==['help-start']


def catalog(brand,key='selected-catalog'):
    return {'id':key,'text':json.dumps({'sku':'ITEM-'+key,'brand':brand}),
            'doc_type':'catalog','status':'current'}


def test_named_other_brand_policy_cannot_govern_selected_catalog_brand():
    docs=[source('other-policy','Orion brand warranty starts from invoice.'),
          source('selected-help','Aster brand warranty starts from delivery.','help'),catalog('Aster')]
    item=brand_constraint(docs)
    assert item['documented_start_events']==['delivery']
    assert item['governing_start_source_ids']==['selected-help']


def test_named_brand_attribute_requires_matching_catalog_scope():
    docs=[source('specific','Aster brand warranty starts from activation.')]
    assert brand_constraint(docs)['documented_start_events']==[]
    assert brand_constraint(docs+[catalog('Aster')])['documented_start_events']==['activation']
    assert brand_constraint(docs+[catalog('Orion')])['documented_start_events']==[]


def test_ambiguous_catalog_brands_do_not_bind_a_named_attribute():
    docs=[source('specific','Aster brand warranty starts from activation.'),catalog('Aster','a'),catalog('Orion','b')]
    assert brand_constraint(docs)['documented_start_events']==[]


def test_generic_brand_policy_remains_applicable_alongside_named_catalog():
    docs=[source('generic','The brand warranty starts from invoice.'),catalog('Aster')]
    assert brand_constraint(docs)['documented_start_events']==['invoice']


def test_source_iterable_is_materialized_once_without_losing_authority():
    docs=[source('p','The brand warranty starts from invoice.'),
          source('h','The brand warranty starts from delivery.','help')]
    assert brand_constraint(iter(docs))['documented_start_events']==['invoice']


@pytest.mark.parametrize('kind',[None,'','unrecognized_external_type'])
def test_unrecognized_or_missing_authority_cannot_alone_authorize_attribute(kind):
    row={'id':'external','text':'The brand warranty starts from delivery.'}
    if kind is not None:row['doc_type']=kind
    constraints=brand_constraint([row])
    assert constraints['documented_start_events']==[]
    with pytest.raises(ValueError,match='unsupported_brand_warranty_start'):
        validate_source_semantics('The brand warranty starts from delivery.',[row])
