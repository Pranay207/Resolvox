import pytest
from src.document_answers import _customer_ownership_echo

@pytest.mark.parametrize('question,answer',[
    ('My order for Aster headphones arrived yesterday; when can I return it?','My order for Aster headphones arrived yesterday, so I have a return window.'),
    ('Mera order Aster Blue Speaker parso aaya, return kab tak?','Mera order Aster Blue Speaker parso aaya aur main return kar sakti hoon.'),
    ('I bought an Aster Blue Speaker yesterday. What warranty applies?','I bought an Aster Blue Speaker yesterday, so the warranty applies.'),
    ('मेरा ऑर्डर कल आया, अब क्या करूँ?','मेरा ऑर्डर कल आया, मैं इसे वापस कर सकती हूँ।')])
def test_customer_story_cannot_become_the_assistants_own_purchase(question,answer):assert _customer_ownership_echo(question,answer)

@pytest.mark.parametrize('answer',[
    'Your order for Aster headphones follows the stated window.',
    'Based on your report, the standard window starts at delivery.',
    'You said, "My order for Aster headphones arrived yesterday". The window starts at delivery.',
    'I cannot verify your order from this question alone.'])
def test_customer_attribution_and_assistant_uncertainty_are_preserved(answer):
    assert not _customer_ownership_echo('My order for Aster headphones arrived yesterday; when can I return it?',answer)
