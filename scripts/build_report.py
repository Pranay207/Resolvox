"""Build a four-page report from recorded evidence, plus synchronized Markdown.

Importing this module does not generate artifacts. Run after final evaluations;
missing/partial evidence remains visibly pending instead of becoming a success.
"""
from collections import Counter
from pathlib import Path
from statistics import mean
from xml.sax.saxutils import escape
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.finalize_evidence import (select_current_live, live_complete, live_result_text,
    live_narrative, composition_text, regional_preview_text)
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon

NAVY = colors.HexColor('#132842')
BLUE = colors.HexColor('#2873ba')
MINT = colors.HexColor('#e7f5f2')
GRAY = colors.HexColor('#516174')
HOLDOUT_HASH = '5f345355d495379623ecc7dfcecdbd7a78f56c3edab62fda5d6f6edfea9d03c7'


def load(name):
    try:
        value = json.loads((ROOT / 'sample_outputs' / name).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def pct(value):
    return f'{100 * value:.1f}%' if isinstance(value, (int, float)) else 'not recorded'


def summary(data):
    value = data.get('summary', {})
    return value if isinstance(value, dict) else {}


def predictions(data):
    for row in data.get('results', []):
        if isinstance(row, dict):
            value = row.get('prediction', row.get('actual_output', {}))
            if isinstance(value, dict):
                yield value


def composition(data):
    recorded = summary(data).get('composition_counts')
    if isinstance(recorded, dict):
        return Counter(recorded)
    return Counter(row.get('composition', row.get('mode', 'unrecorded')) for row in predictions(data))


def count_text(counts):
    return '; '.join(f'{key}: {value}' for key, value in sorted(counts.items())) or 'not recorded'


def pass_text(data):
    values = summary(data)
    total = values.get('total', values.get('evaluated'))
    if total is None or values.get('passed') is None:
        return 'pending'
    status = ' (partial)' if values.get('complete') is False else ''
    return f"{values['passed']}/{total}{status}"


def rate_text(data):
    values = summary(data)
    value = values.get('pass_rate')
    total = values.get('total', values.get('evaluated'))
    if value is None and total:
        value = values.get('passed', 0) / total
    return pct(value)


def search_text(data):
    values = summary(data)
    if values.get('search_recall') is None:
        return 'not recorded at current k'
    ks = values.get('search_k', [])
    return f"{pct(values['search_recall'])} at k={','.join(map(str, ks)) or 'unrecorded'}"


def model_text(data):
    config = data.get('configuration', data.get('metadata', {}))
    configured = '/'.join(str(config[key]) for key in ('llm_provider', 'llm_model') if config.get(key))
    actual = Counter()
    for row in predictions(data):
        provider = row.get('llm', {}).get('provider') or row.get('provider')
        if provider:
            actual[str(provider)] += 1
    parts = []
    if configured:
        parts.append('configured ' + configured)
    if actual:
        parts.append('recorded calls ' + ', '.join(f'{key} ({value})' for key, value in actual.most_common(2)))
    return '; '.join(parts) or 'model/call metadata not recorded'


def first_holdout():
    names = ('eval_holdout_first_pass.json', 'eval_holdout_firstpass.json',
             'eval_holdout_first_run.json', 'eval_holdout_initial.json')
    for name in names:
        data = load(name)
        if summary(data):
            return name, data
    return None, {}


def holdout_progress_text(holdout):
    current=summary(holdout)
    if not current:return 'The current holdout result is pending; no completed score is inferred.'
    remaining=current.get('failed')
    text=f"The current exposed-set offline regression has {remaining} remaining evaluated failures."
    previous=load('eval_holdout_before_normalization_v2.json')
    rescored=load('eval_holdout_scorer_v2_same_predictions.json')
    provenance=rescored.get('rescoring',{})
    if provenance.get('predictions_unchanged'):
        text+=f" Old predictions scored {pass_text(previous)} originally and {pass_text(rescored)} under scorer v2 unchanged; {provenance.get('passed_delta','?')} points are scoring normalization, not runtime improvement."
        if rescored.get('scorer',{}).get('version')==holdout.get('scorer',{}).get('version'):
            text+=f" Runtime fixes then reached {pass_text(holdout)} under that same scorer."
    return text+' Zero evaluated failures would not establish unseen semantic correctness or live-generation performance.'


def seconds_range(values, milliseconds=False):
    values = [value for value in values if isinstance(value, (int, float))]
    if not values:
        return 'not recorded'
    divisor = 1000 if milliseconds else 1
    return f'{min(values) / divisor:.2f}-{max(values) / divisor:.2f} s'


def configured_llm_text():
    """Public selected settings after application config loads; not measurements."""
    values = {key: os.getenv(key, default) for key, default in {
        'LLM_PROVIDER': 'ollama', 'LLM_MODEL': 'qwen3:4b-instruct',
        'LLM_TIMEOUT': '120', 'RAG_LLM_TIMEOUT': '120',
    }.items()}
    return (f"Configured LLM: {values['LLM_PROVIDER']}/{values['LLM_MODEL']}; "
            f"LLM_TIMEOUT={values['LLM_TIMEOUT']} s, RAG_LLM_TIMEOUT={values['RAG_LLM_TIMEOUT']} s. "
            'These are settings, not measured latency; code/example defaults are 120 seconds.')


def voice_text(data):
    if not data:
        return 'Voice validation pending; no speech-success claim is available.'
    batch = data.get('batch', {})
    semantic = data.get('semantic_validation', {})
    return (f"Status: {data.get('status', 'unrecorded')}. Audio batches: "
            f"{batch.get('succeeded', '?')}/{batch.get('total', '?')} succeeded; "
            f"semantic/privacy checks passed: {semantic.get('passed', '?')}, "
            f"failed: {semantic.get('failed', '?')}. Results describe the saved run, not a human listening study.")


def recovery_summary_text(recovery, historical_hindi):
    notes = []
    hs = summary(historical_hindi)
    if hs.get('voice_passed') is not None and hs.get('planned') is not None:
        notes.append(f"Historical Hindi UPI {hs['voice_passed']}/{hs['planned']}; this predates the new answer path.")
    elif historical_hindi:
        notes.append('Historical Hindi UPI has no recorded complete count; no result is inferred.')
    rs = summary(recovery)
    if rs.get('passed') is not None and rs.get('planned') is not None:
        notes.append(f"Current saved silence recovery {rs['passed']}/{rs['planned']}; check its runtime provenance.")
    else:
        notes.append('Current silence recovery is pending; no result is recorded.')
    notes.append('Recovery means an honest spoken clarification with AI disclosure and no actions, not successful speech transcription.')
    return ' '.join(notes)


def engineering_text(data):
    check = data.get('pytest', {})
    if isinstance(check, dict) and check.get('passed') is not None:
        return (f"Engineering pytest result: {check['passed']}/{check.get('total', '?')} passed; "
                f"exit code {check.get('exit_code', 'unrecorded')}.")
    return 'Final engineering result is pending or its count is not recorded; no test count is inferred.'


def benchmark_rows(name, data):
    rows = []
    for item in data.get('models', []):
        if not isinstance(item, dict):
            continue
        values = item.get('summary', {})
        cases = item.get('cases', [])
        generated = values.get('grounded_llm_count', sum(row.get('composition') == 'grounded_llm' for row in cases))
        total = values.get('evaluated', len(cases))
        wall = values.get('mean_latency_ms')
        if wall is None:
            durations = [row['latency_ms'] for row in cases if isinstance(row.get('latency_ms'), (int, float))]
            wall = mean(durations) if durations else None
        warmup = item.get('warmup', {})
        warm = warmup.get('wall_ms')
        rows.append([f"{name}: {item.get('model', 'unrecorded')}",
                     f'{generated}/{total}',
                     f'{wall / 1000:.2f} s' if isinstance(wall, (int, float)) else 'pending',
                     f'{warm / 1000:.2f} s' if isinstance(warm, (int, float)) else 'not recorded'])
    return rows


def latency_text(data):
    groups = summary(data).get('latency_by_path', {})
    parts = []
    for label in ('uncached_llm_attempt', 'cache_hit', 'no_model_call'):
        row = groups.get(label, {})
        if row:
            def timing(key):
                value = row.get(key)
                return f'{value / 1000:.2f}s' if isinstance(value, (int, float)) else '?'
            parts.append(f"{label}: n={row.get('count', '?')}, p50 {timing('p50_ms')}, p95 {timing('p95_ms')}")
    return '; '.join(parts) or 'path-separated turn timings not recorded'


def _sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def current_core_hashes():
    files = sorted((ROOT / 'src').glob('*.py')) + [ROOT / 'src/rule_bindings.json']
    hashes = {path.relative_to(ROOT).as_posix(): _sha(path) for path in files if path.is_file()}
    required = {'src/agent.py', 'src/document_answers.py', 'src/document_context.py', 'src/rule_bindings.json'}
    return hashes if required <= hashes.keys() else {}


def _hashes_match(record, expected, *, finished=False):
    if not expected:
        return False
    if finished:
        candidates = [record.get('runtime_source_sha256_finished', {})]
    else:
        candidates = [record.get('runtime_source_sha256', {})]
        config = record.get('configuration', {})
        config = config if isinstance(config, dict) else {}
        for parent in (record.get('provenance', {}), config.get('provenance', {})):
            if isinstance(parent, dict):
                candidates.append(parent.get('runtime_source_sha256', {}))
    return any(isinstance(hashes, dict) and all(hashes.get(key) == value for key, value in expected.items())
               for hashes in candidates)


def _practice_ids(step):
    from src.evals import rows
    dataset = rows('questions.csv' if step in (1, 2) else 'conversations.csv')
    return [row['id'] if step in (1, 2) else row['conversation_id'] + '.' + row['turn'] for row in dataset]


def select_report_live(step, reader=None, *, expected_provenance=None, expected_ids=None, require_complete=False):
    """Match current runtime/settings/fixture and exact saved prefix before use."""
    from scripts.resume_live_practice import provenance, fingerprint
    reader = reader or load
    name = f'eval_step{step}_live_current.json'
    data = reader(name)
    mode = 'live_prompt_only' if step == 1 else 'live_compose_true'
    config = data.get('configuration', {})
    if not isinstance(config, dict) or config.get('evaluation_mode') != mode:
        return name, {}
    expected_provenance = provenance(step) if expected_provenance is None else expected_provenance
    expected_ids = _practice_ids(step) if expected_ids is None else expected_ids
    if config.get('provenance') != expected_provenance or config.get('inference_fingerprint') != fingerprint(expected_provenance):
        return name, {}
    values = summary(data)
    results = data.get('results', [])
    total = values.get('total')
    if (not isinstance(results, list) or type(total) is not int or not 0 < total <= len(expected_ids)
            or values.get('planned') != len(expected_ids) or len(results) != total
            or any(not isinstance(row, dict) for row in results)
            or [row.get('id') for row in results] != expected_ids[:total]):
        return name, {}
    complete = total == len(expected_ids)
    if values.get('complete') is not complete or data.get('complete') is not complete:
        return name, {}
    if require_complete and not complete:
        return name, {}
    if type(values.get('passed')) is not int or not 0 <= values['passed'] <= total:
        return name, {}
    return name, data


def select_current_baseline(reader=None, *, expected_provenance=None, expected_ids=None):
    return select_report_live(1, reader, expected_provenance=expected_provenance,
                              expected_ids=expected_ids, require_complete=True)


def current_engineering(record):
    values = record.get('pytest', {})
    if (_hashes_match(record, current_core_hashes()) and isinstance(values, dict)
            and type(values.get('total')) is int and values['total'] > 0
            and type(values.get('passed')) is int and 0 <= values['passed'] <= values['total']
            and type(values.get('exit_code')) is int):
        return record
    return {}


def current_voice(record):
    expected = current_core_hashes()
    batch = record.get('batch', {})
    semantic = record.get('semantic_validation', {})
    if not isinstance(batch, dict) or not isinstance(semantic, dict):
        return {}
    if (not _hashes_match(record, expected) or not _hashes_match(record, expected, finished=True)
            or record.get('source_runtime_unchanged') is not True
            or record.get('live_llm_composition_enabled') is not True
            or record.get('status') not in {'tested', 'failed'}):
        return {}
    total = batch.get('total')
    entries, checks = batch.get('entries', []), semantic.get('checks', [])
    if (total != 6 or not isinstance(entries, list) or len(entries) != total
            or not isinstance(checks, list) or len(checks) != total
            or any(type(batch.get(key)) is not int for key in ('succeeded', 'failed'))
            or batch['succeeded'] + batch['failed'] != total
            or any(type(semantic.get(key)) is not int for key in ('passed', 'failed'))
            or semantic['passed'] + semantic['failed'] != total
            or any(not isinstance(check, dict) or type(check.get('passed')) is not bool for check in checks)
            or sum(check['passed'] for check in checks) != semantic['passed']):
        return {}
    return record


def current_recovery(record):
    # These are the exact operational sources recorded by the recovery runner;
    # it performs no normal answer generation or private transaction operation.
    names = ('scripts/validate_voice_recovery.py', 'run.py', 'src/voice.py',
             'src/agent.py', 'src/multilingual.py', 'src/normalize.py',
             'src/languages.py', 'src/answering.py', 'src/tools_wrapper.py')
    if not all((ROOT / name).is_file() for name in names):
        return {}
    expected = {name: _sha(ROOT / name) for name in names}
    values = summary(record)
    if (not _hashes_match(record, expected) or record.get('complete') is not True
            or record.get('status') not in {'tested', 'failed'}
            or record.get('speech_provider') != 'Gnani only'
            or record.get('live_llm_composition_enabled') is not False
            or values.get('planned') != 1 or values.get('evaluated') != 1
            or type(values.get('passed')) is not int or values['passed'] not in (0, 1)
            or values.get('failed') != 1 - values['passed']):
        return {}
    return record


def current_adversarial(record):
    fixture = ROOT / 'tests/adversarial_cases.json'
    runner = ROOT / 'eval_adversarial.py'
    if not fixture.is_file() or not runner.is_file():
        return {}
    cases = json.loads(fixture.read_text(encoding='utf-8'))
    expected_ids = [case['id'] for case in cases]
    expected_ids += [f'MULTI_{kind}{index}' for index in range(1, 7) for kind in ('LOCK', 'SWITCH')]
    expected = dict(current_core_hashes(), **{'eval_adversarial.py': _sha(runner)})
    if (not _hashes_match(record, expected) or not _hashes_match(record, expected, finished=True)
            or record.get('source_runtime_unchanged') is not True
            or record.get('mode') != 'live_compose_true'
            or record.get('configuration', {}).get('evaluation_mode') != 'live_compose_true'
            or record.get('configuration', {}).get('fixture_sha256') != _sha(fixture)
            or record.get('complete') is not True or record.get('status') not in {'tested', 'failed'}):
        return {}
    values = summary(record)
    results = record.get('results', [])
    if (not isinstance(results, list) or values.get('total') != len(expected_ids)
            or values.get('planned') != len(expected_ids) or values.get('complete') is not True
            or any(not isinstance(row, dict) or type(row.get('passed')) is not bool for row in results)
            or [row.get('id') for row in results] != expected_ids
            or values.get('passed') != sum(row['passed'] for row in results)
            or values.get('failed') != sum(not row['passed'] for row in results)):
        return {}
    return record


def current_holdout(record, receipt):
    """Require a real frozen-batch sidecar binding exact holdout artifact bytes."""
    artifact = ROOT / 'sample_outputs/eval_holdout_live_current.json'
    fixture = ROOT / 'tests/holdout_cases.json'
    runner = ROOT / 'eval_holdout.py'
    if not artifact.is_file() or not fixture.is_file() or not runner.is_file():
        return {}
    try:
        if record != json.loads(artifact.read_text(encoding='utf-8')):
            return {}
    except (OSError, ValueError):
        return {}
    expected = current_core_hashes()
    if (receipt.get('receipt_scope') != 'frozen_validation_batch'
            or receipt.get('artifact') != 'sample_outputs/eval_holdout_live_current.json'
            or receipt.get('artifact_sha256') != _sha(artifact)
            or receipt.get('source_runtime_unchanged') is not True
            or not _hashes_match(receipt, expected) or not _hashes_match(receipt, expected, finished=True)):
        return {}
    import eval_holdout
    fixture_data = json.loads(fixture.read_text(encoding='utf-8'))
    try:
        coverage = eval_holdout.validate_fixture(fixture_data)
    except (ValueError, KeyError, TypeError):
        return {}
    ids = [case['id'] for case in fixture_data['single_cases']]
    ids += [scenario['id'] + '/' + turn['id'] for scenario in fixture_data['scenarios'] for turn in scenario['turns']]
    results, values = record.get('results', []), summary(record)
    scorer = record.get('scorer', {})
    if (record.get('mode') != 'llm_compose_true' or record.get('coverage') != coverage
            or scorer.get('source_sha256') != _sha(runner)
            or scorer.get('version') != eval_holdout.SCORER_VERSION
            or scorer.get('frozen_rubric_unchanged') is not True
            or values.get('complete') is not True or values.get('planned') != len(ids)
            or values.get('evaluated') != len(ids) or not isinstance(results, list)
            or any(not isinstance(row, dict) for row in results)
            or [row.get('id') for row in results] != ids
            or any(not isinstance(row.get('judgment'), dict) or type(row['judgment'].get('passed')) is not bool for row in results)
            or values.get('passed') != sum(row['judgment']['passed'] for row in results)
            or values.get('failed') != sum(not row['judgment']['passed'] for row in results)):
        return {}
    return record


def baseline_comparison_text(base, rag, *, current=False):
    if not current:
        return 'The displayed baseline is historical; no fresh complete matching-runtime baseline is selected. Model/version and implementation changes can confound comparison.'
    def identity(data):
        config = data.get('configuration', {})
        return config.get('llm_provider'), config.get('llm_model')
    base_id, rag_id = identity(base), identity(rag)
    if all(base_id) and base_id == rag_id:
        return 'Current baseline and RAG record the same configured provider/model. Document context, prompting and validation still differ, so the comparison does not isolate retrieval alone.'
    return 'The baseline and RAG provider/model configurations differ or are incomplete; model/version changes confound their score comparison. This is not a same-model retrieval ablation.'


def document_composition(data):
    counts = composition(data)
    abstentions = sum(value for key, value in counts.items() if key.startswith('abstained'))
    legacy = sum(value for key, value in counts.items() if 'fallback' in key or key == 'evidence_validated_rules')
    return (f"generated {counts.get('grounded_llm', 0)}; model clarifications {counts.get('grounded_clarification', 0)}; "
            f"host table-input clarifications {counts.get('source_input_clarification', 0)}; "
            f"guards {counts.get('deterministic_guardrail', 0)}; abstentions {abstentions}; "
            f"offline excerpts {counts.get('document_excerpts', 0)}; legacy policy fallbacks/rules {legacy}")


def main():
    historical_base, old_rag, old_conv, old_adv, saved_voice = [load(name) for name in
        ('eval_step1.json', 'eval_step2.json', 'eval_step3.json', 'eval_adversarial.json', 'voice_validation.json')]
    holdout = load('eval_holdout.json')
    baseline_name, current_base = select_current_baseline()
    base = current_base or historical_base
    base_label = 'Current prompt-only baseline' if current_base else 'Historical prompt-only baseline'
    baseline_artifact = baseline_name if current_base else 'eval_step1.json'
    live2_name, live2 = select_report_live(2, load)
    live3_name, live3 = select_report_live(3, load)
    live_adv = current_adversarial(load('eval_adversarial_live_current.json'))
    live_holdout = current_holdout(load('eval_holdout_live_current.json'), load('live_holdout_receipt.json'))
    voice = current_voice(saved_voice)
    first_name, first = first_holdout()
    engineering = current_engineering(load('engineering_verification.json'))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleV', fontName='Helvetica-Bold', fontSize=25, leading=29, textColor=NAVY, spaceAfter=12))
    styles.add(ParagraphStyle(name='HeadingV', fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=NAVY, spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name='BodyV', fontName='Helvetica', fontSize=9.3, leading=12.8, textColor=NAVY, spaceAfter=7))
    styles.add(ParagraphStyle(name='SmallV', fontName='Helvetica', fontSize=8.1, leading=10.6, textColor=GRAY, spaceAfter=6))
    story, md = [], []

    def p(text, style='BodyV'):
        story.append(Paragraph(escape(text), styles[style]))
        md.append(text + '\n')

    def h(text):
        p(text, 'HeadingV')

    def table(rows, widths):
        body = [[Paragraph(escape(str(cell)), styles['SmallV']) for cell in row] for row in rows]
        item = Table(body, colWidths=widths, hAlign='LEFT')
        item.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), MINT), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (0, 0), (-1, 0), .7, BLUE),
            ('LINEBELOW', (0, 1), (-1, -1), .25, colors.HexColor('#dce5ed')),
            ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.extend([item, Spacer(1, 7)])
        md.append('\n'.join('| ' + ' | '.join(map(str, row)) + ' |' for row in rows) + '\n')

    def page():
        story.append(PageBreak())
        md.append('\n---\n')

    p('VoiceOps 2026 Capstone', 'SmallV')
    p('Resolvox', 'TitleV')
    p('AI Voice Support for ZentroMart', 'SmallV')
    p('Technical report | Pranay207 | C&A Club, IIT Guwahati x Gnani.ai', 'SmallV')
    p('Resolvox combines document-first LLM answers, verified order facts, supplied order/ticket tools and Gnani speech. Normal policy answers are generated from retrieved text; validation failures produce uncertainty. Operational guards remain deterministic. Results are local mechanical checks, not organizer scores or a placing guarantee.')
    h('Four cumulative build steps')
    diagram = Drawing(510, 83)
    xs, widths = [0, 67, 150, 254, 346, 426], [57, 73, 94, 82, 70, 80]
    labels = [['Audio'], ['Gnani STT'], ['State + search', 'k=12 sources'], ['Verified facts', 'order tools'], ['LLM answer', '+ checks'], ['Gnani TTS', '+ source trace']]
    for x, width, lines in zip(xs, widths, labels):
        diagram.add(Rect(x, 29, width, 43, rx=5, ry=5, fillColor=MINT, strokeColor=BLUE, strokeWidth=.7))
        for j, label in enumerate(lines):
            diagram.add(String(x + width / 2, 54 - j * 11, label, textAnchor='middle', fontName='Helvetica', fontSize=8, fillColor=NAVY))
    for i in range(5):
        start, end = xs[i] + widths[i], xs[i + 1] - 2
        diagram.add(Line(start, 50, end, 50, strokeColor=BLUE))
        diagram.add(Polygon([end, 50, end - 4, 52, end - 4, 48], fillColor=BLUE, strokeColor=BLUE))
    diagram.add(String(0, 10, 'One session-scoped agent serves text, Streamlit voice and folder-based batch runs.', fontSize=8, fillColor=GRAY))
    story.append(diagram)
    table([
        ['Stage', 'Implementation'],
        ['1 - Baseline', 'Configured LLM API, role/limits and first-reply AI disclosure; no company documents or order access.'],
        ['2 - RAG', 'Hybrid retrieval; actual section text and safe facts; host-recorded generation context; no authored policy answer fallback.'],
        ['3 - Conversation', 'Order/session state, proof-gated lookup, source-derived arithmetic, clarification and confirmed-ticket-only handover.'],
        ['4 - Voice', 'Gnani STT/TTS only, spoken-number normalization, redaction, JSON/text/WAV/source outputs and per-file errors.'],
    ], [94, 416])
    h('Recorded current evidence')
    p(f'{base_label}: {pass_text(base)}. Source-only LLM-enabled questions: {live_result_text(live2)}. Source-only conversation turns: {live_result_text(live3)}. Generated answers, guards and abstentions are counted separately; a completed run does not mean every answer passed or was newly generated.')
    p('Current question model metadata: ' + model_text(live2) + '. ' + base_label + ': ' + model_text(base) + '.', 'SmallV')
    p(engineering_text(engineering) + ' Historical rules-based scores are retained separately and do not validate the new answer path. Demo video remains the final user-recorded artifact.', 'SmallV')

    page()
    p('Architecture and evidence boundaries', 'TitleV')
    h('Retrieve actual documents before generation')
    p('KB sections retain IDs, file, authority, status, version and effective date. BM25 and multilingual MiniLM fusion preserves 12 direct candidates plus up to 4 distinct source dependencies (16 maximum); traces report actual direct/dependency counts. Tables and heading/prose embeddings supply complementary views. Source-first selection retains actual policy/help context for unfamiliar routes. Planner IDs only order retrieved sections; no authored policy answer enters generation.')
    p('The model receives the customer question, retrieved section text and authority metadata, plus safe public/verified records and calculated facts. It receives no authored answer summary, required answer text or expected practice response. Current policy outranks agent guides, help, FAQs and marketing; superseded policy is permitted only within successor-authorized historical scope.')
    h('Generation-context provenance; one repair')
    p('Normal JSON returns answer text plus covered and needs_clarification booleans. The host derives operational labels. Validated Boolean uncertainty is answer with covered=False, reply_kind=uncertainty and evidence_status=insufficient_evidence, without domain-answer source IDs. Legacy explicit and privacy refusals are unchanged; model_flags retain the original flags. Content checks still apply. Exact full source sections and IDs are recorded as generation_context, with empty citations. This identifies supplied context, not model-selected quotes, per-claim support or semantic proof.')
    p('Numeric values/units are checked against supplied context and safe facts. Question-relevant constraints also check source-derived return windows, calculated refund dates and delivery-attempt limits. Language, privacy and common invented actions are checked separately. Invalid output gets one repair, then uncertainty; no prewritten policy answer is substituted. These finite checks and full-section provenance do not prove every applicable condition or question part is covered.')
    h('Verified records and source-derived arithmetic')
    p('Only supplied tool output after verification can provide private order facts. Model context allowlists fields and nested items, excluding contact details, proof, customer IDs, order IDs and internal notes. Existing status/refund references are record readings, not claims that the agent performed an action. Refund bounds, weekday rules and return boundaries come from retrieved text. An explicit customer-stated initiation date may support a clearly labeled unverified projection; it never verifies transaction status. Ambiguous or absent inputs produce no calculation. Calculations retain inputs, source IDs and source hashes.')
    h('Operational exceptions and session safety')
    p('Required table inputs use neutral zero-LLM questions; choices rebind current rows, hashes and order scope, while ambiguous Bank replies remain unresolved. Public prospective delivery capability reaches source-first generation; compound private details require verification. Current sources and verified facts determine business escalation before ticket creation. Its policy explanation is generated separately from the actual tool outcome; failed generation retains that outcome with uncertainty. Authentication, privacy, safety and requested-human workflows remain deterministic. Ticket success requires created=True; deduplication is by order/reason. Proof is discarded, order switches clear verification, and offline domain output is labeled excerpts.')

    page()
    p('Evaluation and observed limitations', 'TitleV')
    rows = [
        ['Recorded check', 'Passes', 'Scope'],
        [base_label, pass_text(base), ('No documents/tools; errors ' if current_base else 'Historical configuration; errors ') + str(summary(base).get('errors', '?'))],
        ['Current source-only policy questions', pass_text(live2), live_result_text(live2)],
        ['Current source-only conversation turns', pass_text(live3), live_result_text(live3)],
        ['Historical offline questions / turns', pass_text(old_rag) + ' / ' + pass_text(old_conv), 'Earlier rules/fallback runtime; not current generation proof'],
        ['Current development adversarial (live)', pass_text(live_adv), 'Fresh full fixture; development cases, not blind evaluation'],
        ['Current exposed regression (live)', pass_text(live_holdout), 'Frozen-batch receipt; exposed cases, not new independent evidence'],
        ['Historical adversarial / exposed offline', pass_text(old_adv) + ' / ' + pass_text(holdout), 'Prior runtime only; not current generation proof'],
    ]
    if first:
        rows.append(['First independent holdout, historical', pass_text(first), 'Offline first pass preserved before tuning'])
    table(rows, [195, 75, 240])
    h('Current response composition')
    p('Questions: ' + (document_composition(live2) if live2 else 'pending') + '.', 'SmallV')
    p('Conversation turns: ' + (document_composition(live3) if live3 else 'pending') + '.', 'SmallV')
    p('Baseline artifact: ' + baseline_artifact + '; current live artifacts: ' + live2_name + ' and ' + live3_name + '; live regressions: eval_adversarial_live_current.json and eval_holdout_live_current.json. Public output-cache hits may reuse a previously validated generation with the same full prompt/source/fact/model key. Private-order calls bypass persistent output caching. Generation attempts, repairs, validation failures and latency remain in raw predictions; no failure is converted to a passing answer.', 'SmallV')
    h('What these scores establish')
    p(baseline_comparison_text(base, live2, current=bool(current_base)) + ' Mechanical scorers can reject valid wording or miss semantic errors. Development practice and exposed regressions are not unseen generalization evidence; historical rules/fallback scores are not carried over to the new path.')
    strict_pilot = load('history/pre_document_answers/strict_quote_pilot.json')
    if strict_pilot:
        p('Historical strict-quote pilot: ' + pass_text(strict_pilot) + '; partial development run, not current context-provenance evaluation.', 'SmallV')
    p('The frozen independent fixture contains 64 questions and 10 scenarios/27 turns (91 responses). Its first pass and failed predictions remain preserved; later runs are exposed regressions. Rubric SHA-256: ' + HOLDOUT_HASH + '.', 'SmallV')
    h('Why the answer path changed')
    p('Earlier live runs could substitute reviewed policy text after generation failed; those outputs and scores remain historical. A strict exact-quote pilot exposed citation-formatting failures in the small local model. Normal generation now uses answer plus coverage/clarification flags; the host derives the decision and records actual context without authored summaries. Strict quote mode remains available as a separate API experiment. One repair then uncertainty replaces policy-answer fallback; context traces and finite checks do not prove semantic correctness.')

    page()
    p('Voice, latency and reproduction', 'TitleV')
    h('Recorded current timing')
    p('Source-only question run: ' + latency_text(live2) + '. Conversation timing: ' + latency_text(live3) + '. ' + configured_llm_text() + ' Measured agent-turn times exclude resource creation before respond. Cached, uncached and no-model paths differ. Request timeouts do not establish a hard end-to-end bound.', 'SmallV')
    h('Gnani speech evidence and its scope')
    p(voice_text(voice))
    wall = [row.get('latency_ms') for row in voice.get('batch', {}).get('entries', [])]
    audio = [row.get('reply_seconds') for row in voice.get('semantic_validation', {}).get('checks', [])]
    p('Saved processing wall range: ' + seconds_range(wall, milliseconds=True) + '; reply audio duration: ' + seconds_range(audio) + '. Processing time and playback duration are different. Only a refreshed run of the current source-only agent establishes integration evidence for this version; old speech outputs remain historical.', 'SmallV')
    recovery = current_recovery(load('voice_recovery.json'))
    hindi_voice = load('history/pre_document_answers/primary_hindi_voice_validation.json')
    p(recovery_summary_text(recovery, hindi_voice), 'SmallV')
    p('Primary scope is English, Hindi and Hinglish. Gnani is the only STT/TTS provider. Additional languages are optional translation previews. Synthetic Gnani-generated inputs establish neither human accent/noise robustness nor subjective intelligibility. Human own-voice rehearsal and listening remain for the final demo step.', 'SmallV')
    extra_languages = load('language_validation.json')
    if extra_languages:
        p('Historical optional preview: ' + regional_preview_text(extra_languages), 'SmallV')
    h('Reproduce and finish the release')
    p('Repository: https://github.com/Pranay207/Resolvox. Install: powershell -File setup.ps1; configure .env and Ollama before launch. Batch: python run.py --audio_dir <in> --out_dir <out>. Live baseline/questions/conversations: python scripts/resume_live_practice.py --step 1, then --step 2 and --step 3. Engineering: python -m pytest -q -p no:cacheprovider. Speech: python generate_voice_samples.py --reuse-inputs. Preserve earlier artifacts before reruns.', 'SmallV')
    p('Demo video stays last and remains pending until recorded by the user: at most 120 seconds, showing a grounded answer, follow-up and handover or uncertainty. Then rebuild and verify the final ZIP. The draft excludes .env, dataset copies, weights, caches, environments and private input audio. Educational proof checking is not production authentication; no rank, prize or real customer outcome is promised.', 'SmallV')
    p('Sources: capstone brief; supplied dataset KB, catalog, calendar and tools; official Gnani documentation; model cards; recorded sample_outputs JSON. This report loads its counts from evidence at generation time. Historical measurements are not relabeled as current.', 'SmallV')

    def footer(canvas, doc):
        canvas.setStrokeColor(colors.HexColor('#dce5ed'))
        canvas.line(42, 37, 553, 37)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(GRAY)
        canvas.drawString(42, 24, 'RESOLVOX  |  VOICEOPS 2026  |  PRANAY207')
        canvas.drawRightString(553, 24, str(doc.page))

    document = SimpleDocTemplate(str(ROOT / 'report.pdf'), pagesize=(595.28, 841.89),
        leftMargin=42, rightMargin=42, topMargin=37, bottomMargin=48,
        title='Resolvox - ZentroMart VoiceOps 2026 Technical Report', author='Pranay207')
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    if document.page > 4:
        raise RuntimeError(f'Report overflowed to {document.page} pages; revise layout and rerender before release.')
    (ROOT / 'report.md').write_text('# Resolvox - AI Voice Support\n\n' + '\n'.join(md), encoding='utf-8')
    print('Created report.pdf and synchronized report.md; render and inspect before release.')


if __name__ == '__main__':
    main()
