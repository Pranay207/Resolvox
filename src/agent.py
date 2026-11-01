"""Session-scoped state machine. Credentials are discarded at the tool boundary."""
from dataclasses import dataclass,field
from functools import lru_cache
import json,os,re,time
from types import SimpleNamespace
from .answering import Policy,Plan,classify
from .config import REFERENCE_DATE
from .data import Data
from .kb import KnowledgeBase
from .retrieval import Retriever,query_facets
from .tools_wrapper import Tools
from .normalize import order_id,proof_value,language,redact,number_words,public_acronyms
from .llm import LLM,LLMUnavailable
from .response_runtime import service_failure, service_message
from .grounding import compatible,abstention
from .document_answers import document_reply
from .generation_diagnostics import failure_diagnostics, failure_validation_error, safe_attempt_metrics
from .document_context import build_context
from .source_inputs import source_input_clarification, make_source_input_workflow, resume_source_input, workflow_binding_sources, ModelCallProbe
from .source_selection import select_policy_context,focus_policy_context
from .operational_explanations import resolve_business_escalation, business_explanation, ticket_outcome, unresolved_business

def _private_delivery_facet_request(query):
    pattern = (
        r'\b(?:tell|show|read|give|share|list|confirm|check|look\s+up)\b.{0,65}'
        r'\b(?:items?|contents?|amount|total|address|payment\s+details?|refund\s+details?|RRN|'
        r'contact\s+details?|delivery\s+pincode|bank\s+details?)\b|'
        r'\b(?:what\s+(?:is|are|was|were))\b.{0,40}\b(?:items?|amount|total|address|refund|payment)\b|'
        r'\b(?:its|my|our|this\s+order[\x27\u2019]s)\s+(?:items?|contents?|amount|total|address|'
        r'refund\s+details?|payment\s+details?|RRN|contact\s+details?)\b|'
        r'(?:आइटम|सामान|राशि|पता|रिफंड\s*विवरण|भुगतान\s*विवरण).{0,25}(?:बताइए|बताओ|दिखाइए)|'
        r'\b(?:items?|amount|address|refund\s+details?)\b.{0,25}\b(?:batao|batayein|dikhao)\b')
    return bool(re.search(pattern,query,re.I))


def _delivery_capability_request(query):
    delivery = r'\b(?:deliver\w*|arriv\w*|courier|carrier|shipment|parcel)\b|डिलीवर|डिलीवरी|डिलिवरी|पहुँचा'
    capability = (
        r'\b(?:can|could|would|will)\s+(?:you|the\s+(?:courier|carrier))\b.{0,70}'
        r'\b(?:promise|guarantee|commit|offer|schedule|arrange)\b|'
        r'\b(?:can|could|may)\s+(?:i|we)\b.{0,55}\b(?:choose|schedule|book|select|request|guarantee)\b|'
        r'\b(?:do|does)\s+(?:you|the\s+(?:courier|carrier))\b.{0,45}\b(?:offer|guarantee|promise)\b|'
        r'\bkya\b.{0,50}\b(?:guarantee|promise|vaada|vada|schedule|arrange)\b|'
        r'क्या.{0,50}(?:गारंटी|वादा|तय|समय\s*चुन)')
    return bool(re.search(delivery,query,re.I) and re.search(capability,query,re.I))


