"""BM25 + quantized multilingual MiniLM vectors, cached and loaded once."""
from collections import Counter
from functools import lru_cache
import hashlib,math,os,re
import numpy as np
from .config import CACHE
from .kb import KnowledgeBase,Chunk,AUTHORITY
from .normalize import number_words
MODEL_ID='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
MODEL_DIR=CACHE/'embedding_model'
def tokenize(text:str) -> list[str]: return re.findall(r'\w+',text.lower(),re.UNICODE)
class Dense:
    def __init__(self):
        from tokenizers import Tokenizer
        import onnxruntime as ort
        opts=ort.SessionOptions(); opts.intra_op_num_threads=3; opts.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(MODEL_DIR/'model.onnx'),sess_options=opts,providers=['CPUExecutionProvider'])
        self.tokenizer=Tokenizer.from_file(str(MODEL_DIR/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=256); self.tokenizer.enable_padding(pad_id=0,pad_token='[PAD]')
    def encode(self,texts:list[str]) -> np.ndarray:
        rows=[]
        for start in range(0,len(texts),12):
            encoded=self.tokenizer.encode_batch(texts[start:start+12])
            inputs={'input_ids':np.array([x.ids for x in encoded],dtype=np.int64),'attention_mask':np.array([x.attention_mask for x in encoded],dtype=np.int64),'token_type_ids':np.array([x.type_ids for x in encoded],dtype=np.int64)}
            allowed={x.name for x in self.session.get_inputs()}; output=self.session.run(None,{k:v for k,v in inputs.items() if k in allowed})[0]
            if output.ndim==3:
                mask=inputs['attention_mask'][...,None]; output=(output*mask).sum(axis=1)/np.maximum(mask.sum(axis=1),1)
            output=output/np.maximum(np.linalg.norm(output,axis=1,keepdims=True),1e-12); rows.extend(output)
        return np.asarray(rows,dtype=np.float32)
@lru_cache(maxsize=1)
def dense_model() -> Dense: return Dense()
class Retriever:
    def __init__(self,kb:KnowledgeBase,dense:bool|None=None):
        self.kb=kb; self.chunks=list(kb.chunks.values()); self.tokens=[Counter(tokenize(c.title+' '+c.text)) for c in self.chunks]
        self.lengths=[sum(t.values()) for t in self.tokens]; self.avg=sum(self.lengths)/len(self.lengths); self.df=Counter(w for c in self.tokens for w in c)
        self.dense_status='disabled'; self.vectors=None; self.model=None
        enabled=(os.getenv('DENSE_ENABLED','true').lower()=='true') if dense is None else dense
        if enabled and (MODEL_DIR/'model.onnx').exists():
            self.model=dense_model(); fingerprint=hashlib.sha256(('v1'+(MODEL_DIR/'revision.txt').read_text()+''.join(c.text for c in self.chunks)).encode()).hexdigest()[:20]; file=CACHE/f'vectors-{fingerprint}.npy'
            if file.exists(): self.vectors=np.load(file,allow_pickle=False)
            else: self.vectors=self.model.encode([c.title+'\n'+c.text for c in self.chunks]); np.save(file,self.vectors)
            self.dense_status='multilingual MiniLM ONNX int8'
        elif enabled: self.dense_status='unavailable: run python setup.py --models'
    def search(self,query:str,k:int=10,historical:bool=False) -> list[dict]:
        q=Counter(tokenize(number_words(query))); bm=[]
        for tf,length in zip(self.tokens,self.lengths):
            score=0.
            for w in q:
                if tf[w]: score+=math.log(1+(len(self.tokens)-self.df[w]+.5)/(self.df[w]+.5))*tf[w]*2.5/(tf[w]+1.5*(.25+.75*length/self.avg))
            bm.append(score)
        ranks={i:0. for i in range(len(bm))}
        for rank,i in enumerate(sorted(ranks,key=lambda i:bm[i],reverse=True)):
            if bm[i]>0: ranks[i]+=1/(40+rank)
        similarities=np.zeros(len(bm))
        if self.model is not None:
            similarities=self.vectors@self.model.encode([query])[0]
            for rank,i in enumerate(np.argsort(-similarities)): ranks[int(i)]+=1/(40+rank)
        scored=[]
        for i,c in enumerate(self.chunks):
            if not self.kb.allowed(c,historical): continue
            if bm[i]<=0 and similarities[i]<.20: continue
            weight={0:1.,1:1.15,2:1.10,3:1.02,4:.8,5:.65}[AUTHORITY[c.doc_type]]
            scored.append({'chunk':c,'score':round(ranks[i]*weight,6),'dense_score':round(float(similarities[i]),4)})
        return sorted(scored,key=lambda x:x['score'],reverse=True)[:k]
