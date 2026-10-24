"""Provider-neutral client: output-only cache, bounded retries, optional fallback."""
import hashlib,json,os,time
import requests
from .config import CACHE
class LLMUnavailable(RuntimeError): pass
class LLM:
    def __init__(self,provider:str|None=None,model:str|None=None):
        self.provider=provider or os.getenv('LLM_PROVIDER','ollama'); self.model=model or os.getenv('LLM_MODEL','qwen3:4b-instruct'); self.last_provider=''; self.cache=CACHE/'llm'; self.cache.mkdir(exist_ok=True)
    def complete(self,system:str,user:str,json_mode:bool=False,cache:bool=True) -> str:
        digest=hashlib.sha256(json.dumps([self.provider,self.model,system,user,json_mode],ensure_ascii=False).encode()).hexdigest(); path=self.cache/(digest+'.json')
        if cache and path.exists():
            value=json.loads(path.read_text(encoding='utf-8')); self.last_provider=value['provider']; return value['text']
        choices=[(self.provider,self.model,os.getenv('LLM_BASE_URL','http://127.0.0.1:11434'),os.getenv('LLM_API_KEY',''))]
        if os.getenv('LLM_FALLBACK_PROVIDER'): choices.append((os.environ['LLM_FALLBACK_PROVIDER'],os.getenv('LLM_FALLBACK_MODEL',''),os.getenv('LLM_FALLBACK_BASE_URL',''),os.getenv('LLM_FALLBACK_API_KEY','')))
        for provider,model,base,key in choices:
            for attempt in range(3):
                try:
                    messages=[{'role':'system','content':system},{'role':'user','content':user}]
                    if provider=='ollama':
                        payload={'model':model,'messages':messages,'stream':False,'think':False,'options':{'temperature':0,'seed':42,'num_predict':240,'num_ctx':8192}}
                        if json_mode: payload['format']='json'
                        response=requests.post(base.rstrip('/')+'/api/chat',json=payload,timeout=float(os.getenv('LLM_TIMEOUT','90')))
                    else:
                        payload={'model':model,'messages':messages,'temperature':0,'max_tokens':240}
                        if json_mode: payload['response_format']={'type':'json_object'}
                        response=requests.post(base.rstrip('/')+'/chat/completions',headers={'Authorization':'Bearer '+key},json=payload,timeout=float(os.getenv('LLM_TIMEOUT','90')))
                    if response.status_code in {403,429,500,502,503,504}: time.sleep(min(2**attempt,4)); continue
                    response.raise_for_status(); data=response.json(); result=data['message']['content'] if provider=='ollama' else data['choices'][0]['message']['content']; self.last_provider=provider+':'+model
                    if cache: path.write_text(json.dumps({'text':result,'provider':self.last_provider},ensure_ascii=False),encoding='utf-8')
                    return result
                except (requests.RequestException,KeyError,ValueError):
                    if attempt<2: time.sleep(2**attempt)
        raise LLMUnavailable('LLM unavailable. Configure .env or start Ollama; no response fabricated.')
BASELINE_SYSTEM="""You are ZentroMart's AI support assistant. You have no company documents or order access. Be honest about uncertainty, never invent completed actions or expose personal data. Answer in the customer's language in 2-3 sentences and disclose that you are an AI assistant. Return JSON with decision (answer, clarify, refuse, escalate) and answer. No markdown."""
def baseline(question:str,llm:LLM|None=None) -> dict:
    client=llm or LLM()
    try:
        data=json.loads(client.complete(BASELINE_SYSTEM,question,json_mode=True)); answer=str(data.get('answer',''))
        if not answer: raise ValueError('Empty answer')
        if not any(x in answer.lower() for x in ['ai assistant','ai support','artificial intelligence','एआई','कृत्रिम बुद्धिमत्ता']):
            from .normalize import language
            lang=language(question)
            answer=({'en':"I'm ZentroMart's AI support assistant. ",'hi':'मैं ZentroMart की AI सहायता सहायक हूँ। ','hi-en':'Main ZentroMart ki AI support assistant hoon. '}[lang])+answer
        return {'answer':answer,'decision':data.get('decision','answer'),'intent':'baseline','retrieved_chunk_ids':[],'sources':[],'tool_calls':[],'provider':client.last_provider,'mode':'prompt_only'}
    except (LLMUnavailable,ValueError): return {'answer':'','decision':'error','intent':'baseline','retrieved_chunk_ids':[],'sources':[],'tool_calls':[],'mode':'blocked','error':'LLM unavailable or invalid JSON'}
