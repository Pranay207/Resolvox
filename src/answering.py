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

def classify(text:str) -> str:
    t=text.lower()
    if has(t,r"(ignore|bypass|override|system prompt|internal notes|another customer|someone else|person who ordered|other.*customer|दूसरे.*ग्राहक|निजी.*जानकारी)"): return 'privacy'
    if has(t,r'(swelling|swollen|battery.*(bulg|hot)|burning|sparks|smoke|injur|आग|धुआ|चिंगारी|बैटरी.*फूल|jal.*raha)'): return 'safety'
    if has(t,r"(never placed|did not (place|make)|didn.t (order|make)|unauthori[sz]ed|fraud|not mine|नहीं किया|मैंने.*नहीं.*किया)"): return 'fraud'
    if has(t,r'(legal action|consumer court|police|lawsuit|वकील|पुलिस|अदालत)'): return 'legal'
    if has(t,r'(human|real person|speak to a person|talk to a person|agent please|insaan|insan|इंसान|मानव|कर्मचारी)'): return 'human'
    if has(t,r'(third time|third.*contact|teesri|तीसरी|again.*week)'): return 'repeat'
    if has(t,r'(gift.?wrap|student discount|gst|invoice|midnight|physical store|store near|shop near|shop in|insurance|दुकान)'): return 'unknown'
    if has(t,r'(voucher|compensat|free money|300 rup|500 rup|मुआव|वाउचर)'): return 'compensation'
    if has(t,r'(coupon|कूपन)'): return 'coupon'
    if has(t,r'(not.*home|not at home|courier comes|delivery attempt|घर.*नहीं|ghar.*nahi)'): return 'attempts'
    if has(t,r'(won.t turn on|not powering|speaker.*(on|power)|earbud.*(side|working)|watch.*sync|charging slowly)'): return 'troubleshoot'
    if has(t,r'(warranty|वारंटी)') and has(t,r'(cover|liquid|physical|repair|कवर)'): return 'warranty'
    if has(t,r'(damage|torn|crack|wrong item|missing item|expired|defect|टूटा|टूट|खराब|गलत|kharab|tuta|toota)'): return 'damage'
    if has(t,r'(warranty|assured|वारंटी|अश्योर्ड)'): return 'warranty'
    if has(t,r'(cancel|stop it|कैंसिल|रद्द)'): return 'cancel'
    if has(t,r'(refund|rrn|refund reference|money.*(?:back|revers)|रिफ़ंड|रिफंड|पैसे.*वापस)'): return 'refund'
    if has(t,r'(pickup|pick.up|collect|पिकअप|पिकअप|उठाने)') and not has(t,r'(store|दुकान)'): return 'pickup'
    if has(t,r'(return|send.*back|लौटा|वापस|badal|exchange)'): return 'return'
    if has(t,r'(change|update)') and has(t,r'(address)'): return 'delivery'
    if has(t,r'(express|late|arriv.*late|देर|लेट)'): return 'late_delivery'
    if has(t,r'(ship.*when|when.*ship|kab ship|कब.*शिप|ship hua|shipped)') and not has(t,r'(cancel|return)'): return 'shipping_date'
    if has(t,r'(deliver|shipping|change.*address|where is|hasn.t arrived|order.*status|track|कहाँ|कब.*आए|kab.*aay|kahaan|kahan)'): return 'delivery'
    if has(t,r'(cod|cash on delivery|payment|wallet|भुगतान|कैश)'): return 'payment'
    if has(t,r'(plus|membership|प्लस|सदस्य)'): return 'plus'
    if has(t,r'(hello|^hi\b|help|नमस्ते|मदद|help chahiye)'): return 'greeting'
    return 'unknown'

