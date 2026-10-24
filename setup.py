"""One-command environment/data/model setup. Run with Python 3.11+."""
from pathlib import Path
import argparse,hashlib,json,ssl,subprocess,sys,urllib.request,zipfile
ROOT=Path(__file__).resolve().parent
DATA_URL='https://drive.google.com/uc?export=download&id=1jeGjWgZJ4vdfmbB71kghovcCUYNeSHOY'
MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
MODEL_REVISION='e8f8c211226b894fcb81acc59f3b34ba3efd5f42'
def download(url,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    request=urllib.request.Request(url,headers={'User-Agent':'VoiceOps-capstone/1.0'})
    with urllib.request.urlopen(request,timeout=120,context=ssl.create_default_context()) as response, path.with_suffix(path.suffix+'.part').open('wb') as f:
        while block:=response.read(1024*1024): f.write(block)
    path.with_suffix(path.suffix+'.part').replace(path)
def main():
    p=argparse.ArgumentParser(); p.add_argument('--models',action='store_true'); p.add_argument('--skip-install',action='store_true'); args=p.parse_args()
    if not args.skip_install: subprocess.run([sys.executable,'-m','pip','install','-r',str(ROOT/'requirements.txt')],check=True)
    data=ROOT/'Capstone_Project_Dataset_FTTT_2026'
    if not data.exists():
        archive=ROOT/'tmp/dataset.zip'; download(DATA_URL,archive)
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                target=(ROOT/name).resolve()
                if not target.is_relative_to(ROOT): raise ValueError('Unsafe archive member')
            z.extractall(ROOT)
    subprocess.run([sys.executable,'-X','utf8',str(data/'validate_dataset.py')],check=True)
    if args.models:
        target=ROOT/'.cache/embedding_model'; target.mkdir(parents=True,exist_ok=True)
        revision=target/'revision.txt'
        if revision.exists(): sha=revision.read_text().strip()
        else:
            sha=MODEL_REVISION
            revision.write_text(sha)
        for remote,local in [('tokenizer.json','tokenizer.json'),('onnx/model_quint8_avx2.onnx','model.onnx')]:
            file=target/local
            if not file.exists():
                print('Downloading',remote,flush=True); download(f'https://huggingface.co/{MODEL}/resolve/{sha}/{remote}?download=true',file)
        hashes={name:hashlib.sha256((target/name).read_bytes()).hexdigest() for name in ['tokenizer.json','model.onnx']}
        (target/'checksums.json').write_text(json.dumps(hashes,indent=2))
        print('Model pinned to',sha,flush=True)
    print('Setup complete. Configure .env; python -m streamlit run app.py')
if __name__=='__main__': main()