def _public_delivery_capability(query):
    """Distinguish a proposed service capability from a private record lookup.

    Finite request-language routing only: this never establishes availability,
    a promised time, or a company restriction. Compound record requests retain
    authentication. No clock values, source IDs, or policy answers are encoded.
    """
    private = (
        r'\b(?:track\w*|where\s+(?:is|are)|(?:order|shipment|parcel)(?:[\x27\u2019]s)?\s+status|'
        r'status\s+(?:of|for)|(?:recorded|promised|expected)\s+(?:delivery\s+)?date|'
        r'ETA|estimated\s+arrival|delivery\s+date\s+(?:for|of)|when\s+will\s+(?:it|this|that)|'
        r'out\s+for\s+delivery|already\s+(?:shipped|delivered|dispatched)|arrived\s+yet)\b|'
        r'\b(?:has|have|did)\s+(?:my|our|the|this)\s+(?:order|parcel|shipment)\b|'
        r'\b(?:where|when)\b.{0,35}\b(?:my|our|this)\s+(?:order|parcel|shipment)\b|'
        r'स्थिति|ट्रैक|कहाँ|कहां|रिकॉर्ड|\b(?:kahan|kahaan|status|record)\b')
    if _private_delivery_facet_request(query):
        return False
    if re.search(private,query,re.I):
        return False
    return _delivery_capability_request(query)


def _public_category_candidate(policy, text, *, awaiting_category=False):
    """Bind ambiguous household/location words only in a product/category role.

    This finite language filter is not policy evidence. Source workflow
    validation still decides whether a bare category choice is allowed.
    """
    home = r'(?:\b(?:home|ghar|ghr)\b|(?<!\w)(?:\u0918\u0930|\u0939\u094b\u092e)(?!\w))'
    noun = (r'(?:goods?|products?|items?|appliances?|furnishings?|decor|category|section|kitchen|'
            r'samaan|saman|shreni|\u0938\u093e\u092e\u093e\u0928|\u0909\u0924\u094d\u092a\u093e\u0926|'
            r'\u0935\u0938\u094d\u0924\u0941|\u0936\u094d\u0930\u0947\u0923\u0940|\u0915\u0948\u091f\u0947\u0917\u0930\u0940|\u0930\u0938\u094b\u0908)')
    suffix = (r'\s*(?:(?:ka|ki|ke|and|or|aur|ya|&|\u0915\u093e|\u0915\u0940|\u0915\u0947|\u0914\u0930)\s*)?'
              + noun + r'(?!\w)')
    named = (r'(?:category|section|shreni|\u0936\u094d\u0930\u0947\u0923\u0940|\u0915\u0948\u091f\u0947\u0917\u0930\u0940)'
             r'\s*(?:(?:is|hai|=|:)\s*)?$')
    negative = (r"\b(?:not|never|no|nahi|nahin|cannot|[A-Za-z]+n['\u2019]t)\b|\u0928\u0939\u0940\u0902")
    policy_action = r'\b(?:return\w*|refund\w*|exchang\w*|warrant\w*|repair\w*|cover\w*)\b'
    bare = awaiting_category and bool(re.fullmatch(r'\s*' + home + r'\s*[.!?]*\s*', text, re.I))
    scoped = text
    for mention in reversed(list(re.finditer(home, text, re.I))):
        before = re.split(r'[,;.!?\u0964\n]|\b(?:but|however|yet|lekin|magar)\b|\u0932\u0947\u0915\u093f\u0928', text[:mention.start()], flags=re.I)[-1][-60:]
        after = text[mention.end():]
        description = re.match(suffix, after, re.I)
        end = mention.end() + (description.end() if description else 0)
        post_negative = re.match(
            r'\s*(?:(?:is|are|hai|hain)\s+)?(?:not|nahi|nahin|\u0928\u0939\u0940\u0902)(?:\s+(?:hai|hain|\u0939\u0948|\u0939\u0948\u0902))?\s*(?:[,;.!?\u0964]|$)',
            text[end:], re.I)
        positive = bare or description or re.search(named, before, re.I)
        operators = list(re.finditer(negative, before, re.I))
        tail = before[operators[-1].end():] if operators else ''
        # Category selection/denial differs from a negative policy-action
        # question. Contrast clauses and not-only quantifiers retain scope.
        denied = bool(post_negative or (operators and not re.match(r'\s*only\b', tail, re.I)
                       and not re.search(policy_action, tail, re.I)))
        if positive and not denied:
            scoped = scoped[:mention.start()] + 'home' + scoped[mention.end():]
        else:
            # Removing a negated noun phrase also removes its coordinated noun.
            scoped = scoped[:mention.start()] + ' ' + scoped[end if denied else mention.end():]
    return policy._category(scoped)


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
    source_input_workflow:dict=field(default_factory=dict)

