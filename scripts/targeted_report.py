"""Four-page report from preserved and targeted evidence; no inferred full scores."""
from pathlib import Path
import json,hashlib,datetime
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors

def build(root, *, in_progress=False):
 root=Path(root)
 from src.app_profile import hosted_settings
 hosted_config=hosted_settings(root)
 hosted_model=hosted_config['LLM_MODEL']
 hosted_effort=hosted_config['LLM_REASONING_EFFORT']
 def load(name):
  try:return json.loads((root/'sample_outputs'/name).read_text(encoding='utf-8'))
  except (OSError,ValueError):return {}
 returns=load('return_date_validation.json');publication=load('release_update_verification.json')
 live=load('targeted_live_validation.json');voice=load('targeted_voice_validation.json');unit=load('refund_scope_verification_20261031.json');release_tests=load('targeted_release_tests_20261031.json');questions=load('eval_step2_latest_cases.json');convos=load('eval_step3_latest_cases.json');baseline=load('eval_step1.json')
 def score(value):
  s=value.get('summary',value.get('pytest',{}));n=s.get('total',s.get('tests',s.get('planned')))
  return str(s.get('passed','pending'))+'/'+str(n if n is not None else 'pending')
 from scripts.targeted_release import blockers
 if blockers(root) and not in_progress:raise ValueError('Finish the current targeted checks before generating the report')
 if not in_progress:
  return_cases=returns.get('cases', [])
  current=live.get('runtime_source_sha256')
  if (returns.get('manual_source_review',{}).get('status')!='passed'
      or returns.get('complete') is not True or returns.get('source_runtime_unchanged') is not True
      or returns.get('runtime_source_sha256')!=current or returns.get('runtime_source_sha256_finished')!=current
      or len(return_cases)!=4 or not all(case.get('passed') is True for case in return_cases)
      or {case.get('id') for case in return_cases}!={'missing_date_compound','missing_date_hindi','missing_date_hinglish','known_placement'}
      or returns.get('verification_driver_sha256',{}).get('scripts/validate_return_dates.py')!=hashlib.sha256((root/'scripts/validate_return_dates.py').read_bytes()).hexdigest()):
   raise ValueError('Finish source review of four current return-date retests before generating the report')
 cases=live.get('cases',[]);passed=sum(c.get('passed') is True for c in cases)
 pacing=float(live.get('inter_turn_pacing_seconds',60))
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
 p('Resolvox','RVTitle');p('VoiceOps 2026 Capstone | Technical Report','RVSmall')
 h('What we built in the four required steps')
 p('Resolvox is a document-grounded voice support agent for ZentroMart. It handles policy questions, verified order follow-ups and confirmed human handover using the supplied synthetic dataset. The same support agent serves text, microphone and folder-based audio input.')
 table([['Required step','Implemented behavior'],['1 - Answer with an LLM','An LLM API role/limits prompt and a prompt-only baseline without company documents or order tools. The shared assistant identifies itself as AI at the start of a conversation.'],['2 - Ground in documents','Policy sections retain IDs, authority, status, version and effective date. A local vector index and lexical search retrieve relevant original chunks. The LLM receives those chunks and source-derived facts; missing support leads to clarification or uncertainty.'],['3 - Hold a conversation','Session state preserves order context and follow-ups. The agent asks one missing-detail question, verifies access before private order disclosure, uses the supplied lookup_order and create_ticket tools, and confirms handover only from an actual tool result.'],['4 - Give it a voice','Gnani STT transcribes the customer clip, the same Step 3 agent responds, and Gnani TTS produces the spoken reply. English, Hindi and Hinglish are the primary supported languages.']],[128,383])
 h('Grounding and control of actions')
 p('Retrieval combines lexical matching with multilingual MiniLM embeddings in an ONNX int8 index and hybrid fusion. Current policy takes precedence over lower-authority material. Source-bound calculations handle return dates, business-day refund windows, payment-method units and membership conditions.')
 p('Operational authentication and tool confirmations are deterministic. When current policy requires an RRN, the host can append its exact authenticated event field; that record-reading step is identified in the trace. Business explanations are generated from actual evidence, with no practice-answer lookup or authored policy-answer fallback. Proof/contact fields are redacted from model input and public traces. Full generation chunks, model flags and tool outcomes are recorded separately from the spoken text.')
 h('Runtime')
 p(f'{"Implemented" if in_progress else "Current verified"} application profile: Groq {hosted_model} with {hosted_effort} reasoning effort, constrained JSON output and an additional source-claim review. Requests and repairs have bounded time budgets; no answer-provider fallback is enabled. Gnani is the only STT/TTS provider. Retrieval and the Streamlit interface run on the laptop. A separate local Ollama profile remains available.')
 page();p('Evaluation: Step 1 vs Step 2','RVTitle')
 base_errors=baseline.get('summary',{}).get('errors',0)
 table([['Required comparison','Recorded score','Basis'],['Step 1 - Prompt-only LLM',score(baseline),f"Baseline artifact; {base_errors} recorded {'error' if base_errors == 1 else 'errors'}. No company documents or order tools."],['Step 2 - Document-grounded answers',score(questions),'Stored actual practice-question predictions and targeted retests across recorded revisions.']],[165,70,276])
 p('The recorded baseline used qwen3:1.7b. The Step 2 total combines actual preserved outputs and targeted retests across earlier model/source revisions. Fresh selected checks now use the explicit Groq application profile. These configuration differences confound a causal comparison; a frozen same-model ablation is a remaining evaluation improvement.')
 h('Verified checks and recorded results' if in_progress else 'Latest verified targeted results')
 conversation_cases=[c for c in cases if c['id'].startswith('PC')]
 turn_total=sum(c.get('summary',{}).get('total',0) for c in conversation_cases)
 turn_passed=sum(c.get('summary',{}).get('passed',0) for c in conversation_cases)
 edges=[c for c in cases if not c['id'].startswith('PC')]
 semantic=voice.get('semantic_validation',{});batch=voice.get('batch',{})
 if in_progress:
  def offline_result(value):
   checked=value.get('pytest',{})
   verification_paths=value.get('source_and_test_sha256_finished',{})
   verified=(value.get('complete') is True and value.get('exit_code')==0
             and value.get('all_tested_bytes_unchanged') is True and bool(verification_paths)
             and value.get('source_and_test_sha256_started')==verification_paths
             and checked.get('failures')==0 and checked.get('errors')==0 and checked.get('skipped')==0
             and all((root/name).is_file() and hashlib.sha256((root/name).read_bytes()).hexdigest()==digest
                     for name,digest in verification_paths.items()))
   return (str(checked['passed'])+'/'+str(checked['tests'])+' verified') if verified else 'Receipt not current'
  table([['Selected check','Recorded result','Scope'],['Selected conversations',f'{turn_passed}/{turn_total} turns','Four current scenarios with source-by-source review of generated replies.'],['Refund edge cases',str(sum(c['passed'] for c in edges))+'/'+str(len(edges)),'Current coupon-context and authenticated completion-date checks.'],['Primary-language Gnani speech',str(semantic.get('passed','recorded'))+'/'+str(batch.get('total','recorded')),'Current synthetic English, Hindi and Hinglish STT/agent/TTS round trips; text/source review and audio integrity.'],['Focused offline regressions',offline_result(publication),'Source support, return-date and eligibility scope, repair context and release safeguards.'],['Refund and grounding regressions',offline_result(unit),'Dates, units, record reading and negative action/privacy cases.'],['Packaging and report regressions',offline_result(release_tests),'Evidence freshness, document limits, archive integrity and release guards.']],[170,90,251])
 else:
  table([['Selected check','Actual result','Scope'],['Four conversation scenarios',f'{turn_passed}/{turn_total} turns','QC status, overdue refund/reference handover, Plus/wallet follow-up and Hindi return/refund guidance.'],['Two refund edge cases',str(sum(c['passed'] for c in edges))+'/'+str(len(edges)),'Compound coupon/partial-refund context and authenticated recorded completion date.'],['Refund and source-grounding regressions',score(unit),'Source binding, record reading, language/context integration and negative action/privacy checks.'],['Packaging and report regressions',score(release_tests),'Evidence freshness, retained-output validation, archive filtering and required artifact gates.'],['Return-date edge checks',str(sum(c.get('passed') is True for c in returns.get('cases',[])))+'/'+str(len(returns.get('cases',[]))),'Missing placement dates in English, Hindi and Hinglish; an explicitly supplied date.'],['Primary-language Gnani speech',str(semantic.get('passed','pending'))+'/'+str(batch.get('total','pending')),'Selected real synthetic-audio round trips in English, Hindi and Hinglish.']],[170,70,271])
 if in_progress:
  p('The selected core conversation, refund and speech checks use the current hosted profile and source revision. The speech matcher was corrected for equivalent Hindi spellings of photo; unchanged predictions and audio were re-evaluated from 2/3 to 3/3, with the original manifest preserved. Supplementary return-date probes were quota-limited and are not claimed as 4/4. Offline selections overlap and are not additive. No fresh full52 or full96 result is claimed.')
 else:
  p(f'These selected conversation, refund and speech checks were freshly executed with the current runtime and declared hosted application profile. The conversation verifier spaces generated turns by {pacing:g} seconds to respect the account token quota; this pacing is separate from per-turn latency. Earlier failed runs remain preserved. The three speech clips use real Gnani STT and TTS with synthetic inputs; generated model text, source checks, output audio and source hashes are retained.')
 p('These are exposed development regressions, not hidden organizer scores or a new full-suite run. The checks establish the stated selected behavior; they do not certify every unseen question or arbitrary semantic claim. Synthetic speech does not establish human accents, noisy-room performance or subjective listening quality.','RVSmall')
 timings=[]
 for case in cases:
  try:
   value=json.loads((root/case['artifact']).read_text(encoding='utf-8'))
   for row in value.get('results',[]) or [value]:
    pred=row.get('prediction',{});ms=pred.get('latency_ms',row.get('latency_ms'))
    if isinstance(ms,(int,float)) and pred.get('generation',{}).get('generation_attempts',0)>0:timings.append(ms/1000)
  except (OSError,ValueError,KeyError):pass
 if timings:p(f'Recorded selected generated-turn latency: {min(timings):.1f}-{max(timings):.1f} seconds across {len(timings)} saved turns. Host-only steps and speech service time are separate. These timings can include provider quota waits and are not a universal latency guarantee. Per-stage timings are preserved in JSON.','RVSmall')
 page();p('What went wrong and the fixes','RVTitle')
 table([['Observed problem','Correction and verification'],['Missing placement date selected a personal return window','A source-bound guard rejects selecting the ordinary window because a placement date is unknown, including Hindi Unicode-hyphen phrasing. General rules and conditional exceptions remain valid, and requested fee evidence is retained during repair. Common Hinglish clothing nouns now bind to the catalog category.'],['Missing QC data became an unsupported status claim','A bound pending-status view distinguishes an unrecorded QC/initiation date from a failed check. An absent RRN cannot be offered for bank tracing. The source initiation clock remains anchored to pickup, with QC pass as a prerequisite. Earlier selected outputs and offline tests cover this distinction.'],['Wallet hours mixed with business days and an invented date','Known payment methods bind to the actual policy row. Wallet hour limits remain hours; other payment methods retain their business-day ranges and initiation anchor. Unsupported dated wallet estimates are rejected.'],['Compound refund questions lost requested coupon details','Coupon, partial-refund and amount requests retain the full original source/fact context through generation and repair. Earlier source-grounded outputs and targeted offline tests cover both requested facets.'],['Valid conditional/record wording was rejected','Source-backed conditional timing is separated from claims of performed actions. Historical completion uses a compact authenticated record-reading view instead of a future policy estimate. The actual recorded date and action/authentication boundaries were checked.'],['Hindi damage guidance abstained on remedy prerequisites','A source-only first reporting view explains the actual reporting window and required photos without promising an unverified benefit. Selected English, Hindi and Hinglish clips used real Gnani STT/TTS with synthetic input and preserved source hashes.']],[172,339])
 p('Interactive checks also exposed a credit-card phrase misread as a compensation-credit claim and a general paid-guarantee delivery request routed to order verification. The instrument scope and public-request routing were corrected. Targeted negative checks retain genuine credit conditions and private-record verification. Focused refund prompts now preserve the original question so requested membership facets remain visible.')
 h('Safeguards retained')
 p('Identity verification precedes private order disclosure. A policy fee cannot establish a personal paid/refund amount. Missing records do not prove a prohibition or failed event. Claim/quality verification is distinct from identity verification. Source metadata and full original validators remain active for focused generation; a rejected draft gets one bounded repair before uncertainty.')
 h('What we would improve next')
 p('Run a frozen same-model Step 1/Step 2 comparison and an independent unseen evaluation. Expand independent review of multi-part and qualitative claims: neither finite validators nor a model-based source review proves complete semantic entailment.')
 p('Measure hosted latency and throughput under deployment load and provider rate limits. Improve Hindi/Hinglish grammar and repetition, then test human speech with accents, background noise and unclear audio. Synthetic checks do not certify those conditions. Shared-customer deployment would additionally require authenticated private history and real store/ticket integrations.')
 page();p('Bonus work and reproducibility','RVTitle')
 h('Additional engineering beyond the basic build')
 table([['Work','Practical benefit'],['Multilingual support','English, Hindi and Hinglish routing and spoken output share the same source-grounded agent. Only these primary routes are claimed here.'],['Local hybrid retrieval','Lexical/dense fusion, multilingual embeddings and ONNX int8 execution support document search on the laptop. Authority/effective-date metadata preserve policy precedence.'],['Source-bound safeguards','Checks cover recognized dates, units, amounts, prerequisites and unsupported action claims. Actual tool confirmations stay separate from generated explanations.'],['Inspectable evaluation and release','Saved input chunks, model flags, original execution epochs, audio hashes and machine-readable receipts make selected results reviewable. Retained outputs are labelled rather than presented as fresh inference.'],['Usable interface and batch processing','A responsive, single conversation supports Speak/Type, case details and supporting policies. Saved chats retain local text/audio/context; reopening does not restore private order verification. History databases stay outside Git and the archive. The batch runner saves text, JSON, real reply audio and source chunks.']],[158,353])
 h('Reproduce the agent')
 p('Code: https://github.com/Pranay207/Resolvox. Install the project dependencies, copy .env.example to the ignored .env, configure your own Gnani key in .env, provide the official extracted dataset and add your Groq key to the ignored .env.hosted for the configured application profile. The separate local profile uses Ollama qwen3:4b-instruct. Setup and environment details are in README.md.')
 p('Windows setup: powershell -ExecutionPolicy Bypass -File setup.ps1. Interactive profile: python scripts/run_app.py --hosted.')
 p('Hosted batch command: python run.py --hosted --audio_dir <in> --out_dir <out>. Omit --hosted only for the separately configured local Ollama profile. Each clip produces answer text, JSON, a real reply WAV and the source chunks supplied to generation; manifest.json records per-clip outcomes. Gnani remains the only speech service, including spoken recovery attempts.')
 h('Evidence accompanying the report')
 p('Step comparison: sample_outputs/eval_step1.json and eval_step2_latest_cases.json. Selected conversations/refunds: targeted_live_validation.json. Return-date check records: return_date_validation.json. Recorded speech: targeted_voice_validation.json. Current offline checks: release_update_verification.json. Earlier automated receipts retain their original source and test hashes. All paths are under sample_outputs/; their referenced artifacts retain their actual scopes.','RVSmall')
 p('Only the supplied synthetic customer data is used. Credentials, private input speech, virtual environments, dataset copies and model weights are excluded from the submission archive. This report describes implemented behavior and recorded results; organizer marks are determined by the separate hidden-audio evaluation.','RVSmall')
 def footer(canvas,doc):
  canvas.setStrokeColor(colors.HexColor('#d2dce6'));canvas.line(42,37,553,37);canvas.setFont('Helvetica',8);canvas.setFillColor(navy);canvas.drawString(42,24,'RESOLVOX | VOICEOPS 2026 | PRANAY207');canvas.drawRightString(553,24,str(doc.page))
 doc=SimpleDocTemplate(str(root/'report.pdf'),pagesize=(595.28,841.89),leftMargin=42,rightMargin=42,topMargin=36,bottomMargin=48,title='Resolvox - VoiceOps 2026 Technical Report',author='Pranay207');doc.build(story,onFirstPage=footer,onLaterPages=footer)
 if doc.page>4:raise RuntimeError('Report exceeded four pages; revise and render again')
 (root/'report.md').write_text('# Resolvox - VoiceOps 2026 Capstone\n\n'+'\n'.join(md),encoding='utf-8',newline='\n')
 print('Updated four-page report and matching Markdown from actual scoped evidence.')
