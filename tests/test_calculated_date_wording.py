import pytest
from src.grounding import _completed_action

@pytest.mark.parametrize('label',['तारीख','अंतिम तारीख','राशि'])
def test_a_calculation_label_is_not_a_performed_business_action(label):
 text=f'रिटर्न के लिए पात्रता है और गणना की गई {label} 13 November 2031 है।'
 assert not _completed_action(text)
 assert _completed_action(text+' मैंने रिफंड जारी कर दिया है।')
 assert _completed_action(text+' टिकट बना दिया गया है।')