class Agent:
    def __init__(self,resources:Resources|None=None,compose:bool|None=None):
        self.resources=resources or globals()['resources'](); self.state=State()
        self.compose=(os.getenv('COMPOSE_WITH_LLM','true').lower()=='true') if compose is None else compose
    def _verification_plan(self,kind:str) -> Plan:
        if kind=='locked': return Plan('verification','refuse',"I cannot share order details because verification failed twice. Please contact support from your registered phone; I can still help with general policies.",'दो बार सत्यापन असफल हुआ, इसलिए ऑर्डर की जानकारी साझा नहीं कर सकती। पंजीकृत फ़ोन से सपोर्ट से संपर्क करें; सामान्य पॉलिसी में मदद कर सकती हूँ।','Verification do baar fail hua, order details share nahi kar sakti. Registered phone se support contact karein; general policy mein help kar sakti hoon.',['IDV-1','IDV-3'])
        if kind=='retry': return Plan('verification','clarify',"That did not match. Please try the last 4 digits of your registered phone again.",'जानकारी मेल नहीं खाई। कृपया पंजीकृत फ़ोन के अंतिम 4 अंक दोबारा बताएँ।','Match nahi hua. Registered phone ke last 4 digits ek baar phir batayein.',['IDV-3'])
        return Plan('verification','clarify','Please provide one verification detail: the last 4 digits of your registered phone or the order delivery pincode.','कृपया एक सत्यापन जानकारी दें: पंजीकृत फ़ोन के अंतिम 4 अंक या ऑर्डर का डिलीवरी पिनकोड।','Ek verification detail dein: registered phone ke last 4 digits ya order ka delivery pincode.',['IDV-1','IDV-2'])
    def respond(self,text:str,language_hint:str|None=None) -> dict:
        text=public_acronyms(text)
        if language_hint not in {None,'en','hi','hi-en'}: raise ValueError('Core agent supports en, hi and hi-en language hints')
        start=time.perf_counter(); s=self.state; r=self.resources; s.turn+=1; s.language=language_hint or language(text,s.language)
        intent=classify(text); oid=order_id(text); calls=[]; candidates=[]; pool=[]; auth_source_ids=[]; retrieval_ms=0.0
        # An order switch invalidates authentication and deferred questions in
        # every branch, including urgent escalation and privacy refusals.
        if oid and oid!=s.order_id:
            if s.order_id is not None: s.pending_intent=''; s.pending_issue=''; s.last_intent=''
            s.order_id=oid; s.order=None
            s.public_context={}
        if s.last_intent=='safety' and intent not in {'privacy','fraud','legal','human'} and re.search(r'try|test|charg|plug|use|turn.{0,4}on|repair|जाँच|चार्ज|चलाऊ|इस्तेमाल',text,re.I):
            intent='safety'
        credential=bool(re.search(r'(last.?four|last.?4|digits|(?:phone|mobile|number).{0,18}(?:ends?|suffix|last|ending)|आख़?िरी|अंतिम|अंक|aakhri|aakhiri|akhri)',text,re.I)) or bool(s.order_id and not s.order and re.search(r'pincode|pin code|पिनकोड',text,re.I))
        if s.order_id and re.fullmatch(r'\s*[\d०-९]{4}(?:[\d०-९]{2})?\s*',text): credential=True
        proof=proof_value(text) if credential or (s.order_id and not s.order and not oid) else None
        safe_text=redact(text,credential_turn=bool(proof) or credential)
        public_pins=re.findall(r'(?<!\d)\d{6}(?!\d)',text) if not credential and not proof and not (s.order_id and not s.order) else []
        answer_query=safe_text
        contextual_text=safe_text
        source_input_resumed=None
        workflow=s.source_input_workflow
        s.source_input_workflow={}
        if workflow and not (oid or credential or proof) and (intent in {'unknown',workflow.get('intent')} or (intent=='payment' and workflow.get('requirement',{}).get('key')=='payment_method')):
            bound_sources=workflow_binding_sources(workflow,r.kb.chunks,r.data.products,r.data.pincodes)
            source_input_resumed=resume_source_input(workflow,safe_text,bound_sources,order_id=s.order_id,
                candidate_product=r.policy.product(safe_text),
                candidate_category=_public_category_candidate(r.policy,safe_text,
                    awaiting_category=workflow.get('awaiting_reply') is True
                    and workflow.get('requirement',{}).get('key')=='return_category'))
            if source_input_resumed:
                intent=source_input_resumed['intent']
                s.public_context=dict(source_input_resumed['public_context'])
                s.source_input_workflow=source_input_resumed['workflow']
                answer_query=source_input_resumed['question']
                contextual_text=source_input_resumed['question']
        explicit_skus=[prefix.upper()+'-'+digits for prefix,digits in
                       re.findall(r'\b(ELE|FSH|HOM|BKS|INR|BEA|GRO|DIG)[-\s]*(\d{4})\b',number_words(safe_text),re.I)]
        unknown_skus=[value for value in explicit_skus if value not in r.data.products]
        # Carry explicit public slots, never concatenate old utterances: that
        # can introduce competing SKUs and superseded dates into a follow-up.
        if not s.order_id and not credential and intent not in {'privacy','safety','fraud','legal','human'}:
            followup=bool(re.search(r'\b(it|this|that|instead|actually|correction|corrected|its|same|what about|then|now|ise|isko|uska)\b|असल|यह|तारीख',safe_text,re.I)) or bool(source_input_resumed)
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
                category=(source_input_resumed['value']
                    if source_input_resumed and source_input_resumed['key']=='return_category'
                    else _public_category_candidate(r.policy,safe_text))
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
        if source_input_resumed and source_input_resumed['key']=='payment_method' and source_input_resumed.get('source_label'):
            contextual_text+='\nPublic payment method: '+source_input_resumed['source_label']+'.'
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
                        'That postal code is not listed in the supplied pincode table, so I cannot confirm its availability.',
                        'वह पिनकोड दी गई तालिका में नहीं है; उसकी उपलब्धता की पुष्टि नहीं कर सकती।',
                        'Woh pincode supplied table mein listed nahi hai; uski availability confirm nahi kar sakti.',
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
            if not order and _delivery_capability_request(query) and _private_delivery_facet_request(query):
                # Compound private-record requests still require the existing
                # identity workflow even if refund wording changed the intent.
                s.pending_intent=kind; s.pending_issue=query
                result=self._verification_plan('ask') if s.order_id else Plan(
                    'delivery','clarify','What is your order ID?','आपका ऑर्डर नंबर क्या है?',
                    'Aapka order ID kya hai?',['IDV-1','STY-5'])
            elif (kind=='delivery' and result.decision=='clarify' and 'IDV-1' in result.ids
                    and _public_delivery_capability(query)):
                # A proposed service capability needs document evidence, not
                # private order access. Keep the actual search context only.
                if s.pending_issue in {query,safe_text}:
                    s.pending_issue=''; s.pending_intent=''
                result=Plan(kind,'answer','','','',[])
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
        business_route=None
        business_ticket=None
        original_plan_escalates=plan.decision=='escalate'
        try:
            if not (unknown_skus and plan.decision=='clarify'):
                business_route=resolve_business_escalation(answer_query,intent,plan.intent,original_plan_escalates,
                    r.kb,pool,r.data,verified_order=s.order,public_context=s.public_context)
        except (ValueError,TypeError) as exc:
            business_route={'state':'unresolved','validation_error':str(exc)}
        if business_route:
            original_kind=intent if intent not in {'unknown','verification'} else 'policy'
            if business_route['state']=='escalate':
                business_kind={'repeat_contact':'repeat','high_value_damage':'damage','refund_overdue':'refund'}[business_route['reason']]
                plan=Plan(business_kind,'escalate','','','',
                    business_route['decision']['source_ids'],business_route['reason'])
                pool=business_route['sources']+pool
            elif original_plan_escalates or plan.intent=='repeat' or business_route['state']=='unresolved':
                # A compiled old comparison cannot authorize a business action
                # when the actual rule is changed, missing or not met.
                plan=Plan(original_kind,'answer','','','',[])
        if plan.decision=='escalate':
            reason=plan.reason or plan.intent
            ticket_key=(s.order_id,reason)
            if ticket_key in s.tickets: ticket=s.tickets[ticket_key]
            else:
                summary=f'Issue: {answer_query[:350]}. Intent: {plan.intent}. Order: {s.order_id or "not provided"}. Checked: '+(', '.join(plan.ids))+f'. Verified caller: {bool(s.order)}. Escalation reason: {reason}. No outcome promised.'
                try: ticket,trace=r.tools.ticket(summary,s.order_id,reason,plan.intent); calls.append(trace)
                except (OSError,ValueError): ticket={'created':False}
                if ticket.get('created'): s.tickets[ticket_key]=ticket
            business_ticket=ticket if business_route and business_route['state']=='escalate' else None
            if ticket.get('created'):
                plan.en=plan.en.replace(' I will request a ticket.','').replace(' I will request a support ticket.','').replace('; I will request a support ticket.','.')
                plan.en+=' A ticket has been created; a human colleague will contact you.'
                plan.hi+=' टिकट बन गया है; मानव सहयोगी संपर्क करेंगे।'
                plan.hinglish+=' Ticket create ho gaya; human colleague contact karenge.'
            else:
                plan.en+=' The ticket could not be created. Please contact support directly.'
                plan.hi+=' टिकट नहीं बन सका। कृपया सीधे सपोर्ट से संपर्क करें।'
                plan.hinglish+=' Ticket create nahi hua. Support ko directly contact karein.'
        catalog_clarification=bool(unknown_skus) and plan.decision=='clarify'
        unlisted_pincode=plan.facts.get('pincode_listed') is False
        guard=catalog_clarification or unlisted_pincode or plan.intent in {'verification','privacy','safety','fraud','legal','human','repeat','unclear_audio','greeting'} or plan.decision=='escalate' or (plan.decision=='clarify' and 'IDV-1' in plan.ids)
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
        validation_error=None; llm_ms=0.0; citations=[]; generation={}; generation_context_sources=[]; context_selection={}
        if business_route and business_route['state']=='unresolved':
            source_ids=[];sources=[];supported=False
            answer=unresolved_business(s.language);plan.decision='answer'
            composition='abstained_unbound_business_rule'
            validation_error=business_route.get('validation_error','unbound_business_rule')
            generation={'reply_kind':'uncertainty','covered':False,'evidence_status':'insufficient_evidence',
                        'decision_origin':'host_unbound_business_rule','generation_attempts':0,
                        'operational_rule_decisions':business_route.get('decisions',[])}
        elif business_route and business_route['state']=='escalate':
            source_ids=[];sources=[];supported=False
            outcome=ticket_outcome(business_ticket,s.language)
            answer=outcome;composition='operational_handover'
            generation={'decision_origin':'host_source_bound_handover','generation_attempts':0,
                        'operational_rule_decisions':business_route['decisions'],
                        'tool_outcome_origin':'actual_create_ticket_result'}
            if self.compose:
                began=time.perf_counter();model_probe=ModelCallProbe(r.llm)
                generation_context_sources=business_route['sources']
                try:
                    generated,plan.facts=business_explanation(model_probe,answer_query,s.language,business_route,
                        r.data,verified_order=s.order,public_context=s.public_context)
                    answer=generated['answer']+' '+outcome
                    source_ids=generated['source_ids'];sources=[available[sid] for sid in source_ids]
                    citations=generated.get('citations',[]);supported=bool(source_ids)
                    generation.update({key:value for key,value in generated.items() if key not in {'answer','source_ids','citations','decision'}})
                    generation['explanation_decision']=generated['decision']
                    composition='source_generated_handover' if source_ids else 'uncertain_handover'
                except (LLMUnavailable,ValueError,TypeError) as exc:
                    generation.update(failure_diagnostics(exc, attempts=model_probe.calls,
                        last_metrics=model_probe.last_metrics))
                    validation_error=failure_validation_error(exc)
                    answer=abstention(s.language)+' '+outcome
                    composition='operational_handover_generation_failed'
                llm_ms=1000*(time.perf_counter()-began) if model_probe.calls else 0.0
            else:
                excerpt_sources=business_route['sources']
                answer='Retrieved document excerpts (offline; no generated answer):\n'+'\n\n'.join(row['text'][:1100] for row in excerpt_sources)+'\n'+outcome
                source_ids=[row['id'] for row in excerpt_sources];sources=excerpt_sources
                composition='document_excerpts_handover';supported=bool(source_ids)
            plan.decision='escalate'
        elif guard:
            # Fixed security and workflow messages carry no business answer.
            supported=compatible(plan.ids,pool)
            source_ids=list(dict.fromkeys(plan.ids)) if supported else []
            sources=[available[c] for c in source_ids]
            answer=plan.text(s.language) if supported else abstention(s.language)
            composition='deterministic_guardrail' if supported else 'abstained_missing_evidence'
        else:
            # Planner text, policy constants and authored summaries are never
            # supplied to generation or used as a customer-facing fallback.
            # IDs are routing hints only: every section must be in actual search.
            # Actual retrieved policy rows survive an unfamiliar legacy route.
            # Planner IDs are ordering hints; style alone is not evidence.
            selected=select_policy_context(pool,plan.ids)
            if selected and plan.intent=='unsupported':
                plan.intent=intent if intent!='unknown' else 'policy'
            context_query=answer_query+('\nPublic catalog pincode: '+public_pins[0] if len(public_pins)==1 else '')
            plan.facts=build_context(context_query,selected,r.data,
                verified_order=s.order,public_context=s.public_context)
            if self.compose and selected and not s.order_id:
                available_context_ids=[row['id'] for row in selected]
                # Resolve source-bound missing inputs before any context focus.
                # Private records and pending source workflows retain full recall.
                if 'required_application_inputs' not in plan.facts:
                    focused=focus_policy_context(selected,candidates,plan.ids,query=answer_query,
                        facet_count=len(query_facets(answer_query)))
                    if len(focused)<len(selected):
                        selected=focused
                        plan.facts=build_context(context_query,selected,r.data,
                            verified_order=s.order,public_context=s.public_context)
                context_selection={'mode':'ranked_sources_with_dependencies',
                    'available_source_ids':available_context_ids,
                    'focused_source_ids':[row['id'] for row in selected]}
            supported=bool(selected)
            source_ids=[]; sources=[]
            answer=abstention(s.language)
            composition='abstained_missing_evidence'
            if selected and self.compose:
                began=time.perf_counter()
                generation_context_sources=selected
                model_probe=ModelCallProbe(r.llm)
                try:
                    generated=source_input_clarification(plan.facts,selected,s.language)
                    if generated is None:
                        s.source_input_workflow={}
                        generated=document_reply(model_probe,answer_query,s.language,selected,
                            facts=plan.facts,private=bool(s.order_id),context_provenance=True,fast_uncertainty=True)
                    else:
                        generation_context_sources=[]
                        s.source_input_workflow=make_source_input_workflow(plan.facts,selected,answer_query,
                            plan.intent,s.public_context,s.order_id)
                    if 'context_source_ids' in generated:
                        supplied_ids = set(generated['context_source_ids'])
                        generation_context_sources = [row for row in selected if row['id'] in supplied_ids]
                    answer=generated['answer']; source_ids=generated['source_ids']
                    citations=generated.get('citations',[])
                    sources=[available[c] for c in source_ids]
                    plan.decision=generated['decision']
                    composition='grounded_llm' if source_ids else ('grounded_clarification' if plan.decision=='clarify' else 'abstained_missing_evidence')
                    supported=bool(source_ids)
                    if generated.get('decision_origin')=='host_source_table_input':
                        composition='source_input_clarification'
                    generation={k:v for k,v in generated.items() if k not in {'answer','source_ids','citations','decision'}}
                    if source_input_resumed:
                        generation['workflow_input_resolution']={key:source_input_resumed[key] for key in ('key','value','source_ids')}
                        generation['workflow_input_resolution']['input_status']='customer_provided_unverified' if source_input_resumed.get('value') is not None else 'unresolved'
                except (LLMUnavailable,ValueError,TypeError) as exc:
                    generation.update(failure_diagnostics(exc, attempts=model_probe.calls,
                        last_metrics=model_probe.last_metrics))
                    validation_error=failure_validation_error(exc)
                    composition='abstained_model_or_evidence'
                    plan.decision='answer' if intent=='unknown' else 'refuse'
                llm_ms=1000*(time.perf_counter()-began) if model_probe.calls else 0.0
            elif selected:
                # Explicit offline mode is an inspectable source-excerpt view,
                # not a substitute prewritten policy answer or a model result.
                excerpt_sources=selected
                excerpts=[x['text'][:1100] for x in excerpt_sources]
                answer='Retrieved document excerpts (offline; no generated answer):\n'+'\n\n'.join(excerpts)
                source_ids=[x['id'] for x in excerpt_sources]; sources=excerpt_sources
                citations=[{'id':x['id'],'quote':quote} for x,quote in zip(excerpt_sources,excerpts)]
                composition='document_excerpts'; plan.decision='answer'
            else:
                plan.facts={}; plan.decision='answer' if intent=='unknown' else 'refuse'
            if composition.startswith('abstained'):
                supported=False
                plan.intent='unsupported'
        service_error=service_failure(generation)
        if service_error:
            # Infrastructure failure is not evidence that a policy is absent.
            answer=service_message(service_error,s.language)
            if composition=='operational_handover_generation_failed':
                answer+=' '+outcome
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
                'retrieved_chunk_ids':source_ids,'sources':sources,'retrieval_candidates':[{'id':x['chunk'].id,'score':x['score'],'dense_score':x['dense_score'],**{key:x[key] for key in ('retrieval_role','direct_rank','dependency_weight') if key in x}} for x in candidates],
                'tool_calls':calls,'facts':plan.facts,'verified':bool(s.order),'reference_date':REFERENCE_DATE.isoformat(),'composition':composition,
                'retrieval_mode':r.retriever.dense_status,'retrieval_k':12,'retrieval_direct_k':12,'retrieval_dependency_limit':4,'retrieval_candidate_limit':16,'retrieval_returned_count':len(candidates),'retrieval_direct_count':sum(x.get('retrieval_role')=='direct' for x in candidates),'retrieval_dependency_count':sum(x.get('retrieval_role')=='dependency' for x in candidates),'evidence_supported':supported,
                'validation_error':validation_error,'citations':citations,'generation':generation,'service_error':service_error,
                'generation_context_sources':generation_context_sources,'context_selection':context_selection,
                'llm':(safe_attempt_metrics(r.llm.last_metrics) if generation.get('generation_failed')
                       else r.llm.last_metrics.copy()) if llm_ms else {},
                'timings':{'retrieval_ms':round(retrieval_ms,2),'llm_ms':round(llm_ms,2)},
                'latency_ms':round(1000*(time.perf_counter()-start),2)}
