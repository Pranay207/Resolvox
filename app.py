"""Resolvox support console. Voice and text share one verified conversation."""
import tempfile
from pathlib import Path

import streamlit as st
from src.agent import resources
from src.multilingual import MultilingualAgent as Agent
from src.languages import LANGUAGE_NAMES, STT_CODES, normalize_language
from src.config import ROOT
from src.voice import GnaniVoice, VoiceError, VoiceUnavailable

st.set_page_config(page_title='Resolvox | ZentroMart', page_icon='🎧', layout='wide')
st.markdown("""<style>
.stApp {background:#f5f8fd;color:#14243b;color-scheme:light;}
[data-testid="stHeader"] {background:#f5f8fd;}
[data-testid="stMainBlockContainer"] {max-width:1320px;padding:2.5rem 2.5rem 3rem;}
[data-testid="stMain"] h1,[data-testid="stMain"] h2,[data-testid="stMain"] h3,
[data-testid="stMain"] label,[data-testid="stMain"] [data-testid="stMarkdownContainer"] {color:#14243b;}
[data-testid="stMain"] h1 {font-size:2.65rem;letter-spacing:-1.6px;line-height:1.1;}
[data-testid="stMain"] h3 {font-size:1.2rem;letter-spacing:-.3px;}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] * {color:#596b82!important;}
[data-testid="stSidebar"] {background:#eef3fb;border-right:1px solid #dce5f1;}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] label {color:#233b58;}
[data-testid="stSidebar"] h1 {font-size:1.65rem;letter-spacing:-.8px;}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {padding-top:1.5rem;}
.st-key-voice_workspace,.st-key-text_workspace {background:white;border-radius:22px;border:1px solid #dfe7f2;box-shadow:0 10px 35px #233b5806;}
[data-testid="stTabs"] [role="tablist"] {gap:1.4rem;border-bottom:1px solid #dbe4f0;}
[data-testid="stTabs"] [role="tab"] {color:#52647c;padding:.8rem .2rem;font-weight:600;}
[data-testid="stTabs"] [aria-selected="true"] {color:#2563eb;}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {background:#2563eb;}
[data-testid="stMetric"] {background:#fff;border:1px solid #dfe7f2;border-radius:16px;padding:1.1rem;}
[data-testid="stMetricValue"],[data-testid="stMetricLabel"] {color:#14243b;}
[data-testid="stChatMessage"] {background:#f5f8fd;border-radius:16px;}
[data-testid="stFileUploaderDropzone"] {background:#f5f8fd;border:1px dashed #b9c9df;color:#233b58;border-radius:14px;}
[data-testid="stFileUploaderDropzone"] [data-testid="stMarkdownContainer"] {color:#233b58;}
[data-baseweb="select"]>div {background:#f5f8fd;color:#14243b;border-color:#cedaeb;border-radius:12px;}
[data-baseweb="select"] input {color:#14243b;}
[data-testid="stChatInput"] {background:#f5f8fd;border-color:#cedaeb;}
[data-testid="stChatInput"] textarea {color:#14243b;}
[data-testid="stAudioInput"] {color-scheme:light;}
[data-testid="stBaseButton-primary"] {background:#2563eb;color:#fff;border-radius:12px;border-color:#2563eb;min-height:3rem;}
[data-testid="stBaseButton-primary"] [data-testid="stMarkdownContainer"] {color:#fff!important;}
[data-testid="stBaseButton-secondary"] {background:white;color:#233b58;border:1px solid #cedaeb;border-radius:12px;}
[data-testid="stBaseButton-secondary"] [data-testid="stMarkdownContainer"] {color:#233b58;}
.brand-mark {display:inline-flex;width:38px;height:38px;align-items:center;justify-content:center;background:#2563eb;color:white;border-radius:12px;font-weight:800;font-size:22px;margin-bottom:8px;}
.eyebrow {color:#2563eb;font-size:.73rem;letter-spacing:1.6px;font-weight:750;margin-bottom:.6rem;}
.hero-note {display:inline-flex;gap:9px;align-items:center;border:1px solid #dce5f1;border-radius:30px;padding:8px 14px;background:#fff;color:#52647c;font-size:.8rem;margin-top:1rem;}
.topic-row {display:flex;gap:10px;flex-wrap:wrap;margin:.75rem 0 1.5rem;}
.topic {background:#eaf1fc;border:1px solid #dce7f9;border-radius:9px;color:#345783;padding:7px 12px;font-size:.8rem;}
.empty-reply {display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:290px;text-align:center;padding:1.7rem;background:#f7faff;border:1px dashed #d5e0ef;border-radius:18px;margin-top:10px;}
.empty-reply strong {color:#233b58;font-size:1.05rem;margin-top:18px;}
.empty-reply p {color:#667890!important;font-size:.9rem;max-width:280px;margin-top:8px;}
.wave {height:48px;display:flex;align-items:center;gap:5px;}
.wave i {display:block;width:6px;border-radius:8px;background:#729bf0;}
.step-guide {font-size:.8rem;color:#667890;line-height:1.7;margin-bottom:1rem;}
@media(max-width:800px) {[data-testid="stMainBlockContainer"] {padding:1.5rem 1rem;}[data-testid="stMain"] h1 {font-size:2rem;}.empty-reply {min-height:170px;}}
</style>""", unsafe_allow_html=True)

