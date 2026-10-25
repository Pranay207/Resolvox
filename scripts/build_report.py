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


def document_run(data):
    """Recognize new source-only evidence without promoting legacy live files."""
    provenance = data.get('configuration', {}).get('provenance', {})
    hashes = provenance.get('runtime_source_sha256', {})
    return all(name in hashes for name in ('src/document_answers.py', 'src/document_context.py'))


def document_composition(data):
    counts = composition(data)
    abstentions = sum(value for key, value in counts.items() if key.startswith('abstained'))
    legacy = sum(value for key, value in counts.items() if 'fallback' in key or key == 'evidence_validated_rules')
    return (f"generated {counts.get('grounded_llm', 0)}; model clarifications {counts.get('grounded_clarification', 0)}; "
            f"guards {counts.get('deterministic_guardrail', 0)}; abstentions {abstentions}; "
            f"offline excerpts {counts.get('document_excerpts', 0)}; legacy policy fallbacks/rules {legacy}")


def main():
    base, old_rag, old_conv, old_adv, voice = [load(name) for name in
        ('eval_step1.json', 'eval_step2.json', 'eval_step3.json', 'eval_adversarial.json', 'voice_validation.json')]
    holdout = load('eval_holdout.json')
    live2_name, live2 = select_current_live(2, load)
    live3_name, live3 = select_current_live(3, load)
    # A stale perfect score must never become evidence for the replacement path.
    for name, data in ((live2_name, live2), (live3_name, live3)):
        if data and not document_run(data):
            raise RuntimeError(f'{name} is legacy evidence. Archive it and run the source-only runtime before authoring the report.')
    first_name, first = first_holdout()
    engineering = load('engineering_verification.json')
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
    p(f'Historical prompt-only baseline: {pass_text(base)}. Source-only LLM-enabled questions: {live_result_text(live2)}. Source-only conversation turns: {live_result_text(live3)}. Generated answers, guards and abstentions are counted separately; a completed run does not mean every answer passed or was newly generated.')
    p('Current question model metadata: ' + model_text(live2) + '. Historical baseline: ' + model_text(base) + '.', 'SmallV')
    p(engineering_text(engineering) + ' Historical rules-based scores are retained separately and do not validate the new answer path. Demo video remains the final user-recorded artifact.', 'SmallV')

    page()
    p('Architecture and evidence boundaries', 'TitleV')
    h('Retrieve actual documents before generation')
    p('KB sections retain IDs, file, authority, status, version and effective date. BM25 and multilingual MiniLM retrieval fuse raw and narrowly expanded query channels at k=12. Complete tables and heading/prose embeddings supply complementary views. Routing hints may prefer governing sections only when those sections are present in actual retrieval; they cannot invent evidence or add policy answers to the prompt.')
    p('The model receives the customer question, retrieved section text and authority metadata, plus safe public/verified records and calculated facts. It receives no authored answer summary, required answer text or expected practice response. Current policy outranks agent guides, help, FAQs and marketing; superseded policy is permitted only within successor-authorized historical scope.')
    h('Generation-context provenance; one repair')
    p('Normal JSON returns answer text plus covered and needs_clarification booleans. The host derives clarify when clarification is needed, otherwise answer if covered or refuse if uncovered; model_flags retain the original flags. Content checks still apply. Exact full source sections and IDs are recorded as generation_context, with empty citations. This identifies supplied context, not model-selected quotes, per-claim support or semantic proof.')
    p('Numeric values/units are checked against supplied context and safe facts. Question-relevant constraints also check source-derived return windows, calculated refund dates and delivery-attempt limits. Language, privacy and common invented actions are checked separately. Invalid output gets one repair, then uncertainty; no prewritten policy answer is substituted. These finite checks and full-section provenance do not prove every applicable condition or question part is covered.')
    h('Verified records and source-derived arithmetic')
    p('Only supplied tool output after verification can provide private order facts. Model context allowlists fields and nested items, excluding contact details, proof, customer IDs, order IDs and internal notes. Existing status/refund references are record readings, not claims that the agent performed an action. Refund bounds, weekday rules and return boundaries come from retrieved text. An explicit customer-stated initiation date may support a clearly labeled unverified projection; it never verifies transaction status. Ambiguous or absent inputs produce no calculation. Calculations retain inputs, source IDs and source hashes.')
    h('Operational exceptions and session safety')
    p('Authentication, privacy, safety, escalation, greetings and catalog-miss messages remain reviewed deterministic guards. Escalation may retain a policy-bearing explanation; this report does not claim all deterministic text was removed. A ticket is claimed only after created=True and is deduplicated by order/reason. Order switches clear verified context; proof is discarded at lookup. Offline mode shows explicitly labeled source excerpts, never generated or canned policy answers.')

    page()
    p('Evaluation and observed limitations', 'TitleV')
    rows = [
        ['Recorded check', 'Passes', 'Scope'],
        ['Historical prompt-only baseline', pass_text(base), 'Earlier model/version; errors ' + str(summary(base).get('errors', '?'))],
        ['Current source-only policy questions', pass_text(live2), live_result_text(live2)],
        ['Current source-only conversation turns', pass_text(live3), live_result_text(live3)],
        ['Historical offline questions / turns', pass_text(old_rag) + ' / ' + pass_text(old_conv), 'Earlier rules/fallback runtime; not current generation proof'],
        ['Historical adversarial/stateful run', pass_text(old_adv), 'Saved development regression; not current policy generation proof'],
    ]
    if first:
        rows.append(['First independent holdout, historical', pass_text(first), 'Offline first pass preserved before tuning'])
    rows.append(['Historical exposed offline regression', pass_text(holdout), 'Prior runtime; exposed cases, not a fresh blind/live result'])
    table(rows, [195, 75, 240])
    h('Current response composition')
    p('Questions: ' + (document_composition(live2) if live2 else 'pending') + '.', 'SmallV')
    p('Conversation turns: ' + (document_composition(live3) if live3 else 'pending') + '.', 'SmallV')
    p('Current live artifacts: ' + live2_name + ' and ' + live3_name + '. Public output-cache hits may reuse a previously validated generation with the same full prompt/source/fact/model key. Private-order calls bypass persistent output caching. Generation attempts, repairs, validation failures and latency remain in raw predictions; no failure is converted to a passing answer.', 'SmallV')
    h('What these scores establish')
    p('The historical prompt-only baseline used qwen3:1.7b; current runs use a different model/version. Model, retrieval, prompting and validation changes are confounded: this is not a same-model retrieval ablation. Mechanical scorers can reject valid wording or miss semantic errors. Development practice and exposed regressions are not unseen generalization evidence; historical rules/fallback scores are not carried over to the new path.')
    strict_pilot = load('history/pre_document_answers/strict_quote_pilot.json')
    if strict_pilot:
        p('Historical strict-quote pilot: ' + pass_text(strict_pilot) + '; partial development run, not current context-provenance evaluation.', 'SmallV')
    p('The frozen independent fixture contains 64 questions and 10 scenarios/27 turns (91 responses). Its first pass and failed predictions remain preserved; later runs are exposed regressions. Rubric SHA-256: ' + HOLDOUT_HASH + '.', 'SmallV')
    h('Why the answer path changed')
    p('Earlier live runs could substitute reviewed policy text after generation failed; those outputs and scores remain historical. A strict exact-quote pilot exposed citation-formatting failures in the small local model. Normal generation now uses answer plus coverage/clarification flags; the host derives the decision and records actual context without authored summaries. Strict quote mode remains available as a separate API experiment. One repair then uncertainty replaces policy-answer fallback; context traces and finite checks do not prove semantic correctness.')

    page()
    p('Voice, latency and reproduction', 'TitleV')
    h('Recorded current timing')
    p('Source-only question run: ' + latency_text(live2) + '. Conversation timing: ' + latency_text(live3) + '. Selected local defaults are qwen3:4b-instruct and a 120-second model-request timeout. These are agent-turn timings; resource creation before respond is excluded. Cached, uncached and no-model paths differ. Outliers remain recorded; request timeouts do not establish a hard end-to-end bound.', 'SmallV')
    h('Gnani speech evidence and its scope')
    p(voice_text(voice))
    wall = [row.get('latency_ms') for row in voice.get('batch', {}).get('entries', [])]
    audio = [row.get('reply_seconds') for row in voice.get('semantic_validation', {}).get('checks', [])]
    p('Saved processing wall range: ' + seconds_range(wall, milliseconds=True) + '; reply audio duration: ' + seconds_range(audio) + '. Processing time and playback duration are different. Only a refreshed run of the current source-only agent establishes integration evidence for this version; old speech outputs remain historical.', 'SmallV')
    recovery = load('voice_recovery.json')
    hindi_voice = load('history/pre_document_answers/primary_hindi_voice_validation.json')
    if recovery or hindi_voice:
        rs = recovery.get('summary', {})
        hs = hindi_voice.get('summary', {})
        p(f"Historical Hindi UPI {hs.get('voice_passed', 0)}/{hs.get('planned', '?')}; separately saved silence recovery {rs.get('passed', 0)}/{rs.get('planned', '?')}. Hindi predates the new answer path; check recovery runtime provenance. Silence recovery means an honest spoken clarification with AI disclosure and no actions, not successful transcription of speech.", 'SmallV')
    p('Primary scope is English, Hindi and Hinglish. Gnani is the only STT/TTS provider. Additional languages are optional translation previews. Synthetic Gnani-generated inputs establish neither human accent/noise robustness nor subjective intelligibility. Human own-voice rehearsal and listening remain for the final demo step.', 'SmallV')
    extra_languages = load('language_validation.json')
    if extra_languages:
        p('Historical optional preview: ' + regional_preview_text(extra_languages), 'SmallV')
    h('Reproduce and finish the release')
    p('Repository: https://github.com/Pranay207/Resolvox. Install: powershell -File setup.ps1; configure .env and Ollama before launch. Batch: python run.py --audio_dir <in> --out_dir <out>. Live questions/conversations: python scripts/resume_live_practice.py --step 2, then --step 3. Engineering: python -m pytest -q -p no:cacheprovider. Speech: python generate_voice_samples.py --reuse-inputs. Preserve earlier artifacts before reruns.', 'SmallV')
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
