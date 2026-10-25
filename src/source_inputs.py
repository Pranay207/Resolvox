"""Neutral host workflows for unresolved, source-bound policy-table inputs.

Prompts contain no policy values or operational outcomes. Only actual current
same-row evidence can create or resume a workflow; old utterances are not joined.
"""
from datetime import date
import hashlib
import json
import re

from .config import REFERENCE_DATE
from .document_context import _payment, _rows
from .normalize import redact

_PROMPTS = {
    'return_category': {
        'en':'Which product or category are you asking about?',
        'hi':'\u0906\u092a \u0915\u093f\u0938 \u0909\u0924\u094d\u092a\u093e\u0926 \u092f\u093e \u0936\u094d\u0930\u0947\u0923\u0940 \u0915\u0947 \u092c\u093e\u0930\u0947 \u092e\u0947\u0902 \u092a\u0942\u091b \u0930\u0939\u0947 \u0939\u0948\u0902?',
        'hi-en':'Aap kis product ya category ke baare mein pooch rahe hain?',
    },
    'payment_method': {
        'en':'Which payment method did you use?',
        'hi':'\u0906\u092a\u0928\u0947 \u092d\u0941\u0917\u0924\u093e\u0928 \u0915\u093f\u0938 \u0924\u0930\u0940\u0915\u0947 \u0938\u0947 \u0915\u093f\u092f\u093e \u0925\u093e?',
        'hi-en':'Aapne payment kis tareeke se kiya tha?',
    },
}


def _fingerprint(source):
    data={key:source[key] for key in ('id','text','doc_type','status','effective_from','version') if key in source}
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def _actual(sources):
    values=sources.values() if isinstance(sources,dict) else sources
    return {source['id']:source for source in values if isinstance(source,dict)
            and isinstance(source.get('id'),str) and isinstance(source.get('text'),str)}


def _current_policy(source):
    if source.get('doc_type')!='policy' or source.get('status')!='current':return False
    try:return date.fromisoformat(source['effective_from'])<=REFERENCE_DATE
    except (KeyError,TypeError,ValueError):return False


def validated_source_inputs(facts,sources):
    """Rebind every lookup to exact cells in actual current policy-table rows."""
    if not isinstance(facts,dict):raise ValueError('invalid_required_application_inputs')
    required=facts.get('required_application_inputs',[])
    if not isinstance(required,list):raise ValueError('invalid_required_application_inputs')
    actual=_actual(sources);result=[]
    for item in required:
        if not isinstance(item,dict) or item.get('key') not in _PROMPTS:raise ValueError('invalid_required_application_inputs')
        key=item['key'];ids=item.get('source_ids');wanted=item.get('allowed_rows')
        if (not isinstance(ids,list) or not ids or any(not isinstance(sid,str) or sid not in actual for sid in ids)
                or len(set(ids))!=len(ids) or not isinstance(wanted,list) or len(wanted)<2):
            raise ValueError('unbound_required_application_input')
        if item.get('lookup_column',key)!=key:raise ValueError('unbound_required_application_input')
        parsed=[]
        for sid in ids:
            source=actual[sid]
            if not _current_policy(source):raise ValueError('unbound_required_application_input')
            for cells in _rows(source):
                if (key=='return_category' and len(cells)==3
                        and re.fullmatch(r'[a-z]+(?:_[a-z]+)*',cells[2])
                        and re.fullmatch(r'(?:\d+\s+(?:calendar\s+)?days?|not\s+returnable)',cells[1],re.I)):
                    parsed.append({'return_category':cells[2],'return_window':cells[1],'label':cells[0],'source_id':sid})
                elif key=='payment_method' and len(cells)==2 and cells[1] and _payment(cells[0]):
                    parsed.append({'payment_method':_payment(cells[0]),'label':cells[0],'timeline':cells[1],'source_id':sid})
        rows=[]
        for row in wanted:
            if not isinstance(row,dict):raise ValueError('unbound_required_application_input')
            fields=('return_category','return_window') if key=='return_category' else ('label','timeline')
            if any(not isinstance(row.get(field),str) or not row[field] for field in fields):
                raise ValueError('unbound_required_application_input')
            matches=[candidate for candidate in parsed if all(candidate[field]==row[field] for field in fields)]
            variants={tuple(candidate[field] for field in (key,'label','return_window' if key=='return_category' else 'timeline')) for candidate in matches}
            if len(variants)!=1:raise ValueError('unbound_required_application_input')
            candidate=matches[0]
            if key=='payment_method' and row.get(key,candidate[key])!=candidate[key]:raise ValueError('unbound_required_application_input')
            if key=='return_category' and row.get('label',candidate['label'])!=candidate['label']:raise ValueError('unbound_required_application_input')
            rows.append(candidate)
        if len({row[key] for row in rows})!=len(rows):raise ValueError('unbound_required_application_input')
        # A category/method cannot have conflicting current rows hidden elsewhere
        # in the same supplied tables while metadata selects just one of them.
        for row in rows:
            variants={(candidate['label'],candidate.get('return_window',candidate.get('timeline'))) for candidate in parsed if candidate[key]==row[key]}
            if len(variants)!=1:raise ValueError('unbound_required_application_input')
        result.append({'key':key,'source_ids':list(ids),'allowed_rows':rows})
    return result


