"""A fee-only relative clause must not detach a membership exclusion."""
import pytest
from src.source_semantics import validate_source_semantics
from test_source_semantics import credit_source

@pytest.mark.parametrize('label',['Orchid Club','Aster Elite'])
@pytest.mark.parametrize('relative',['who pay no express fee','who do not pay the express fee','who are not charged an express fee'])
def test_relative_fee_clause_preserves_the_named_no_credit_subject(label,relative):
 answer=f'The Express fee you paid is credited. {label} members, {relative}, do not receive any credit.'
 validate_source_semantics(answer,[credit_source(label)])

@pytest.mark.parametrize('tail',[
 'Orchid Club members, who pay no express fee, receive credit.',
 'Other Club members, who pay no express fee, get no credit.',
 'Orchid Club members, who pay no express fee, receive credit. Other members get no credit.',
])
def test_fee_negation_wrong_group_and_unrelated_denial_do_not_prove_exclusion(tail):
 with pytest.raises(ValueError,match='source_credit_membership_exclusion_missing'):
  validate_source_semantics('The Express fee you paid is credited. '+tail,[credit_source()])

@pytest.mark.parametrize('label',['Orchid Club','Aster Elite'])
@pytest.mark.parametrize('relative',['',' who does not pay the express fee',' who pays no express fee'])
def test_same_person_conditional_membership_exclusion_survives_comma(label,relative):
 answer=f'The Express fee you paid is credited. If you are a {label} member{relative}, you do not receive any credit.'
 validate_source_semantics(answer,[credit_source(label)])

@pytest.mark.parametrize('tail',[
 'If you are a Other Club member, you do not receive any credit.',
 'If you are a Orchid Club member who does not pay the fee, you receive credit.',
 'If you are a Orchid Club member, other customers get no credit.',
])
def test_conditional_fee_negation_or_another_group_cannot_prove_exclusion(tail):
 with pytest.raises(ValueError,match='source_credit_membership_exclusion_missing'):
  validate_source_semantics('The Express fee you paid is credited. '+tail,[credit_source()])
