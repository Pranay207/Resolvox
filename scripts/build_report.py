"""Build a four-page report from recorded evidence, plus synchronized Markdown.

Importing this module does not generate artifacts. Run after final evaluations;
missing/partial evidence remains visibly pending instead of becoming a success.
"""
from collections import Counter
from pathlib import Path
from statistics import mean
from xml.sax.saxutils import escape
import json
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


def voice_text(data):
    if not data:
        return 'Voice validation pending; no speech-success claim is available.'
    batch = data.get('batch', {})
    semantic = data.get('semantic_validation', {})
    return (f"Status: {data.get('status', 'unrecorded')}. Audio batches: "
            f"{batch.get('succeeded', '?')}/{batch.get('total', '?')} succeeded; "
            f"semantic/privacy checks passed: {semantic.get('passed', '?')}, "
            f"failed: {semantic.get('failed', '?')}. Results describe the saved run, not a human listening study.")


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


def main():
    base, rag, conv, adv, voice = [load(name) for name in
        ('eval_step1.json', 'eval_step2.json', 'eval_step3.json', 'eval_adversarial.json', 'voice_validation.json')]
    holdout = load('eval_holdout.json')
    live_partial = load('eval_step2_live_postfix_partial.json')
    live2_name, live2 = select_current_live(2, load)
    live3_name, live3 = select_current_live(3, load)
    primary_rag = live2 or rag
    first_name, first = first_holdout()
    engineering = load('engineering_verification.json')
    sections = load('generation_benchmark_sections.json')
    selected = load('generation_benchmark_selected.json')
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

    p('VoiceOps 2026', 'SmallV')
    p('Resolvox', 'TitleV')
    p('Multilingual AI Voice Support for ZentroMart', 'SmallV')
    p('Technical report | Pranay207 | C&A Club, IIT Guwahati x Gnani.ai', 'SmallV')
    p('One multilingual support agent combines retrieval-first source-text generation, deterministic verification and arithmetic, supplied order/ticket tools, and Gnani speech. Recorded results distinguish generated answers, checked fallbacks, guardrails and abstentions. No organizer score or placing is claimed.')
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
    diagram.add(String(0, 10, 'The same stateful agent handles text, voice and batch evaluation.', fontSize=8, fillColor=GRAY))
    story.append(diagram)
    table([
        ['Stage', 'Implementation'],
        ['1 - Baseline', 'Actual configured LLM; role/limits and AI disclosure; no company documents or order access.'],
        ['2 - RAG', 'Search first; scope policy rules to actual results; generate from supplied section text and checked facts; record source provenance.'],
        ['3 - Conversation', 'Session/order state, proof-gated lookup, calendar/coupon arithmetic, explicit guard policies and confirmed-ticket-only handover.'],
        ['4 - Voice', 'Official Gnani STT/TTS, spoken-number normalization, redaction, per-file failure isolation and JSON/text/WAV/source outputs.'],
    ], [94, 416])
    h('Evidence snapshot at report generation')
    p(f'Actual prompt-only baseline: {pass_text(base)}. LLM-enabled grounded questions: {live_result_text(live2)}. LLM-enabled conversation turns: {live_result_text(live3)}. Offline checks remain separate: {pass_text(rag)} questions, {pass_text(conv)} conversation turns; development adversarial/stateful checks {pass_text(adv)}. Mechanical checks on development practice do not establish unseen semantic quality.')
    p('Grounded run model metadata: ' + model_text(primary_rag) + '.', 'SmallV')
    p(engineering_text(engineering) + ' Required report limit: four pages. The user records the final demo within 120 seconds after validation.', 'SmallV')

    page()
    p('Architecture and evidence boundaries', 'TitleV')
    h('Retrieval before policy planning')
    p('KB sections preserve IDs, file, authority, status, version and effective date. Raw-query BM25 and multilingual MiniLM channels are fused separately from narrow glossary expansion. Complete tables and concise heading/prose embeddings provide complementary views; Hindi tokenization retains combining marks. Intent is a weak hint, not a mapping from practice questions to evidence.')
    p('The agent searches at k=12 before planning. Explicit references, named policy concepts and bounded calendar/precedence/exception dependencies add governing context. Planning sees only retrieved sections, with public catalog/pincode facts supplied independently. A planner cannot append preferred citations from the full KB. Historical filtering excludes obsolete text unless the current successor authorizes that case.')
    h('Actual source-text generation; explicit provenance')
    p('The LLM receives actual section text, authority/version metadata, deterministic facts and an optional checked rule summary. It writes new reply wording. The current answer-only output contract avoids asking small models to reproduce section identifiers or select citation spans. Code records the IDs and exact full sections actually supplied as context provenance; this does not prove that every generated claim follows from those sections.')
    p('Source-contract validation checks source membership, required coverage, numeric values and units, selected omitted constraints, language, private identifiers and common invented completed actions. These are finite heuristics, not general semantic entailment. Broad section support can contain multiple payment rows or exceptions; a model can still misapply them. Citation provenance and factual correctness are reported separately.')
    h('Reviewed fallback and guard paths')
    p('Offline, invalid-output and timeout fallback uses a static policy answer only when every governing section was actually retrieved and matches its reviewed content/metadata SHA-256 in rule_bindings.json. Missing or changed evidence causes abstention. Policy edits require reviewing rules and bindings; hashes do not automatically update policy logic. Authentication, privacy, urgent escalation and tool-result wording use explicit guard-policy lookups, labeled separately from answer search.')
    h('Policy, time and private state')
    p('Current policy outranks agent guide, help, FAQ and marketing; historical support logs never govern. The frozen date is 20 October 2026. Business days are Monday-Saturday excluding supplied holidays. Return deadlines use delivery + N calendar days: the supplied wording leaves inclusive counting ambiguous, so the consistent day-zero convention is documented. Proof is discarded after the supplied lookup; order switches clear verified context while retaining per-order failure counts. Tickets are deduplicated by order and reason, and success requires created=True.')

    page()
    p('Evaluation and observed limitations', 'TitleV')
    rows = [
        ['Recorded evaluation', 'Passes', 'Interpretation'],
        ['Prompt-only questions', pass_text(base), rate_text(base) + '; errors ' + str(summary(base).get('errors', 'not recorded'))],
        ['Grounded questions (LLM-enabled)', pass_text(live2), f"{summary(live2).get('total',0)}/{summary(live2).get('planned','?')} evaluated; complete={live_complete(live2)}; compose=True" if live2 else 'pending; no current live artifact'],
        ['Conversation turns (LLM-enabled)', pass_text(live3), f"{summary(live3).get('total',0)}/{summary(live3).get('planned','?')} evaluated; complete={live_complete(live3)}; compose=True" if live3 else 'pending; no current live artifact'],
        ['Offline questions / conversations', pass_text(rag)+' / '+pass_text(conv), 'compose=False; separate rules/guard checks'],
        ['Development adversarial/stateful', pass_text(adv), rate_text(adv) + '; used for development'],
    ]
    if first:
        rows.append(['First holdout (offline)', pass_text(first), rate_text(first)])
        if holdout:
            rows.append(['Post-fix holdout (offline)', pass_text(holdout), rate_text(holdout)])
    else:
        rows.append(['Saved holdout run', pass_text(holdout), rate_text(holdout) if holdout else 'pending; no result inferred'])
    rows.append(['Used-source recall (selected runs)', 'Single / conversation', pct(summary(primary_rag).get('evidence_recall')) + ' / ' + pct(summary(live3 or conv).get('evidence_recall'))])
    table(rows, [207, 72, 231])
    p('The scorer checks decisions, required/forbidden facts and expected tools; independent holdout checks also inspect language, evidence, tool arguments and privacy. Mechanical regex/fact checks can miss semantic errors or reject valid paraphrases. Conversation search includes many guard/verification turns and is not directly comparable with standalone query recall.')
    historical_note=(f"Historical {summary(live_partial).get('passed','?')}/{summary(live_partial).get('planned','?')} partial subset remains preserved unchanged. " if live_partial else '')
    p('LLM-enabled question composition: ' + (composition_text(live2) if live2 else 'pending') + '. LLM-enabled conversation composition: ' + (composition_text(live3) if live3 else 'pending') + '. These include cached generation, reviewed fallbacks and guards; a passing live run is not all fresh generation. '+historical_note+'Earlier complete live runs are separate historical evidence.', 'SmallV')
    h('Frozen holdout and honest reruns')
    p('The independent fixture contains 64 single questions and 10 scenarios/27 turns: 91 judged responses. Full rubric SHA-256: ' + HOLDOUT_HASH + '. It is evaluation data, never runtime knowledge. Preserve the first pass before observing failures; later runs after fixes are regressions on an exposed set, not a new independent holdout.', 'SmallV')
    if first:
        p(holdout_progress_text(holdout) + ' First-pass artifact: ' + first_name + '; current: eval_holdout.json. Scorer provenance is retained in eval_holdout_scorer_v2_same_predictions.json.', 'SmallV')
    else:
        p('A separately named first-pass artifact is not present. A saved current holdout score alone does not establish whether it preceded tuning; pending results remain pending.', 'SmallV')
    h('Failures that shaped the implementation')
    p('Early sentence ordering concealed the distinction between retrieval and rules. The revised path scopes planning to actual search results. Product variants, historical return windows, policy precedence, order switching and ticket reuse require independent checks. Development model experiments produced correct-looking prose with missing/invalid citations or unsupported constraints; their factual pass and accepted-generation counts are kept separate. The answer-only contract now attaches actual context provenance in code. New wording, multilingual conditions and multi-item decisions still require semantic review.')
    p('Baseline model metadata: ' + model_text(base) + '. Compare run configurations before attributing differences solely to retrieval.', 'SmallV')

    page()
    p('Latency, voice and reproducibility', 'TitleV')
    h('Model and latency evidence')
    p('Recorded LLM-enabled question timing: ' + latency_text(live2 or live_partial) + '. Conversation timings are retained in ' + live3_name + '; offline measurements remain separate. All outliers are retained; request timeouts do not establish a hard end-to-end bound.', 'SmallV')
    bench = benchmark_rows('selected-model check', selected) if selected else benchmark_rows('section experiment', sections)
    if bench:
        table([['Recorded model experiment', 'Accepted generation', 'Mean case wall', 'Warm-up wall']] + bench[:3], [218, 88, 97, 107])
    else:
        p('Final model benchmarking is pending; no speed or selected-model success is inferred.', 'SmallV')
    p('Benchmarks use a small development sample and do not estimate unseen quality. Warm-up wall includes its request and may include loading; it is not automatically a controlled cold start. Warm uncached inference performs a new request, whereas an output-cache hit reuses stored text. Agent turn latency excludes resource creation before respond; inspect cache status and provider load/prompt/decode timings. Full prompt/source/fact/model settings enter cache keys; private-order calls bypass persistent output caching.', 'SmallV')
    extra_languages = load('language_validation.json')
    if extra_languages:
        h('Optional regional-language preview')
        p('Primary support is English, Hindi and Hinglish. Additional regional choices are an optional preview using separate local translation with masked identifiers and round-trip checks. '+regional_preview_text(extra_languages)+' Failures and prior attempts remain in language_validation.json; translation weights are excluded from the archive.', 'SmallV')
    h('Real Gnani speech; separate time measures')
    p(voice_text(voice))
    wall = [row.get('latency_ms') for row in voice.get('batch', {}).get('entries', [])]
    audio = [row.get('reply_seconds') for row in voice.get('semantic_validation', {}).get('checks', [])]
    p('Saved voice processing wall range: ' + seconds_range(wall, milliseconds=True) + '; generated reply audio duration: ' + seconds_range(audio) + '. Processing time and playback length are different quantities. Gnani TTS input clips are synthetic, not human recordings; accent/noise robustness and subjective listening remain unverified.', 'SmallV')
    p('Gnani is the only STT/TTS provider. Bounded retries rewind inputs; invalid transcripts, truncated PCM and empty speech are rejected. Stream-style WAV sizes are finalized without changing samples. Batch results retain redacted transcripts, sources, tool traces, timing and per-file errors. An offline-rules run disables answer generation but still requires Gnani speech.')
    h('Reproduce and release')
    p('Repository: https://github.com/Pranay207/Resolvox. Setup: powershell -File setup.ps1. Batch: python run.py --audio_dir <in> --out_dir <out>. Current live practice: python scripts/resume_live_practice.py --step 2, then --step 3; separate baseline/adversarial/holdout scripts retain earlier evidence. Run python -m pytest -q. Reproduce voice with generate_voice_samples.py --reuse-inputs. Generated JSON retains the measured configuration and failures.', 'SmallV')
    p('After final checks, regenerate the report, visually inspect all pages, record demo.mp4 within 120 seconds, then build/verify the release ZIP. Packaging excludes .env, dataset copies, model weights, caches, environments and private audio. Educational proof checking is not production authentication. No rank, prize or real customer outcome is promised.', 'SmallV')
    p('Sources: capstone brief; supplied dataset README, dictionary, KB and tools; official Gnani STT/TTS docs; pinned multilingual MiniLM model card; sample_outputs JSON named above. Report measurements are loaded when this file is generated.', 'SmallV')

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
    (ROOT / 'report.md').write_text('# Resolvox - Multilingual AI Voice Support\n\n' + '\n'.join(md), encoding='utf-8')
    print('Created report.pdf and synchronized report.md; render and inspect before release.')


if __name__ == '__main__':
    main()
