"""Session-scoped state machine. Credentials are discarded at the tool boundary."""
from dataclasses import dataclass,field
from functools import lru_cache
import json,os,re,time
from types import SimpleNamespace
from .answering import Policy,Plan,classify
from .config import REFERENCE_DATE
from .data import Data
from .kb import KnowledgeBase
from .retrieval import Retriever
from .tools_wrapper import Tools
from .normalize import order_id,proof_value,language,redact
from .llm import LLM,LLMUnavailable
from .grounding import compatible,generate,abstention

class Resources:
    def __init__(self,dense:bool|None=None):
        self.data=Data(); self.kb=KnowledgeBase(); self.retriever=Retriever(self.kb,dense=dense); self.policy=Policy(self.kb,self.data); self.tools=Tools(); self.llm=LLM()
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
        self.compose=(os.getenv('COMPOSE_WITH_LLM','true').lower()=='true') if compose is None else compose
    def _verification_plan(self,kind:str) -> Plan:
        if kind=='locked': return Plan('verification','refuse',"I cannot share order details because verification failed twice. Please contact support from your registered phone; I can still help with general policies.",'दो बार सत्यापन असफल हुआ, इसलिए ऑर्डर की जानकारी साझा नहीं कर सकती। पंजीकृत फ़ोन से सपोर्ट से संपर्क करें; सामान्य पॉलिसी में मदद कर सकती हूँ।','Verification do baar fail hua, order details share nahi kar sakti. Registered phone se support contact karein; general policy mein help kar sakti hoon.',['IDV-1','IDV-3'])
        if kind=='retry': return Plan('verification','clarify',"That did not match. Please try the last 4 digits of your registered phone again.",'जानकारी मेल नहीं खाई। कृपया पंजीकृत फ़ोन के आख़िरी 4 अंक दोबारा बताएँ।','Match nahi hua. Registered phone ke last 4 digits ek baar phir batayein.',['IDV-3'])
        return Plan('verification','clarify','Please provide the last 4 digits of your registered phone.','कृपया अपने पंजीकृत फ़ोन के आख़िरी 4 अंक बताएँ।','Registered phone ke last 4 digits batayein.',['IDV-1','IDV-2'])
    def respond(self,text:str) -> dict:
        start=time.perf_counter(); s=self.state; r=self.resources; s.turn+=1; s.language=language(text,s.language)
        intent=classify(text); oid=order_id(text); calls=[]; candidates=[]; pool=[]; auth_source_ids=[]; retrieval_ms=0.0
        # An order switch invalidates authentication and deferred questions in
        # every branch, including urgent escalation and privacy refusals.
        if oid and oid!=s.order_id:
            if s.order_id is not None: s.pending_intent=''; s.pending_issue=''; s.last_intent=''
            s.order_id=oid; s.order=None
        if s.last_intent=='safety' and intent not in {'privacy','fraud','legal','human'} and re.search(r'try|test|charg|plug|use|turn.{0,4}on|repair|जाँच|चार्ज|चलाऊ|इस्तेमाल',text,re.I):
            intent='safety'
        credential=bool(re.search(r'(last.?four|last.?4|digits|(?:phone|mobile|number).{0,18}(?:ends?|suffix|last|ending)|आख़?िरी|अंतिम|अंक|aakhri|aakhiri|akhri)',text,re.I)) or bool(s.order_id and not s.order and re.search(r'pincode|pin code|पिनकोड',text,re.I))
        if s.order_id and re.fullmatch(r'\s*[\d०-९]{4}(?:[\d०-९]{2})?\s*',text): credential=True
        proof=proof_value(text) if credential or (s.order_id and not s.order and not oid) else None
        safe_text=redact(text,credential_turn=bool(proof) or credential)
        public_pins=re.findall(r'(?<!\d)\d{6}(?!\d)',text) if not credential and not proof and not (s.order_id and not s.order) else []
        answer_query=safe_text
        contextual_text=safe_text
        if not s.order_id and not credential and re.search(r'\b(it|this|that|instead|actually|correction|its|ise|isko|uska)\b|असल|यह|तारीख',safe_text,re.I):
            previous=[h['user'] for h in reversed(s.safe_history) if h['intent'] not in {'verification','privacy','safety','fraud','legal','human'} and not h['user'].startswith('[verification')][:2]
            if previous:
                contextual_text+='\nPrevious customer context: '+' '.join(previous)
                if intent=='unknown' and s.last_intent in {'return','refund','warranty','delivery'}: intent=s.last_intent
        def grounded_plan(query,kind,order=None):
            nonlocal candidates,pool,retrieval_ms,answer_query
            answer_query=query
            began=time.perf_counter()
            delivered=(order or {}).get('delivered_on') or ''
            date=r.policy._date_in(query)
            historical=bool((delivered and delivered<'2026-08-01') or (date and date.isoformat()<'2026-08-01'))
            retrieval_query=query
            if order:
                # Retrieval can use minimal verified context to resolve short
                # follow-ups. No identity proof or customer identifiers enter it.
                context=[kind.replace('_',' ')]
                if kind=='refund':
                    context += ['refund',str(order.get('payment_method') or ''),'after initiation']
                    if order.get('return_status') and not order.get('return_refund_initiated_on'):
                        context += ['return quality check pickup refund initiation']
                if kind in {'delivery','shipping_date'}: context += ['track order status promised delivery date']
                if kind in {'return','pickup'} and order.get('is_plus'): context += ['Plus membership pickup fee']
                retrieval_query+='\n'+' '.join(context)
            found=r.retriever.search(retrieval_query,k=12,historical=historical,intent=kind)
            # Re-read by ID so stale index objects cannot resurrect removed or
            # changed policy text after an in-memory KB update.
            candidates=[dict(x,chunk=r.kb.chunks[x['chunk'].id]) for x in found if x['chunk'].id in r.kb.chunks and r.kb.allowed(r.kb.chunks[x['chunk'].id],historical)]
            pool=[x['chunk'].public() for x in candidates]
            # Public catalog/calendar rows are looked up independently of a
            # policy answer. Private order tables never enter this reader.
            product=r.policy.product(query,order)
            products=[product] if product else [p for p in r.data.products.values() if p['title'].split(',')[0].lower() in query.lower()]
            for product in products:
                pool.append({'id':'products.csv:'+product['sku'],'file':'data/products.csv','text':json.dumps(product,ensure_ascii=False),'doc_type':'catalog','status':'current'})
            for pin in public_pins:
                if pin in r.data.pincodes:
                    pool.append({'id':'pincodes.csv:'+pin,'file':'data/pincodes.csv','text':json.dumps(r.data.pincodes[pin]),'doc_type':'catalog','status':'current'})
            view=SimpleNamespace(chunks={x['chunk'].id:x['chunk'] for x in candidates})
            scoped=Policy(view,r.data)
            # Public serviceability is catalog information, never evidence of a
            # caller's identity. Verification turns cannot enter this branch.
            if len(public_pins)==1 and public_pins[0] in r.data.pincodes and re.search(r'cod|deliver|express|service|पहुंच|डिलीवरी',query,re.I):
                pin=public_pins[0]; row=r.data.pincodes[pin]
                field='cod_available' if re.search(r'cod|cash.on.delivery',query,re.I) else 'express_available' if re.search(r'express',query,re.I) else 'serviceable'
                enabled=row[field]=='True'; label={'cod_available':'COD','express_available':'Express delivery','serviceable':'Delivery'}[field]
                result=Plan(kind,'answer',f'{label} is '+('available' if enabled else 'not available')+' at that postal code.',f'उस पिनकोड पर {label} '+('उपलब्ध है।' if enabled else 'उपलब्ध नहीं है।'),f'Us pincode par {label} '+('available hai.' if enabled else 'available nahi hai.'),['pincodes.csv:'+pin],facts={field:enabled})
                if field=='cod_available':
                    result.en+=' COD is limited to 10,000 rupees and has a 25 rupee fee per order.'
                    result.hi+=' COD की सीमा 10,000 रुपये और प्रति ऑर्डर फ़ीस 25 रुपये है।'
                    result.hinglish+=' COD limit 10,000 rupees aur per-order fee 25 rupees hai.'
                    result.ids.append('PAY-2')
                    if any(int(v)>10000 for v in re.findall(r'(?<!\d)\d{1,5}(?!\d)',query.replace(',',''))):
                        result.en+=' An amount above that limit is not eligible for COD.'
                        result.hi+=' इससे अधिक राशि पर COD उपलब्ध नहीं है।'
                        result.hinglish+=' Isse zyada amount par COD eligible nahi hai.'
                        result.facts['cod_eligible']=False
                retrieval_ms+=1000*(time.perf_counter()-began)
                return result
            try: result=scoped.plan(query,kind,order)
            except (KeyError,ValueError): result=scoped.unknown()
            retrieval_ms+=1000*(time.perf_counter()-began)
            return result
        # Authentication bypass, third-party disclosure and internal-note requests never reach the LLM/tools.
        if intent in {'privacy','safety','fraud','legal','human'}:
            # Guardrail policy lookups are explicit, separate from answer RAG.
            plan=r.policy.plan(safe_text,intent)
        elif oid and (oid!=s.order_id or not s.order):
            if oid!=s.order_id: s.order_id=oid; s.order=None
            if s.attempts.get(oid,0)>=2: plan=self._verification_plan('locked')
            else:
                _,trace=r.tools.lookup(oid); calls.append(trace)
                if intent not in {'greeting','unknown'}: s.pending_intent=intent; s.pending_issue=safe_text
                elif intent=='unknown' and re.search(r'status|track|shipment|parcel|arriv|where|when|कहाँ|कब',safe_text,re.I): s.pending_intent='delivery'; s.pending_issue=safe_text
                elif re.search(r'issue|problem|concern|unresolved|समस्या',safe_text,re.I): s.pending_issue=safe_text
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
            elif s.order is None and intent in {'greeting','unknown'} and re.search(r'issue|problem|concern|unresolved|समस्या',safe_text,re.I): s.pending_issue=safe_text
            plan=grounded_plan(contextual_text,intent,s.order)
            if s.order and int(s.order.get('contacts_last_7_days') or 0)>=2 and intent in {'refund','delivery','damage','repeat'}:
                plan=r.policy.plan(safe_text,'repeat',s.order)
        if proof and s.order_id and not s.order and intent not in {'privacy','safety','fraud','legal','human'}:
            if s.attempts.get(s.order_id,0)>=2: plan=self._verification_plan('locked')
            else:
                order,trace=r.tools.lookup(s.order_id,proof); calls.append(trace)
                if order:
                    s.order=order
                    if s.pending_intent:
                        plan=grounded_plan(s.pending_issue,s.pending_intent,s.order)
                        if int(s.order.get('contacts_last_7_days') or 0)>=2 and s.pending_intent in {'refund','delivery','damage','repeat'}:
                            plan=r.policy.plan(s.pending_issue,'repeat',s.order)
                    else:
                        plan=Plan('verification','answer','Verification succeeded. How can I help with this order?','सत्यापन सफल हुआ। इस ऑर्डर में क्या मदद चाहिए?','Verification successful. Order ke baare mein kya help chahiye?',['IDV-2'])
                    if s.pending_issue and int(s.order.get('contacts_last_7_days') or 0)>=2:
                        answer_query=s.pending_issue
                        plan=r.policy.plan(s.pending_issue,'repeat',s.order)
                    auth_source_ids=['IDV-2']
                    s.pending_issue=''; s.pending_intent=''
                else:
                    s.attempts[s.order_id]=s.attempts.get(s.order_id,0)+1
                    plan=self._verification_plan('locked' if s.attempts[s.order_id]>=2 else 'retry')
            safe_text=redact(text,credential_turn=True)
        proof=None  # Never place proof in state, model inputs, traces or output.
        if plan.decision=='escalate':
            reason=plan.reason or plan.intent
            ticket_key=(s.order_id,reason)
            if ticket_key in s.tickets: ticket=s.tickets[ticket_key]
            else:
                summary=f'Issue: {answer_query[:350]}. Intent: {plan.intent}. Order: {s.order_id or "not provided"}. Checked: '+(', '.join(plan.ids))+f'. Verified caller: {bool(s.order)}. Escalation reason: {reason}. No outcome promised.'
                try: ticket,trace=r.tools.ticket(summary,s.order_id,reason,plan.intent); calls.append(trace)
                except (OSError,ValueError): ticket={'created':False}
                if ticket.get('created'): s.tickets[ticket_key]=ticket
            if ticket.get('created'):
                plan.en=plan.en.replace(' I will request a ticket.','').replace(' I will request a support ticket.','').replace('; I will request a support ticket.','.')
                plan.en+=' A ticket has been created; a human colleague will contact you.'
                plan.hi+=' टिकट बन गया है; मानव सहयोगी संपर्क करेंगे।'
                plan.hinglish+=' Ticket create ho gaya; human colleague contact karenge.'
            else:
                plan.en+=' The ticket could not be created. Please contact support directly.'
                plan.hi+=' टिकट नहीं बन सका। कृपया सीधे सपोर्ट से संपर्क करें।'
                plan.hinglish+=' Ticket create nahi hua. Support ko directly contact karein.'
        guard=plan.intent in {'verification','privacy','safety','fraud','legal','human','repeat','unclear_audio','greeting','compensation'} or plan.decision=='escalate' or (plan.decision=='clarify' and 'IDV-1' in plan.ids)
        if guard:
            pool=[r.kb.chunks[c].public() for c in plan.ids if c in r.kb.chunks]+pool
        available={x['id']:x for x in pool}
        supported=compatible(plan.ids,pool)
        if not supported: plan.facts={}
        source_ids=list(dict.fromkeys(plan.ids)) if supported else []
        sources=[available[c] for c in source_ids]
        answer=plan.text(s.language) if supported else abstention(s.language)
        composition='deterministic_guardrail' if guard else ('evidence_validated_rules' if supported else 'abstained_missing_evidence')
        validation_error=None; llm_ms=0.0
        if self.compose and plan.decision=='answer' and not guard and plan.intent!='unsupported':
            # Select only actual query results; never append a planner's source.
            selected=sources if supported else ([x for x in pool if x.get('doc_type')=='catalog']+[x for x in pool if x.get('doc_type') in {'policy','help','agent_guide'}][:3])
            if selected:
                began=time.perf_counter()
                try:
                    answer,source_ids=generate(r.llm,answer_query,s.language,selected,plan if supported else None,private=bool(s.order_id))
                    sources=[available[c] for c in source_ids]; composition='grounded_llm'
                except (LLMUnavailable,ValueError,TypeError) as exc:
                    validation_error=str(exc) if isinstance(exc,ValueError) else 'model_unavailable_or_invalid'
                    composition='evidence_validated_fallback' if supported else 'abstained_model_or_evidence'
                llm_ms=1000*(time.perf_counter()-began)
        if not supported and composition!='grounded_llm' and not guard:
            plan.facts={}; plan.intent='unsupported'; plan.decision='answer'
        for cid in auth_source_ids:
            if cid not in source_ids:
                source_ids.append(cid); sources.append(r.kb.chunks[cid].public())
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
                'retrieval_mode':r.retriever.dense_status,'retrieval_k':12,'evidence_supported':supported,
                'validation_error':validation_error,'llm':r.llm.last_metrics.copy() if llm_ms else {},
                'timings':{'retrieval_ms':round(retrieval_ms,2),'llm_ms':round(llm_ms,2)},
                'latency_ms':round(1000*(time.perf_counter()-start),2)}
