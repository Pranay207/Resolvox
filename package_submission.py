"""Package only permitted deliverables, with explicit readiness blockers."""
from pathlib import Path
import hashlib,json,re,struct,subprocess,zipfile
ROOT=Path(__file__).resolve().parent

def mp4_duration(path:Path):
    def boxes(f,end):
        while f.tell()+8<=end:
            begin=f.tell();head=f.read(8);size,kind=struct.unpack('>I4s',head)
            if size==1:size=struct.unpack('>Q',f.read(8))[0]
            if size==0:size=end-begin
            if size<8 or begin+size>end:return None
            if kind==b'moov':
                value=boxes(f,begin+size)
                if value is not None:return value
            elif kind==b'mvhd':
                data=f.read(32);version=data[0];ts=struct.unpack('>I',data[20:24] if version else data[12:16])[0];dur=struct.unpack('>Q' if version else '>I',data[24:32] if version else data[16:20])[0]
                return dur/ts if ts else None
            f.seek(begin+size)
    if not path.is_file():return None
    try:
        with path.open('rb') as f:return boxes(f,path.stat().st_size)
    except (OSError,ValueError,struct.error,IndexError):return None

def status():
    blockers=[];voice_path=ROOT/'sample_outputs/voice_validation.json'
    voice=json.loads(voice_path.read_text(encoding='utf-8')) if voice_path.exists() else {}
    if voice.get('status')!='tested' or voice.get('semantic_validation',{}).get('failed',1) or voice.get('batch',{}).get('failed',1) or voice.get('batch',{}).get('total',0)<5:blockers.append('Live Gnani validation incomplete: configure GNANI_API_KEY locally and run generate_voice_samples.py with semantic checks')
    duration=mp4_duration(ROOT/'demo.mp4')
    if duration is None:blockers.append('User-recorded demo.mp4 missing or duration unverified')
    elif duration>120:blockers.append('demo.mp4 exceeds the 120-second brief limit')
    report=ROOT/'report.pdf';pages=len(re.findall(rb'/Type\s*/Page\b',report.read_bytes())) if report.exists() else 0
    if pages!=4:blockers.append(f'Report expected 4 verified pages; found {pages}')
    return {'ready_to_submit':not blockers,'blockers':blockers,'report_pages':pages,'demo_seconds':duration,'public_repository':'https://github.com/Pranay207/ESD','team_name_assumption':'pranay','speech_provider':'Gnani only','warning':'Mechanical test passes are not organizer scores.'}

def main():
    release=status();(ROOT/'SUBMISSION_STATUS.json').write_text(json.dumps(release,indent=2),encoding='utf-8')
    files=[]
    roots=['README.md','.gitignore','.gitattributes','.env.example','requirements.txt','requirements-lock.txt','pytest.ini','setup.py','setup.ps1','run.py','app.py','eval_step1.py','eval_step2.py','eval_step3.py','eval_adversarial.py','eval_holdout.py','generate_voice_samples.py','check_all.py','package_submission.py','BRIEF_CHECKLIST.md','DESIGN.md','DEMO_SCRIPT.md','THIRD_PARTY.md','VERIFICATION.md','report.pdf','report.md','SUBMISSION_STATUS.json']
    files.extend(ROOT/name for name in roots if (ROOT/name).is_file())
    if (ROOT/'demo.mp4').exists():files.append(ROOT/'demo.mp4')
    for folder in ['src','scripts','tests','sample_outputs']:
        for p in (ROOT/folder).rglob('*'):
            if not p.is_file() or any(part in {'__pycache__','.pytest_cache','voice_inputs'} for part in p.relative_to(ROOT).parts):continue
            if p.suffix.lower() in {'.py','.json','.txt','.wav','.md'}:files.append(p)
    manifest=[]
    for p in files:
        name=p.relative_to(ROOT).as_posix()
        if any(x in name for x in ['Capstone_Project_Dataset','.cache/','.venv/']) or p.name=='.env':raise ValueError('Forbidden archive entry')
        data=p.read_bytes()
        if p.suffix in {'.py','.json','.md','.txt'} and re.search(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}',data):raise ValueError('Potential API secret in deliverable')
        manifest.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    out=ROOT/'dist';out.mkdir(exist_ok=True);archive=out/'pranay_voiceops.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(ROOT).as_posix())
        z.writestr('package_manifest.json',json.dumps({'files':manifest,'release':release},indent=2))
    print(json.dumps({'archive':str(archive),'files':len(files),'release':release},indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
