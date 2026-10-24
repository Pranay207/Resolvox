"""Read public catalog/calendar only; private orders stay behind supplied tools."""
import csv
from pathlib import Path
from .config import dataset_dir
class Data:
    def __init__(self,root: Path|None=None):
        self.root=root or dataset_dir()
        self.products={r['sku']:r for r in self.read('products')}
        self.holidays={r['date'] for r in self.read('holidays')}
        self.pincodes={r['pincode']:r for r in self.read('pincodes')}
    def read(self,table: str) -> list[dict[str,str]]:
        if table not in {'products','holidays','pincodes'}: raise ValueError('Use supplied tools for private tables')
        with (self.root/'data'/(table+'.csv')).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
