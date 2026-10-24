"""Session-scoped state machine. Credentials are discarded at the tool boundary."""
from dataclasses import dataclass,field
from functools import lru_cache
import json,os,re,time
from .answering import Policy,Plan,classify
from .config import REFERENCE_DATE
from .data import Data
from .kb import KnowledgeBase
from .retrieval import Retriever
from .tools_wrapper import Tools
from .normalize import order_id,proof_value,language,redact
from .llm import LLM,LLMUnavailable

class Resources:
    def __init__(self,dense:bool|None=None):
        self.data=Data(); self.kb=KnowledgeBase(); self.retriever=Retriever(self.kb,dense=dense); self.policy=Policy(self.kb,self.data); self.tools=Tools()
@lru_cache(maxsize=1)
def resources() -> Resources: return Resources()
@dataclass
class State:
    order_id:str|None=None
    order:dict|None=None
    attempts:dict[str,int]=field(default_factory=dict)
    language:str='en'
    turn:int=0
    pending_issue:str=''
    pending_intent:str=''
    last_intent:str=''
    tickets:dict[str,dict]=field(default_factory=dict)
    safe_history:list[dict]=field(default_factory=list)

class Agent:
    def __init__(self,resources:Resources|None=None,compose:bool|None=None):
        self.resources=resources or globals()['resources'](); self.state=State()
        self.compose=(os.getenv('COMPOSE_WITH_LLM','false').lower()=='true') if compose is None else compose
    def _verification_plan(self,kind:str) -> Plan:
        if kind=='locked': return Plan('verification','refuse',"I cannot share order details because verification failed twice. Please contact support from your registered phone; I can still help with general policies.",'दो बार सत्यापन असफल हुआ, इसलिए ऑर्डर की जानकारी साझा नहीं कर सकती। पंजीकृत फ़ोन से सपोर्ट से संपर्क करें; सामान्य पॉलिसी में मदद कर सकती हूँ।','Verification do baar fail hua, order details share nahi kar sakti. Registered phone se support contact karein; general policy mein help kar sakti hoon.',['IDV-1','IDV-3'])
        if kind=='retry': return Plan('verification','clarify',"That did not match. Please try the last 4 digits of your registered phone again.",'जानकारी मेल नहीं खाई। कृपया पंजीकृत फ़ोन के आख़िरी 4 अंक दोबारा बताएँ।','Match nahi hua. Registered phone ke last 4 digits ek baar phir batayein.',['IDV-3'])
        return Plan('verification','clarify','Please provide the last 4 digits of your registered phone.','कृपया अपने पंजीकृत फ़ोन के आख़िरी 4 अंक बताएँ।','Registered phone ke last 4 digits batayein.',['IDV-1','IDV-2'])
    def respond(self,text:str) -> dict:
        start=time.perf_counter(); s=self.state; r=self.resources; s.turn+=1; s.language=language(text,s.language)
        intent=classify(text); oid=order_id(text); calls=[]
        credential=bool(re.search(r'(last.?four|last.?4|digits|pincode|pin code|(?:phone|mobile|number).{0,18}(?:ends?|suffix|last|ending)|आख़?िरी|अंतिम|अंक|पिनकोड|aakhri|aakhiri|akhri)',text,re.I))
        proof=proof_value(text) if credential or (s.order_id and not s.order and not oid) else None
        safe_text=redact(text,credential_turn=bool(proof) or credential)
        # Authentication bypass, third-party disclosure and internal-note requests never reach the LLM/tools.
        if intent in {'privacy','safety','fraud','legal','human'}:
            plan=r.policy.plan(safe_text,intent)
            if oid and intent!='privacy': s.order_id=oid
        elif oid and (oid!=s.order_id or not s.order):
            if oid!=s.order_id: s.order_id=oid; s.order=None
            if s.attempts.get(oid,0)>=2: plan=self._verification_plan('locked')
            else:
                _,trace=r.tools.lookup(oid); calls.append(trace)
                if intent not in {'greeting','unknown'}: s.pending_intent=intent; s.pending_issue=safe_text
                plan=self._verification_plan('ask')
                # If caller supplies both ID and proof in one turn, accept the provided value, never disclose expected proof.
                remainder=re.sub(r'\d{4}[ -]?\d{4}','',text)
                simultaneous=proof_value(remainder) if credential else None
                if simultaneous: proof=simultaneous; safe_text='[order ID and verification value redacted]'
        elif s.order_id and not s.order and proof:
            plan=self._verification_plan('ask')
        elif credential and not s.order_id:
            plan=Plan('verification','clarify','What is your order ID?','आपका ऑर्डर नंबर क्या है?','Order ID kya hai?',['IDV-2'])
        elif not text.strip():
            plan=Plan('unclear_audio','clarify',"Sorry, I didn't catch that. Could you say it again?",'माफ़ कीजिए, सुनाई नहीं दिया। कृपया फिर कहें।','Maaf karein, sunai nahi diya. Dobara bolenge?',['STY-5'])
        else:
            if intent=='unknown' and s.last_intent in {'refund','return'} and re.search(r'(how long|kitn|कितने|that|उस)',text,re.I): intent=s.last_intent
            if s.order is None and intent=='delivery' and re.search(r'(my order|where is|hasn.t arrived|मेरे ऑर्डर|मेरा ऑर्डर)',text,re.I):
                s.pending_intent=intent; s.pending_issue=safe_text
            plan=r.policy.plan(safe_text,intent,s.order)
            if s.order and int(s.order.get('contacts_last_7_days') or 0)>=2 and intent in {'refund','delivery','damage','repeat'}:
                plan=r.policy.plan(safe_text,'repeat',s.order)
        if proof and s.order_id and not s.order and intent not in {'privacy','safety','fraud','legal','human'}:
            if s.attempts.get(s.order_id,0)>=2: plan=self._verification_plan('locked')
            else:
                order,trace=r.tools.lookup(s.order_id,proof); calls.append(trace)
                if order:
                    s.order=order
                    if s.pending_intent:
                        plan=r.policy.plan(s.pending_issue,s.pending_intent,s.order)
                    else:
                        plan=Plan('verification','answer','Verification succeeded. How can I help with this order?','सत्यापन सफल हुआ। इस ऑर्डर में क्या मदद चाहिए?','Verification successful. Order ke baare mein kya help chahiye?',['IDV-2'])
                    if 'IDV-2' not in plan.ids: plan.ids.append('IDV-2')
                    s.pending_issue=''; s.pending_intent=''
                else:
                    s.attempts[s.order_id]=s.attempts.get(s.order_id,0)+1
                    plan=self._verification_plan('locked' if s.attempts[s.order_id]>=2 else 'retry')
            safe_text=redact(text,credential_turn=True)
        proof=None  # Never place proof in state, model inputs, traces or output.
        if plan.decision=='escalate':
            reason=plan.reason or plan.intent
            if reason in s.tickets: ticket=s.tickets[reason]
            else:
                summary=f'Issue: {safe_text[:350]}. Intent: {plan.intent}. Order: {s.order_id or "not provided"}. Checked: '+(', '.join(plan.ids))+f'. Verified caller: {bool(s.order)}. Escalation reason: {reason}. No outcome promised.'
                try: ticket,trace=r.tools.ticket(summary,s.order_id,reason,plan.intent); calls.append(trace)
                except (OSError,ValueError): ticket={'created':False}
                if ticket.get('created'): s.tickets[reason]=ticket
            if ticket.get('created'):
                plan.en=plan.en.replace(' I will request a ticket.','').replace(' I will request a support ticket.','').replace('; I will request a support ticket.','.')
                plan.en+=' A ticket has been created; a human colleague will contact you.'
                plan.hi+=' टिकट बन गया है; मानव सहयोगी संपर्क करेंगे।'
                plan.hinglish+=' Ticket create ho gaya; human colleague contact karenge.'
            else:
                plan.en+=' The ticket could not be created. Please contact support directly.'
                plan.hi+=' टिकट नहीं बन सका। कृपया सीधे सपोर्ट से संपर्क करें।'
                plan.hinglish+=' Ticket create nahi hua. Support ko directly contact karein.'
        historical='RETv3-2' in plan.ids
        candidates=r.retriever.search(safe_text,k=8,historical=historical,intent=plan.intent) if safe_text and not credential and plan.intent!='verification' else []
        # Governing sections are explicit policy retrieval by rule; broad search results are logged separately.
        source_ids=list(dict.fromkeys(plan.ids)); sources=[]
        for cid in source_ids:
            if cid in r.kb.chunks: sources.append(r.kb.chunks[cid].public())
            elif cid.startswith('products.csv:'):
                sku=cid.split(':',1)[1]; sources.append({'id':cid,'file':'data/products.csv','text':json.dumps(r.data.products[sku],ensure_ascii=False),'doc_type':'catalog','status':'current'})
        answer=plan.text(s.language); composition='deterministic'
        # The model composes only from an approved sentence bank; it cannot inject new factual wording.
        if self.compose and plan.decision=='answer' and plan.intent not in {'verification','unsupported'}:
            try:
                sentences=re.split(r'(?<=[.!?।])\s+',answer); client=LLM()
                prompt=json.dumps({'question':safe_text,'language':s.language,'sentences':sentences},ensure_ascii=False)
                raw=json.loads(client.complete('Arrange the supplied verified sentences into a clear customer reply. Return JSON {"order":[indices]}. Include EVERY index exactly once. Never add text or facts.',prompt,True))
                indices=raw.get('order',[])
                if sorted(indices)==list(range(len(sentences))): answer=' '.join(sentences[i] for i in indices); composition='llm_sentence_composition'
                else: composition='deterministic_invalid_model_plan'
            except (LLMUnavailable,ValueError,TypeError): composition='deterministic_llm_unavailable'
        if s.turn==1:
            opener={'en':"I'm ZentroMart's AI support assistant. ",'hi':'मैं ZentroMart की AI सहायता सहायक हूँ। ','hi-en':'Main ZentroMart ki AI support assistant hoon. '}[s.language]
            answer=opener+answer; source_ids=list(dict.fromkeys(['STY-1']+source_ids))
            if not any(x['id']=='STY-1' for x in sources): sources.insert(0,r.kb.chunks['STY-1'].public())
        answer=redact(answer)
        s.last_intent=plan.intent if plan.intent!='verification' else s.last_intent
        s.safe_history.append({'user':safe_text,'intent':plan.intent,'decision':plan.decision}); s.safe_history=s.safe_history[-12:]
        return {'transcript':safe_text,'answer':answer,'intent':plan.intent,'decision':plan.decision,'language':s.language,
                'retrieved_chunk_ids':source_ids,'sources':sources,'retrieval_candidates':[{'id':x['chunk'].id,'score':x['score'],'dense_score':x['dense_score']} for x in candidates],
                'tool_calls':calls,'facts':plan.facts,'verified':bool(s.order),'reference_date':REFERENCE_DATE.isoformat(),'composition':composition,
                'retrieval_mode':r.retriever.dense_status,'latency_ms':round(1000*(time.perf_counter()-start),2)}
