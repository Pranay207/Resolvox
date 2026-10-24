"""Project settings; secrets never appear in diagnostics."""
from pathlib import Path
from datetime import date
import os
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parent.parent
load_dotenv(ROOT/'.env',override=False)
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError: pass
CACHE=ROOT/'.cache'; CACHE.mkdir(exist_ok=True)
REFERENCE_DATE=date.fromisoformat(os.getenv('REFERENCE_DATE','2026-10-20'))
def dataset_dir() -> Path:
    configured=Path(os.getenv('DATASET_DIR','Capstone_Project_Dataset_FTTT_2026'))
    for p in [configured,ROOT/configured,ROOT/'Capstone_Project_Dataset_FTTT_2026']:
        if (p/'kb').is_dir() and (p/'tools/tools.py').is_file(): return p.resolve()
    raise FileNotFoundError('Run python setup.py or set DATASET_DIR to the official extracted folder.')
