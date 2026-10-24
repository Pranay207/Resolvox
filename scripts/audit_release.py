"""Check deliverables against configured secrets without printing their values."""
from pathlib import Path
import json,subprocess,zipfile
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]

def main():
    values=dotenv_values(ROOT/'.env')
    secrets=[str(values[k]).encode() for k in ('GNANI_API_KEY','LLM_API_KEY','LLM_FALLBACK_API_KEY') if values.get(k)]
    ignored=subprocess.run(['git','check-ignore','--quiet','.env'],cwd=ROOT).returncode==0
    assert ignored,'Local environment file must stay ignored'
    names=subprocess.check_output(['git','ls-files','-c','-o','--exclude-standard'],cwd=ROOT,text=True,encoding='utf-8').splitlines()
    checked=0
    for name in set(names):
        path=ROOT/name
        if not path.is_file():continue
        data=path.read_bytes()
        if any(secret in data for secret in secrets):raise RuntimeError('Configured secret found in deliverable: '+name)
        assert name!='.env' and not name.startswith(('Capstone_Project_Dataset_FTTT_2026/','.cache/','.venv/'))
        checked+=1
    archive=ROOT/'dist/pranay_voiceops.zip';entries=0
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                assert name!='.env' and not name.startswith(('Capstone_Project_Dataset_FTTT_2026/','.cache/','.venv/','.git/'))
                if any(secret in z.read(name) for secret in secrets):raise RuntimeError('Configured secret found in archive entry: '+name)
                entries+=1
    record={'passed':True,'env_ignored':ignored,'deliverables_checked':checked,'archive_entries_checked':entries,'configured_secret_values_checked':len(secrets),'secret_values_printed':False}
    (ROOT/'sample_outputs/secret_audit.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))

if __name__=='__main__':main()
