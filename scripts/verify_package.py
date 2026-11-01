"""Verify archive hashes and smoke-test its explicit offline excerpt diagnostic."""
from pathlib import Path, PurePosixPath
import hashlib,json,os,re,subprocess,sys,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[1]


def verify_manifest(archive):
    """Every archived deliverable must match its unique manifest size/hash."""
    names=archive.namelist()
    if len(names)!=len(set(names)):
        raise ValueError('Duplicate archive entries')
    if 'package_manifest.json' not in names:
        raise ValueError('Archive manifest missing')
    for name in names:
        path=PurePosixPath(name)
        if not name or '\\' in name or path.is_absolute() or '..' in path.parts or ':' in name:
            raise ValueError('Unsafe archive path')
    try:manifest=json.loads(archive.read('package_manifest.json'))
    except (ValueError,KeyError) as exc:raise ValueError('Invalid archive manifest') from exc
    if not isinstance(manifest,dict) or not isinstance(manifest.get('files'),list):
        raise ValueError('Invalid archive manifest')
    listed={}
    for entry in manifest['files']:
        if not isinstance(entry,dict) or not isinstance(entry.get('path'),str):
            raise ValueError('Invalid manifest entry')
        name=entry['path']
        if name in listed:raise ValueError('Duplicate manifest entry')
        listed[name]=entry
    if set(listed)!=set(names)-{'package_manifest.json'}:
        raise ValueError('Manifest does not cover exactly the archived deliverables')
    for name,entry in listed.items():
        data=archive.read(name)
        if type(entry.get('bytes')) is not int or entry['bytes']!=len(data):
            raise ValueError('Manifest byte count mismatch: '+name)
        digest=entry.get('sha256')
        if not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest) or hashlib.sha256(data).hexdigest()!=digest:
            raise ValueError('Manifest SHA256 mismatch: '+name)
    return {'manifest_verified':True,'manifest_deliverables':len(listed)}


def main():
    archive=ROOT/'dist/pranay_voiceops.zip';folder=ROOT/'tmp';folder.mkdir(exist_ok=True);target=Path(tempfile.mkdtemp(prefix='package-check-',dir=folder)).resolve()
    assert target.is_relative_to(ROOT.resolve())
    with zipfile.ZipFile(archive) as z:
        integrity=verify_manifest(z)
        names=z.namelist()
        assert all(not n.startswith(('Capstone_Project_Dataset_FTTT_2026/','.venv/','.cache/','.git/')) for n in names)
        assert all('voice_inputs' not in PurePosixPath(n).parts for n in names)
        assert '.env' not in names and '.streamlit/secrets.toml' not in names
        required={'.env.example','pytest.ini','.streamlit/config.toml','README.md','LICENSE','report.pdf',
                  'requirements.txt','run.py','app.py','ENGINEERING_DEEP_DIVE.md','SUBMISSION_STATUS.json','demo.mp4',
                  'src/agent.py','src/document_answers.py','src/document_context.py'}
        assert required<=set(names),'Release is missing required source or submission files'
        for name in names:assert (target/name).resolve().is_relative_to(target)
        z.extractall(target)
    env=os.environ.copy();env['DATASET_DIR']=str(ROOT/'Capstone_Project_Dataset_FTTT_2026');env['DENSE_ENABLED']='false';env['COMPOSE_WITH_LLM']='false'
    code="""from src.agent import Agent
output=Agent(compose=False).respond('UPI refund timing please')
assert output['composition']=='document_excerpts'
assert 'offline; no generated answer' in output['answer']
assert output['decision']=='answer' and not output.get('llm')
sources={source['id']:source['text'] for source in output['sources']}
assert 'REF-2' in sources and output['citations']
assert all(citation['quote'] in sources[citation['id']] for citation in output['citations'])
"""
    smoke=subprocess.run([sys.executable,'-X','utf8','-c',code],cwd=target,env=env,capture_output=True,text=True)
    if smoke.returncode:raise RuntimeError('Extracted package failed import/document-excerpt diagnostic check')
    cli=subprocess.run([sys.executable,'run.py','--help'],cwd=target,env=env,capture_output=True,text=True);assert cli.returncode==0
    status=json.loads((target/'SUBMISSION_STATUS.json').read_text())
    assert status.get('ready_to_submit') is True and status.get('blockers') == [], 'Release blockers remain'
    assert 1 <= status['report_pages'] <= 4
    record={'archive_files':len(names),**integrity,'excluded_secrets_dataset_models_venv':True,
            'extracted_imports_and_document_excerpts':True,'smoke_mode':'offline document_excerpts diagnostic',
            'llm_inference_tested':False,'recorded_release_status_checked':True,
            'release_gate_rerun_in_smoke':False,'dataset_source':'working checkout; not a clean setup',
            'smoke_dense_enabled':False,'cli_help':True,'test_collection_scoped':True,
            'report_pages':status['report_pages'],'release_blockers':status['blockers']}
    (ROOT/'sample_outputs/package_smoke.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record,indent=2))
if __name__=='__main__':main()
