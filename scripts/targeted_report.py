"""Four-page report from preserved and targeted evidence; no inferred full scores."""
from pathlib import Path
import json,hashlib,datetime
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors

def build(root):
 root=Path(root)
 def load(name):
  try:return json.loads((root/'sample_outputs'/name).read_text(encoding='utf-8'))
  except (OSError,ValueError):return {}
 live=load('targeted_live_validation.json');voice=load('targeted_voice_validation.json');unit=load('refund_scope_verification_20261031.json');release_tests=load('targeted_release_tests_20261031.json');questions=load('eval_step2_latest_cases.json');convos=load('eval_step3_latest_cases.json');baseline=load('eval_step1.json')
 def score(value):
  s=value.get('summary',value.get('pytest',{}));n=s.get('total',s.get('tests',s.get('planned')))
  return str(s.get('passed','pending'))+'/'+str(n if n is not None else 'pending')
 cases=live.get('cases',[]);passed=sum(c.get('passed') is True for c in cases)
 styles=getSampleStyleSheet();navy=colors.HexColor('#132842');blue=colors.HexColor('#2873ba')
 styles.add(ParagraphStyle(name='RVTitle',fontName='Helvetica-Bold',fontSize=24,leading=28,textColor=navy,spaceAfter=11))
 styles.add(ParagraphStyle(name='RVHead',fontName='Helvetica-Bold',fontSize=12,leading=15,textColor=blue,spaceBefore=9,spaceAfter=6))
 styles.add(ParagraphStyle(name='RVBody',fontName='Helvetica',fontSize=9,leading=12,textColor=navy,spaceAfter=7))
 styles.add(ParagraphStyle(name='RVSmall',fontName='Helvetica',fontSize=8,leading=10.3,textColor=navy,spaceAfter=5))
 story=[];md=[]
 def p(text,style='RVBody'):
  story.append(Paragraph(escape(text),styles[style]));md.append(text+'\n')
 def h(text):p(text,'RVHead');md[-1]='## '+text+'\n'
 def table(rows,widths):
  table=Table([[Paragraph(escape(str(c)),styles['RVSmall']) for c in row] for row in rows],colWidths=widths,hAlign='LEFT',repeatRows=1)
  table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9f1f9')),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#d2dce6')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));story.append(table);story.append(Spacer(1,8));md.append('| '+' | '.join(map(str,rows[0]))+' |');md.append('| '+' | '.join('---' for _ in rows[0])+' |');md.extend('| '+' | '.join(map(str,row))+' |' for row in rows[1:]);md.append('')
 def page():story.append(PageBreak());md.append('\n---\n')
 p('Resolvox','RVTitle');p('VoiceOps 2026 Capstone | Technical Report | 31 October 2026','RVSmall')
 h('What we built in the four required steps')
 p('Resolvox is a document-grounded voice support agent for ZentroMart. It handles policy questions, verified order follow-ups and confirmed human handover using the supplied synthetic dataset. The same support agent serves text, microphone and folder-based audio input.')
 table([['Required step','Implemented behavior'],['1 - Answer with an LLM','An LLM API role/limits prompt and a prompt-only baseline without company documents or order tools. The shared assistant identifies itself as AI at the start of a conversation.'],['2 - Ground in documents','Policy sections retain IDs, authority, status, version and effective date. A local vector index and lexical search retrieve relevant original chunks. The LLM receives those chunks and source-derived facts; missing support leads to clarification or uncertainty.'],['3 - Hold a conversation','Session state preserves order context and follow-ups. The agent asks one missing-detail question, verifies access before private order disclosure, uses the supplied lookup_order and create_ticket tools, and confirms handover only from an actual tool result.'],['4 - Give it a voice','Gnani STT transcribes the customer clip, the same Step 3 agent responds, and Gnani TTS produces the spoken reply. English, Hindi and Hinglish are the primary supported languages.']],[128,383])
 h('Grounding and control of actions')
 p('Retrieval combines lexical matching with multilingual MiniLM embeddings in an ONNX int8 index and hybrid fusion. Current policy takes precedence over lower-authority material. Source-bound calculations handle return dates, business-day refund windows, payment-method units and membership conditions.')
 p('Operational authentication and tool confirmations are deterministic. Business explanations are generated from actual evidence, with no practice-answer lookup or authored policy-answer fallback. Proof/contact fields are redacted from model input and public traces. Full generation chunks, model flags and tool outcomes are recorded separately from the spoken text.')
 h('Runtime')
 p('Selected runtime: local Ollama qwen3:4b-instruct through its HTTP API, CPU-only laptop, 4096-token request context and 600-second request timeouts. Gnani is the only STT/TTS provider. Streamlit provides voice/text input and source inspection. The supplied dataset reference date is 20 October 2026.')
 page();p('Evaluation: Step 1 vs Step 2','RVTitle')
 base_errors=baseline.get('summary',{}).get('errors',0)
 table([['Required comparison','Recorded score','Basis'],['Step 1 - Prompt-only LLM',score(baseline),f'Baseline artifact; {base_errors} recorded error(s). No company documents or order tools.'],['Step 2 - Document-grounded answers',score(questions),'Stored actual practice-question predictions and targeted retests across recorded revisions.']],[165,70,276])
 p('The recorded baseline used qwen3:1.7b. The Step 2 total combines preserved outputs and targeted retests across model/source revisions; the currently selected model is qwen3:4b-instruct. These configuration differences confound a causal comparison. A complete controlled same-model ablation is a remaining evaluation improvement, rather than a claimed result.')
 h('Latest verified targeted results')
 conversation_cases=[c for c in cases if c['id'].startswith('PC')]
 turn_total=sum(c.get('summary',{}).get('total',0) for c in conversation_cases)
 turn_passed=sum(c.get('summary',{}).get('passed',0) for c in conversation_cases)
 edges=[c for c in cases if not c['id'].startswith('PC')]
 semantic=voice.get('semantic_validation',{});batch=voice.get('batch',{})
 table([['Selected check','Actual result','Scope'],['Four conversation scenarios',f'{turn_passed}/{turn_total} turns','QC status, overdue refund/reference handover, Plus/wallet follow-up and Hindi return/refund guidance.'],['Two refund edge cases',str(sum(c['passed'] for c in edges))+'/'+str(len(edges)),'Compound coupon/partial-refund context and authenticated recorded completion date.'],['Affected refund/reporting regressions',score(unit),'Source binding, record reading, language/context integration and negative action/privacy checks.'],['Packaging/report regressions',score(release_tests),'Evidence freshness, retained-output validation, archive filtering and required artifact gates.'],['Primary-language Gnani speech',str(semantic.get('passed','pending'))+'/'+str(batch.get('total','pending')),'Selected real synthetic-audio round trips in English, Hindi and Hinglish.']],[170,70,271])
 p('Selected earlier conversation outputs retain their original inference revision and are revalidated by current finite guards. The initial speech batch delivered all three replies but its Hindi answer abstained; only Hindi was retested. English/Hinglish recordings were retained and their final spoken text checked with current guards. Per-case epochs, real audio and earlier failures remain in the evidence.')
 p('These are exposed development regressions, not hidden organizer scores or a new full-suite run. The checks establish the stated selected behavior; they do not certify every unseen question or arbitrary semantic claim. Synthetic speech does not establish human accents, noisy-room performance or subjective listening quality.','RVSmall')
 timings=[]
 for case in cases:
  try:
   value=json.loads((root/case['artifact']).read_text(encoding='utf-8'))
   for row in value.get('results',[]) or [value]:
    pred=row.get('prediction',{});ms=pred.get('latency_ms',row.get('latency_ms'))
    if isinstance(ms,(int,float)) and pred.get('generation',{}).get('generation_attempts',0)>0:timings.append(ms/1000)
  except (OSError,ValueError,KeyError):pass
 if timings:p(f'Recorded selected generated-turn latency: {min(timings):.1f}-{max(timings):.1f} seconds across {len(timings)} saved turns. CPU/model initialization, host-only steps and speech service time are separate measurements. Per-stage timings are preserved in JSON.','RVSmall')
 page();p('What went wrong and the fixes','RVTitle')
 table([['Observed problem','Correction and verification'],['Missing QC data became an unsupported status claim','A bound pending-status view distinguishes an unrecorded QC/initiation date from a failed check. An absent RRN cannot be offered for bank tracing. The affected conversation was retested.'],['Wallet hours mixed with business days and an invented date','Known payment methods bind to the actual policy row. Wallet hour limits remain hours; other payment methods retain their business-day ranges and initiation anchor. Unsupported dated wallet estimates are rejected.'],['Compound refund questions lost requested coupon details','Coupon, partial-refund and amount requests retain the full original source/fact context through generation and repair. The live edge verifies both timing and the coupon deduction condition.'],['Valid conditional/record wording was rejected','Source-backed conditional timing is separated from claims of performed actions. Historical completion uses a compact authenticated record-reading view instead of a future policy estimate. The actual recorded date and action/authentication boundaries were checked.'],['Hindi damage guidance abstained on remedy prerequisites','A source-only first reporting view explains the actual reporting window and required photos without promising an unverified benefit. Only the failed Hindi speech clip was repeated, using real Gnani STT/TTS.']],[172,339])
 p('Interactive checks also exposed a credit-card phrase misread as a compensation-credit claim and a general paid-guarantee delivery request routed to order verification. The instrument scope and public-request routing were corrected. Targeted negative checks retain genuine credit conditions and private-record verification. Focused refund prompts now preserve the original question so requested membership facets remain visible.')
 h('Safeguards retained')
 p('Identity verification precedes private order disclosure. A policy fee cannot establish a personal paid/refund amount. Missing records do not prove a prohibition or failed event. Claim/quality verification is distinct from identity verification. Source metadata and full original validators remain active for focused generation; a rejected draft gets one bounded repair before uncertainty.')
 h('What we would improve next')
 p('Run a frozen same-model Step 1/Step 2 comparison and an independent unseen evaluation. Expand review of multi-part and qualitative claims because finite validators do not prove complete semantic entailment.')
 p('Reduce CPU response latency with a measured, quality-preserving deployment change. Improve Hindi/Hinglish grammar and repetition, then test own-voice synthetic support scenarios with accents, background noise and unclear audio. The current synthetic checks do not certify those conditions.')
 page();p('Bonus work and reproducibility','RVTitle')
 h('Additional engineering beyond the basic build')
 table([['Work','Practical benefit'],['Multilingual support','English, Hindi and Hinglish routing and spoken output share the same source-grounded agent. Only these primary routes are claimed here.'],['Local hybrid retrieval','Lexical/dense fusion, multilingual embeddings and ONNX int8 execution support document search on the laptop. Authority/effective-date metadata preserve policy precedence.'],['Source-bound safeguards','Checks cover recognized dates, units, amounts, prerequisites and unsupported action claims. Actual tool confirmations stay separate from generated explanations.'],['Inspectable evaluation and release','Saved input chunks, model flags, original execution epochs, audio hashes and machine-readable receipts make selected results reviewable. Retained outputs are labelled rather than presented as fresh inference.'],['Usable interface and batch processing','Streamlit supports voice/text interaction and source inspection. The batch runner saves text, JSON, real reply audio and source chunks, while isolating clip failures.']],[158,353])
 h('Reproduce the agent')
 p('Code: https://github.com/Pranay207/Resolvox. Install the project dependencies, copy .env.example to the ignored .env, configure your own Gnani key, provide the official extracted dataset and start Ollama with qwen3:4b-instruct at the configured endpoint. Setup and environment details are in README.md.')
 p('Windows setup: powershell -ExecutionPolicy Bypass -File setup.ps1. Interactive support: python -m streamlit run app.py.')
 p('Organizer batch command: python run.py --audio_dir <in> --out_dir <out>. Each clip produces answer text, JSON, a real reply WAV and the source chunks supplied to generation; manifest.json records per-clip outcomes. Gnani remains the only speech service, including spoken recovery attempts.')
 h('Evidence accompanying the report')
 p('Step comparison: sample_outputs/eval_step1.json and eval_step2_latest_cases.json. Selected conversations/refunds: targeted_live_validation.json. Speech: targeted_voice_validation.json with the initial batch and Hindi-only retest. Current automated receipts: refund_scope_verification_20261031.json and targeted_release_tests_20261031.json. All paths are under sample_outputs/; their referenced artifacts retain their actual scopes.','RVSmall')
 p('Only the supplied synthetic customer data is used. Credentials, private input speech, virtual environments, dataset copies and model weights are excluded from the submission archive. This report describes implemented behavior and recorded results; organizer marks are determined by the separate hidden-audio evaluation.','RVSmall')
 def footer(canvas,doc):
  canvas.setStrokeColor(colors.HexColor('#d2dce6'));canvas.line(42,37,553,37);canvas.setFont('Helvetica',8);canvas.setFillColor(navy);canvas.drawString(42,24,'RESOLVOX | VOICEOPS 2026 | PRANAY207');canvas.drawRightString(553,24,str(doc.page))
 doc=SimpleDocTemplate(str(root/'report.pdf'),pagesize=(595.28,841.89),leftMargin=42,rightMargin=42,topMargin=36,bottomMargin=48,title='Resolvox - VoiceOps 2026 Technical Report',author='Pranay207');doc.build(story,onFirstPage=footer,onLaterPages=footer)
 if doc.page>4:raise RuntimeError('Report exceeded four pages; revise and render again')
 (root/'report.md').write_text('# Resolvox - VoiceOps 2026 Capstone\n\n'+'\n'.join(md),encoding='utf-8',newline='\n')
 print('Updated four-page report and matching Markdown from actual scoped evidence.')
