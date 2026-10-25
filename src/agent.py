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
from .normalize import order_id,proof_value,language,redact,number_words
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
    public_context:dict[str,str]=field(default_factory=dict)

class Agent:
    def __init__(self,resources:Resources|None=None,compose:bool|None=None):
        self.resources=resources or globals()['resources'](); self.state=State()
        self.compose=(os.getenv('COMPOSE_WITH_LLM','true').lower()=='true') if compose is None else compose
    def _verification_plan(self,kind:str) -> Plan:
        if kind=='locked': return Plan('verification','refuse',"I cannot share order details because verification failed twice. Please contact support from your registered phone; I can still help with general policies.",'दो बार सत्यापन असफल हुआ, इसलिए ऑर्डर की जानकारी साझा नहीं कर सकती। पंजीकृत फ़ोन से सपोर्ट से संपर्क करें; सामान्य पॉलिसी में मदद कर सकती हूँ।','Verification do baar fail hua, order details share nahi kar sakti. Registered phone se support contact karein; general policy mein help kar sakti hoon.',['IDV-1','IDV-3'])
        if kind=='retry': return Plan('verification','clarify',"That did not match. Please try the last 4 digits of your registered phone again.",'जानकारी मेल नहीं खाई। कृपया पंजीकृत फ़ोन के अंतिम 4 अंक दोबारा बताएँ।','Match nahi hua. Registered phone ke last 4 digits ek baar phir batayein.',['IDV-3'])
        return Plan('verification','clarify','Please provide one verification detail: the last 4 digits of your registered phone or the order delivery pincode.','कृपया एक सत्यापन जानकारी दें: पंजीकृत फ़ोन के अंतिम 4 अंक या ऑर्डर का डिलीवरी पिनकोड।','Ek verification detail dein: registered phone ke last 4 digits ya order ka delivery pincode.',['IDV-1','IDV-2'])
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
        explicit_skus=[prefix.upper()+'-'+digits for prefix,digits in
                       re.findall(r'\b(ELE|FSH|HOM|BKS|INR|BEA|GRO|DIG)[-\s]*(\d{4})\b',number_words(safe_text),re.I)]
        unknown_skus=[value for value in explicit_skus if value not in r.data.products]
        # Carry explicit public slots, never concatenate old utterances: that
        # can introduce competing SKUs and superseded dates into a follow-up.
        if not s.order_id and not credential and intent not in {'privacy','safety','fraud','legal','human'}:
            followup=bool(re.search(r'\b(it|this|that|instead|actually|correction|corrected|its|same|what about|then|now|ise|isko|uska)\b|असल|यह|तारीख',safe_text,re.I))
            prior_intent=s.last_intent
            if explicit_skus and s.safe_history and s.safe_history[-1]['decision']=='clarify': followup=True
            date_revision=followup and prior_intent=='return' and bool(re.search(r'correction|corrected|revise|actually',safe_text,re.I))
            if (intent=='unknown' and followup and prior_intent in {'return','refund','warranty','delivery'}) or date_revision:
                intent=prior_intent
            context=dict(s.public_context) if followup else {}
            product=r.policy.product(safe_text)
            if explicit_skus:
                context.pop('sku',None)
                context.pop('category',None)
            if product:
                context['sku']=product['sku']
                context.pop('category',None)
            else:
                category=r.policy._category(safe_text)
                if category:
                    context['category']=category
                    context.pop('sku',None)
            for event,key in [('placement','placed_on'),('delivery','delivered_on')]:
                date=r.policy._event_date(safe_text,event)
                if date: context[key]=date.isoformat()
            if followup and context:
                details=[]
                if context.get('sku'): details.append('Product '+context['sku'])
                elif context.get('category'): details.append('Product category '+context['category'])
                if context.get('placed_on'): details.append('Order placed on '+context['placed_on'])
                if context.get('delivered_on'): details.append('Delivered on '+context['delivered_on'])
                contextual_text+='\nPublic context: '+'. '.join(details)+'.'
            s.public_context=context
        def grounded_plan(query,kind,order=None):
            nonlocal candidates,pool,retrieval_ms,answer_query
            answer_query=query
            began=time.perf_counter()
            if unknown_skus:
                # An explicit unknown replacement must not inherit the previous
                # catalog item or guess its category from an older utterance.
                return Plan(kind,'clarify',
                    'I could not find that SKU in the supplied product catalog. What is the correct product SKU?',
                    'वह SKU दिए गए उत्पाद कैटलॉग में नहीं मिला। सही उत्पाद SKU क्या है?',
                    'Woh SKU supplied product catalog mein nahi mila. Correct product SKU kya hai?',
                    ['STY-5'],facts={'catalog_match':False})
            delivered=(order or {}).get('delivered_on') or ''
            date=r.policy._date_in(query)
            historical=bool((delivered and delivered<'2026-08-01') or (date and date.isoformat()<'2026-08-01'))
            product=r.policy.product(query,order)
            retrieval_query=query
            if product and kind in {'return','warranty','damage','pickup','troubleshoot'}:
                # Catalog metadata gives semantic context, not expected KB IDs.
                fields={key:value for key,value in product.items() if key in
                        {'return_category','seller_type','seller_name','zentromart_assured','is_assured','assured','warranty_months','fulfilled_by'}}
                retrieval_query+='\nPublic catalog attributes: '+json.dumps(fields,ensure_ascii=False)
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
            want_cod=bool(re.search(r'\bcod\b|cash[ -]on[ -]delivery|cash.{0,15}(?:door|deliver)|कैश|नकद',query,re.I))
            want_express=bool(re.search(r'\bexpress\b|एक्सप्रेस',query,re.I))
            service_request=kind in {'delivery','payment','unknown'} and bool(
                want_cod or want_express or re.search(r'\b(?:deliver(?:y)?|serviceable|serviceability|prepaid)\b|डिलीवरी|पहुँच',query,re.I))
            # A location mentioned alongside a return or warranty question must
            # not replace the requested policy answer with serviceability.
            if len(public_pins)==1 and service_request:
                pin=public_pins[0]
                if pin not in r.data.pincodes:
                    retrieval_ms+=1000*(time.perf_counter()-began)
                    return Plan(kind,'refuse',
                        'That postal code is not listed in the supplied pincode table, so I cannot confirm delivery, COD or Express availability. Delivery requires a listed serviceable pincode.',
                        'वह पिनकोड दी गई तालिका में नहीं है, इसलिए डिलीवरी, COD या एक्सप्रेस की उपलब्धता की पुष्टि नहीं कर सकती। डिलीवरी के लिए सूची में सेवा योग्य पिनकोड होना चाहिए।',
                        'Woh pincode supplied table mein listed nahi hai; delivery, COD ya Express availability confirm nahi kar sakti. Listed serviceable pincode zaroori hai.',
                        ['DEL-5'],facts={'pincode_listed':False})
                row=r.data.pincodes[pin]
                serviceable=row['serviceable']=='True'
                result=Plan(kind,'answer',
                    'Standard delivery is '+('available' if serviceable else 'not available')+' at that postal code. Delivery within India also requires a serviceable pincode.',
                    'उस पिनकोड पर सामान्य डिलीवरी '+('उपलब्ध है।' if serviceable else 'उपलब्ध नहीं है।')+' भारत में भी पिनकोड का सेवा योग्य होना ज़रूरी है।',
                    'Us pincode par Standard delivery '+('available hai.' if serviceable else 'available nahi hai.')+' India mein bhi serviceable pincode zaroori hai.',
                    ['pincodes.csv:'+pin,'DEL-5'],facts={'serviceable':serviceable})
                if want_express:
                    enabled=serviceable and row['express_available']=='True'
                    result.en+=' Express delivery is '+('available' if enabled else 'not available')+'; being in a metro does not by itself establish Express eligibility.'
                    result.hi+=' एक्सप्रेस डिलीवरी '+('उपलब्ध है।' if enabled else 'उपलब्ध नहीं है।')+' मेट्रो शहर में होने से ही एक्सप्रेस उपलब्ध नहीं होती।'
                    result.hinglish+=' Express delivery '+('available hai.' if enabled else 'available nahi hai.')+' Metro hone se Express eligibility confirm nahi hoti.'
                    result.facts['express_available']=enabled
                if want_cod:
                    enabled=serviceable and row['cod_available']=='True'
                    result.en+=' COD is '+('available' if enabled else 'not available')+'. COD is limited to 10,000 rupees and has a 25 rupee fee per order.'
                    result.hi+=' COD '+('उपलब्ध है।' if enabled else 'उपलब्ध नहीं है।')+' COD की सीमा 10,000 रुपये और प्रति ऑर्डर फ़ीस 25 रुपये है।'
                    result.hinglish+=' COD '+('available hai.' if enabled else 'available nahi hai.')+' COD limit 10,000 rupees aur per-order fee 25 rupees hai.'
                    result.ids.append('PAY-2'); result.facts['cod_available']=enabled
                    amounts=[int(v) for v in re.findall(r'(?<!\d)\d{1,5}(?!\d)',query.replace(',',''))]
                    if any(v>10000 for v in amounts):
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
                elif intent=='unknown' and re.search(r'status|stage|reached|track|shipment|parcel|arriv|where|when|कहाँ|कब',safe_text,re.I): s.pending_intent='delivery'; s.pending_issue=safe_text
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
        # Conversation style and authentication instructions are explicit
        # guard-policy lookups; answer-policy evidence still comes from search.
        if plan.decision=='clarify':
            plan.ids=list(dict.fromkeys(plan.ids+['STY-5']))
            pool += [r.kb.chunks['STY-5'].public()]
            if 'IDV-1' in plan.ids and 'order ID' in plan.en:
                plan.ids=list(dict.fromkeys(plan.ids+['IDV-2']))
                pool += [r.kb.chunks['IDV-2'].public()]
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
            plan.facts={}; plan.intent='unsupported'
            # An unknown general-information question receives an uncertainty
            # answer. An unsupported claim within a recognized policy domain
            # is refused; neither path asserts an invented company rule.
            plan.decision='answer' if intent=='unknown' else 'refuse'
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
