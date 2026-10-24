"""Evidence-backed policy plans. No practice files are imported at runtime."""
from dataclasses import dataclass,field
from datetime import date,timedelta
import re
from .config import REFERENCE_DATE
from .dates import parse_date,business_add,business_elapsed,return_deadline,return_window,fmt,partial_refund
from .normalize import number_words

@dataclass
class Plan:
    intent:str
    decision:str
    en:str
    hi:str
    hinglish:str
    ids:list[str]=field(default_factory=list)
    reason:str|None=None
    facts:dict=field(default_factory=dict)
    def text(self,language:str) -> str: return self.hi if language=='hi' else self.hinglish if language=='hi-en' else self.en

def has(text:str,pattern:str) -> bool: return bool(re.search(pattern,text,re.I))

def affirmed(text:str,pattern:str) -> bool:
    """Detect an asserted hazard while respecting local, enumerated negation."""
    for match in re.finditer(pattern,text,re.I):
        prefix=re.split(r'[.;!?।]|\b(?:but|however|lekin)\b|लेकिन',text[:match.start()],flags=re.I)[-1][-85:]
        suffix=re.split(r'[.;!?।]|\b(?:but|however|lekin)\b|लेकिन',text[match.end():],flags=re.I)[0][:30]
        if re.search(r'\b(?:no|not|without|never|nahi|nahin)\b|नहीं|नही|बिना',prefix,re.I): continue
        if re.search(r'\b(?:bilkul\s+)?(?:nahi|nahin)\b|नहीं|नही',suffix,re.I): continue
        return True
    return False

def classify(text:str) -> str:
    t=text.lower()
    if has(t,r"\b(?:ignore|bypass|override)\b|system prompt|internal notes|another customer|someone else|person who ordered|other.*customer|दूसरे.*ग्राहक|निजी.*जानकारी") or has(t,r'(?:read|show|reveal|share|give|tell).{0,60}(?:(?:full|registered|account).{0,20}(?:phone|email|contact|address)|internal\s+notes)'): return 'privacy'
    if affirmed(t,r'\b(?:swell\w*|swollen|bulg\w*|puff\w*|burning|burnt|sparks?|smoke|injur\w*|overheat\w*)\b|battery.{0,15}\b(?:hot|heat)\b|आग|धुआ|चिंगारी|बैटरी.{0,15}फूल|jal.{0,10}raha'): return 'safety'
    if has(t,r"\b(?:never\s+(?:placed|ordered)|didn.t\s+order|not\s+mine|fraud)\b|\b(?:did\s+not|didn.t)\s+(?:place|make)\s+(?:(?:this|the|an?|any|that|my)\s+)?(?:order|purchase|payment|transaction|charge)\b|\bunauthori[sz]ed\s+(?:activity|payment|order|charge|transaction|account|purchase)\b|(?:मैंने|मेरे).{0,30}(?:ऑर्डर|खरीद|भुगतान).{0,20}नहीं"): return 'fraud'
    if has(t,r'(legal action|consumer court|police|lawsuit|वकील|पुलिस|अदालत)'): return 'legal'
    if has(t,r'\b(?:human|representative|colleague|real person|speak to a person|talk to a person|agent please|insaan|insan)\b|\btransfer\s+me\b|इंसान|मानव|कर्मचारी'): return 'human'
    if has(t,r'(third time|third.*contact|teesri|तीसरी|again.*week)'): return 'repeat'
    if has(t,r'(gift.?wrap|student discount|gst|invoice|midnight|physical store|store near|shop near|shop in|insurance|दुकान)'): return 'unknown'
    if has(t,r'(voucher|free money|300 rup|500 rup|वाउचर)') or (has(t,r'compensat|मुआव') and not has(t,r'\b(?:express|standard|policy|appl\w*)\b')): return 'compensation'
    if has(t,r'(coupon|कूपन)'):
        return 'refund' if has(t,r'\b(?:refund|return\w*)\b') and has(t,r'\b(?:partial|discount|minimum|share|basket|remaining)\b') else 'coupon'
    if has(t,r'(not.*home|not at home|courier comes|delivery attempt|घर.*नहीं|ghar.*nahi)'): return 'attempts'
    if has(t,r"won.t\s+(?:turn|power)\s+on|not\s+powering|speaker.{0,25}(?:not|won.t|will not|no).{0,12}(?:power|turn|switch)|earbuds?.{0,30}(?:not working|silent|chup|one side|ek side)|watch.{0,15}(?:not|won.t).{0,10}sync|charg(?:ing|es)\s+slowly"): return 'troubleshoot'
    if has(t,r'\b(?:warrant(?:y|ies)|assured|manufacturer|brand)\b|वारंटी|अश्योर्ड') and has(t,r'\b(?:cover\w*|liquid|physical|repair\w*|duration\w*|month\w*|warrant\w*)\b|कवर'): return 'warranty'
    if has(t,r'(damage|torn|crack|wrong item|missing item|expired|defect|टूटा|टूट|खराब|गलत|kharab|tuta|toota)'): return 'damage'
    if has(t,r'\b(?:warrant(?:y|ies)|assured)\b|वारंटी|अश्योर्ड'): return 'warranty'
    if has(t,r'\b(?:plus|membership)\b|प्लस|सदस्य') and has(t,r'cancel|refund|रकम.*वापस|सदस्यता.*वापस'):
        membership_refund=has(t,r'cancel|membership.{0,30}full refund|refund.{0,20}membership|रकम.*वापस|सदस्यता.*वापस')
        return 'cancel' if membership_refund and not has(t,r'\b(?:return|pickup|bank|upi|card)\b') else 'refund'
    if has(t,r'(cancel|stop it|कैंसिल|रद्द)'): return 'cancel'
    if has(t,r'(refund|rrn|refund reference|money.*(?:back|revers)|रिफ़ंड|रिफंड|पैसे.*वापस)'): return 'refund'
    if has(t,r'(pickup|pick.up|collect|पिकअप|पिकअप|उठाने)') and not has(t,r'(store|दुकान)'): return 'pickup'
    if has(t,r'(return|send.*back|रिटर्न|लौटा|वापस|badal|exchange)'): return 'return'
    if has(t,r'(change|update)') and has(t,r'(address)'): return 'delivery'
    if has(t,r'\b(?:late|delay\w*)\b|arriv.*late|देर|लेट') or (has(t,r'compensat|मुआव') and has(t,r'express|standard')): return 'late_delivery'
    if has(t,r'(ship.*when|when.*ship|kab ship|कब.*शिप|ship hua|shipped)') and not has(t,r'(cancel|return)'): return 'shipping_date'
    if has(t,r'(deliver|shipping|express|change.*address|redirect|where is|hasn.t arrived|order.*status|track|स्थिति|कहाँ|कब.*आए|kab.*aay|kahaan|kahan)'): return 'delivery'
    if has(t,r'(cod|cash on delivery|payment|wallet|भुगतान|कैश)'): return 'payment'
    if has(t,r'(plus|membership|प्लस|सदस्य)'): return 'plus'
    if has(t,r'(hello|^hi\b|help|नमस्ते|मदद|help chahiye)'): return 'greeting'
    return 'unknown'

