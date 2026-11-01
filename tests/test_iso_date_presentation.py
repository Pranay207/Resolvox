import pytest
from src.answer_polarity import normalize_iso_date_punctuation

@pytest.mark.parametrize('dash',['\u2010','\u2011','\u2012','\u2013','\u2014','\u2015'])
def test_iso_punctuation_changes_without_changing_date_values(dash):
 value={'answer':f'Deadline 2031{dash}04{dash}19.','covered':True,'needs_clarification':False}
 out,edit=normalize_iso_date_punctuation(value)
 assert out['answer']=='Deadline 2031-04-19.' and value['answer']!=out['answer']
 assert out['covered']==value['covered'] and edit['date_values_unchanged']

@pytest.mark.parametrize('text',['2031–02–31','19–04–2031','3–5 business days','No date provided.'])
def test_other_quantities_and_invalid_dates_are_unchanged(text):
 value={'answer':text};out,edit=normalize_iso_date_punctuation(value)
 assert out==value and edit is None