@st.cache_resource
def shared():
    return resources()

r = shared()
if st.session_state.get('ui_version') != 'support-console-v4':
    st.session_state.ui_version = 'support-console-v4'
    st.session_state.agent = Agent(r)
    st.session_state.messages = []
    st.session_state.voice_epoch = 0
    st.session_state.voice_error = None
    st.session_state.pop('voice_agent', None)

def reset_conversation():
    st.session_state.agent = Agent(r, compose=st.session_state.get('compose_live', True))
    st.session_state.messages = []
    st.session_state.voice_error = None
    st.session_state.voice_epoch += 1
    for key in list(st.session_state):
        if key.startswith(('voice_recording_', 'voice_upload_')):
            del st.session_state[key]

with st.sidebar:
    st.markdown('<div class="brand-mark">R</div>', unsafe_allow_html=True)
    st.title('Resolvox')
    st.caption('VOICE SUPPORT FOR ZENTROMART')
    st.write('A clear next step, in your language.')
    st.button('＋ New conversation', use_container_width=True, on_click=reset_conversation)
    st.divider()
    st.markdown('**How it works**')
    st.caption('1. Record or type your question.\n\n2. We check the relevant information.\n\n3. Read or listen to the reply.')
    st.caption('Voice and text share the same conversation.')
    with st.expander('Demo settings'):
        live = st.toggle('Generate from retrieved policies', value=True, key='compose_live',
                         help='Generate from retrieved source text. Invalid output is repaired once, then answered with uncertainty. Turn off to inspect document excerpts without generation.')
        st.caption('Synthetic order records · 20 October 2026')
        st.caption('Primary speech: English, Hindi and Hinglish')
        regional_preview = st.toggle('Preview additional languages', value=False, key='regional_preview', help='Experimental regional translation. Per-language results are shown in Evaluation details.')
    st.link_button('Project & documentation ↗', 'https://github.com/Pranay207/Resolvox', use_container_width=True)

st.session_state.agent.compose = live
head, badge = st.columns([3, 1])
with head:
    st.markdown('<div class="eyebrow">MULTILINGUAL AI CUSTOMER SUPPORT</div>', unsafe_allow_html=True)
    st.title('Resolvox')
    st.write('Speak naturally. Get help with your ZentroMart order.')
with badge:
    badge_text = '10 languages + Hinglish · preview' if regional_preview else 'English · हिन्दी · Hinglish'
    st.markdown(f'<div class="hero-note">{badge_text}</div>', unsafe_allow_html=True)
st.markdown('<div class="topic-row"><span class="topic">Returns & refunds</span><span class="topic">Orders & delivery</span><span class="topic">Product support</span></div>', unsafe_allow_html=True)
voice_tab, text_tab = st.tabs(['Voice support', 'Text support'])

def evidence(out):
    with st.expander('Sources and actions'):
        ids = out.get('retrieved_chunk_ids', [])
        st.write(' · '.join(ids) or 'No supporting company information found.')
        for source in out.get('sources', []):
            st.markdown('**' + source['id'] + '** — ' + source.get('file', ''))
            st.text(source['text'])
        if out.get('tool_calls'):
            st.json(out['tool_calls'])
        st.caption(f"Decision: {out['decision']} · {out.get('latency_ms', 0):.0f} ms · {out.get('composition', '')}")

def speak_reply(entry, voice=None):
    folder = ROOT / 'tmp/voice_ui'
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=folder, suffix='.wav', delete=False) as handle:
        reply_path = Path(handle.name)
    try:
        (voice or GnaniVoice()).synthesize(entry['output']['answer'], reply_path, entry['output']['language'])
        entry['audio'] = reply_path.read_bytes()
        entry['audio_error'] = None
    finally:
        reply_path.unlink(missing_ok=True)

def render_conversation(channel):
    messages = st.session_state.messages
    if not messages:
        st.markdown('<div class="empty-reply"><div class="wave" aria-hidden="true"><i style="height:14px"></i><i style="height:28px"></i><i style="height:44px"></i><i style="height:32px"></i><i style="height:20px"></i></div><strong>Your conversation starts here</strong><p>Your transcript, answer and voice reply will appear here.</p></div>', unsafe_allow_html=True)
        return
    for i, entry in enumerate(messages):
        out = entry['output']
        with st.chat_message('user'):
            st.write(out['transcript'])  # Only the agent's redacted transcript.
        with st.chat_message('assistant'):
            st.write(out['answer'])
            if entry.get('audio'):
                st.audio(entry['audio'], format='audio/wav')
            if entry.get('audio_error'):
                st.warning('Your text answer is saved. Voice playback is unavailable; you can continue in text or retry the audio.')
                if st.button('Retry reply audio', key=f'{channel}_retry_audio_{i}'):
                    try:
                        with st.spinner('Preparing reply audio…'):
                            speak_reply(entry)
                    except (VoiceError, VoiceUnavailable, OSError) as exc:
                        entry['audio_error'] = str(exc)
                    st.rerun()
            evidence(out)

