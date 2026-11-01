"""Generic context focusing preserves source lineage and bound dependencies."""
from types import SimpleNamespace
from src.source_selection import focus_policy_context


def row(ident, kind='policy', value='17'):
    return {'id': ident, 'doc_type':kind, 'text':'Actual source value '+value}


def hit(ident, rank=None, role='direct'):
    return {'chunk':SimpleNamespace(id=ident),'retrieval_role':role,'direct_rank':rank}


def test_simple_question_drops_weak_unrelated_matches_without_editing_sources():
    selected=[row(str(i)) for i in range(1,9)]
    candidates=[hit(str(i),i) for i in range(1,9)]
    out=focus_policy_context(selected,candidates,query='source value')
    assert [r['id'] for r in out]==['1','2']
    assert out[0] is selected[0] and selected[0]['text']=='Actual source value 17'
    assert len(selected)==8


def test_dependencies_catalog_and_supplied_route_hints_are_retained():
    selected=[row('1'),row('2'),row('3'),row('hint'),row('dep'),row('product','catalog'),row('calendar','meta')]
    candidates=[hit('1',1),hit('2',2),hit('3',role='dependency'),hit('hint',9),hit('dep',role='dependency')]
    out=focus_policy_context(selected,candidates,['hint','invented-id'],query='source value')
    assert out==selected
    assert all(r['id']!='invented-id' for r in out)


def test_compound_questions_expand_the_direct_context():
    selected=[row(str(i)) for i in range(1,9)]
    candidates=[hit(str(i),i) for i in range(1,9)]
    assert len(focus_policy_context(selected,candidates,query='source value',facet_count=4))==5


def test_unknown_candidate_metadata_preserves_all_actual_context():
    selected=[row('changed-id',value='93'),row('b')]
    assert focus_policy_context(selected,[{'chunk':SimpleNamespace(id='changed-id')}]) is selected
    assert focus_policy_context(selected,[]) is selected


def test_arbitrary_changed_source_values_are_not_replaced_by_policy_constants():
    selected=[row('unseen-source',value='93')]
    assert focus_policy_context(selected,[hit('unseen-source',1)])==selected


def test_weak_literal_overlap_keeps_broad_recall_for_unfamiliar_wording():
    selected=[row(str(i)) for i in range(1,9)]
    candidates=[hit(str(i),i) for i in range(1,9)]
    assert focus_policy_context(selected,candidates,query='Can another courier have another go?') is selected
