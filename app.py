"""Local Streamlit demo; text and voice use exactly the same agent."""
import json,tempfile
from pathlib import Path
import streamlit as st
from src.agent import Agent,resources
from src.config import ROOT
from src.voice import GnaniVoice,VoiceError,VoiceUnavailable

st.set_page_config(page_title='Resolvox | ZentroMart',page_icon='🎧',layout='wide')
st.markdown("""<style>.stApp{background:linear-gradient(135deg,#f5f8fd,#ffffff)}h1{letter-spacing:-1.2px}div[data-testid='stMetric']{background:#eaf1fb;border-radius:14px;padding:18px}section[data-testid='stSidebar']{background:#101f38}section[data-testid='stSidebar'] *{color:#eef4ff}</style>""",unsafe_allow_html=True)
@st.cache_resource
def shared():return resources()
r=shared()
with st.sidebar:
    st.title('Resolvox')
    st.caption('ZENTROMART · VOICEOPS 2026')
    st.write('Ask about returns, refunds, deliveries and your order.')
    live=st.toggle('Generate from retrieved policies',value=True,help='The model receives actual source text and checked facts. Invalid or timed-out output uses an evidence-checked fallback. Turn off for offline rules.')
    if st.button('New conversation',use_container_width=True):
        st.session_state.agent=Agent(r,compose=live);st.session_state.messages=[];st.session_state.voice_agent=Agent(r,compose=live)
    st.caption('Dataset date: 20 October 2026')
    st.caption('Synthetic customer records only')
if 'agent' not in st.session_state:st.session_state.agent=Agent(r,compose=live)
if 'voice_agent' not in st.session_state:st.session_state.voice_agent=Agent(r,compose=live)
if 'messages' not in st.session_state:st.session_state.messages=[]
st.session_state.agent.compose=live;st.session_state.voice_agent.compose=live
st.caption('C&A CLUB, IIT GUWAHATI × GNANI.AI')
st.title('Resolvox')
st.write('Multilingual AI voice support for ZentroMart. Policies, checked order details, and a clear next step.')
text_tab,voice_tab,eval_tab=st.tabs(['💬 Text conversation','🎙️ Voice conversation','📊 Evaluation'])
def evidence(out):
    with st.expander('Sources and actions'):
        st.write(' · '.join(out.get('retrieved_chunk_ids',[])) or 'No supporting company document found.')
        for source in out.get('sources',[]):
            st.markdown('**'+source['id']+'** — '+source.get('file',''));st.text(source['text'])
        if out.get('tool_calls'):st.json(out['tool_calls'])
        st.caption(f"Decision: {out['decision']} · {out.get('latency_ms',0):.0f} ms · {out.get('composition','')}")
with text_tab:
    st.caption('Try: “What is the refund timeline for UPI?” Verification values are hidden from history.')
    for item in st.session_state.messages:
        with st.chat_message('user'):st.write(item['transcript'])
        with st.chat_message('assistant'):st.write(item['answer']);evidence(item)
    prompt=st.chat_input('How can we help?',key='support_chat')
    if prompt:
        with st.spinner('Checking the policy…'):out=st.session_state.agent.respond(prompt)
        st.session_state.messages.append(out);st.rerun()
with voice_tab:
    st.write('Record a short message or upload a clip. Gnani listens and speaks; the support agent stays the same.')
    language=st.selectbox('Spoken language',['English / Hinglish','Hindi'])
    recording=st.audio_input('Record your message')
    uploaded=st.file_uploader('Or upload audio',type=['wav','mp3','ogg','flac','aac','m4a'])
    audio=recording or uploaded
    if st.button('Ask by voice',disabled=audio is None):
        folder=ROOT/'tmp/voice_ui';folder.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder,suffix=Path(audio.name).suffix or '.wav',delete=False) as handle:
            path=Path(handle.name);handle.write(audio.getvalue())
        reply_path=path.with_name(path.stem+'_reply.wav')
        try:
            voice=GnaniVoice()
            with st.spinner('Listening with Gnani…'):heard=voice.transcribe(path,'hi-IN' if language=='Hindi' else 'en-IN')
            with st.spinner('Checking and replying…'):out=st.session_state.voice_agent.respond(heard)
            st.caption('Transcript');st.write(out['transcript']);st.write(out['answer']);evidence(out)
            voice.synthesize(out['answer'],reply_path,out['language']);st.audio(reply_path.read_bytes(),format='audio/wav')
        except (VoiceUnavailable,VoiceError) as error:st.error(str(error))
        finally:path.unlink(missing_ok=True);reply_path.unlink(missing_ok=True)
with eval_tab:
    values=[]
    for step in [1,2,3]:
        path=ROOT/'sample_outputs'/f'eval_step{step}.json'
        if path.exists():values.append(json.loads(path.read_text(encoding='utf-8'))['summary'])
    columns=st.columns(3)
    for col,s,label in zip(columns,values,['Prompt-only baseline','Grounded questions','Conversation turns']):col.metric(label,f"{s['passed']} / {s['total']}")
    st.caption('Mechanical regression checks on supplied practice cases. These are not organizer scores or a guarantee of held-out performance.')
    path=ROOT/'sample_outputs/eval_adversarial.json'
    if path.exists():
        s=json.loads(path.read_text(encoding='utf-8'))['summary'];st.write(f"Original adversarial checks: {s['passed']} / {s['total']}")
    path=ROOT/'sample_outputs/voice_validation.json'
    if path.exists():
        value=json.loads(path.read_text(encoding='utf-8'));st.write('Live voice validation: '+value['status'])
    st.caption('Dense retrieval: '+r.retriever.dense_status)
