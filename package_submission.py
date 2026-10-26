"""Package only permitted deliverables, with explicit readiness blockers."""
from pathlib import Path
import hashlib,json,re,struct,subprocess,zipfile
from scripts.release_evidence import blockers as release_evidence_blockers
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

def _json_record(name):
    try:
        value=json.loads((ROOT/'sample_outputs'/name).read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):
        return {}


def runtime_source_hashes():
    """The actual answer/speech implementation, never a saved score's label."""
    return {path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT/'src').glob('*.py')) if path.is_file()}


def _current_runtime(record,expected):
    """Require every current source file, including the document-only modules."""
    if not {'src/agent.py','src/document_answers.py','src/document_context.py'} <= set(expected):
        return False
    candidates=[record.get('runtime_source_sha256',{})]
    provenance=record.get('provenance',{})
    if isinstance(provenance,dict):candidates.append(provenance.get('runtime_source_sha256',{}))
    config=record.get('configuration',{})
    if isinstance(config,dict):
        provenance=config.get('provenance',{})
        if isinstance(provenance,dict):candidates.append(provenance.get('runtime_source_sha256',{}))
    return any(isinstance(hashes,dict) and all(hashes.get(name)==digest for name,digest in expected.items())
               for hashes in candidates)


def _complete_live(record,planned):
    values=record.get('summary',{})
    config=record.get('configuration',{})
    return (isinstance(values,dict) and isinstance(config,dict)
            and config.get('evaluation_mode')=='live_compose_true'
            and values.get('complete') is True and record.get('complete') is not False
            and values.get('planned')==planned and values.get('total')==planned
            and isinstance(record.get('results'),list) and len(record['results'])==planned)


def status():
    # Recompute every readiness condition from actual current evidence. An old
    # perfect score must not clear unresolved verification/report blockers.
    blockers=release_evidence_blockers(ROOT);expected=runtime_source_hashes()
    for step,planned,label in ((2,52,'questions'),(3,96,'conversation turns')):
        live=_json_record(f'eval_step{step}_live_current.json')
        if not _current_runtime(live,expected):
            blockers.append(f'Current source-only {label} verification missing or stale')
        elif not _complete_live(live,planned):
            blockers.append(f'Current source-only {label} verification incomplete: {planned} responses required')
        else:
            summary=live['summary']
            if summary.get('passed')!=planned or summary.get('failed',0)!=0 or summary.get('errors')!=0:
                blockers.append(f'Current source-only {label} verification has failed or erroneous responses')
    engineering=_json_record('engineering_verification.json')
    pytest=engineering.get('pytest',{})
    if (not _current_runtime(engineering,expected) or not isinstance(pytest,dict)
            or type(pytest.get('total')) is not int or pytest['total']<=0
            or pytest.get('passed')!=pytest['total'] or pytest.get('exit_code')!=0):
        blockers.append('Current engineering test verification missing, stale or failing')
    voice=_json_record('voice_validation.json')
    batch=voice.get('batch',{});semantic=voice.get('semantic_validation',{})
    checks=semantic.get('checks',[]) if isinstance(semantic,dict) else []
    total=batch.get('total',0) if isinstance(batch,dict) else 0
    voice_passed=(voice.get('status')=='tested' and voice.get('live_llm_composition_enabled') is True
        and isinstance(batch,dict) and isinstance(semantic,dict)
        and type(total) is int and total>=5
        and batch.get('succeeded')==total and batch.get('failed')==0
        and semantic.get('passed')==total and semantic.get('failed')==0
        and isinstance(checks,list) and len(checks)==total
        and all(isinstance(check,dict) and check.get('passed') is True for check in checks))
    finished={'runtime_source_sha256':voice.get('runtime_source_sha256_finished',{})}
    if (not _current_runtime(voice,expected) or not _current_runtime(finished,expected)
            or voice.get('source_runtime_unchanged') is not True or not voice_passed):
        blockers.append('Current Gnani speech semantic validation missing, stale or failing')
    duration=mp4_duration(ROOT/'demo.mp4')
    if duration is None:blockers.append('User-recorded demo.mp4 missing or duration unverified')
    elif duration<=0 or duration>120:blockers.append('demo.mp4 must contain at most 120 seconds of valid video')
    report=ROOT/'report.pdf'
    try:report_bytes=report.read_bytes()
    except OSError:report_bytes=b''
    pages=len(re.findall(rb'/Type\s*/Page\b',report_bytes))
    if not 1 <= pages <= 4:blockers.append(f'Report must contain 1 to 4 verified pages; found {pages}')
    qa=_json_record('pdf_qa.json')
    if (not _current_runtime(qa,expected) or not report_bytes
            or qa.get('pdf_sha256')!=hashlib.sha256(report_bytes).hexdigest()
            or qa.get('pages')!=pages or qa.get('visually_reviewed_pages')!=list(range(1,pages+1))
            or qa.get('layout_issues_found') is not False):
        blockers.append('Current report visual QA missing or stale')
    return {'ready_to_submit':not blockers,'blockers':blockers,'report_pages':pages,
        'demo_seconds':duration,'public_repository':'https://github.com/Pranay207/Resolvox',
        'team_name_assumption':'pranay','speech_provider':'Gnani only',
        'answer_path':'document_context_generation','runtime_source_sha256':expected,
        'warning':'Mechanical test passes are not organizer scores.'}

def main():
    release=status()
    if release.get('ready_to_submit') is not True or release.get('blockers'):
        print(json.dumps({'status':'blocked','release':release},indent=2))
        return 2
    (ROOT/'SUBMISSION_STATUS.json').write_text(json.dumps(release,indent=2),encoding='utf-8')
    files=[]
    roots=['.streamlit/config.toml','README.md','.gitignore','.gitattributes','.env.example','requirements.txt','requirements-lock.txt','pytest.ini','setup.py','setup.ps1','run.py','app.py','eval_step1.py','eval_step2.py','eval_step3.py','eval_adversarial.py','eval_holdout.py','generate_voice_samples.py','check_all.py','package_submission.py','BRIEF_CHECKLIST.md','DESIGN.md','DEMO_SCRIPT.md','THIRD_PARTY.md','VERIFICATION.md','report.pdf','report.md','SUBMISSION_STATUS.json']
    files.extend(ROOT/name for name in roots if (ROOT/name).is_file())
    if (ROOT/'demo.mp4').exists():files.append(ROOT/'demo.mp4')
    for folder in ['src','scripts','tests','sample_outputs']:
        for p in (ROOT/folder).rglob('*'):
            if not p.is_file() or any(part in {'__pycache__','.pytest_cache','voice_inputs'} for part in p.relative_to(ROOT).parts):continue
            relative=p.relative_to(ROOT)
            engineering_evidence=(relative.parts[:2]==('sample_outputs','engineering_artifacts')
                                  and p.suffix.lower() in {'.xml','.log'})
            if p.suffix.lower() in {'.py','.json','.txt','.wav','.md'} or engineering_evidence:files.append(p)
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