class Policy:
    def __init__(self,kb,data):
        self.kb=kb; self.data=data
        self.windows={}
        for line in (kb.chunks['RET-2'].text if 'RET-2' in kb.chunks else '').splitlines():
            m=re.search(r'\|\s*(\d+) days\s*\|\s*`(\w+)`',line)
            if m: self.windows[m[2]]=int(m[1])
        self.refunds={}
        for line in (kb.chunks['REF-2'].text if 'REF-2' in kb.chunks else '').splitlines():
            if not line.startswith('|'): continue
            cells=[x.strip() for x in line.strip('|').split('|')]
            if len(cells)!=2: continue
            span=re.search(r'(\d+) to (\d+)',cells[1]); lower=cells[0].lower()
            key='cod_bank' if 'neft' in lower else 'cod_wallet' if 'cash-on' in lower else 'upi' if 'upi' in lower else 'card' if 'card' in lower else 'netbanking' if 'net banking' in lower else 'wallet' if 'wallet' in lower else None
            if key: self.refunds[key]=(int(span[1]),int(span[2])) if span else (0,0)
    def product(self,text:str,order:dict|None=None) -> dict|None:
        t=number_words(text).lower(); matches=[]
        # Explicit identifiers outrank a title shared by several catalog rows.
        # Check all SKUs before attempting any title/fuzzy match.
        explicit=[p for sku,p in self.data.products.items() if re.search(r'(?<![a-z0-9])'+re.escape(sku.lower()).replace(r'\-',r'[-\s]*')+r'(?![a-z0-9])',t)]
        if explicit: return explicit[0] if len(explicit)==1 else None
        titles=[p for p in self.data.products.values() if p['title'].casefold() in text.casefold()]
        if len(titles)==1: return titles[0]
        if len(titles)>1: return None
        for sku,p in self.data.products.items():
            words=set(re.findall(r'[a-z0-9]+',p['title'].lower())); query=set(re.findall(r'[a-z0-9]+',text.lower()))
            score=len(words&query)/max(1,len(words))
            if len(words&query)>=2 and score>=.65: matches.append((score,p))
        if matches:
            best=max(x[0] for x in matches); tied=[p for score,p in matches if score==best]
            if len(tied)==1: return tied[0]
            return None
        if order and len(order.get('items',[]))==1: return self.data.products[order['items'][0]['sku']]
        return None
    def _date_in(self,text:str) -> date|None:
        iso=re.search(r'\b(2026-\d{2}-\d{2})\b',text)
        if iso:
            try:return date.fromisoformat(iso[1])
            except ValueError:return None
        months={'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,'अक्टूबर':10,'जुलाई':7,'अगस्त':8,'नवंबर':11}
        for month,n in months.items():
            m=re.search(r'(\d{1,2})\s+'+month+r'(?:\s+(2026))?',text,re.I)
            if m:
                try:return date(2026,n,int(m[1]))
                except ValueError:return None
        return None
    def plan(self,text:str,intent:str,order:dict|None=None) -> Plan:
        return self.plan_multi(text,intent,order)

    def plan_multi(self,text:str,intent:str,order:dict|None=None) -> Plan:
        """Combine explicitly requested policy aspects without expanding evidence.

        The Policy instance still sees only its caller's retrieved KB view. Each
        component keeps its own governing IDs for the existing evidence contract.
        """
        primary=self._plan_single(text,intent,order)
        if intent in {'safety','fraud','privacy','human','legal','repeat','verification','greeting'} or primary.decision=='escalate': return primary
        topics=[intent]
        if has(text,r'\b(?:return\w*|send.{0,15}back)\b|रिटर्न|लौटा') and has(text,r'\b(?:warrant\w*|assured|manufacturer.{0,12}cover|brand.{0,12}cover)\b|वारंटी'):
            topics.extend(['return','warranty'])
        if has(text,r'\b(?:cancel\w*)\b|कैंसिल|रद्द') and has(text,r'(?:change|redirect|update|बदल).{0,25}(?:address|office|पता)'):
            topics.append('delivery')
        plans=[primary]
        for topic in dict.fromkeys(topics):
            if topic!=intent:
                item=self._plan_single(text,topic,order)
                if item.intent!='unsupported': plans.append(item)
        if intent=='return' and has(text,r'\b(?:window|period|days?|long|deadline)\b|दिन|अवधि') and 'RET-4' in primary.ids:
            product=self.product(text,order); category=self._category(text,product)
            item=self._return_window(text,order,product,category)
            if item.intent!='unsupported' and item.decision!='clarify': plans.append(item)
        if len(plans)==1: return primary
        merged=Plan(intent,'refuse' if any(x.decision=='refuse' for x in plans) else 'clarify' if any(x.decision=='clarify' for x in plans) else 'answer',
                    ' '.join(dict.fromkeys(x.en for x in plans)), ' '.join(dict.fromkeys(x.hi for x in plans)),
                    ' '.join(dict.fromkeys(x.hinglish for x in plans)),
                    list(dict.fromkeys(cid for x in plans for cid in x.ids)),facts={key:value for x in plans for key,value in x.facts.items()})
        if any(x.facts.get('return_condition_eligible') is False for x in plans): merged.facts['eligible']=False
        return merged

    def _category(self,text,product=None):
        if product: return product['return_category']
        patterns=[('grocery',r'\b(?:grocery|groceries|fresh|perishables?|fruit|vegetable)\b|किराना'),
                  ('innerwear',r'\b(?:innerwear|lingerie|swimwear|swimsuit|briefs|sports bra)\b'),
                  ('digital',r'\b(?:gift[ -]?cards?|digital codes?)\b'),
                  ('beauty_sealed',r'\b(?:beauty|personal care|lipstick|parfum|perfume|serum|cream)\b|ब्यूटी|सीरम'),
                  ('electronics',r'\b(?:electronics?|accessor(?:y|ies)|smartphone|phone|smartwatch|earbuds?|laptop|speaker|cable|charger|power bank)\b|इलेक्ट्रॉनिक'),
                  ('fashion',r'\b(?:fashion|clothing|shirt|jeans|kurta|shoes?|bags?|sneakers?|hoodie|footwear|trousers?|saree|dress)\b|कपड़े|जूते'),
                  ('home_kitchen',r'\b(?:home|kitchen|furniture|bedsheet|mixer|kettle)\b|रसोई'),
                  ('books_media',r'\b(?:books?|notebook|stationery)\b|किताब')]
        return next((category for category,pattern in patterns if has(text,pattern)),None)

    def _event_date(self,text,event):
        pattern=r'\b(?:delivered|delivery|reached|arrived)\b|डिलीवर' if event=='delivery' else r'\b(?:placed|ordered|bought|purchased)\b|खरीद'
        for match in re.finditer(pattern,text,re.I):
            after=self._date_in(text[match.end():match.end()+65])
            if after: return after
        return None

    def _return_window(self,text,order=None,product=None,category=None,product_ids=None):
        t=text.lower(); cat=category or self._category(text,product)
        product_ids=product_ids if product_ids is not None else ['products.csv:'+product['sku']] if product else []
        festive=has(t,r'\b(?:festiv\w*|sale|october|extend\w*)\b|त्योहार|अक्टूबर')
        if not cat:
            if festive:
                return Plan('return','answer','Only clothing, footwear and bags ordered from 1 to 15 October 2026 get 30 calendar days from delivery. Other categories retain their normal return windows; the order placement date controls the offer, not the delivery date.','केवल 1 से 15 अक्टूबर 2026 के कपड़े, जूते और बैग के ऑर्डर पर डिलीवरी से 30 कैलेंडर दिन मिलते हैं। अन्य श्रेणियों की सामान्य अवधि रहती है; ऑफ़र ऑर्डर की तारीख से तय होता है, डिलीवरी से नहीं।','Sirf 1 to 15 October 2026 placed clothing, footwear aur bags orders par delivery se 30 calendar days milte hain. Other categories ki normal window same hai; order placement date matter karti hai, delivery date nahi.',['RET-2','RET-8'])
            return Plan('return','clarify','Which product or category would you like to return?','आप कौन सा उत्पाद या श्रेणी लौटाना चाहती हैं?','Kaunsa product ya category return karna hai?',['RET-2'])
        if cat in {'grocery','innerwear','digital'}:
            return Plan('return','answer','This catalog category is not returnable for change of mind, even when unopened or unused. Damaged, expired, wrong or missing items must be reported within 48 hours with photos of the item and packaging.','इस कैटलॉग श्रेणी में बंद या बिना इस्तेमाल सामान भी पसंद बदलने पर नहीं लौट सकता। खराब, एक्सपायर, गलत या गुम सामान की 48 घंटे में सामान और पैकिंग की फ़ोटो से शिकायत करें।','Yeh catalog category unopened ya unused hone par bhi change-of-mind ke liye return nahi hoti. Damaged, expired, wrong ya missing item 48 hours mein item aur packaging photos ke saath report karein.',['RET-5','DWM-1']+product_ids,facts={'return_category':cat,'eligible':False})
        delivered=parse_date(order.get('delivered_on')) if order else self._event_date(text,'delivery')
        placed=parse_date(order.get('placed_at')) if order else self._event_date(text,'placement')
        days=return_window(cat,delivered,placed,self.windows.get(cat))
        if days is None: return self.unknown()
        ids=['RET-2']+product_ids
        if cat=='electronics': ids+=['RET-3']+(['RETv3-2'] if delivered and delivered<date(2026,8,1) else [])
        if cat=='fashion' or festive: ids+=['RET-8']
        deadline=return_deadline(delivered,days) if delivered else None
        eligible=deadline is None or REFERENCE_DATE<=deadline
        labels={'electronics':'electronics and accessories','fashion':'clothing, footwear and bags','home_kitchen':'home, kitchen and furniture','beauty_sealed':'beauty and personal care','books_media':'books and stationery'}
        label=labels.get(cat,cat)
        if deadline and order:
            end=fmt(deadline)
            en=f'The catalog category is {label}; its return window is {days} calendar days from delivery. '+(f'You can request a return through {end}.' if eligible else f'The return window ended on {end}.')
            hi=f'कैटलॉग श्रेणी {label} है; डिलीवरी से {days} कैलेंडर दिन। रिटर्न की अंतिम तारीख {end} है।'
            hing=f'Catalog category {label} hai; delivery se {days} calendar days. Return ki last date {end} hai.'
        else:
            en=f'The catalog return category is {label}; its window is {days} calendar days from delivery, subject to item condition.'
            hi=f'कैटलॉग की रिटर्न श्रेणी {label} है; डिलीवरी से {days} कैलेंडर दिन, सामान की शर्तों के अनुसार।'
            hing=f'Catalog return category {label} hai; delivery se {days} calendar days, condition rules ke saath.'
        if festive:
            en+=' The 30-day festive extension is only for clothing, footwear and bags placed from 1 to 15 October 2026; other categories keep their ordinary window.'
            hi+=' 30 दिन का ऑफ़र केवल 1 से 15 अक्टूबर 2026 के कपड़े, जूते और बैग के ऑर्डर पर है; अन्य श्रेणियों की अवधि नहीं बदलती।'
            hing+=' 30-day festive extension sirf 1 to 15 October 2026 placed clothing, footwear aur bags par hai; other categories ki window same hai.'
        if cat=='fashion' and (order or has(t,r'\b(?:fee|pickup|charge|cost)\b|शुल्क|फ़ीस|फीस')):
            fee=0 if order and order.get('is_plus') else 49
            en+=f' Change-of-mind reverse pickup costs {fee} rupees'+(' for Plus members.' if not fee else '; Plus members and damaged, defective or wrong items are exempt.')
            hi+=f' पसंद बदलने के पिकअप की फ़ीस {fee} रुपये; प्लस और खराब, दोषपूर्ण या गलत सामान पर छूट।'
            hing+=f' Change-of-mind pickup fee {fee} rupees; Plus aur damaged, defective ya wrong item exempt hain.'
            ids+=['RET-6']
        if has(t,r'\bseller\b|marketplace'):
            en+=' Seller-fulfilled items use the same return windows and pickup rules.'
            hi+=' विक्रेता के सामान पर भी वही रिटर्न अवधि और पिकअप नियम लागू हैं।'
            hing+=' Seller items par bhi same return windows aur pickup rules apply hote hain.'
            ids+=['MKS-2']
        return Plan('return','answer',en,hi,hing,list(dict.fromkeys(ids)),facts={'return_category':cat,'return_days':days,'deadline':deadline.isoformat() if deadline else None,'eligible':eligible})

    def _plan_single(self,text:str,intent:str,order:dict|None=None) -> Plan:
        t=text.lower(); p=self.product(text,order); cat=self._category(text,p); product_ids=['products.csv:'+p['sku']] if p else []
        if intent=='return' and not cat:
            candidates=[v for v in self.data.products.values() if v['title'].split(',')[0].lower() in t]
            if candidates and len({v['return_category'] for v in candidates})==1:
                cat=candidates[0]['return_category']; product_ids=['products.csv:'+v['sku'] for v in candidates]
        if intent in {'safety','fraud','legal','human','repeat'}:
            lead='Stop using the product immediately. ' if intent=='safety' else ''
            return Plan(intent,'escalate',lead+'This needs a human colleague; I will request a support ticket.',('कृपया सामान का उपयोग तुरंत बंद करें। ' if intent=='safety' else '')+'इस मामले के लिए मानव सहयोगी और टिकट ज़रूरी है।',('Product use turant band karein. ' if intent=='safety' else '')+'Iske liye human team ka ticket zaroori hai.',['ESC-1','ESC-2','ESC-3']+(['DWM-5'] if intent=='safety' else []),intent)
        if intent=='privacy': return Plan(intent,'refuse',"I can't share another customer's details, internal notes, or bypass verification.",'मैं दूसरे ग्राहक की जानकारी या आंतरिक नोट्स साझा नहीं कर सकती और सत्यापन नहीं छोड़ सकती।',"Main kisi aur customer ki details share nahi kar sakti ya verification bypass nahi kar sakti.",['ESC-4','IDV-1','IDV-4'])
        if intent=='compensation': return Plan(intent,'refuse',"I'm sorry, I can't grant a voucher or compensation outside policy. For a late Express delivery, only the paid 79 rupee fee is credited to Wallet within 48 hours; Plus members who paid no fee get no credit; Standard delays have no compensation.",'माफ़ कीजिए, पॉलिसी के बाहर वाउचर या मुआवज़ा नहीं दे सकती। देर से आई एक्सप्रेस डिलीवरी में केवल चुकाई गई 79 रुपये की फ़ीस 48 घंटे में वॉलेट में आती है; प्लस में फ़ीस नहीं दी तो क्रेडिट नहीं।','Maaf karein, policy ke bahar voucher ya compensation nahi de sakti. Late Express par sirf paid 79 rupee fee 48 hours mein Wallet mein aati hai; Plus ki free delivery par credit nahi.',['DEL-4','ESC-4'])
        if intent=='payment' and has(t,r'(deduct|failed|not placed|कट|कटा)'):
            return Plan(intent,'answer','If payment was deducted but no order was placed, the payment provider reverses it automatically within 5 business days; no ticket is needed before then.','भुगतान कट गया और ऑर्डर नहीं बना तो भुगतान प्रदाता 5 कार्यदिवस में अपने आप राशि लौटाता है; उससे पहले टिकट ज़रूरी नहीं।','Payment deduct hua par order place nahi hua to provider 5 business days mein automatically reverse karta hai; pehle ticket nahi chahiye.',['PAY-3'])
        if intent=='greeting': return Plan(intent,'clarify','What is your order ID?','आपका ऑर्डर नंबर क्या है?','Aapka order ID kya hai?',['STY-1','STY-5'])
        if intent=='coupon':
            if has(t,r'(expired|expire|समाप्त)'): return Plan(intent,'answer','Expired coupons cannot be reissued. A valid coupon that failed because of a technical error may be reissued once if the order was placed within its validity.','समाप्त कूपन फिर जारी नहीं होता। वैध कूपन तकनीकी त्रुटि से न लगा हो तो वैधता के अंदर के ऑर्डर पर एक बार फिर जारी हो सकता है।','Expired coupon reissue nahi hota; valid coupon technical error se fail hua ho to validity ke andar placed order ke liye once reissue ho sakta hai.',['CPN-2'])
            return Plan(intent,'answer','Only 1 coupon is allowed per order; coupons cannot be combined, added after ordering, or exchanged for cash.','हर ऑर्डर पर केवल 1 कूपन; कूपन जोड़ना, ऑर्डर के बाद लगाना या नकद लेना संभव नहीं।','Har order par sirf 1 coupon; combine, order ke baad add, ya cash exchange nahi ho sakta.',['CPN-1'])
        if intent=='attempts': return Plan(intent,'answer','The courier makes up to 3 delivery attempts; after a missed attempt, use the SMS to reschedule. After the third failed attempt the parcel returns to the warehouse; a prepaid refund starts only when it reaches the warehouse, usually 7 to 10 calendar days after the last attempt.','कूरियर 3 बार कोशिश करता है; असफल प्रयास के बाद SMS से समय चुनें। तीसरा प्रयास असफल होने पर सामान गोदाम लौटता है; प्रीपेड रिफ़ंड गोदाम पहुँचने पर ही शुरू होता है, आम तौर पर आख़िरी प्रयास से 7 से 10 कैलेंडर दिन बाद।','Courier 3 attempts karta hai; missed attempt ke baad SMS se reschedule karein. Third attempt fail ho to parcel warehouse lautta hai; prepaid refund warehouse pahunchne par start hota hai, usually last attempt se 7 to 10 calendar days.',['DEL-3','REF-1'])
        if intent=='shipping_date' and order:
            value=fmt(order.get('shipped_on'))
            return Plan(intent,'answer',f'Your order shipped on {value}.' if order.get('shipped_on') else 'No shipping date is recorded.',f'आपका ऑर्डर {value} को शिप हुआ।' if order.get('shipped_on') else 'शिप होने की तारीख दर्ज नहीं है।',f'Order {value} ko ship hua.' if order.get('shipped_on') else 'Shipping date recorded nahi hai.',['TRK-1'],facts={'order.shipped_on':order.get('shipped_on')})
        if intent=='cancel':
            if has(t,r'(membership|plus|सदस्य|प्लस)'):
                return Plan(intent,'answer','Plus membership can be cancelled for a full refund within 14 days of purchase only if no benefit has been used.','प्लस सदस्यता खरीद से 14 दिन में पूरा रिफ़ंड लेकर कैंसिल हो सकती है, केवल तब जब कोई लाभ न लिया हो।','Plus membership purchase se 14 days mein full refund ke liye cancel ho sakti hai, agar koi benefit use nahi hua.',['PLS-3'])
            if (order and order.get('delivery_type')=='slot') or has(t,r'\bgrocery\b.{0,25}\bslot\b|किराना.{0,15}स्लॉट'): return Plan(intent,'clarify','What slot start time is shown in My Orders? Grocery cancellation closes 2 hours before that time.','My Orders में स्लॉट शुरू होने का समय क्या है? किराना कैंसिल करने की सीमा उससे 2 घंटे पहले है।','My Orders mein slot start time kya hai? Grocery cancellation cutoff usse 2 hours pehle hai.',['CAN-3'])
            shipped=bool(order and order.get('shipped_on')) or has(t,r'(shipped|on its way|शिप हो|ship ho)')
            if shipped:
                result=Plan(intent,'refuse' if order else 'answer',"A shipped order cannot be cancelled; you can refuse the parcel at the door or return an eligible item after delivery. For prepaid refusals, refund processing follows the refund policy once the parcel returns to the warehouse.",'शिप हुआ ऑर्डर कैंसिल नहीं हो सकता; डिलीवरी पर पार्सल लेने से मना करें या पात्र सामान डिलीवरी के बाद लौटाएँ। प्रीपेड में सामान गोदाम लौटने पर रिफ़ंड पॉलिसी लागू होती है।','Shipped order cancel nahi hota; parcel lene se mana ya refuse kar sakte hain, ya eligible item baad mein return. Prepaid refusal par parcel warehouse lautne par refund policy apply hoti hai.',['CAN-2'])
                if order and order.get('payment_method')!='cod':
                    result.en+=' For prepaid refusals, the parcel usually reaches the warehouse 7 to 10 calendar days after the last delivery attempt.'
                    result.hi+=' प्रीपेड पार्सल आम तौर पर आख़िरी डिलीवरी प्रयास के 7 से 10 कैलेंडर दिन बाद गोदाम पहुँचता है।'
                    result.hinglish+=' Prepaid parcel usually last delivery attempt ke 7 to 10 calendar days baad warehouse pahunchta hai.'
                    result.ids.append('REF-1')
                if (order and order.get('payment_method')=='cod') or has(t,r'\b(?:cod|cash[ -]on[ -]delivery)\b'):
                    result.en+=' Refusing a cash-on-delivery parcel incurs no charge.'
                    result.hi+=' कैश ऑन डिलीवरी पार्सल लेने से मना करने पर कोई शुल्क नहीं लगता।'
                    result.hinglish+=' COD parcel refuse karne par koi charge nahi lagta.'
                return result
            return Plan(intent,'answer',"Before shipping, cancellation is free in the app under My Orders and a prepaid refund starts immediately. I can guide you, but I cannot cancel the order myself.",'शिप होने से पहले ऐप के My Orders में मुफ़्त कैंसिल करें; प्रीपेड रिफ़ंड तुरंत शुरू होता है। मैं मार्गदर्शन कर सकती हूँ, खुद कैंसिल नहीं कर सकती।','Shipping se pehle app ke My Orders mein free cancel karein; prepaid refund turant initiate hoga. Main guide kar sakti hoon, khud cancel nahi.',['CAN-1'])
        if intent=='refund':
            if has(t,r'plus|membership|प्लस') and has(t,r'immediat|instant|every|तुरंत|turant'):
                if has(t,r'\b(?:beauty|opened|eligible|returnable|stage|bank|change\w*)\b|सील|खोल'):
                    result=Plan('refund','answer','Plus changes initiation of return refunds to the pickup time; it does not change return eligibility, return windows or payment-method timelines after initiation.','प्लस में रिटर्न रिफ़ंड पिकअप पर शुरू होता है; रिटर्न पात्रता, अवधि या शुरू होने के बाद भुगतान की समयसीमा नहीं बदलती।','Plus return refund pickup par initiate karta hai; return eligibility, window aur initiation ke baad payment timeline change nahi hoti.',['PLS-2','RET-7'])
                    if cat=='beauty_sealed' and has(t,r'open|खोल|खुल'):
                        result.en+=' Opened beauty items remain ineligible for change-of-mind returns; the seal must be intact.'
                        result.hi+=' खुले ब्यूटी सामान पसंद बदलने पर नहीं लौटते; सील सही होनी चाहिए।'
                        result.hinglish+=' Opened beauty item change-of-mind par return nahi hota; seal intact chahiye.'
                        result.ids+=['RET-4']
                    return result
                return Plan('refund','clarify','Plus initiates return refunds at pickup; it does not shorten the payment-method timeline after initiation. Which payment method did you use?','प्लस में रिटर्न रिफ़ंड पिकअप पर शुरू होता है; शुरू होने के बाद समयसीमा नहीं बदलती। भुगतान का तरीका क्या था?','Plus return refund pickup par initiate hota hai; initiation ke baad timeline change nahi hoti. Payment method kya tha?',['PLS-2'])
            return self.refund(text,order)
        if intent=='warranty':
            if has(t,r'(?:price|cost|charge).{0,55}(?:repair|replace|battery)|international.{0,30}(?:courier|repair)') and has(t,r'after.{0,15}warranty|out.of.warranty|international'): return self.unknown()
            if has(t,r'\b(?:physical|liquid|water|cracked|unauthori[sz]ed|normal wear)\b|पानी|भौतिक'):
                return Plan(intent,'answer','Warranty does not cover physical damage, liquid damage, normal wear or unauthorized repairs.','वारंटी में भौतिक क्षति, पानी से नुकसान, सामान्य घिसावट या अनधिकृत मरम्मत शामिल नहीं।','Physical damage, liquid damage, normal wear aur unauthorized repairs warranty mein cover nahi.',['WAR-3'])
            if not p: return Plan(intent,'clarify','Which product or SKU is this about?','कौन सा उत्पाद या SKU है?','Kaunsa product ya SKU hai?',['WAR-1','WAR-2','MKS-3'])
            months=p['warranty_months']; seller=p['fulfilled_by']!='ZentroMart'; assured=str(p['assured']).casefold()=='true' and not seller
            facts={'brand_warranty_months':int(months or 0),'assured_warranty_months':12 if assured else 0,'assured_eligible':assured}
            if assured:
                return Plan(intent,'answer',f'This has 12 months of ZentroMart Assured coverage from delivery, in addition to the {months}-month brand warranty. Start an Assured claim in My Orders; claim the brand warranty through the manufacturer service centre. Physical/liquid damage, normal wear and unauthorized repairs are excluded.',f'डिलीवरी से 12 महीने की ZentroMart Assured के अतिरिक्त {months} महीने की ब्रांड वारंटी है। Assured दावा My Orders से और ब्रांड दावा निर्माता के सेवा केंद्र से करें। भौतिक या पानी की क्षति, सामान्य घिसावट और अनधिकृत मरम्मत शामिल नहीं।',f'Delivery se 12 months ZentroMart Assured, {months} months brand warranty ke alawa hai. Assured claim My Orders se, brand claim manufacturer service centre par karein. Physical/liquid damage, normal wear aur unauthorized repairs cover nahi.',['WAR-1','WAR-2','WAR-3']+product_ids,facts=facts)
            reason=('Marketplace seller items never have ZentroMart Assured coverage, even if the listing badge says assured.' if seller else 'This catalog item is not marked Assured; shipment by ZentroMart alone does not create Assured eligibility.')
            hi_reason='मार्केटप्लेस विक्रेता के सामान पर बैज होने पर भी ZentroMart Assured लागू नहीं।' if seller else 'कैटलॉग में इस सामान पर Assured नहीं है; केवल ZentroMart से शिप होना पात्रता नहीं बनाता।'
            hing_reason='Marketplace seller item par badge ke bawajood ZentroMart Assured nahi lagta.' if seller else 'Catalog mein Assured false hai; sirf ZentroMart shipment se Assured eligibility nahi milti.'
            return Plan(intent,'answer',f'The brand warranty is {months} months, claimed through the manufacturer service centre. '+reason,f'ब्रांड वारंटी {months} महीने है, दावा निर्माता के सेवा केंद्र में करें। '+hi_reason,f'Brand warranty {months} months hai; manufacturer service centre par claim karein. '+hing_reason,['WAR-1','MKS-3' if seller else 'WAR-2']+product_ids,facts=facts)
        if intent in {'return','pickup'}:
            if intent=='pickup':
                if has(t,r'(miss|nobody|no.one|नहीं आया|nahi aaya)'): return Plan(intent,'answer','A missed pickup is automatically rescheduled to the next business day. After two missed pickups, ask support for a priority pickup.','छूटा पिकअप अगले कार्यदिवस पर अपने आप तय होता है। दो बार पिकअप छूटने पर सपोर्ट से प्राथमिक पिकअप माँगें।','Missed pickup next business day par automatically reschedule hota hai. Do missed pickups ke baad priority pickup support se maangein.',['RVP-2'])
                positive_plus=has(t,r'\bplus\b|प्लस') and not has(t,r'\bnon[ -]?plus\b|\bnot\s+(?:a\s+)?plus\b|without.{0,10}plus|प्लस.{0,8}नहीं')
                free=positive_plus or has(t,r'(torn|damag|defect|wrong|फटा|खराब)') or bool(order and order.get('is_plus'))
                return Plan(intent,'answer',('No pickup fee; it is waived for Plus members and damaged, defective or wrong items.' if free else 'Change-of-mind fashion returns have a 49 rupee reverse pickup fee; Plus members and damaged, defective or wrong items are exempt.'),'प्लस सदस्यों और खराब, दोषपूर्ण या गलत सामान पर पिकअप फ़ीस नहीं है।' if free else 'पसंद बदलने के फ़ैशन रिटर्न पर 49 रुपये पिकअप फ़ीस; प्लस और खराब, दोषपूर्ण या गलत सामान पर छूट।','Plus members aur damaged, defective ya wrong item par pickup free hai.' if free else 'Change-of-mind fashion return par 49 rupee pickup fee hai; Plus aur damaged/wrong/defective items exempt hain.',['RET-6','PLS-2','DWM-2'] if free else ['RET-6'])
            if has(t,r'(?<!un)\bopen(?:ed|ing)?\b|tried it|खोल|खुला|seal.*broken') and (cat=='beauty_sealed' or has(t,r'(lipstick|parfum|perfume|beauty|cream)')):
                return Plan(intent,'answer','Opened beauty products cannot be returned for change of mind; they must be unopened with the seal intact.','खुला ब्यूटी उत्पाद पसंद बदलने पर नहीं लौट सकता; सामान बंद और सील सही होनी चाहिए।','Opened beauty item change-of-mind par return nahi hota; unopened aur seal intact hona chahiye.',['RET-4']+product_ids,facts={'return_condition_eligible':False})
            if cat in {'grocery','innerwear','digital'}:
                return Plan(intent,'answer','This category is not returnable for fit or change of mind, even if unopened or unused. Damage, expired, wrong or missing items can be reported within 48 hours with photos of the item and packaging.','इस श्रेणी को बंद या बिना इस्तेमाल होने पर भी फ़िट या पसंद बदलने के लिए वापस नहीं कर सकते। खराब, एक्सपायर, गलत या गुम सामान की 48 घंटे में सामान और पैकिंग की फ़ोटो से शिकायत करें।','Yeh category unopened ya unused hone par bhi fit ya change-of-mind ke liye return nahi hoti. Damage, expired, wrong ya missing item 48 hours mein item aur packaging photos ke saath report karein.',['RET-5','DWM-1']+product_ids)
            if has(t,r'(exchange|different size|different colour|different color|बदल)'):
                return Plan('return','answer','Size or colour exchanges cover clothing and footwear only, not bags, within the return window and subject to stock. If the size is unavailable, a return and refund is offered instead.','साइज़ या रंग बदलना केवल कपड़े और जूते के लिए है, बैग के लिए नहीं; रिटर्न अवधि और स्टॉक की शर्त है। साइज़ उपलब्ध न हो तो रिटर्न और रिफ़ंड मिलता है।','Size/colour exchange sirf clothing aur footwear par hai, bags par nahi; return window aur stock ki condition hai. Size unavailable ho to return aur refund milta hai.',['RET-9'])
            if has(t,r'(?:(?<!un)\bused\b|tags|packaging|screen lock|account lock|original accessories|इस्तेमाल)'):
                return Plan('return','answer','Returns must be unused with original tags, packaging, accessories and free gifts. Beauty items must be sealed; electronics must have no physical damage and all screen or account locks removed.','रिटर्न सामान बिना इस्तेमाल, मूल टैग, पैकिंग, एक्सेसरी और उपहार के साथ हो। ब्यूटी की सील सही और इलेक्ट्रॉनिक्स में नुकसान या स्क्रीन/अकाउंट लॉक नहीं होना चाहिए।','Return item unused ho, original tags, packaging, accessories aur free gifts ke saath. Beauty seal intact; electronics physically damaged nahi aur screen/account locks removed.',['RET-4'])
            return self._return_window(text,order,p,cat,product_ids)
        if intent=='damage':
            value=int(p['price_inr']) if p else 0
            if not p and not order and has(t,r'high.value|priority|threshold'):
                return Plan(intent,'answer','Priority Resolution applies only when the item value is more than 10,000 rupees; exactly 10,000 rupees does not cross that threshold. Damage, wrong or missing claims still follow the reporting and verification rules.','Priority Resolution केवल 10,000 रुपये से अधिक मूल्य पर लागू है; ठीक 10,000 रुपये सीमा से अधिक नहीं है। नुकसान, गलत या गुम सामान पर रिपोर्ट और जाँच के नियम लागू हैं।','Priority Resolution sirf 10,000 rupees se zyada value par hai; exactly 10,000 threshold cross nahi karta. Damage, wrong ya missing claims par reporting aur verification rules apply hote hain.',['DWM-3','DWM-1'])
            if order:
                relevant=[i for i in order.get('items',[]) if not p or i['sku']==p['sku']]
                if relevant: value=max(int(i['unit_price_inr']) for i in relevant)
            if value>10000: return Plan(intent,'escalate','Damage claims above 10,000 rupees need the Priority Resolution team; I cannot approve a replacement. I will request a ticket.','10,000 रुपये से ऊपर के नुकसान के लिए Priority Resolution टीम ज़रूरी है; मैं रिप्लेसमेंट मंज़ूर नहीं कर सकती। टिकट का अनुरोध करूँगी।','10,000 rupees se upar damage claim Priority Resolution team handle karti hai; main replacement approve nahi kar sakti. Ticket request karungi.',['DWM-3','ESC-1','ESC-4']+product_ids,'high_value_damage')
            if has(t,r'(collection|pickup|free)'): return self.plan(text,'pickup',order)
            return Plan(intent,'answer','Report damaged, defective, expired, wrong or missing items within 48 hours of delivery, with photos of the item and packaging. After verification, the policy provides a free replacement or full refund including delivery fees, with no pickup fee.','डिलीवरी के 48 घंटे में सामान और पैकिंग की फ़ोटो के साथ शिकायत करें। जाँच के बाद मुफ़्त रिप्लेसमेंट या डिलीवरी फ़ीस सहित पूरा रिफ़ंड मिलेगा, पिकअप फ़ीस नहीं।','Delivery ke 48 hours mein item aur packaging photos ke saath report karein. Verification ke baad free replacement ya full refund including delivery fees, pickup fee nahi.',['DWM-1','DWM-2'])
        if intent=='late_delivery': return Plan(intent,'answer','For a late Express order, the paid 79 rupee Express fee is automatically credited to ZentroMart Wallet within 48 hours. Plus members who paid no Express fee get no credit; Standard delays have no compensation.','देर से आई एक्सप्रेस डिलीवरी की चुकाई 79 रुपये फ़ीस 48 घंटे में ZentroMart Wallet में आती है। प्लस में फ़ीस नहीं दी तो क्रेडिट नहीं; सामान्य डिलीवरी में मुआवज़ा नहीं।','Late Express ki paid 79 rupee fee 48 hours mein ZentroMart Wallet mein automatically credit hoti hai. Plus ne fee nahi di to credit nahi; Standard delay par compensation nahi.',['DEL-4'])
        if intent=='delivery':
            if has(t,r'(change|update|बदल)') and has(t,r'(address|पता)'):
                shipped=bool(order and order.get('shipped_on')) or has(t,r'(shipped|shipping.*already)')
                return Plan(intent,'answer','After shipping, the address cannot be changed.' if shipped else 'The delivery address can be changed before shipping; after shipping it cannot be changed.','शिप होने के बाद पता नहीं बदल सकता।' if shipped else 'शिप होने से पहले डिलीवरी पता बदल सकते हैं; बाद में नहीं।','Shipping ke baad address change nahi hota.' if shipped else 'Shipping se pehle delivery address badal sakte hain; baad mein nahi.',['DEL-6'])
            if has(t,r'(fee|cost|free|charge|फ़ीस|शुल्क)'):
                return Plan(intent,'answer','Standard delivery is free for orders of 499 rupees or more, otherwise 40 rupees. Express costs 79 rupees and is free for Plus members where available.','499 रुपये या अधिक पर सामान्य डिलीवरी मुफ़्त, वरना 40 रुपये। एक्सप्रेस 79 रुपये; उपलब्ध जगह प्लस के लिए मुफ़्त।','Standard delivery 499 rupees ya above par free, otherwise 40 rupees. Express 79 rupees, available area mein Plus ke liye free.',['DEL-2','PLS-2'])
            if has(t,r'(standard|metro|how long|shipping time|days.*deliver|express.*cutoff|2 pm|time.*express)') and not order:
                return Plan(intent,'answer','Standard delivery takes 3 to 6 business days in metros, 5 to 9 elsewhere. At enabled metro pincodes, Express is next business day if ordered before 2 pm, otherwise the following business day; the checkout promised date is the commitment.','मेट्रो में सामान्य डिलीवरी 3 से 6 कार्यदिवस, अन्य जगह 5 से 9। उपलब्ध मेट्रो पिनकोड पर दोपहर 2 बजे से पहले एक्सप्रेस ऑर्डर अगले कार्यदिवस, बाद में उसके अगले कार्यदिवस; चेकआउट की तारीख वादा है।','Standard metro mein 3 to 6 business days, elsewhere 5 to 9. Enabled metro pincodes par 2 pm se pehle Express next business day, otherwise uske agle business day; checkout promised date commitment hai.',['DEL-1','DEL-5','KB-00.3'])
            if (not order or order.get('status')=='Delivered') and has(t,r'(?:delivered|डिलीवर्ड).{0,100}(?:not received|never received|nowhere|missing|नहीं मिला|nahi mila)|(?:not received|never received).{0,40}delivered'):
                return Plan(intent,'answer','Check with family, neighbours or building security, then report delivered-but-not-received within 48 hours as a missing item.','परिवार, पड़ोसियों या सुरक्षा कर्मियों से पूछें, फिर 48 घंटे में नहीं मिले डिलीवर्ड सामान की शिकायत करें।','Family, neighbours ya building security se check karein, phir 48 hours mein missing item report karein.',['TRK-2','DWM-1'])
            if has(t,r'(dubai|outside india|international|विदेश)'): return Plan(intent,'answer','Delivery is only within India, to serviceable pincodes.','डिलीवरी केवल भारत के सेवा-योग्य पिनकोड में है।','Delivery sirf India ke serviceable pincodes par hoti hai.',['DEL-5','FAQ-5'])
            if order:
                return Plan(intent,'answer',f"Your order status is {order['status']}; its promised delivery date is {fmt(order.get('promised_date'))}.",f"आपके ऑर्डर की स्थिति {order['status']} है; वादा की गई डिलीवरी तारीख {fmt(order.get('promised_date'))} है।",f"Order status {order['status']} hai; promised delivery {fmt(order.get('promised_date'))} hai.",['TRK-1','DEL-1'],facts={'order.status':order['status'],'order.promised_date':order.get('promised_date')})
            if has(t,r'(midnight|store|pickup|दुकान)'): return self.unknown()
            return Plan(intent,'clarify','What is your order ID?','आपका ऑर्डर नंबर क्या है?','Aapka order ID kya hai?',['IDV-1','STY-5'])
        if intent=='troubleshoot':
            cid='TRB-1' if 'earbud' in t else 'TRB-2' if 'watch' in t else 'TRB-3' if re.search(r'charg(?:ing|es)',t) else 'TRB-4'
            content=self.kb.chunks[cid].text.split('\n',1)[1].strip()
            return Plan(intent,'answer',re.sub(r'(?m)^\d+\.\s*','',content).replace('\n',' '),content,content,[cid])
        if intent=='plus': return Plan(intent,'answer','Plus costs 999 rupees per year: free Express where available, no reverse pickup fee, and return refunds initiated at pickup. It does not extend return windows or post-initiation refund timelines.','प्लस सालाना 999 रुपये: उपलब्ध जगह मुफ़्त एक्सप्रेस, पिकअप फ़ीस नहीं, और रिफ़ंड पिकअप पर शुरू। रिटर्न अवधि या शुरू होने के बाद रिफ़ंड समय नहीं बदलता।','Plus 999 rupees yearly: available pincodes par free Express, pickup fee nahi aur refund pickup par start. Return window aur refund initiation ke baad timeline same hai.',['PLS-1','PLS-2'])
        if intent=='payment':
            if has(t,r'(wallet|वॉलेट)'): return Plan(intent,'answer','Wallet credit never expires and can be used on any order, but cannot be transferred to a bank. For COD refunds, choose bank or Wallet before the refund is made.','वॉलेट बैलेंस कभी समाप्त नहीं होता और किसी ऑर्डर पर लग सकता है, लेकिन बैंक में नहीं भेज सकते। COD रिफ़ंड से पहले बैंक या वॉलेट चुनें।','Wallet balance expire nahi hota, kisi order par use kar sakte hain, bank mein transfer nahi. COD refund hone se pehle bank ya Wallet choose karein.',['PAY-4','REF-3'])
            if has(t,r'cod|cash on delivery|कैश'):
                return Plan(intent,'answer','COD is available up to 10,000 rupees only at enabled pincodes, with a 25 rupee fee per order.','COD 10,000 रुपये तक उपलब्ध पिनकोड में, प्रति ऑर्डर 25 रुपये फ़ीस है।','COD 10,000 rupees tak enabled pincodes par hai, 25 rupee fee per order.',['PAY-2'])
            return Plan(intent,'answer','Payment methods include UPI, cards, net banking, Wallet and COD where enabled.','UPI, कार्ड, नेट बैंकिंग, वॉलेट और उपलब्ध जगह COD से भुगतान करें।','UPI, cards, net banking, Wallet aur enabled areas mein COD payment available hai.',['PAY-1','PAY-2'])
        return self.unknown()
    def unknown(self) -> Plan:
        return Plan('unsupported','answer',"I don't have information about that in the supplied documents. I can connect you to a human colleague.",'दिए गए दस्तावेज़ों में इस बारे में जानकारी नहीं है। मैं आपको मानव सहयोगी से जोड़ सकती हूँ।','Documents mein iski jaankari nahi hai; human colleague se connect kar sakti hoon.',[])
    def refund(self,text:str,order:dict|None) -> Plan:
        t=text.lower(); method=None; initiated=None; ids=['REF-2','KB-00.1']; rrn=None
        if has(t,r'\b(?:coupon|discount)\b') and has(t,r'\b(?:partial|minimum|remaining|basket|sticker|share)\b'):
            return Plan('refund','answer',"A partial refund uses the item's price after its share of the coupon discount. If the remaining order falls below the coupon minimum, the remaining items' coupon discount is also deducted from the refund.",'आंशिक रिफ़ंड में उस सामान के हिस्से का कूपन डिस्काउंट घटता है। बाकी ऑर्डर कूपन की न्यूनतम राशि से नीचे हो तो बाकी सामान का कूपन डिस्काउंट भी रिफ़ंड से घटता है।','Partial refund mein item price se uska coupon discount share deduct hota hai. Remaining order coupon minimum se neeche ho to remaining items ka coupon discount bhi refund se deduct hota hai.',['REF-4'])
        if has(t,r'\b(?:delivery|cod)\b.{0,20}\b(?:fee|fees|charge|charges)\b') and has(t,r'\b(?:refund|returned|cancelled|whole|entire)\b'):
            return Plan('refund','answer','Delivery fees and the 25 rupee COD fee are refunded only if the whole order is cancelled before shipping or returned because it was damaged, defective or wrong; a change-of-mind return does not qualify.','डिलीवरी और 25 रुपये COD फ़ीस केवल पूरा ऑर्डर शिप होने से पहले कैंसिल हो या खराब, दोषपूर्ण या गलत होने से लौटे तो वापस होती है; पसंद बदलने पर नहीं।','Delivery fees aur 25 rupee COD fee sirf whole order shipping se pehle cancel ho ya damaged, defective ya wrong hone par return ho to refund hoti hai; change-of-mind par nahi.',['REF-5'])
        if has(t,r'wallet|वॉलेट') and has(t,r'\b(?:transfer|moved?|bank|expire\w*)\b') and has(t,r'already|landed|credited|balance|unused|now|पहले|आ चुका'):
            return self._plan_single(text,'payment',order)
        if not order and has(t,r'\b(?:rrn|reference|trace)\b'):
            return Plan('refund','answer','An initiated refund has a refund reference number (RRN); support can share it so your bank can trace the refund. The specific reference requires verified order access.','शुरू हुए रिफ़ंड का refund reference number (RRN) होता है; इसे बैंक रिफ़ंड ट्रेस करने के लिए उपयोग कर सकता है। खास RRN के लिए ऑर्डर सत्यापन चाहिए।','Initiated refund ka refund reference number (RRN) hota hai; bank usse refund trace kar sakta hai. Specific RRN ke liye verified order access chahiye.',['REF-6','IDV-1'])
        if has(t,r'(upi|u p i|यूपीआई)'): method='upi'
        elif has(t,r'(credit|debit|card|कार्ड)'): method='card'
        elif has(t,r'(net.?bank|नेट बैंक)'): method='netbanking'
        elif has(t,r'(wallet|वॉलेट)'): method='wallet'
        if has(t,r'(cash[ -]on[ -]delivery|\bcod\b|कैश ऑन)') and (not method or (has(t,r'\bbank\b') and has(t,r'wallet|वॉलेट'))):
            return Plan('refund','answer','For COD refunds, choose ZentroMart Wallet, instant, or bank transfer, 5 to 7 business days after verified bank details.','COD रिफ़ंड के लिए ZentroMart Wallet तुरंत, या बैंक डिटेल्स जाँच के बाद 5 से 7 कार्यदिवस में बैंक ट्रांसफ़र चुनें।','COD refund mein ZentroMart Wallet instant, ya verified bank details ke baad 5 to 7 business days bank transfer choose karein.',['REF-3'])
        if order and order.get('return_refund_completed_on'):
            completed=fmt(order['return_refund_completed_on']); reference=order.get('return_rrn') or 'not recorded'
            return Plan('refund','answer',f'The order record marks the refund completed on {completed}; this does not prove your bank has posted it. Your refund reference number (RRN) is {reference}; your bank can trace it.',f'रिकॉर्ड में रिफ़ंड {completed} को पूरा दर्ज है; इससे बैंक में पैसा दिखना साबित नहीं होता। RRN {reference} से बैंक जाँच सकता है।',f'Record mein refund {completed} ko completed hai; bank credit confirm nahi hota. Refund reference number (RRN) {reference} se bank trace kar sakta hai.',['REF-6'])
        if order:
            for prefix in ['return','cancellation','rto']:
                if order.get(prefix+'_refund_initiated_on'):
                    initiated=parse_date(order[prefix+'_refund_initiated_on']); method=order.get(prefix+'_refund_method') or method; rrn=order.get(prefix+'_rrn'); break
            if not method: method=order.get('payment_method')
            if method=='cod': return self.refund('cash on delivery',None)
            if not initiated and order.get('return_status'):
                return Plan('refund','answer','The return refund has not been recorded as initiated. For non-Plus returns it starts after quality check (QC), within 2 business days of pickup; Plus initiation is at pickup.','रिटर्न रिफ़ंड शुरू होना दर्ज नहीं है। गैर-प्लस में quality check (QC) के बाद, पिकअप से 2 कार्यदिवस के अंदर शुरू होता है; प्लस में पिकअप पर।','Return refund initiate hona recorded nahi hai. Non-Plus ke liye quality check (QC) ke baad pickup se 2 business days mein; Plus par pickup ke time.',['RET-7','REF-1','PLS-2'])
        initiated=initiated or self._date_in(text)
        if not order and has(t,r'pickup|quality\s+check|\bqc\b|initiation.{0,15}stage|stage.{0,15}initiation') and has(t,r'return|pickup|quality'):
            result=Plan('refund','answer','For non-Plus returns, initiation follows quality check within 2 business days of pickup; Plus members initiate at pickup. The payment-method timeline starts only after initiation.','गैर-प्लस रिटर्न में quality check के बाद पिकअप से 2 कार्यदिवस में रिफ़ंड शुरू होता है; प्लस में पिकअप पर। भुगतान की समयसीमा शुरू होने के बाद गिनी जाती है।','Non-Plus return mein QC ke baad pickup se 2 business days mein refund initiate hota hai; Plus par pickup ke time. Payment-method timeline initiation ke baad start hoti hai.',['RET-7','REF-1','PLS-2'])
            if method in self.refunds:
                low,high=self.refunds[method]
                result.en+=f' After initiation, {method} refunds take {low} to {high} business days.'
                result.hi+=f' शुरू होने के बाद {method} में {low} से {high} कार्यदिवस लगते हैं।'
                result.hinglish+=f' Initiation ke baad {method} refund {low} to {high} business days leta hai.'
                result.ids+=['REF-2']
            return result
        if not method: return Plan('refund','clarify','Which payment method did you use?','आपने किस तरीके से भुगतान किया था?','Payment kaunsa method se kiya tha?',['REF-2'])
        low,high=self.refunds.get(method,(0,0)); label={'upi':'UPI','card':'card','netbanking':'net banking','wallet':'ZentroMart Wallet','cod_wallet':'ZentroMart Wallet','cod_bank':'bank transfer'}.get(method,method)
        if high==0:
            return Plan('refund','answer',f'{label} refunds are instant, within 2 hours after initiation.',f'{label} रिफ़ंड शुरू होने के बाद तुरंत, 2 घंटे में आता है।',f'{label} refund initiation ke baad instant, 2 hours mein aata hai.',['REF-2'])
        if initiated:
            first=business_add(initiated,low,self.data.holidays); last=business_add(initiated,high,self.data.holidays); ids+=['KB-00.3']
            if order and business_elapsed(last,REFERENCE_DATE,self.data.holidays)>3:
                return Plan('refund','escalate',f'The refund is more than 3 business days beyond its maximum date of {fmt(last)}. I will request a human ticket; the refund reference number (RRN) is {rrn or "not recorded"}.',f'रिफ़ंड की अंतिम तारीख {fmt(last)} से 3 कार्यदिवस से अधिक हो गए हैं। मानव टीम के लिए टिकट चाहिए; reference number (RRN) {rrn or "दर्ज नहीं"} है।',f'Refund maximum date {fmt(last)} se 3 business days se zyada overdue hai. Human team ticket chahiye; reference number (RRN) {rrn or "recorded nahi"} hai.',ids+['ESC-1','REF-6'],'refund_overdue',{'refund_first':first.isoformat(),'refund_last':last.isoformat()})
            return Plan('refund','answer',f'{label} takes {low} to {high} business days: {fmt(first)} to {fmt(last)}, excluding Sundays and warehouse holidays.',f'{label} में {low} से {high} कार्यदिवस: {fmt(first)} से {fmt(last)}, रविवार और गोदाम की छुट्टियाँ छोड़कर।',f'{label} mein {low} to {high} business days: {fmt(first)} se {fmt(last)}, Sundays aur warehouse holidays exclude karke.',ids,facts={'refund_first':first.isoformat(),'refund_last':last.isoformat()})
        return Plan('refund','answer',f'{label} refunds take {low} to {high} business days after initiation.',f'{label} रिफ़ंड शुरू होने के बाद {low} से {high} कार्यदिवस लगते हैं।',f'{label} refund initiation ke baad {low} to {high} business days leta hai.',['REF-2'])
