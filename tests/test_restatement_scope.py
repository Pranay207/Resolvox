from src.document_answers import _restatement_scope
WARRANTY=[{'id':'novel-w','doc_type':'policy','text':'The warranty applies from delivery. Claims are in the app under Cases.'}]
REFUND=[{'id':'novel-r','doc_type':'policy','text':'For these refunds, the customer chooses the documented payment method.'}]
def test_a_compound_request_cannot_drop_the_refund_topic():
 allowed,proof=_restatement_scope('How do I claim the warranty? How do refunds work?',WARRANTY)
 assert not allowed and proof['requested_topics']==['refund','warranty']
def test_background_return_does_not_replace_the_actual_refund_question():
 allowed,proof=_restatement_scope('I returned the item. How do I get my money back?',REFUND)
 assert allowed and proof['requested_topics']==['refund']
def test_statements_without_question_marks_still_keep_all_requested_topics():
 allowed,_=_restatement_scope('Tell me the warranty and refund policies.',WARRANTY)
 assert not allowed
def test_related_warranty_location_question_keeps_its_actual_source_topic():
 allowed,_=_restatement_scope('Does this have a warranty? How do I claim?',WARRANTY)
 assert allowed
