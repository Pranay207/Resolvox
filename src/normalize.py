"""Conservative speech/entity normalization and credential redaction."""
import re,unicodedata
DIGITS={'zero':'0','oh':'0','o':'0','one':'1','two':'2','to':'2','too':'2','three':'3','four':'4','for':'4','five':'5','six':'6','seven':'7','eight':'8','nine':'9','shunya':'0','ek':'1','do':'2','teen':'3','char':'4','chaar':'4','paanch':'5','panch':'5','chhe':'6','chhah':'6','saat':'7','aath':'8','nau':'9','शून्य':'0','एक':'1','दो':'2','तीन':'3','चार':'4','पाँच':'5','पांच':'5','छह':'6','सात':'7','आठ':'8','नौ':'9'}
REPEAT={'double':2,'triple':3,'डबल':2,'ट्रिपल':3}
SCALES={'hundred','thousand','hazaar','hazar','sau','हजार','हज़ार','सौ'}
def ascii_digits(text:str) -> str:
    return ''.join(str(unicodedata.digit(c)) if c.isdigit() else c for c in text)
def number_words(text:str) -> str:
    tokens=re.findall(r'\d+|[A-Za-z]+|[\u0900-\u0963\u0971-\u097f]+|[^\w\s]',ascii_digits(text).lower(),re.UNICODE); out=[]; run=[]
    def flush():
        if not run: return
        if any(x in SCALES for x in run):
            total=0; part=0
            for x in run:
                if x in {'hundred','sau','??'}: part=max(part,1)*100
                elif x in SCALES: total+=max(part,1)*1000; part=0
                else: part+=int(DIGITS.get(x,x))
            out.append(str(total+part))
        else:
            value=''; times=1
            for x in run:
                if x in REPEAT: times=REPEAT[x]
                else: value+=DIGITS.get(x,x)*times; times=1
            out.append(value)
        run.clear()
    for t in tokens:
        numeric=t in DIGITS or t.isdigit() or t in REPEAT or t in SCALES
        if t in {'to','too','for','o'} and not run: numeric=False
        if numeric: run.append(t)
        else: flush(); out.append(t)
    flush(); result=' '.join(out)
    return re.sub(r'\b(ele|fsh|hom|bks|inr|bea|gro|dig)\s*-?\s*(\d{4})\b',lambda m:m[1].upper()+'-'+m[2],result,flags=re.I)
def order_id(text:str) -> str|None:
    literal=re.search(r'(?<!\d)(\d{4})[\s-]*(\d{4})(?!\d)',ascii_digits(text))
    if literal: return literal[1]+literal[2]
    m=re.search(r'(?<!\d)(\d{4})[\s-]*(\d{4})(?!\d)',number_words(text))
    return m[1]+m[2] if m else None
def proof_value(text:str) -> str|None:
    literal=[v for v in re.findall(r'(?<!\d)\d{4,6}(?!\d)',ascii_digits(text)) if len(v) in {4,6} and v!='2026']
    if len(literal)==1: return literal[0]
    vals=[v for v in re.findall(r'(?<!\d)\d{4,6}(?!\d)',number_words(text)) if len(v) in {4,6} and v!='2026']
    return vals[0] if len(vals)==1 else None
def redact(text:str,proof:str|None=None,credential_turn:bool=False) -> str:
    if credential_turn: return '[verification value redacted]'
    text=ascii_digits(text)
    if proof: text=text.replace(proof,'[REDACTED]')
    text=re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b','[REDACTED EMAIL]',text)
    text=re.sub(r'(?<!\d)(?:\+91[ -]?)?[5-9]\d{9}(?!\d)','[REDACTED PHONE]',text)
    return re.sub(r'(?<![\w-])\d{6}(?!\d)','[REDACTED PIN]',text)
def language(text:str,previous:str='en') -> str:
    if re.search(r'[\u0900-\u097f]',text): return 'hi'
    if re.search(r'\b(mera|meri|mujhe|kya|hai|hain|kitne|kab|kaise|chahiye|nahi|kar|wala|mein|hoon|sawaal|parso|theek|namaste)\b',text,re.I): return 'hi-en'
    return 'en' if re.search(r'[A-Za-z]{3,}',text) else previous


_UPI_ACRONYM = re.compile(r'(?<![A-Za-z])U[\s.]*P[\s.]*I(?![A-Za-z])|यू[\s.]*पी[\s.]*आई|यू[\s.]*पी[\s.]*आय|య[ుూ][\s.]*ప[ిీ][\s.]*ఐ|ய[ுூ]?[\s.]*பி[\s.]*ஐ|ಯ[ುೂ][\s.]*ಪಿ[\s.]*ಐ|യ[ുൂ][\s.]*പി[\s.]*ഐ|ਯੂ[\s.]*ਪੀ[\s.]*ਆਈ|ইউ[\s.]*পি[\s.]*আই|યુ[\s.]*પી[\s.]*આઈ', re.I)

def public_acronyms(text:str) -> str:
    """Canonicalize public UPI spellings from speech; never touch digits/proof."""
    return _UPI_ACRONYM.sub('UPI', text)
