"""Section-preserving KB parsing and successor-authorized historical scope."""
from dataclasses import dataclass,asdict
from pathlib import Path
import re
from .config import dataset_dir
AUTHORITY={'meta':0,'policy':1,'agent_guide':2,'help':3,'faq':4,'marketing':5}
@dataclass(frozen=True)
class Chunk:
    id:str; text:str; file:str; doc_type:str; status:str; effective_from:str; version:str; title:str
    def public(self) -> dict: return asdict(self)
class KnowledgeBase:
    def __init__(self,root:Path|None=None):
        self.chunks={}
        for path in sorted(((root or dataset_dir())/'kb').glob('*.md')):
            text=path.read_text(encoding='utf-8-sig'); header=text.split('---',2)[1]
            meta=dict(re.findall(r'^([\w_]+):\s*(.+)$',header,re.M))
            matches=list(re.finditer(r'^##\s*\[([^\]]+)\]\s*(.+)$',text,re.M))
            for i,m in enumerate(matches):
                body=text[m.start():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
                self.chunks[m[1]]=Chunk(m[1],body,path.name,meta['doc_type'],meta['status'],meta['effective_from'],meta.get('version',''),m[2])
    def allowed(self,c:Chunk,historical:bool=False) -> bool:
        return c.status=='current' or (historical and c.id=='RETv3-2')
    def require(self,*ids:str) -> list[Chunk]: return [self.chunks[i] for i in dict.fromkeys(ids) if i in self.chunks]
