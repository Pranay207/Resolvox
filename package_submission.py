"""Package only permitted deliverables, with explicit readiness blockers."""
from pathlib import Path
import hashlib,json,re,struct,subprocess,zipfile
from scripts.release_evidence import blockers as release_evidence_blockers
from scripts.targeted_release import WARNINGS as TARGETED_WARNINGS
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

DEMO_NAMES=('Resolovox Demo.mp4','demo.mp4')


def demo_file():
    return next((ROOT/name for name in DEMO_NAMES if (ROOT/name).is_file()),ROOT/'demo.mp4')


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
    targeted=(ROOT/'sample_outputs/targeted_live_validation.json').is_file()
    if not targeted:
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
    duration=mp4_duration(demo_file())
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
    public=_json_record('repository_visibility.json')
    if targeted and not (public.get('is_public') is True and public.get('repository_url')=='https://github.com/Pranay207/Resolvox' and public.get('http_status')==200):
        blockers.append('Public GitHub repository access has not been confirmed')
    return {'ready_to_submit':not blockers,'blockers':blockers,'report_pages':pages,
        'demo_seconds':duration,'demo_filename':demo_file().name,'public_repository':'https://github.com/Pranay207/Resolvox',
        'team_name_assumption':'pranay','speech_provider':'Gnani only',
        'answer_path':'document_context_generation','runtime_source_sha256':expected,
        'verification_policy':'targeted_live_with_disclosed_limits' if targeted else 'full_fixture',
        'evaluation_warnings':TARGETED_WARNINGS if targeted else [],
        'warning':'Mechanical test passes are not organizer scores.'}

def referenced_evidence_files():
    """Follow published evidence references; exclude unreferenced working history."""
    names=['engineering_verification.json','reliability_engineering.json','release_update_verification.json','return_date_validation.json','refund_scope_verification_20261031.json',
           'targeted_release_tests_20261031.json','targeted_live_validation.json',
           'targeted_voice_validation.json','pdf_qa.json','eval_step1.json',
           'eval_step2_latest_cases.json','eval_step3_latest_cases.json','language_validation.json',
           'repository_visibility.json','demo_validation.json']
    pending=[ROOT/'sample_outputs'/name for name in names];seen=set();result=[]
    def strings(value):
        if isinstance(value,str):yield value
        elif isinstance(value,dict):
            for key,child in value.items():yield key;yield from strings(child)
        elif isinstance(value,list):
            for child in value:yield from strings(child)
    while pending:
        path=pending.pop()
        if path in seen or not path.is_file():continue
        seen.add(path)
        if path.is_symlink() or not path.resolve().is_relative_to((ROOT/'sample_outputs').resolve()):
            raise ValueError('Unsafe evidence reference')
        result.append(path)
        if path.suffix=='.json':
            try:value=json.loads(path.read_text(encoding='utf-8'))
            except ValueError:continue
            for name in strings(value):
                if isinstance(name,str) and name.startswith('sample_outputs/'):
                    target=ROOT/name
                    if target.is_file():pending.append(target)
    return result


def contains_credential(data):
    patterns=[rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}',rb'\bgsk_[A-Za-z0-9_-]{20,}',
              rb'\bvach_[A-Za-z0-9_=-]{30,}',rb'\b(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{20,}',
              rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
    if any(re.search(pattern,data) for pattern in patterns):return True
    from dotenv import dotenv_values
    for name in ('.env','.env.hosted'):
        path=ROOT/name
        if not path.is_file():continue
        for key,value in dotenv_values(path).items():
            if re.search(r'KEY|TOKEN|SECRET|PASSWORD',key,re.I) and isinstance(value,str) and len(value)>=12 and value.encode() in data:return True
    return False


