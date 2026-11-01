"""Synthetic archive fixtures; no model, speech or real video is generated."""
import json
import zipfile
from pathlib import Path
import pytest
import package_submission as package
from scripts.verify_package import verify_manifest


@pytest.fixture
def draft_tree(tmp_path, monkeypatch):
    required=['README.md','.env.example','requirements.txt','run.py','app.py','setup.py',
              'report.pdf','ENGINEERING_DEEP_DIVE.md','LICENSE','src/agent.py']
    for name in required:
        path=tmp_path/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('Synthetic archive test fixture',encoding='utf-8')
    (tmp_path/'.env.example').write_text('GNANI_API_KEY=\n',encoding='utf-8')
    (tmp_path/'.env').write_text('GNANI_API_KEY=unit-secret-not-for-export-123456\n',encoding='utf-8')
    (tmp_path/'SUBMISSION_STATUS.json').write_text('{"unchanged":true}',encoding='utf-8')
    sample=tmp_path/'sample_outputs'
    sample.mkdir()
    (sample/'eval_step1.json').write_text(json.dumps({'summary':{'total':52,'passed':1}}),encoding='utf-8')
    hidden=sample/'history/unreferenced.json'
    hidden.parent.mkdir()
    hidden.write_text('Unreferenced working history',encoding='utf-8')
    (tmp_path/'.cache').mkdir()
    (tmp_path/'.cache/model.bin').write_bytes(b'Not a deliverable')
    monkeypatch.setattr(package,'ROOT',tmp_path)
    release={'ready_to_submit':False,'blockers':[
        'User-recorded demo.mp4 missing or duration unverified',
        'Public GitHub repository access has not been confirmed'],
        'report_pages':4,'demo_seconds':None}
    monkeypatch.setattr(package,'status',lambda:release)
    return tmp_path,release


def test_draft_has_manifest_notice_true_scores_and_no_private_or_unreferenced_files(draft_tree):
    root,_=draft_tree
    before=(root/'SUBMISSION_STATUS.json').read_bytes()
    assert package.main(draft=True)==0
    assert (root/'SUBMISSION_STATUS.json').read_bytes()==before
    with zipfile.ZipFile(root/'dist/pranay_voiceops_draft.zip') as archive:
        assert verify_manifest(archive)['manifest_verified'] is True
        assert archive.testzip() is None
        names=set(archive.namelist())
        assert {'DRAFT_SUBMISSION.txt','ENGINEERING_DEEP_DIVE.md','report.pdf'}<=names
        assert not {'.env','demo.mp4','sample_outputs/history/unreferenced.json','.cache/model.bin'} & names
        release=json.loads(archive.read('SUBMISSION_STATUS.json'))
        assert release['ready_to_submit'] is False and release['package_kind']=='draft'
        assert len(release['blockers'])==2
        assert json.loads(archive.read('sample_outputs/eval_step1.json'))['summary']['passed']==1
    assert not (root/'dist/pranay_voiceops.zip').exists()


def test_final_packaging_still_refuses_without_demo_and_public_access(draft_tree):
    root,_=draft_tree
    assert package.main()==2
    assert not (root/'dist').exists()


@pytest.mark.parametrize('blocker',['Current report visual QA missing or stale','Current speech evidence missing'])
def test_draft_cannot_bypass_other_release_failures(draft_tree,blocker):
    root,release=draft_tree
    release['blockers'].append(blocker)
    assert package.main(draft=True)==2
    assert not (root/'dist').exists()


def test_draft_refuses_missing_required_engineering_document(draft_tree):
    root,_=draft_tree
    (root/'ENGINEERING_DEEP_DIVE.md').unlink()
    with pytest.raises(ValueError,match='Required deliverables missing'):
        package.main(draft=True)
    assert not (root/'dist').exists()


def test_draft_scans_configured_secret_before_writing_zip(draft_tree):
    root,_=draft_tree
    (root/'README.md').write_text('unit-secret-not-for-export-123456',encoding='utf-8')
    with pytest.raises(ValueError,match='Potential API secret'):
        package.main(draft=True)
    assert not (root/'dist').exists()


def test_draft_is_marked_unready_even_when_all_final_checks_pass(draft_tree):
    root,release=draft_tree
    release.update(ready_to_submit=True,blockers=[])
    assert package.main(draft=True)==0
    with zipfile.ZipFile(root/'dist/pranay_voiceops_draft.zip') as archive:
        assert json.loads(archive.read('SUBMISSION_STATUS.json'))['ready_to_submit'] is False


def test_draft_includes_the_two_readme_screenshots(draft_tree):
    root,_=draft_tree
    assets=root/'assets'
    assets.mkdir()
    for name in ['resolvox-desktop.jpg','resolvox-mobile.jpg']:
        (assets/name).write_bytes(b'Synthetic screenshot archive fixture')
    assert package.main(draft=True)==0
    with zipfile.ZipFile(root/'dist/pranay_voiceops_draft.zip') as archive:
        for name in ['resolvox-desktop.jpg','resolvox-mobile.jpg']:
            assert archive.read('assets/'+name)==(assets/name).read_bytes()


def test_draft_notice_accurately_identifies_an_included_demo(draft_tree):
    root,release=draft_tree
    (root/'demo.mp4').write_bytes(b'Synthetic archive fixture; not a real video')
    release['blockers']=['Public GitHub repository access has not been confirmed']
    assert package.main(draft=True)==0
    with zipfile.ZipFile(root/'dist/pranay_voiceops_draft.zip') as archive:
        note=archive.read('DRAFT_SUBMISSION.txt').decode('utf-8')
        assert 'included for review' in note and 'will be added next' not in note
