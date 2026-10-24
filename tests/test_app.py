"""Streamlit integration test: launch, text reply, and proof-safe rendered history."""
from streamlit.testing.v1 import AppTest

def test_text_ui_and_source_panel():
    app=AppTest.from_file('app.py',default_timeout=40).run()
    assert not app.exception
    app.toggle[0].set_value(False).run()
    app.chat_input[0].set_value('UPI refund timing please').run()
    assert not app.exception
    assert any('1 to 3' in x.value for x in app.markdown)
    assert len(app.expander)>=1