def source_input_clarification(facts,sources,language):
    if language not in {'en','hi','hi-en'}:raise ValueError('unsupported_language')
    required=validated_source_inputs(facts,sources)
    if not required:return None
    item=required[0]
    return {'answer':_PROMPTS[item['key']][language], 'source_ids':item['source_ids'],
            'decision':'clarify','covered':False,'citations':[], 'provenance_kind':'source_table_input',
            'context_source_ids':[],'workflow_source_ids':item['source_ids'],'decision_origin':'host_source_table_input',
            'required_input':item['key'],'generation_attempts':0,'repair_attempted':False,
            'repair_errors':[],'validation_error':None,'attempt_metrics':[],'model_flags':None}


def _scope(order_id):
    return hashlib.sha256(str(order_id).encode()).hexdigest() if order_id else None


def _safe_public_context(public_context,sources,requirement):
    public={};catalog={}
    for source in _actual(sources).values():
        if source.get('doc_type')=='catalog' and source.get('status')=='current':
            try:
                row=json.loads(source['text'])
                if isinstance(row,dict) and isinstance(row.get('sku'),str):catalog[row['sku']]=row
            except (ValueError,TypeError):pass
    sku=public_context.get('sku')
    if isinstance(sku,str) and sku in catalog:public['sku']=sku
    categories=set()
    for source in _actual(sources).values():
        if _current_policy(source):
            categories.update(cells[2] for cells in _rows(source) if len(cells)==3 and re.fullmatch(r'[a-z]+(?:_[a-z]+)*',cells[2]) and re.fullmatch(r'(?:\d+\s+(?:calendar\s+)?days?|not\s+returnable)',cells[1],re.I))
    if public_context.get('category') in categories:public['category']=public_context['category']
    if requirement['key']=='payment_method':
        method=_payment(public_context.get('payment_method'))
        if method in {row['payment_method'] for row in requirement['allowed_rows']}:public['payment_method']=method
    for key in ('placed_on','delivered_on'):
        value=public_context.get(key)
        if isinstance(value,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
            try:public[key]=date.fromisoformat(value).isoformat()
            except ValueError:pass
    return public


def make_source_input_workflow(facts,sources,question,intent,public_context,order_id):
    required=validated_source_inputs(facts,sources)
    if not required:return {}
    item=required[0];actual=_actual(sources)
    query=redact(question)
    for marker in ('\nPublic context:', '\nPublic payment method:', '\nPublic catalog pincode:'):
        query=query.split(marker,1)[0]
    if order_id:
        query=re.sub(re.escape(order_id[:4])+r'[ -]?'+re.escape(order_id[4:]),'[order reference]',query)
    public=_safe_public_context(public_context,sources,item)
    bound={sid:source for sid,source in actual.items() if sid in item['source_ids'] or (_current_policy(source) and any(_rows(source))) or (source.get('doc_type')=='catalog' and source.get('status')=='current')}
    return {'question':query,'intent':'return' if item['key']=='return_category' else 'refund',
            'requirement':item,'source_sha256':{sid:_fingerprint(source) for sid,source in bound.items()},
            'public_context':public,'order_scope':_scope(order_id),'awaiting_reply':True}


def _norm(value):
    return ' '.join(re.findall(r'[^\W_]+',value.casefold()))


def resume_source_input(workflow,text,sources,*,order_id=None,candidate_product=None,candidate_category=None):
    """Resolve a bare source-defined choice; return typed context, not an answer."""
    if not isinstance(workflow,dict) or workflow.get('awaiting_reply') is not True or workflow.get('order_scope')!=_scope(order_id):return None
    if not isinstance(workflow.get('question'),str) or not workflow['question'].strip():return None
    try:
        required=validated_source_inputs({'required_application_inputs':[workflow['requirement']]},sources)
        actual=_actual(sources)
        if workflow.get('source_sha256')!={sid:_fingerprint(actual[sid]) for sid in workflow.get('source_sha256',{}) if sid in actual}:return None
    except (KeyError,ValueError,TypeError):return None
    reply=re.sub(r'^\s*(?:actually|instead|what\s+about|it\s+is|it\s+was|by|with)\s+','',text,flags=re.I)
    reply=re.sub(r'\s+please\s*[.!?]*\s*$','',reply,flags=re.I)
    if len(reply)>140:return None
    value=_norm(reply);tokens=set(value.split());key=required[0]['key'];exact=[];partial=[]
    if not tokens:return None
    for row in required[0]['allowed_rows']:
        aliases={_norm(row[key]),_norm(row['label'])}
        content=tokens-{'a','an','the','and','or','for','of','to','by','with','in','on'}
        short=bool(content and len(tokens)<=3 and tokens<=set(_norm(row['label']).split()))
        if value in aliases:exact.append(row)
        elif short:partial.append(row)
    matches=exact or partial
    public=_safe_public_context(workflow.get('public_context',{}),sources,required[0])
    if key=='payment_method' and not exact and partial:
        # A partial label such as Bank cannot distinguish a refund route.
        # Retain the original question and ask the same neutral input question.
        public.pop('payment_method',None)
        return {'question':workflow['question'],'intent':workflow['intent'],'public_context':public,
                'key':key,'value':None,'source_label':'','source_ids':required[0]['source_ids'],
                'workflow':{**workflow,'public_context':public,'awaiting_reply':True},
                'resolution':'unresolved'}
    product_match=False
    if key=='return_category' and isinstance(candidate_product,dict):
        names={_norm(str(candidate_product.get('sku',''))),_norm(str(candidate_product.get('title','')))}
        if value in names:
            matches=[row for row in required[0]['allowed_rows'] if row[key]==candidate_product.get('return_category')]
            product_match=bool(matches)
    if not matches and key=='return_category' and len(tokens)<=2 and candidate_category:
        matches=[row for row in required[0]['allowed_rows'] if row[key]==candidate_category]
    if len(matches)!=1:return None
    row=matches[0]
    if key=='return_category':
        public.pop('sku',None);public.pop('category',None)
        public['sku' if product_match else 'category']=candidate_product['sku'] if product_match else row[key]
    else:public['payment_method']=row[key]
    updated={**workflow,'public_context':public,'awaiting_reply':False}
    return {'question':workflow['question'],'intent':workflow['intent'],'public_context':public,
            'key':key,'value':row[key],'source_label':row['label'],'source_ids':required[0]['source_ids'],
            'workflow':updated}


def workflow_binding_sources(workflow,chunks,products,pincodes):
    """Re-read public source rows at the same existing application boundaries."""
    sources=[]
    for sid in workflow.get('source_sha256',{}):
        if sid in chunks:
            sources.append(chunks[sid].public())
        elif sid.startswith('products.csv:') and sid.split(':',1)[1] in products:
            row=products[sid.split(':',1)[1]]
            sources.append({'id':sid,'file':'data/products.csv','text':json.dumps(row,ensure_ascii=False),'doc_type':'catalog','status':'current'})
        elif sid.startswith('pincodes.csv:') and sid.split(':',1)[1] in pincodes:
            row=pincodes[sid.split(':',1)[1]]
            sources.append({'id':sid,'file':'data/pincodes.csv','text':json.dumps(row),'doc_type':'catalog','status':'current'})
    return sources


class ModelCallProbe:
    """Count actual client invocations so pre-call failures have no model timing."""
    def __init__(self,client):self.client=client;self.calls=0
    @property
    def last_metrics(self):return getattr(self.client,'last_metrics',{})
    def complete(self,*args,**kwargs):
        self.calls+=1
        return self.client.complete(*args,**kwargs)