class Policy:
    def __init__(self,kb,data):
        self.kb=kb; self.data=data
        self.windows={}
        for line in kb.chunks['RET-2'].text.splitlines():
            m=re.search(r'\|\s*(\d+) days\s*\|\s*`(\w+)`',line)
            if m: self.windows[m[2]]=int(m[1])
        self.refunds={}
        for line in kb.chunks['REF-2'].text.splitlines():
            if not line.startswith('|'): continue
            cells=[x.strip() for x in line.strip('|').split('|')]
            if len(cells)!=2: continue
            span=re.search(r'(\d+) to (\d+)',cells[1]); lower=cells[0].lower()
            key='cod_bank' if 'neft' in lower else 'cod_wallet' if 'cash-on' in lower else 'upi' if 'upi' in lower else 'card' if 'card' in lower else 'netbanking' if 'net banking' in lower else 'wallet' if 'wallet' in lower else None
            if key: self.refunds[key]=(int(span[1]),int(span[2])) if span else (0,0)
    def product(self,text:str,order:dict|None=None) -> dict|None:
        t=number_words(text).lower(); matches=[]
        for sku,p in self.data.products.items():
            if sku.lower() in t or p['title'].lower() in text.lower(): return p
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
        t=text.lower(); p=self.product(text,order); cat=p['return_category'] if p else None; product_ids=['products.csv:'+p['sku']] if p else []
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
            return Plan(intent,'answer','If payment was deducted but no order was placed, the payment provider reverses it automatically within 5 business days; no ticket is needed before then.','भुगतान कट गया और ऑर्डर नहीं बना तो भुगतान प्रदाता 5 कार्यदिवस में अपने आप राशि लौटाता है; उससे पहले टिकट ज़रूरी नहीं।','Payment deduct hua par order place nahi hua to provider 5 business days mein automatically reverse karta hai; pehle ticket nahi chahiye.',['PAY-3','KB-00.3'])
        if intent=='greeting': return Plan(intent,'clarify','What is your order ID?','आपका ऑर्डर नंबर क्या है?','Aapka order ID kya hai?',['STY-1','STY-5'])
        if intent=='coupon':
            if has(t,r'(expired|expire|समाप्त)'): return Plan(intent,'answer','Expired coupons cannot be reissued. A valid coupon that failed because of a technical error may be reissued once if the order was placed within its validity.','समाप्त कूपन फिर जारी नहीं होता। वैध कूपन तकनीकी त्रुटि से न लगा हो तो वैधता के अंदर के ऑर्डर पर एक बार फिर जारी हो सकता है।','Expired coupon reissue nahi hota; valid coupon technical error se fail hua ho to validity ke andar placed order ke liye once reissue ho sakta hai.',['CPN-2'])
            return Plan(intent,'answer','Only 1 coupon is allowed per order; coupons cannot be combined, added after ordering, or exchanged for cash.','हर ऑर्डर पर केवल 1 कूपन; कूपन जोड़ना, ऑर्डर के बाद लगाना या नकद लेना संभव नहीं।','Har order par sirf 1 coupon; combine, order ke baad add, ya cash exchange nahi ho sakta.',['CPN-1'])
        if intent=='attempts': return Plan(intent,'answer','The courier makes up to 3 delivery attempts; after a missed attempt, use the SMS to reschedule. After the third failed attempt, the parcel returns to the warehouse and prepaid refunds follow the refund policy.','कूरियर 3 बार डिलीवरी की कोशिश करता है; असफल प्रयास के बाद SMS से दोबारा समय चुनें। तीसरा प्रयास असफल होने पर सामान गोदाम लौटता है और प्रीपेड रिफ़ंड पॉलिसी लागू होती है।','Courier 3 delivery attempts karta hai; missed attempt ke baad SMS se reschedule karein. Third attempt fail ho to parcel warehouse lautega aur prepaid refund policy lagegi.',['DEL-3','REF-1'])
        if intent=='shipping_date' and order:
            value=fmt(order.get('shipped_on'))
            return Plan(intent,'answer',f'Your order shipped on {value}.' if order.get('shipped_on') else 'No shipping date is recorded.',f'आपका ऑर्डर {value} को शिप हुआ।' if order.get('shipped_on') else 'शिप होने की तारीख दर्ज नहीं है।',f'Order {value} ko ship hua.' if order.get('shipped_on') else 'Shipping date recorded nahi hai.',['TRK-1'],facts={'order.shipped_on':order.get('shipped_on')})
        if intent=='cancel':
            if has(t,r'(membership|plus|सदस्य|प्लस)'):
                return Plan(intent,'answer','Plus membership can be cancelled for a full refund within 14 days of purchase only if no benefit has been used.','प्लस सदस्यता खरीद से 14 दिन में पूरा रिफ़ंड लेकर कैंसिल हो सकती है, केवल तब जब कोई लाभ न लिया हो।','Plus membership purchase se 14 days mein full refund ke liye cancel ho sakti hai, agar koi benefit use nahi hua.',['PLS-3'])
            if order and order.get('delivery_type')=='slot': return Plan(intent,'clarify','What slot start time is shown in My Orders? Grocery cancellation closes 2 hours before that time.','My Orders में स्लॉट शुरू होने का समय क्या है? किराना कैंसिल करने की सीमा उससे 2 घंटे पहले है।','My Orders mein slot start time kya hai? Grocery cancellation cutoff usse 2 hours pehle hai.',['CAN-3'])
            shipped=bool(order and order.get('shipped_on')) or has(t,r'(shipped|on its way|शिप हो|ship ho)')
            if shipped:
                return Plan(intent,'refuse' if order else 'answer',"A shipped order cannot be cancelled; you can refuse the parcel at the door or return an eligible item after delivery. For prepaid refusals, the refund starts when it reaches the warehouse, usually 7 to 10 calendar days after the last delivery attempt.",'शिप हुआ ऑर्डर कैंसिल नहीं हो सकता; डिलीवरी पर पार्सल लेने से मना करें या पात्र सामान डिलीवरी के बाद लौटाएँ। प्रीपेड में सामान गोदाम पहुँचने पर रिफ़ंड शुरू होगा, आम तौर पर आख़िरी प्रयास से 7 से 10 कैलेंडर दिन।','Shipped order cancel nahi hota; parcel lene se mana ya refuse kar sakte hain, ya eligible item baad mein return. Prepaid refund warehouse pahunchne par start hota hai, usually last delivery attempt ke 7 to 10 calendar days baad.',['CAN-2','REF-1'])
            return Plan(intent,'answer',"Before shipping, cancellation is free in the app under My Orders and a prepaid refund starts immediately. I can guide you, but I cannot cancel the order myself.",'शिप होने से पहले ऐप के My Orders में मुफ़्त कैंसिल करें; प्रीपेड रिफ़ंड तुरंत शुरू होता है। मैं मार्गदर्शन कर सकती हूँ, खुद कैंसिल नहीं कर सकती।','Shipping se pehle app ke My Orders mein free cancel karein; prepaid refund turant initiate hoga. Main guide kar sakti hoon, khud cancel nahi.',['CAN-1'])
        if intent=='refund': return self.refund(text,order)
        if intent=='warranty':
            if has(t,r'(physical|liquid|unauthori|wear|पानी|भौतिक)'):
                return Plan(intent,'answer','Warranty does not cover physical damage, liquid damage, normal wear or unauthorized repairs.','वारंटी में भौतिक क्षति, पानी से नुकसान, सामान्य घिसावट या अनधिकृत मरम्मत शामिल नहीं।','Physical damage, liquid damage, normal wear aur unauthorized repairs warranty mein cover nahi.',['WAR-3'])
            if not p: return Plan(intent,'clarify','Which product or SKU is this about?','कौन सा उत्पाद या SKU है?','Kaunsa product ya SKU hai?',['WAR-1','WAR-2','MKS-3'])
            months=p['warranty_months']; seller=p['fulfilled_by']!='ZentroMart'; assured=p['assured']=='True' and not seller
            if assured:
                return Plan(intent,'answer',f'This has 12 months of ZentroMart Assured coverage from delivery, plus the {months}-month brand warranty. Raise an Assured claim in the app under My Orders; physical/liquid damage and unauthorized repairs are excluded.',f'डिलीवरी से 12 महीने की ZentroMart Assured और {months} महीने की ब्रांड वारंटी है। Assured दावा ऐप के My Orders से करें; भौतिक या पानी की क्षति और अनधिकृत मरम्मत शामिल नहीं।',f'Delivery se 12 months ZentroMart Assured aur {months} months brand warranty hai. Assured claim app ke My Orders mein karein; physical/liquid damage aur unauthorized repairs cover nahi.',['WAR-1','WAR-2','WAR-3']+product_ids)
            return Plan(intent,'answer',f'The brand warranty is {months} months, claimed through the manufacturer service centre. ZentroMart Assured does not apply to marketplace seller items, even if the listing badge says assured.',f'ब्रांड वारंटी {months} महीने है, दावा निर्माता के सेवा केंद्र में करें। मार्केटप्लेस विक्रेता के सामान पर बैज होने पर भी ZentroMart Assured लागू नहीं।',f'Brand warranty {months} months hai; manufacturer service centre par claim karein. Marketplace seller item par badge ke bawajood ZentroMart Assured nahi lagta.',['WAR-1','MKS-3']+product_ids)
        if intent in {'return','pickup'}:
            if intent=='pickup':
                if has(t,r'(miss|nobody|no.one|नहीं आया|nahi aaya)'): return Plan(intent,'answer','A missed pickup is automatically rescheduled to the next business day. After two missed pickups, ask support for a priority pickup.','छूटा पिकअप अगले कार्यदिवस पर अपने आप तय होता है। दो बार पिकअप छूटने पर सपोर्ट से प्राथमिक पिकअप माँगें।','Missed pickup next business day par automatically reschedule hota hai. Do missed pickups ke baad priority pickup support se maangein.',['RVP-2','KB-00.3'])
                free=has(t,r'(plus|torn|damag|defect|wrong|प्लस|फटा|खराब)') or bool(order and order.get('is_plus'))
                return Plan(intent,'answer',('No pickup fee; it is waived for Plus members and damaged, defective or wrong items.' if free else 'Change-of-mind fashion returns have a 49 rupee reverse pickup fee; Plus members and damaged, defective or wrong items are exempt.'),'प्लस सदस्यों और खराब, दोषपूर्ण या गलत सामान पर पिकअप फ़ीस नहीं है।' if free else 'पसंद बदलने के फ़ैशन रिटर्न पर 49 रुपये पिकअप फ़ीस; प्लस और खराब, दोषपूर्ण या गलत सामान पर छूट।','Plus members aur damaged, defective ya wrong item par pickup free hai.' if free else 'Change-of-mind fashion return par 49 rupee pickup fee hai; Plus aur damaged/wrong/defective items exempt hain.',['RET-6','PLS-2','DWM-2'] if free else ['RET-6'])
            if has(t,r'(open|tried it|खोल|खुला|seal.*broken)') and (cat=='beauty_sealed' or has(t,r'(lipstick|parfum|perfume|beauty|cream)')):
                return Plan(intent,'answer','Opened beauty products cannot be returned for change of mind; they must be unopened with the seal intact. Report damage, wrong or defective items within 48 hours instead.','खुला ब्यूटी उत्पाद पसंद बदलने पर नहीं लौट सकता; सामान बंद और सील सही होनी चाहिए। खराब या गलत सामान की 48 घंटे में शिकायत करें।','Opened beauty item change-of-mind par return nahi hota; unopened aur seal intact hona chahiye. Damaged ya wrong item 48 hours mein report karein.',['RET-4','DWM-1','RET-2'])
            if cat in {'grocery','innerwear','digital'}:
                return Plan(intent,'answer','This category is not returnable for fit or change of mind. Damage, expired, wrong or missing items can be reported within 48 hours with photos.','इस श्रेणी को फ़िट या पसंद बदलने पर वापस नहीं कर सकते। खराब, एक्सपायर, गलत या गुम सामान की 48 घंटे में फ़ोटो के साथ शिकायत करें।','Yeh category fit ya change-of-mind par return nahi hoti. Damage, expired, wrong ya missing item 48 hours mein photos ke saath report karein.',['RET-2','RET-5','DWM-1']+product_ids)
            if has(t,r'(exchange|different size|different colour|different color|बदल)'):
                return Plan('return','answer','Clothing and footwear can be exchanged for another size or colour within the return window, subject to stock. If the size is unavailable, request a return and refund instead.','कपड़े और जूते रिटर्न समय में स्टॉक होने पर साइज़ या रंग के लिए बदल सकते हैं। साइज़ उपलब्ध न हो तो रिटर्न और रिफ़ंड का विकल्प है।','Clothing aur footwear return window mein stock ke hisab se size/colour exchange ho sakte hain. Size unavailable ho to return aur refund option hai.',['RET-9'])
            if has(t,r'(?:(?<!un)\bused\b|tags|packaging|screen lock|account lock|original accessories|इस्तेमाल)'):
                return Plan('return','answer','Returns must be unused with original tags, packaging, accessories and free gifts. Beauty items must be sealed; electronics must have no physical damage and all screen or account locks removed.','रिटर्न सामान बिना इस्तेमाल, मूल टैग, पैकिंग, एक्सेसरी और उपहार के साथ हो। ब्यूटी की सील सही और इलेक्ट्रॉनिक्स में नुकसान या स्क्रीन/अकाउंट लॉक नहीं होना चाहिए।','Return item unused ho, original tags, packaging, accessories aur free gifts ke saath. Beauty seal intact; electronics physically damaged nahi aur screen/account locks removed.',['RET-4'])
            if not cat:
                if has(t,r'(grocery|groceries|fresh|perishable|fruit|vegetable|किराना)'): cat='grocery'
                elif has(t,r'(innerwear|lingerie|swimwear|swimsuit|briefs)'): cat='innerwear'
                elif has(t,r'(gift card|digital code)'): cat='digital'
                elif has(t,r'(home|kitchen|furniture|bedsheet|रसोई)'): cat='home_kitchen'
                elif has(t,r'(beauty|personal care|sealed|ब्यूटी)'): cat='beauty_sealed'
                elif has(t,r'(electronics|smartphone|smartwatch|earbuds|laptop|speaker|इलेक्ट्रॉनिक)'): cat='electronics'
                elif has(t,r'(fashion|clothing|shirt|jeans|kurta|shoe|bag|sneaker|कपड़े|जूते)'): cat='fashion'
                elif has(t,r'(book|notebook|किताब)'): cat='books_media'
            if cat in {'grocery','innerwear','digital'}:
                return Plan(intent,'answer','This category cannot be returned for change of mind; damage, wrong, expired or missing items must be reported within 48 hours with photos.','इस श्रेणी को पसंद बदलने पर वापस नहीं कर सकते; खराब, गलत, एक्सपायर या गुम सामान की 48 घंटे में फ़ोटो के साथ शिकायत करें।','Yeh category change-of-mind par return nahi hoti; damaged, wrong, expired ya missing item 48 hours mein photos ke saath report karein.',['RET-2','RET-5','DWM-1'])
            if not cat: return Plan(intent,'clarify','Which product or category would you like to return?','आप कौन सा उत्पाद या श्रेणी लौटाना चाहती हैं?','Kaunsa product ya category return karna hai?',['RET-2'])
            mentioned=self._date_in(text); delivered=parse_date(order.get('delivered_on')) if order else (mentioned if has(t,r'(deliver|डिलीवर)') else None)
            placed=parse_date(order.get('placed_at')) if order else (mentioned if has(t,r'(sale|order|bought|खरीद)') else None)
            days=return_window(cat,delivered,placed,self.windows.get(cat)); ids=['RET-2']+product_ids
            if cat=='electronics': ids+=['RET-3']+(['RETv3-2'] if delivered and delivered<date(2026,8,1) else [])
            if cat=='fashion': ids+=['RET-8']
            if days is None: return self.unknown()
            deadline=return_deadline(delivered,days) if delivered else None
            eligible=deadline is None or REFERENCE_DATE<=deadline
            fee=49 if cat=='fashion' and not (order and order.get('is_plus')) else 0
            if deadline and order:
                end=fmt(deadline); prefix='You can request a return through' if eligible else 'The return window ended on'
                en=f'{prefix} {end}; the window is {days} calendar days after delivery.'
                hi=f'रिटर्न की अंतिम तारीख {end} है; डिलीवरी के बाद {days} कैलेंडर दिन।' if eligible else f'रिटर्न की अवधि {end} को समाप्त हुई; {days} कैलेंडर दिन थे।'
                hing=f'Return ki last date {end} hai; delivery ke baad {days} calendar days.' if eligible else f'Return window {end} ko khatam hui; {days} calendar days the.'
            else:
                en=f'The return window is {days} calendar days, measured from delivery, subject to item condition.'; hi=f'डिलीवरी के दिन से {days} कैलेंडर दिन का रिटर्न समय है, सामान की शर्तों के अनुसार।'; hing=f'Delivery se {days} calendar days ka return window hai, condition rules ke saath.'
            if cat=='fashion':
                en+=f' Reverse pickup is {fee} rupees'+(' for a change-of-mind return.' if fee else ' for Plus members.'); hi+=f' पिकअप फ़ीस {fee} रुपये।'; hing+=f' Pickup fee {fee} rupees.'; ids+=['RET-6']+(['PLS-2'] if order and order.get('is_plus') else [])
            return Plan(intent,'answer',en,hi,hing,ids,facts={'return_days':days,'deadline':deadline.isoformat() if deadline else None,'eligible':eligible})
        if intent=='damage':
            value=int(p['price_inr']) if p else 0
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
            if order and order.get('status')=='Delivered' and has(t,r'(not received|never received|नहीं मिला|nahi mila)'):
                return Plan(intent,'answer','Check with family, neighbours or building security, then report delivered-but-not-received within 48 hours as a missing item.','परिवार, पड़ोसियों या सुरक्षा कर्मियों से पूछें, फिर 48 घंटे में नहीं मिले डिलीवर्ड सामान की शिकायत करें।','Family, neighbours ya building security se check karein, phir 48 hours mein missing item report karein.',['TRK-2','DWM-1'])
            if has(t,r'(dubai|outside india|international|विदेश)'): return Plan(intent,'answer','Delivery is only within India, to serviceable pincodes.','डिलीवरी केवल भारत के सेवा-योग्य पिनकोड में है।','Delivery sirf India ke serviceable pincodes par hoti hai.',['DEL-5','FAQ-5'])
            if order:
                return Plan(intent,'answer',f"Your order status is {order['status']}; its promised delivery date is {fmt(order.get('promised_date'))}.",f"आपके ऑर्डर की स्थिति {order['status']} है; वादा की गई डिलीवरी तारीख {fmt(order.get('promised_date'))} है।",f"Order status {order['status']} hai; promised delivery {fmt(order.get('promised_date'))} hai.",['TRK-1','DEL-1'],facts={'order.status':order['status'],'order.promised_date':order.get('promised_date')})
            if has(t,r'(midnight|store|pickup|दुकान)'): return self.unknown()
            return Plan(intent,'clarify','What is your order ID?','आपका ऑर्डर नंबर क्या है?','Aapka order ID kya hai?',['IDV-1','STY-5'])
        if intent=='troubleshoot':
            cid='TRB-1' if 'earbud' in t else 'TRB-2' if 'watch' in t else 'TRB-3' if 'charging' in t else 'TRB-4'
            content=self.kb.chunks[cid].text.split('\n',1)[1].strip()
            return Plan(intent,'answer',re.sub(r'(?m)^\d+\.\s*','',content).replace('\n',' '),content,content,[cid])
        if intent=='plus': return Plan(intent,'answer','Plus costs 999 rupees per year: free Express where available, no reverse pickup fee, and return refunds initiated at pickup. It does not extend return windows or post-initiation refund timelines.','प्लस सालाना 999 रुपये: उपलब्ध जगह मुफ़्त एक्सप्रेस, पिकअप फ़ीस नहीं, और रिफ़ंड पिकअप पर शुरू। रिटर्न अवधि या शुरू होने के बाद रिफ़ंड समय नहीं बदलता।','Plus 999 rupees yearly: available pincodes par free Express, pickup fee nahi aur refund pickup par start. Return window aur refund initiation ke baad timeline same hai.',['PLS-1','PLS-2'])
        if intent=='payment':
            if has(t,r'(wallet|वॉलेट)'): return Plan(intent,'answer','Wallet credit never expires and can be used on any order, but cannot be transferred to a bank. For COD refunds, choose bank or Wallet before the refund is made.','वॉलेट बैलेंस कभी समाप्त नहीं होता और किसी ऑर्डर पर लग सकता है, लेकिन बैंक में नहीं भेज सकते। COD रिफ़ंड से पहले बैंक या वॉलेट चुनें।','Wallet balance expire nahi hota, kisi order par use kar sakte hain, bank mein transfer nahi. COD refund hone se pehle bank ya Wallet choose karein.',['PAY-4','REF-3'])
            return Plan(intent,'answer','COD is available up to 10,000 rupees only at enabled pincodes, with a 25 rupee fee per order. Other methods include UPI, cards, net banking and Wallet.','COD 10,000 रुपये तक उपलब्ध पिनकोड में, प्रति ऑर्डर 25 रुपये फ़ीस है। UPI, कार्ड, नेट बैंकिंग और वॉलेट भी उपलब्ध हैं।','COD 10,000 rupees tak enabled pincodes par hai, 25 rupee fee per order. UPI, cards, net banking aur Wallet bhi available hain.',['PAY-1','PAY-2','DEL-5'])
        return self.unknown()
    def unknown(self) -> Plan:
        return Plan('unsupported','answer',"I don't have information about that in the supplied documents. I can connect you to a human colleague.",'दिए गए दस्तावेज़ों में इस बारे में जानकारी नहीं है। मैं आपको मानव सहयोगी से जोड़ सकती हूँ।','Documents mein iski jaankari nahi hai; human colleague se connect kar sakti hoon.',[])
    def refund(self,text:str,order:dict|None) -> Plan:
        t=text.lower(); method=None; initiated=None; ids=['REF-2','KB-00.1']; rrn=None
        if has(t,r'(upi|u p i|यूपीआई)'): method='upi'
        elif has(t,r'(credit|debit|card|कार्ड)'): method='card'
        elif has(t,r'(net.?bank|नेट बैंक)'): method='netbanking'
        elif has(t,r'(wallet|वॉलेट)'): method='wallet'
        if has(t,r'(cash on delivery|cod|कैश ऑन)') and not method:
            return Plan('refund','answer','For COD refunds, choose ZentroMart Wallet, instant within 2 hours, or bank transfer, 5 to 7 business days after verified bank details.','COD रिफ़ंड के लिए ZentroMart Wallet तुरंत, 2 घंटे में, या बैंक डिटेल्स जाँच के बाद 5 से 7 कार्यदिवस में बैंक ट्रांसफ़र चुनें।','COD refund mein ZentroMart Wallet instant, 2 hours mein, ya verified bank details ke baad 5 to 7 business days bank transfer choose karein.',['REF-3','REF-2'])
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
        if not method: return Plan('refund','clarify','Which payment method did you use?','आपने किस तरीके से भुगतान किया था?','Payment kaunsa method se kiya tha?',['REF-2'])
        low,high=self.refunds.get(method,(0,0)); label={'upi':'UPI','card':'card','netbanking':'net banking','wallet':'ZentroMart Wallet','cod_wallet':'ZentroMart Wallet','cod_bank':'bank transfer'}.get(method,method)
        if high==0:
            return Plan('refund','answer',f'{label} refunds are instant, within 2 hours after initiation. For a return, Plus initiation is at pickup; other returns need QC within 2 business days of pickup.',f'{label} रिफ़ंड शुरू होने के बाद तुरंत, 2 घंटे में आता है। प्लस में पिकअप पर शुरू; अन्य रिटर्न में QC के बाद पिकअप से 2 कार्यदिवस में।',f'{label} refund initiation ke baad instant, 2 hours mein aata hai. Plus refund pickup par start; baaki returns QC ke baad pickup se 2 business days mein.',['REF-2','RET-7','PLS-2','KB-00.1'])
        if initiated:
            first=business_add(initiated,low,self.data.holidays); last=business_add(initiated,high,self.data.holidays); ids+=['KB-00.3']
            if order and business_elapsed(last,REFERENCE_DATE,self.data.holidays)>3:
                return Plan('refund','escalate',f'The refund is more than 3 business days beyond its maximum date of {fmt(last)}. I will request a human ticket; the refund reference number (RRN) is {rrn or "not recorded"}.',f'रिफ़ंड की अंतिम तारीख {fmt(last)} से 3 कार्यदिवस से अधिक हो गए हैं। मानव टीम के लिए टिकट चाहिए; reference number (RRN) {rrn or "दर्ज नहीं"} है।',f'Refund maximum date {fmt(last)} se 3 business days se zyada overdue hai. Human team ticket chahiye; reference number (RRN) {rrn or "recorded nahi"} hai.',ids+['ESC-1','REF-6'],'refund_overdue',{'refund_first':first.isoformat(),'refund_last':last.isoformat()})
            return Plan('refund','answer',f'{label} takes {low} to {high} business days: {fmt(first)} to {fmt(last)}, excluding Sundays and warehouse holidays.',f'{label} में {low} से {high} कार्यदिवस: {fmt(first)} से {fmt(last)}, रविवार और गोदाम की छुट्टियाँ छोड़कर।',f'{label} mein {low} to {high} business days: {fmt(first)} se {fmt(last)}, Sundays aur warehouse holidays exclude karke.',ids,facts={'refund_first':first.isoformat(),'refund_last':last.isoformat()})
        return Plan('refund','answer',f'{label} refunds take {low} to {high} business days after initiation; Sundays and warehouse holidays do not count. For returns, initiation follows QC within 2 business days of pickup, or at pickup for Plus.',f'{label} रिफ़ंड शुरू होने के बाद {low} से {high} कार्यदिवस; रविवार और गोदाम छुट्टियाँ नहीं गिनते। रिटर्न में QC के बाद पिकअप से 2 कार्यदिवस में, प्लस में पिकअप पर शुरू होता है।',f'{label} refund initiation ke baad {low} to {high} business days; Sunday aur warehouse holidays exclude. Return refund QC ke baad pickup se 2 business days mein start; Plus ke liye pickup par.',ids+['RET-7','PLS-2'])