VOICE_LANGUAGES = {'English / Hinglish': 'en', **{name: code for code, name in LANGUAGE_NAMES.items() if code not in {'en', 'hi-en'}}}

def respond_in_language(text, selected=None):
    if selected is None:
        return st.session_state.agent.respond(text)
    return st.session_state.agent.respond(text, language_hint=selected)

def process_voice(audio, spoken_language):
    folder = ROOT / 'tmp/voice_ui'
    folder.mkdir(parents=True, exist_ok=True)
    suffix = Path(audio.name).suffix.lower()
    if suffix not in {'.wav', '.mp3', '.ogg', '.flac', '.aac', '.m4a'}:
        suffix = '.wav'
    with tempfile.NamedTemporaryFile(dir=folder, suffix=suffix, delete=False) as handle:
        path = Path(handle.name)
        handle.write(audio.getvalue())
    entry = None
    st.session_state.voice_error = None
    try:
        with st.status('Listening to your message…', expanded=True) as progress:
            voice = GnaniVoice()
            st.write('1 / 3 · Listening with Gnani')
            selected = VOICE_LANGUAGES[spoken_language]
            heard = voice.transcribe(path, STT_CODES[selected])
            progress.update(label='Checking your question…')
            st.write('2 / 3 · Checking information and conversation context')
            out = respond_in_language(heard, None if spoken_language == 'English / Hinglish' else selected)
            entry = {'output': out, 'audio': None, 'audio_error': None}
            st.session_state.messages.append(entry)
            progress.update(label='Preparing your voice reply…')
            st.write('3 / 3 · Preparing reply audio')
            speak_reply(entry, voice)
            progress.update(label='Reply ready', state='complete', expanded=False)
    except (VoiceUnavailable, VoiceError, OSError) as exc:
        if entry is not None:
            entry['audio_error'] = str(exc)
        else:
            st.session_state.voice_error = str(exc)
    finally:
        path.unlink(missing_ok=True)
        st.session_state.voice_epoch += 1

with voice_tab:
    with st.container(border=True, key='voice_workspace'):
        controls, conversation = st.columns([1, 1.15], gap='large')
        with controls:
            st.subheader('Speak with Resolvox')
            st.caption('Record a question or send an audio clip. You can switch to text at any time.')
            spoken_language = st.selectbox('Spoken language', list(VOICE_LANGUAGES) if regional_preview else ['English / Hinglish', 'Hindi'], key='spoken_language')
            audio_source = st.radio('Audio source', ['Record', 'Upload'], horizontal=True, key='audio_source')
            epoch = st.session_state.voice_epoch
            if audio_source == 'Record':
                audio = st.audio_input('Record your question', key=f'voice_recording_{epoch}')
            else:
                audio = st.file_uploader('Choose an audio clip', type=['wav', 'mp3', 'ogg', 'flac', 'aac', 'm4a'], key=f'voice_upload_{epoch}')
            st.caption('Up to 60 seconds · WAV, MP3, OGG, FLAC, AAC or M4A')
            send_voice = st.button('Send voice message', type='primary', use_container_width=True, disabled=audio is None)
            st.markdown('<div class="step-guide">Listen → Check → Reply<br>Try: “When will my UPI refund arrive?”</div>', unsafe_allow_html=True)
            if st.session_state.voice_error:
                st.error('We could not process that recording. Try a clear, short clip or continue in Text support.')
                st.caption(st.session_state.voice_error)
            if send_voice:
                process_voice(audio, spoken_language)
                st.rerun()
        with conversation:
            st.subheader('Your conversation')
            st.caption('Transcripts hide verification details. Private order information requires verification.')
            render_conversation('voice')

with text_tab:
    with st.container(border=True, key='text_workspace'):
        st.subheader('Continue by text')
        st.caption('The same conversation and verified order context carry across voice and text.')
        text_choices = LANGUAGE_NAMES.values() if regional_preview else [LANGUAGE_NAMES[c] for c in ['en', 'hi', 'hi-en']]
        text_language = st.selectbox('Question language', ['Auto-detect', *text_choices], key='text_language')
        render_conversation('text')
        examples = [('Refund timing', 'How long does a UPI refund take?'),
                    ('Return policy', 'What is the return window for electronics?'),
                    ('Track an order', 'Where is my order?')]
        example_prompt = None
        for col, (label, question) in zip(st.columns(3), examples):
            if col.button(label, use_container_width=True):
                example_prompt = question
        prompt = st.chat_input('Type your question…', key='support_chat') or example_prompt
        if prompt:
            with st.spinner('Checking your question…'):
                selected = None if text_language == 'Auto-detect' else normalize_language(text_language)
                out = respond_in_language(prompt, selected)
            st.session_state.messages.append({'output': out, 'audio': None, 'audio_error': None})
            st.rerun()