def main(*,draft=False):
    release=status()
    deferred={'User-recorded demo.mp4 missing or duration unverified',
              'Public GitHub repository access has not been confirmed'}
    blocked=(any(reason not in deferred for reason in release.get('blockers',[]))
             if draft else release.get('ready_to_submit') is not True or bool(release.get('blockers')))
    if blocked:
        print(json.dumps({'status':'blocked','release':release},indent=2))
        return 2
    selected_demo=demo_file()
    release=dict(release,demo_filename=selected_demo.name)
    if draft:
        release=dict(release,ready_to_submit=False,package_kind='draft')
    else:
        (ROOT/'SUBMISSION_STATUS.json').write_text(json.dumps(release,indent=2),encoding='utf-8')
    files=[]
    roots=['.streamlit/config.toml','README.md','LICENSE','assets/resolvox-logo.svg','assets/resolvox-demo-cover.png','assets/resolvox-demo-cover.svg','assets/resolvox-desktop.jpg','assets/resolvox-mobile.jpg','.gitignore','.gitattributes','.env.example','requirements.txt','requirements-lock.txt','pytest.ini','setup.py','setup.ps1','run.py','app.py','eval_step1.py','eval_step2.py','eval_step3.py','eval_adversarial.py','eval_holdout.py','generate_voice_samples.py','check_all.py','package_submission.py','BRIEF_CHECKLIST.md','ENGINEERING_DEEP_DIVE.md','DESIGN.md','DEMO_SCRIPT.md','THIRD_PARTY.md','VERIFICATION.md','report.pdf','report.md','SUBMISSION_STATUS.json']
    files.extend(ROOT/name for name in roots if (ROOT/name).is_file())
    if selected_demo.exists():files.append(selected_demo)
    files.extend(referenced_evidence_files())
    for folder in ['src','scripts','tests']:
        for p in (ROOT/folder).rglob('*'):
            if not p.is_file() or any(part in {'__pycache__','.pytest_cache','voice_inputs'} for part in p.relative_to(ROOT).parts):continue
            relative=p.relative_to(ROOT)
            engineering_evidence=(relative.parts[:2]==('sample_outputs','engineering_artifacts')
                                  and p.suffix.lower() in {'.xml','.log'})
            if p.suffix.lower() in {'.py','.json','.txt','.wav','.md'} or engineering_evidence:files.append(p)
    payloads={}
    for p in sorted(set(files)):
        name=p.relative_to(ROOT).as_posix()
        if (p.is_symlink() or not p.resolve().is_relative_to(ROOT.resolve())
                or any(x in name for x in ['Capstone_Project_Dataset','.cache/','.venv/'])
                or p.name in {'.env','.env.hosted','secrets.toml'}):raise ValueError('Forbidden archive entry')
        data=p.read_bytes()
        if selected_demo.name!='demo.mp4' and p.suffix=='.md':
            text=data.decode('utf-8').replace('](demo.mp4)','](<'+selected_demo.name+'>)').replace('demo.mp4',selected_demo.name)
            data=text.encode('utf-8')
        elif name=='sample_outputs/demo_validation.json':
            record=json.loads(data.decode('utf-8'))
            record['video']=selected_demo.name
            artifacts=record.get('artifacts',{})
            for alias in DEMO_NAMES:
                if alias in artifacts:artifacts[selected_demo.name]=artifacts.pop(alias)
            data=(json.dumps(record,indent=2,ensure_ascii=False)+'\n').encode('utf-8')
        payloads[name]=data
    payloads['SUBMISSION_STATUS.json']=json.dumps(release,indent=2).encode('utf-8')
    if draft:
        demo_note=('The actual '+selected_demo.name+' is included for review.\n' if selected_demo.name in payloads
                   else 'The demo will be added next. No placeholder video is included.\n')
        note=('DRAFT PACKAGE - NOT THE FINAL SUBMISSION\n\n'+demo_note+
              'Before final submission, provide a reviewed demo video (at most 120 seconds), confirm\n'
              'anonymous public repository access, and run python package_submission.py\n'
              'without --draft to rebuild and verify the final package.\n\n'
              'Current blockers:\n'+''.join('- '+reason+'\n' for reason in release.get('blockers',[])))
        payloads['DRAFT_SUBMISSION.txt']=note.encode('utf-8')
    required={'README.md','.env.example','requirements.txt','run.py','app.py','setup.py',
              'report.pdf','ENGINEERING_DEEP_DIVE.md','LICENSE','src/agent.py'}
    if not required<=set(payloads):raise ValueError('Required deliverables missing: '+', '.join(sorted(required-set(payloads))))
    manifest=[]
    for name,data in sorted(payloads.items()):
        if contains_credential(data):raise ValueError('Potential API secret in deliverable: '+name)
        manifest.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    archive=out/('pranay_voiceops_draft.zip' if draft else 'pranay_voiceops.zip')
    if not archive.resolve().is_relative_to(ROOT.resolve()):raise ValueError('Unsafe archive target')
    pending=archive.with_suffix('.zip.part')
    with zipfile.ZipFile(pending,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(payloads.items()):z.writestr(name,data)
        z.writestr('package_manifest.json',json.dumps({'files':manifest,'release':release},indent=2))
    from scripts.verify_package import verify_manifest
    with zipfile.ZipFile(pending) as z:
        verify_manifest(z)
        if z.testzip() is not None:raise ValueError('Archive CRC verification failed')
    pending.replace(archive)
    print(json.dumps({'archive':str(archive),'files':len(payloads),'draft':draft,'release':release},indent=2))
    return 0
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft',action='store_true',help='Prepare a clearly marked draft while demo/public access are pending; retain all other release checks.')
    args=parser.parse_args()
    raise SystemExit(main(draft=args.draft))
