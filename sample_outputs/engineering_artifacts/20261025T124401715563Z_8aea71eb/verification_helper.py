"""Run real offline engineering verification and publish a provenance receipt.

Import-safe: importing this module does not run pytest, validation or inference.
Only main() launches the full suite and the supplied dataset validator. A failed
attempt keeps its real logs and never publishes current passing evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def path_key(root, path):
    return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def hash_paths(root, paths):
    return {path_key(root, path): sha256(path) for path in sorted(set(paths))}


def runtime_hashes(root):
    paths = list((root / 'src').glob('*.py'))
    bindings = root / 'src' / 'rule_bindings.json'
    if not paths or not bindings.is_file():
        raise ValueError('Missing runtime Python sources or rule_bindings.json')
    return hash_paths(root, paths + [bindings])


def frozen_inputs(root, helper):
    dataset = root / 'Capstone_Project_Dataset_FTTT_2026'
    # Match the live driver's treatment of append-only tool outputs: these
    # are not policy, catalog, practice, validator or tool source inputs.
    generated_outputs = {'tools/tickets_created.csv'}
    dataset_paths = [p for p in dataset.rglob('*')
                     if p.is_file() and p.suffix.lower() in {'.py', '.csv', '.md', '.json'}
                     and p.relative_to(dataset).as_posix() not in generated_outputs]
    test_paths = [p for p in (root / 'tests').rglob('*')
                  if p.is_file() and p.suffix.lower() in {'.py', '.json', '.csv'}]
    test_paths.append(root / 'pytest.ini')
    return {'runtime_source_sha256': runtime_hashes(root),
            'test_source_sha256': hash_paths(root, test_paths),
            'dataset_source_sha256': hash_paths(root, dataset_paths),
            'verification_helper_sha256': sha256(helper)}


def git_state(root):
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, check=True,
                          text=True, encoding='utf-8', capture_output=True).stdout.strip()
    if not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', head):
        raise ValueError('Git did not return a valid HEAD object ID')
    status = subprocess.run(['git', 'status', '--porcelain=v1'], cwd=root, check=True,
                            text=True, encoding='utf-8', capture_output=True).stdout.splitlines()
    return {'head': head, 'dirty': bool(status), 'status_porcelain': status}


def selected_environment(root):
    # Use the same environment-over-dotenv precedence as src.config, without
    # importing runtime modules or copying private values into the receipt.
    from dotenv import dotenv_values
    file_values = {key: value for key, value in dotenv_values(root / '.env').items()
                   if isinstance(value, str)}
    env = dict(file_values, **os.environ)
    provider, model = env.get('LLM_PROVIDER', 'ollama'), env.get('LLM_MODEL', 'qwen3:4b-instruct')
    if any(not re.fullmatch(r'[A-Za-z0-9_:./+@-]{1,180}', value) for value in (provider, model)):
        raise ValueError('Provider/model must be public identifiers')
    llm_timeout = float(env.get('LLM_TIMEOUT', '120'))
    rag_timeout = float(env.get('RAG_LLM_TIMEOUT', '120'))
    if any(not math.isfinite(value) or value <= 0 for value in (llm_timeout, rag_timeout)):
        raise ValueError('Selected timeouts must be finite positive numbers')
    public = {'provider': provider, 'model': model,
              'request_timeout_seconds': rag_timeout,
              'llm_timeout_seconds': llm_timeout,
              'rag_llm_timeout_seconds': rag_timeout,
              'configuration_scope': 'Selected application settings; no inference score is claimed by this engineering run.'}
    # The full test suite is deliberately offline. Do not let inherited pytest
    # selectors silently turn a full regression into a subset.
    env.update(COMPOSE_WITH_LLM='false', PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
               PYTEST_ADDOPTS='')
    env.pop('PYTEST_CURRENT_TEST', None)
    env.pop('PYTEST_PLUGINS', None)
    return env, public


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.new')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n',
                         encoding='utf-8', newline='\n')
    temporary.replace(path)


def parse_junit(path):
    """Read actual pytest JUnit counts and time; never invent a suite total.

    JUnit does not contain a dependable process exit code. The caller records
    the real subprocess return code independently.
    """
    tree = ET.parse(path)
    suites = [node for node in tree.getroot().iter()
              if node.tag.rsplit('}', 1)[-1] == 'testsuite'
              and not any(child.tag.rsplit('}', 1)[-1] == 'testsuite' for child in node)]
    if not suites:
        raise ValueError('JUnit XML contains no leaf testsuite')
    totals = dict(total=0, failures=0, errors=0, skipped=0)
    duration = 0.0
    for suite in suites:
        for output, attribute in [('total', 'tests'), ('failures', 'failures'),
                                  ('errors', 'errors'), ('skipped', 'skipped')]:
            value = suite.attrib.get(attribute)
            if value is None or not re.fullmatch(r'\d+', value):
                raise ValueError('Missing or invalid JUnit count: ' + attribute)
            totals[output] += int(value)
        seconds = float(suite.attrib['time'])
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError('Invalid JUnit duration')
        duration += seconds
    passed = totals['total'] - totals['failures'] - totals['errors'] - totals['skipped']
    if totals['total'] <= 0 or passed < 0:
        raise ValueError('Empty or inconsistent JUnit totals')
    cases = [node for node in tree.getroot().iter() if node.tag.rsplit('}', 1)[-1] == 'testcase']
    if not totals['failures'] and not totals['errors'] and len(cases) != totals['total']:
        raise ValueError('Passing JUnit totals do not match actual testcase entries')
    return dict(totals, passed=passed, duration_seconds=round(duration, 6),
                testcase_entries=len(cases), result_source='pytest_junit_xml')


def parse_dataset_log(path):
    text = Path(path).read_text(encoding='utf-8')
    overall = re.search(r'PASS\s*[\u2014\u2013-]\s*all\s+([\d,]+)\s+CSVs,\s*([\d,]+)\s+KB documents', text)
    counts = {key: int(number.replace(',', '')) for number, key in
              re.findall(r'([\d,]+)\s+(orders|items|logs|questions|conversations)\b', text)}
    if not overall or set(counts) != {'orders', 'items', 'logs', 'questions', 'conversations'}:
        raise ValueError('Official dataset validator did not emit its complete PASS summary')
    return {'csv_files': int(overall[1].replace(',', '')),
            'kb_documents': int(overall[2].replace(',', '')),
            'orders': counts['orders'], 'order_items': counts['items'],
            'support_logs': counts['logs'], 'practice_questions': counts['questions'],
            'conversations': counts['conversations'], 'result_source': 'official_validator_stdout'}


def run_stage(command, root, env, log, unchanged):
    started = utc_now()
    timer = time.perf_counter()
    mutation = False
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with Path(log).open('wb') as output:
        process = subprocess.Popen(command, cwd=root, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, creationflags=flags)
        try:
            while process.poll() is None:
                try:
                    stable = unchanged()
                except (OSError, ValueError):
                    stable = False
                if not stable:
                    mutation = True
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    break
                time.sleep(1)
            exit_code = process.wait()
        except BaseException:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            raise
    return {'started_at': started, 'finished_at': utc_now(), 'exit_code': exit_code,
            'wall_duration_seconds': round(time.perf_counter() - timer, 6),
            'command': subprocess.list2cmdline([str(arg) for arg in command]),
            'argv': [str(arg) for arg in command], 'log': path_key(root, log),
            'log_sha256': sha256(log), 'stopped_for_input_change': mutation}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    helper = Path(__file__).resolve()
    attempt_name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_' + uuid.uuid4().hex[:8]
    attempt = root / 'tmp' / 'engineering_runs' / attempt_name
    current = root / 'sample_outputs' / 'engineering_verification.json'
    lock = root / 'tmp' / 'final_engineering.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(handle, json.dumps({'pid': os.getpid(), 'started_at': utc_now()}).encode('utf-8'))
    os.close(handle)
    result = {'started_at': utc_now(), 'status': 'running', 'complete': False,
              'scope': 'Full offline engineering regressions and official dataset integrity; not semantic certification or organizer scoring.',
              'answer_path': 'document_context_generation', 'attempt_directory': path_key(root, attempt),
              'excluded_generated_outputs': ['Capstone_Project_Dataset_FTTT_2026/tools/tickets_created.csv']}
    before = None
    try:
        attempt.mkdir(parents=True)
        current.parent.mkdir(exist_ok=True)
        # Preserve exact previous bytes and remove stale current promotion.
        if current.exists():
            previous = attempt / 'previous_engineering_verification.json'
            current.replace(previous)
            result['previous_receipt'] = path_key(root, previous)
            result['previous_receipt_sha256'] = sha256(previous)
        before = frozen_inputs(root, helper)
        result.update(before)
        result['git_started'] = git_state(root)
        result['runtime_commit'] = result['git_started']['head']
        env, public = selected_environment(root)
        result['inference_environment'] = public
        result['pytest_environment'] = {'COMPOSE_WITH_LLM': False, 'PYTEST_ADDOPTS': '',
                                        'scope': 'All tests under tests/; inherited selectors disabled.'}
        write_json(attempt / 'attempt_started.json', result)
        print('Engineering attempt: ' + str(attempt), flush=True)
        unchanged = lambda: frozen_inputs(root, helper) == before
        junit = attempt / 'pytest.xml'
        command = [sys.executable, '-u', '-m', 'pytest', str(root / 'tests'), '-q',
                   '-p', 'no:cacheprovider', '--junitxml=' + str(junit),
                   '-o', 'junit_family=xunit2', '-o', 'addopts=']
        result['pytest'] = run_stage(command, root, env, attempt / 'pytest.log', unchanged)
        if junit.exists():
            result['pytest'].update(parse_junit(junit), junit_xml=path_key(root, junit),
                                    junit_xml_sha256=sha256(junit))
        else:
            raise ValueError('Pytest produced no JUnit XML; see the actual pytest log')
        if not unchanged() or result['pytest']['stopped_for_input_change']:
            raise ValueError('Runtime, test, dataset or helper bytes changed during pytest')
        if (result['pytest']['exit_code'] != 0 or result['pytest']['failures']
                or result['pytest']['errors']):
            raise ValueError('Full pytest suite failed; current evidence remains pending')
        print('Pytest completed: ' + str(result['pytest']['passed']) + '/' + str(result['pytest']['total']), flush=True)
        validator = root / 'Capstone_Project_Dataset_FTTT_2026' / 'validate_dataset.py'
        result['dataset_validation'] = run_stage([sys.executable, '-u', str(validator)],
                    root, env, attempt / 'dataset_validation.log', unchanged)
        if not unchanged() or result['dataset_validation']['stopped_for_input_change']:
            raise ValueError('Runtime, test, dataset or helper bytes changed during dataset validation')
        if result['dataset_validation']['exit_code'] != 0:
            raise ValueError('Official dataset validation failed; see its actual log')
        result['dataset_validation'].update(parse_dataset_log(attempt / 'dataset_validation.log'),
                                             validator_sha256=sha256(validator))
        result.update(status='tested', complete=True)
    except Exception as exc:
        result.update(status='failed', complete=False, failure_reason=str(exc))
    finally:
        result['finished_at'] = utc_now()
        try:
            after = frozen_inputs(root, helper)
            result['runtime_source_sha256_finished'] = after['runtime_source_sha256']
            result['test_source_sha256_finished'] = after['test_source_sha256']
            result['dataset_source_sha256_finished'] = after['dataset_source_sha256']
            result['verification_helper_sha256_finished'] = after['verification_helper_sha256']
            result['source_runtime_unchanged'] = bool(before and before['runtime_source_sha256'] == after['runtime_source_sha256'])
            result['all_verification_inputs_unchanged'] = before == after
            if before != after:
                result.update(status='failed', complete=False,
                              failure_reason=result.get('failure_reason', 'Verification inputs changed'))
            result['git_finished'] = git_state(root)
            result['runtime_commit_finished'] = result['git_finished']['head']
            result['git_head_unchanged'] = result.get('runtime_commit') == result['git_finished']['head']
        except Exception as exc:
            result.update(status='failed', complete=False, source_runtime_unchanged=False,
                          final_snapshot_error=str(exc))
        try:
            if attempt.exists():
                if result['status'] == 'tested' and result.get('all_verification_inputs_unchanged') is True:
                    artifacts = root / 'sample_outputs' / 'engineering_artifacts' / attempt_name
                    artifacts.mkdir(parents=True)
                    for stage, field, source_name in (
                            ('pytest', 'log', 'pytest.log'),
                            ('pytest', 'junit_xml', 'pytest.xml'),
                            ('dataset_validation', 'log', 'dataset_validation.log')):
                        source_path = attempt / source_name
                        destination = artifacts / source_name
                        shutil.copyfile(source_path, destination)
                        if sha256(source_path) != sha256(destination):
                            raise ValueError('Published engineering artifact differs from its original log')
                        result[stage]['original_' + field] = result[stage][field]
                        result[stage][field] = path_key(root, destination)
                    result['engineering_artifact_directory'] = path_key(root, artifacts)
                write_json(attempt / 'engineering_verification.json', result)
                if result['status'] == 'tested' and result.get('all_verification_inputs_unchanged') is True:
                    write_json(current, result)
                    print('Published: ' + str(current), flush=True)
                else:
                    print('FAILED; current evidence is pending. Attempt receipt: ' + str(attempt / 'engineering_verification.json'), flush=True)
        except Exception as exc:
            result.update(status='failed', complete=False, publication_error=str(exc))
            if attempt.exists():
                write_json(attempt / 'engineering_verification.json', result)
            print('FAILED to publish engineering evidence; see attempt receipt.', flush=True)
        finally:
            lock.unlink(missing_ok=True)
    return 0 if result['status'] == 'tested' else 1


if __name__ == '__main__':
    raise SystemExit(main())
