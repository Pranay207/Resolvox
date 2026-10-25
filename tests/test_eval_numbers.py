from src.evals import facts_present


def test_spoken_and_written_numbers_are_equivalent():
    assert facts_present('The courier makes up to three attempts.','3')[1]==[]
    assert facts_present('It takes two hours.','2 hours')[1]==[]


def test_number_normalization_preserves_value_boundaries():
    assert facts_present('The courier makes thirty attempts.','3')[1]==['3']
    assert facts_present('It takes five business days.','3')[1]==['3']
