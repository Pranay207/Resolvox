"""Source-bound business handover explanations, separate from tool outcomes."""
from datetime import date
import copy
import hashlib
import json
import re

from .config import REFERENCE_DATE
from .document_answers import document_reply
from .document_context import build_context
from .source_inputs import source_input_clarification
from .escalation_rules import derive_escalation, source_fingerprint

_BUSINESS_INTENTS=frozenset({'damage','refund','delivery','repeat'})
_PROTECTED_INTENTS=frozenset({'verification','privacy','safety','fraud','legal','human','unclear_audio','greeting'})


def _effective(source):
    if source.get('status')!='current':return False
    try:return date.fromisoformat(source['effective_from'])<=REFERENCE_DATE
    except (KeyError,TypeError,ValueError):return False


def business_sources(kb,pool):
    """Read actual current sources, never legacy plan IDs or authored strings."""
    actual={}
    for chunk in kb.chunks.values():
        row=chunk.public()
        if row.get('doc_type') in {'policy','agent_guide','meta'} and _effective(row):actual[row['id']]=row
    for row in pool:
        if row.get('doc_type')=='catalog' and row.get('status')=='current':actual.setdefault(row['id'],row)
    return copy.deepcopy(list(actual.values()))


def _source_digest(source):
    return hashlib.sha256(json.dumps(source,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def resolve_business_escalation(query,intent,plan_intent,legacy_escalate,kb,pool,data,*,verified_order=None,public_context=None):
    if plan_intent in _PROTECTED_INTENTS:return None
    if intent not in _BUSINESS_INTENTS and plan_intent!='repeat' and not legacy_escalate:return None
    actual=business_sources(kb,pool)
    result=derive_escalation(query,actual,data,verified_order=verified_order,
                             public_context=public_context,reference_date=REFERENCE_DATE)
    if not isinstance(result,dict) or not isinstance(result.get('decisions'),list):raise ValueError('invalid_business_escalation_derivation')
    decisions=result['decisions']
    selected_sources=result.get('selected_sources',actual)
    by_id={row['id']:row for row in selected_sources if isinstance(row,dict) and isinstance(row.get('id'),str)}
    if len(by_id)!=len(selected_sources):raise ValueError('invalid_business_escalation_sources')
    original_by_id={row['id']:row for row in actual}
    for sid,row in by_id.items():
        if sid in original_by_id:
            if source_fingerprint(row)!=source_fingerprint(original_by_id[sid]):raise ValueError('changed_business_escalation_sources')
        elif row.get('file')=='data/holidays.csv' and row.get('doc_type')=='catalog':
            expected_holidays=sorted({date.fromisoformat(str(value)[:10]).isoformat() for value in data.holidays})
            if json.loads(row['text'])!={'warehouse_holidays':expected_holidays}:raise ValueError('changed_business_calendar_input')
        else:raise ValueError('unbound_business_escalation_source')
    for item in decisions:
        if not isinstance(item,dict) or (item.get('applicable') is not None and type(item.get('applicable')) is not bool):raise ValueError('invalid_business_escalation_derivation')
        ids=item.get('source_ids',[])
        if not isinstance(ids,list) or any(not isinstance(sid,str) or sid not in by_id for sid in ids):raise ValueError('unbound_business_escalation_derivation')
        if item.get('applicable') is True and (not ids or item.get('binding_status')!='bound'):raise ValueError('unbound_business_escalation_derivation')
        if item.get('binding_status')=='bound':
            expected={sid:source_fingerprint(by_id[sid]) for sid in ids}
            if item.get('source_sha256')!=expected:raise ValueError('changed_business_escalation_sources')
    reason=result.get('recommended_reason')
    chosen=[item for item in decisions if item.get('reason')==reason and item.get('applicable') is True]
    if reason and len(chosen)!=1:raise ValueError('unbound_business_escalation_recommendation')
    if not chosen:
        unresolved=any(item.get('applicable') is None and item.get('binding_status') in {'unbound','ambiguous'} for item in decisions)
        # Missing customer input is left to ordinary source-based clarification;
        # missing/conflicting policy cannot authorize an automatic action.
        return {'state':'unresolved' if unresolved else 'ordinary','decisions':decisions}
    selected=chosen[0]
    # Retain selected search policy/context as well as the actual operational
    # sources used by derivation; never replace a source with a plan summary.
    explanation={sid:by_id[sid] for sid in selected['source_ids']}
    original={row['id']:row for row in actual}
    extra_topic = re.search(r'warrant|refund|return|cancel|fees?|delivery\s+(?:time|date)|वारंटी|रिफंड|रिटर्न|वापस|कैंसिल|शुल्क', query, re.I)
    if reason == 'refund_overdue':
        extra_topic = re.search(r'warrant|cancel|fees?|pick[ -]?up|quality\s+check|\bQC\b|return.{0,20}(?:window|eligib|deadline)|delivery\s+(?:time|date)|वारंटी|कैंसिल|शुल्क|पिकअप|गुणवत्ता', query, re.I)
    if reason in {'high_value_damage', 'refund_overdue', 'repeat_contact'} and not extra_topic:
        # Keep the complete governing policy files, selected workflow and calendar.
        # Unrelated retrieval branches must not overflow or redirect this explanation.
        policy_files = {row.get('file') for row in explanation.values()
                        if row.get('doc_type') == 'policy' and row.get('file')}
        for row in actual:
            if row.get('doc_type') == 'policy' and row.get('file') in policy_files:
                explanation.setdefault(row['id'], row)
    else:
        for row in pool:
            if row.get('id') in original and row.get('doc_type') in {'policy','meta','catalog'}:
                explanation.setdefault(row['id'],original[row['id']])
    return {'state':'escalate','reason':reason,'decision':selected,'decisions':decisions,
            'sources':list(explanation.values()),'source_sha256':{sid:_source_digest(row) for sid,row in explanation.items()}}


def business_explanation(client,query,language,route,data,*,verified_order=None,public_context=None):
    sources=route['sources']
    if route.get('source_sha256')!={row['id']:_source_digest(row) for row in sources}:raise ValueError('changed_business_explanation_sources')
    facts=build_context(query,sources,data,verified_order=verified_order,public_context=public_context)
    selected=route['decision']
    facts['operational_escalation']={key:copy.deepcopy(selected[key]) for key in ('reason','source_ids','source_sha256','facts','calculations','binding_status') if key in selected}
    generated=source_input_clarification(facts,sources,language)
    if generated is None:
        generated=document_reply(client,query,language,sources,facts=facts,
                                 private=bool(verified_order),context_provenance=True)
    return generated,facts


_TICKET={
    'en':{True:'A ticket has been created; a human colleague will contact you.',False:'The ticket could not be created. Please contact support directly.'},
    'hi':{True:'\u091f\u093f\u0915\u091f \u092c\u0928 \u0917\u092f\u093e \u0939\u0948; \u092e\u093e\u0928\u0935 \u0938\u0939\u092f\u094b\u0917\u0940 \u0938\u0902\u092a\u0930\u094d\u0915 \u0915\u0930\u0947\u0902\u0917\u0947\u0964',False:'\u091f\u093f\u0915\u091f \u0928\u0939\u0940\u0902 \u092c\u0928 \u0938\u0915\u093e\u0964 \u0915\u0943\u092a\u092f\u093e \u0938\u0940\u0927\u0947 \u0938\u092a\u094b\u0930\u094d\u091f \u0938\u0947 \u0938\u0902\u092a\u0930\u094d\u0915 \u0915\u0930\u0947\u0902\u0964'},
    'hi-en':{True:'Ticket create ho gaya; human colleague contact karenge.',False:'Ticket create nahi hua. Support ko directly contact karein.'},
}
_UNRESOLVED={
    'en':'I cannot confirm the applicable handover policy from the supplied evidence. Please contact support for review.',
    'hi':'\u0926\u093f\u090f \u0917\u090f \u092a\u094d\u0930\u092e\u093e\u0923 \u0938\u0947 \u0932\u093e\u0917\u0942 \u0939\u0948\u0902\u0921\u0913\u0935\u0930 \u0928\u0940\u0924\u093f \u0915\u0940 \u092a\u0941\u0937\u094d\u091f\u093f \u0928\u0939\u0940\u0902 \u0915\u0930 \u0938\u0915\u0924\u0940\u0964 \u0915\u0943\u092a\u092f\u093e \u0938\u092e\u0940\u0915\u094d\u0937\u093e \u0915\u0947 \u0932\u093f\u090f \u0938\u092a\u094b\u0930\u094d\u091f \u0938\u0947 \u0938\u0902\u092a\u0930\u094d\u0915 \u0915\u0930\u0947\u0902\u0964',
    'hi-en':'Diye gaye evidence se applicable handover policy confirm nahi kar sakti. Review ke liye support se contact karein.',
}


def _spoken(text):
    return text.encode('ascii').decode('unicode_escape') if chr(92)+'u' in text else text


def ticket_outcome(ticket,language):
    if not isinstance(ticket,dict) or type(ticket.get('created')) is not bool:raise ValueError('invalid_ticket_outcome')
    return _spoken(_TICKET[language][ticket['created']])


def unresolved_business(language):return _spoken(_UNRESOLVED[language])
