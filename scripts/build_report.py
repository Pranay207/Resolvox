"""Generate the synchronized four-page technical report and Markdown source."""
from pathlib import Path
from collections import Counter
from xml.sax.saxutils import escape
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.graphics.shapes import Drawing,Rect,String,Line,Polygon

NAVY=colors.HexColor('#132842');BLUE=colors.HexColor('#2873ba');MINT=colors.HexColor('#e7f5f2');GRAY=colors.HexColor('#516174')
def load(name):return json.loads((ROOT/'sample_outputs'/name).read_text(encoding='utf-8'))
def pct(x):return f'{100*x:.1f}%'
def main():
    base=load('eval_step1.json');rag=load('eval_step2.json');conv=load('eval_step3.json');adv=load('eval_adversarial.json');voice=load('voice_validation.json')
    b=base['summary'];r=rag['summary'];c=conv['summary'];a=adv['summary']
    composition=Counter(x['prediction'].get('composition','none') for x in rag['results']); conv_composition=Counter(x['prediction'].get('composition','none') for x in conv['results'])
    styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='TitleV',fontName='Helvetica-Bold',fontSize=25,leading=29,textColor=NAVY,spaceAfter=12))
    styles.add(ParagraphStyle(name='HeadingV',fontName='Helvetica-Bold',fontSize=14,leading=18,textColor=NAVY,spaceBefore=12,spaceAfter=7))
    styles.add(ParagraphStyle(name='BodyV',fontName='Helvetica',fontSize=9.6,leading=13.5,textColor=NAVY,spaceAfter=7))
    styles.add(ParagraphStyle(name='SmallV',fontName='Helvetica',fontSize=8.3,leading=11,textColor=GRAY,spaceAfter=6))
    story=[];md=[]
    def p(text,style='BodyV'):
        story.append(Paragraph(escape(text),styles[style]));md.append(text+'\n')
    def h(text):p(text,'HeadingV')
    def table(rows,widths):
        body=[[Paragraph(escape(str(cell)),styles['SmallV']) for cell in row] for row in rows]
        t=Table(body,colWidths=widths,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),MINT),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,BLUE),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#dce5ed')),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.append(t);story.append(Spacer(1,8));md.append('\n'.join('| '+' | '.join(map(str,row))+' |' for row in rows)+'\n')
    def page():story.append(PageBreak());md.append('\n---\n')
    p('VoiceOps 2026','SmallV');p('ZentroMart: support that listens','TitleV')
    p('Technical report | Pranay207 | C&A Club, IIT Guwahati x Gnani.ai','SmallV')
    p('A multilingual support agent grounded in the supplied synthetic retailer policies and order tools. Its priority is defensible answers and safe handovers, rather than unconstrained generation. A top-20 ranking is an aspiration, not an evaluated result.')
    h('One support agent, four build steps')
    diagram=Drawing(510,85);xs=[0,67,150,254,346,426];widths=[57,73,94,82,70,80];labels=[['Audio'],['Gnani STT'],['State / RAG','Policy rules'],['Verified','order tools'],['LLM','sentence plan'],['Gnani TTS','+ source trace']]
    for x,w,lines in zip(xs,widths,labels):
        diagram.add(Rect(x,29,w,43,rx=5,ry=5,fillColor=MINT,strokeColor=BLUE,strokeWidth=.7))
        for j,label in enumerate(lines):diagram.add(String(x+w/2,54-j*11,label,textAnchor='middle',fontName='Helvetica',fontSize=8,fillColor=NAVY))
    for i in range(5):
        x=xs[i]+widths[i];end=xs[i+1]-2;diagram.add(Line(x,50,end,50,strokeColor=BLUE));diagram.add(Polygon([end,50,end-4,52,end-4,48],fillColor=BLUE,strokeColor=BLUE))
    diagram.add(String(0,10,'Same stateful brain for text, voice, and batch evaluation. No alternate speech provider.',fontSize=8,fillColor=GRAY));story.append(diagram)
    table([['Stage','What was built'],['1 - Baseline','Actual Ollama API call; role/limits; AI disclosure; no documents or order access.'],['2 - Grounding','Section-ID KB index; BM25 + multilingual MiniLM dense search; authority-aware ranking; traceable policy plans and abstention.'],['3 - Conversation','Session state, proof-gated supplied tools, date/eligibility rules, refusals and successful-ticket-only handover.'],['4 - Voice','Official Gnani REST STT/TTS wrapper, spoken-number handling and fault-isolated audio-folder CLI. Six synthetic voice round trips and semantic checks verified.']],[94,416])
    h('Observed local results')
    p(f"Baseline: {b['passed']}/{b['total']} mechanical checks. Grounded: {r['passed']}/{r['total']}. Conversations: {c['passed']}/{c['total']} turns. Original adversarial/stateful checks: {a['passed']}/{a['total']}. These are transparent local regression checks, not organizer scores or proof of hidden-test accuracy.")
    p('Release status: text, local LLM composition and six real Gnani speech round trips verified. Synthetic audio does not establish human-speech robustness. The user-recorded demo remains outstanding.','SmallV')
    page();p('Design choices and boundaries','TitleV')
    h('Grounding is a data contract')
    p('All 21 knowledge documents were read, preserving section IDs, version, status and effective dates. The public catalog and calendar are loaded separately. Customer and order tables are accessed only through the unchanged organizer tool module. Practice questions, expected answers and historical support logs never enter the runtime index.')
    p('Authority is current policy > agent guide > help > FAQ > marketing. KB-00 supplies the date and precedence rules. Superseded text cannot govern unless its successor explicitly preserves a historical case: RET-3 keeps the 10-day electronics window only for deliveries before 1 August 2026; otherwise 7 days applies. A marketplace badge cannot override MKS-3, which excludes seller items from Assured coverage.')
    h('Hybrid retrieval without a heavyweight training stack')
    p('BM25 uses stop-word removal and light plural normalization. Dense retrieval uses the official 118 MB int8 ONNX export of multilingual MiniLM (384 dimensions), pinned to an immutable model revision. Intent vocabulary expands Hinglish and colloquial queries into policy terminology. Reciprocal-rank fusion combines both searches, with a modest authority prior. Model and section embeddings load once and are cached on disk.')
    p('Search candidates and governing evidence are distinct. Policy rules retrieve specific source sections for decisions, while broad search candidates are logged independently. Explicit rule coverage helps structured policy cases but limits open-ended generalization; high answer-check pass rates must not hide weak search or intent coverage.')
    h('Deterministic decisions; constrained LLM composition')
    p('Code computes date windows, business-day deadlines, coupon arithmetic, proof limits and eligibility. Policy-derived statements are written in English, Hindi and Hinglish. The LLM arranges a verified sentence bank; its output must contain every sentence index exactly once. Invalid plans fall back to the original verified wording. This deliberately limits language freedom and prevents invented policy facts; it is not an unrestricted answer-generation model.')
    h('Dates and a documented ambiguity')
    p('The reference date is 20 October 2026. Refund/logistics days are Monday-Saturday excluding the four supplied holidays; initiation day is day zero. RET-2 says returns start on delivery, but does not spell out inclusive arithmetic. The supplied expected deadlines consistently use delivery + N calendar days. That operational convention is used globally and tested at category, sale-period and historical-policy boundaries; no question-specific date exceptions are coded.')
    p('Schema: 300 customers -> 1,000 orders -> 1,783 order lines -> 70 products. Delivery pincodes reference 36 serviceability rows; four holidays define the business calendar. Identifiers remain strings. Blank completion dates are not interpreted as completed refunds.','SmallV')
    page();p('Evaluation and failure analysis','TitleV')
    table([['Generated evaluation','Passes','Rate / interpretation'],['Prompt-only, same 52 questions',f"{b['passed']}/{b['total']}",pct(b['pass_rate'])+f"; {b['errors']} invalid-output errors counted"],['Grounded single questions',f"{r['passed']}/{r['total']}",pct(r['pass_rate'])+' mechanical fact/decision checks'],['Conversation turns',f"{c['passed']}/{c['total']}",pct(c['pass_rate'])+'; 23 sequential sessions'],['Original adversarial + stateful',f"{a['passed']}/{a['total']}",f"{a['authored_single_questions']} authored questions + {a['stateful_cases']} stateful cases"],['Independent KB search recall@8','Single questions',pct(r.get('search_recall_at_8') or 0)],['Used-source evidence recall','Single / conversation',pct(r['evidence_recall'])+' / '+pct(c['evidence_recall'])]],[222,74,214])
    p('The scorer checks acceptable decisions, required factual alternatives, forbidden claims and expected tool names. Dates are canonicalized across English/Hindi forms. It does not judge every semantic entailment, language nuance or action argument, so a perfect local pass rate is not equivalent to a perfect support agent.')
    p(f"Single-turn LLM composition counts: {dict(composition)}. Conversation composition counts: {dict(conv_composition)}. Deterministic gates and abstentions need no LLM call. Saved baseline results are real API outputs; identical prompts may subsequently use cache. Invalid baseline JSON remains an error, not an edited answer.",'SmallV')
    h('What broke, and what changed')
    p('The baseline predicted Wallet refunds take 3-5 business days. REF-2 instead says instant, within 2 hours. The grounded path resolves payment methods before choosing a timeline and cites the policy rather than the generic FAQ.')
    p('Product aliases initially missed a swimsuit because of the hyphenated product name and omitted colour. Matching now distinguishes exact variants from shared-category variants, using category evidence without inventing a specific variant. Initial return dates used inclusive counting and failed two expected dates; the globally applied day-zero convention above corrected that ambiguity.')
    p('Broad hybrid search alone initially recalled 44.2% of single-question gold KB sections at eight candidates. Removing filler words and expanding intent vocabulary raised it to the figure reported above. Used-source recall is higher because deterministic policy routing separately retrieves governing sections. Conversation search recall includes many non-search authentication/greeting turns, so it is not directly comparable to standalone search quality.')
    p('Live Gnani testing exposed stream-style WAV headers with unknown 0xffffffff lengths: short clips appeared longer than the STT limit. Header finalization now preserves identical PCM samples while recording actual lengths. Invalid transcripts and incomplete PCM frames are rejected; extra privacy tests cover spoken phone-ending phrases without masking ordinary product questions.')
    p('Original tests also exposed routing bugs for unused beauty items and delivery-address changes. Added corpus-wide coverage catches these alongside proof lockout, order switching, safety, fraud, unsupported services, historical returns, festive boundaries and payment calendars. All raw generated results remain in sample_outputs/.')
    page();p('Reproducibility, voice and next steps','TitleV')
    h('Privacy and tool correctness')
    p('The initial lookup never discloses order status or existence. Caller proof is sent only to the unchanged supplied lookup function, then discarded. A maximum of two attempts is tracked per order per session, and changing orders clears verified order context without clearing its failed-attempt counter. Sanitized traces hide proof, phone, email, pincode and internal notes; the LLM never sees verification values.')
    p('Handover summaries record the issue, intent, order, checks and reason. Success wording requires created=True. No cancellation, compensation or replacement execution is fabricated: the provided tools cannot perform those actions. Their identity mechanism is an educational synthetic simulation, not secure real-world authentication.')
    h('Voice implementation and honest validation status')
    p('Gnani is the only STT/TTS provider. The REST adapter uses /stt/v3 and /api/v1/tts/inference, X-API-Key-ID authentication, explicit timbre-v2.5 and matching English/Hindi/Hinglish voices. WAV duration is checked against the 60-second REST limit. Multipart streams rewind on bounded 403/429/5xx retries, and returned audio must be a valid nonempty WAV.')
    p('The batch runner isolates malformed clips, records errors in manifest.json, and attempts a real Gnani spoken recovery. It never creates fake speech. Successful clips save redacted transcript/decision/tool JSON, text, source chunks and reply WAV. Session-named filenames preserve multi-turn calls; unrelated files remain independent.')
    p('Live speech status: '+voice['status']+'. Six genuine Gnani TTS inputs passed STT, agent and spoken-reply checks: English UPI, Hindi damage, Hinglish net banking, spoken order ID, first wrong-proof clarification and second wrong-proof refusal. All six input-understanding, semantic, privacy and nonempty-speech checks passed. Live LLM composition is enabled for answer turns; verification gates remain deterministic.')
    p('The inputs are synthetic TTS, not human recordings. Human accent/noise robustness and subjective pronunciation are still unverified. The measured pipeline uses only Gnani speech services; 41 automated engineering tests also pass. generate_voice_samples.py reproduces the live checks; --reuse-inputs reuses the same genuine input clips without inventing speech.')

    h('Run and release')
    p('Repository: https://github.com/Pranay207/ESD. One-command Windows setup: powershell -File setup.ps1. Organizer CLI: python run.py --audio_dir <in> --out_dir <out>. Run eval_step1.py, eval_step2.py --live, eval_step3.py --live, eval_adversarial.py, and python -m pytest -q from the clean .venv. requirements-lock.txt captures the tested Windows dependency set; setup.py pins the model revision.')
    p('Before submitting: keep GNANI_API_KEY only in the ignored local .env, record demo.mp4 within 120 seconds using DEMO_SCRIPT.md, and regenerate the package. Rerun generate_voice_samples.py after speech-related changes. package_submission.py excludes the dataset, secrets, environments and model caches and marks remaining blockers. The brief allows at most four report pages and two video minutes.')
    h('Limitations and useful next work')
    p('Intent routing and sentence templates may miss unseen phrasing or nuanced multi-item cases. Numeric/fact checks do not replace semantic review. Improve unstructured-query fallback and native-language review; evaluate unseen audio, packet failures and latency; strengthen identity verification only for a separately scoped production system. No rank, prize or real customer outcome is claimed.')
    p('Sources: official 14-page capstone brief; supplied dataset README, dictionary, KB and tools; official Gnani STT/TTS API docs; official multilingual MiniLM model card. Dataset and model are downloaded separately and are not redistributed in the submission.','SmallV')
    def footer(canvas,doc):
        canvas.setStrokeColor(colors.HexColor('#dce5ed'));canvas.line(42,37,553,37);canvas.setFont('Helvetica',8);canvas.setFillColor(GRAY);canvas.drawString(42,24,'VOICEOPS 2026  |  ZENTROMART  |  PRANAY207');canvas.drawRightString(553,24,str(doc.page))
    doc=SimpleDocTemplate(str(ROOT/'report.pdf'),pagesize=(595.28,841.89),leftMargin=42,rightMargin=42,topMargin=37,bottomMargin=48,title='ZentroMart VoiceOps 2026 - Technical Report',author='Pranay207')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    (ROOT/'report.md').write_text('# ZentroMart VoiceOps 2026\n\n'+'\n'.join(md),encoding='utf-8')
    print('Created report.pdf and synchronized report.md')
if __name__=='__main__':main()
