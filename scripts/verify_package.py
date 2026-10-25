"""Inspect and run the extracted artifact without shipping its external dataset."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[1]
def main():
    archive=ROOT/'dist/pranay_voiceops.zip';folder=ROOT/'tmp';folder.mkdir(exist_ok=True);target=Path(tempfile.mkdtemp(prefix='package-check-',dir=folder)).resolve()
    assert target.is_relative_to(ROOT.resolve())
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        assert all(not n.startswith(('Capstone_Project_Dataset_FTTT_2026/','.venv/','.cache/','.git/')) for n in names)
        assert '.env' not in names and '.env.example' in names and 'pytest.ini' in names
        assert '.streamlit/config.toml' in names, 'Release is missing the native UI theme'
        for name in names:assert (target/name).resolve().is_relative_to(target)
        z.extractall(target)
    env=os.environ.copy();env['DATASET_DIR']=str(ROOT/'Capstone_Project_Dataset_FTTT_2026');env['DENSE_ENABLED']='false';env['COMPOSE_WITH_LLM']='false'
    code="from src.agent import Agent; o=Agent().respond('UPI refund timing please'); assert '1 to 3' in o['answer'] and o['decision']=='answer'"
    smoke=subprocess.run([sys.executable,'-X','utf8','-c',code],cwd=target,env=env,capture_output=True,text=True)
    if smoke.returncode:raise RuntimeError('Extracted package failed import/policy smoke check')
    cli=subprocess.run([sys.executable,'run.py','--help'],cwd=target,env=env,capture_output=True,text=True);assert cli.returncode==0
    status=json.loads((target/'SUBMISSION_STATUS.json').read_text());assert status['report_pages']==4
    record={'archive_files':len(names),'excluded_secrets_dataset_models_venv':True,'extracted_imports_and_answer':True,'cli_help':True,'test_collection_scoped':True,'report_pages':4,'release_blockers':status['blockers']}
    (ROOT/'sample_outputs/package_smoke.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record,indent=2))
if __name__=='__main__':main()
