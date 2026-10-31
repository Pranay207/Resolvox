"""Resolvox support console. Voice and text share one verified conversation."""
import base64
import tempfile
from pathlib import Path
from datetime import date

import streamlit as st
from src.agent import resources
from src.multilingual import MultilingualAgent as Agent
from src.languages import LANGUAGE_NAMES, STT_CODES, normalize_language
from src.config import ROOT
from src.voice import GnaniVoice, VoiceError, VoiceUnavailable

# Inline SVG keeps the sidebar mark and favicon portable in the submission.
LOGO_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64" role="img" aria-label="Resolvox voice support">\n  <title>Resolvox voice support</title>\n  <path fill="#2563eb" d="M16 5h32c7.18 0 13 5.82 13 13v24c0 7.18-5.82 13-13 13H24l-14 7v-9.2C5.85 50.6 3 46.2 3 41.3V18C3 10.82 8.82 5 16 5Z"/>\n  <path fill="#ffffff" fill-rule="evenodd" d="M16 18h11.2C34 18 38 21.2 38 26.7c0 4-2 6.7-5.7 8L39 45h-7l-5.5-9.4H22V45h-6V18Zm6 5.3v7.1h4.8c3.4 0 5.2-1.3 5.2-3.6 0-2.2-1.8-3.5-5.2-3.5H22Z"/>\n  <g fill="#ffffff">\n    <rect x="42" y="27" width="3" height="9" rx="1.5"/>\n    <rect x="48" y="23" width="3" height="17" rx="1.5"/>\n    <rect x="54" y="28" width="3" height="7" rx="1.5"/>\n  </g>\n</svg>'
LOGO_DATA_URI = 'data:image/svg+xml;base64,' + base64.b64encode(LOGO_SVG.encode('utf-8')).decode('ascii')

st.set_page_config(page_title='Resolvox | ZentroMart', page_icon=LOGO_SVG, layout='wide')
st.markdown("""<style>
.stApp {background:#f5f8fd;color:#14243b;color-scheme:light;}
[data-testid="stHeader"] {background:#f5f8fd;height:1.5rem;min-height:1.5rem;}
[data-testid="stMainBlockContainer"] {max-width:1280px;padding:1.25rem 1.75rem 1.5rem;}
[data-testid="stMain"] h1,[data-testid="stMain"] h2,[data-testid="stMain"] h3,
[data-testid="stMain"] label,[data-testid="stMain"] [data-testid="stMarkdownContainer"] {color:#14243b;}
[data-testid="stMain"] h1 {font-size:1.65rem;letter-spacing:-.5px;line-height:1.2;padding:0 0 .25rem;margin:0;}
[data-testid="stMain"] h3 {font-size:1.1rem;letter-spacing:-.25px;padding:.1rem 0 .35rem;}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] * {color:#596b82!important;}
[data-testid="stSidebar"] {background:#eef3fb;border-right:1px solid #dce5f1;}
[data-testid="stSidebar"][aria-expanded="true"] {width:15rem!important;min-width:15rem!important;max-width:15rem!important;}
[data-testid="stSidebarUserContent"] {padding:2rem .9rem 1rem!important;}
[data-testid="stSidebarHeader"] {position:absolute;top:0;right:.25rem;width:2rem;height:2rem;min-height:2rem;padding:0!important;box-sizing:border-box;z-index:2;}
[data-testid="stSidebar"] button p,[data-testid="stSidebar"] a p {font-size:.875rem!important;white-space:nowrap;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {font-size:.8rem;color:#52647c!important;line-height:1.45;}
[data-testid="stSidebar"] hr {margin:1rem 0;}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] label {color:#233b58;}
[data-testid="stSidebar"] label p {font-size:.82rem;line-height:1.4;}
[data-testid="stSidebar"] h1 {font-size:1.65rem;letter-spacing:-.8px;}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {padding:0!important;}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {gap:.75rem;}
.st-key-support_conversation {background:white;border-radius:18px;border:1px solid #dfe7f2;box-shadow:0 10px 35px #233b5806;}
.st-key-support_conversation [data-testid="stVerticalBlock"] {gap:.65rem;}
[data-testid="stChatMessage"] {background:#f5f8fd;border-radius:16px;}
[data-testid="stFileUploaderDropzone"] {background:#f5f8fd;border:1px dashed #b9c9df;color:#233b58;border-radius:14px;}
[data-testid="stFileUploaderDropzone"] [data-testid="stMarkdownContainer"] {color:#233b58;}
[data-baseweb="select"]>div {background:#f5f8fd;color:#14243b;border-color:#cedaeb;border-radius:12px;}
[data-baseweb="select"] input {color:#14243b;}
[data-testid="stChatInput"] {background:#f5f8fd;border-color:#cedaeb;}
[data-testid="stChatInput"] textarea {color:#14243b;}
[data-testid="stAudioInput"] {color-scheme:light;}
[data-testid="stAudioInput"] button {min-width:44px;min-height:44px;}
[data-testid="stChatMessage"] {min-width:0;}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {overflow-wrap:anywhere;}
[data-testid="stExpander"] pre {max-width:100%;overflow-x:auto;}
[data-testid="stBaseButton-primary"] {background:#2563eb;color:#fff;border-radius:12px;border-color:#2563eb;min-height:2.6rem;}
[data-testid="stBaseButton-primary"] [data-testid="stMarkdownContainer"] {color:#fff!important;}
[data-testid="stBaseButton-primary"]:disabled {background:#edf2f8!important;border-color:#d4deeb!important;color:#64758c!important;}
[data-testid="stBaseButton-primary"]:disabled [data-testid="stMarkdownContainer"],[data-testid="stBaseButton-primary"]:disabled p {color:#64758c!important;}
[data-testid="stBaseButton-secondary"] {background:white;color:#233b58;border:1px solid #cedaeb;border-radius:12px;}
[data-testid="stBaseButton-secondary"] [data-testid="stMarkdownContainer"] {color:#233b58;}
.brand-mark {display:inline-flex;flex:none;width:44px;height:44px;align-items:center;justify-content:center;}
.brand-mark img {display:block;width:100%;height:100%;}
.brand-lockup {display:flex;align-items:center;gap:10px;margin:0 0 .65rem;}
.brand-lockup strong {display:block;font-size:1.85rem;font-weight:800;letter-spacing:-.65px;color:#14243b;line-height:1.15;}
.brand-lockup small {display:block;font-size:.6rem;letter-spacing:1px;color:#52647c;margin-top:4px;}
.empty-reply {display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:180px;text-align:center;padding:1rem;background:#f7faff;border:1px dashed #d5e0ef;border-radius:18px;margin-top:10px;}
.empty-reply strong {color:#233b58;font-size:1rem;margin-top:10px;}
.empty-reply p {color:#52647c!important;font-size:.85rem;max-width:300px;margin:6px 0 0;}
.wave {height:48px;display:flex;align-items:center;gap:5px;}
.wave i {display:block;width:6px;border-radius:8px;background:#729bf0;}
.step-guide {font-size:.8rem;color:#667890;line-height:1.7;margin-bottom:.5rem;}
@media(max-width:1100px) {[data-testid="stMainBlockContainer"] {padding:1.25rem 1.25rem 1.5rem;}}
.stApp:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stHeader"] {height:2.5rem;min-height:2.5rem;}
.stApp:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stMainBlockContainer"] {padding-top:2.75rem;}
@media(max-width:800px) {
[data-testid="stMainBlockContainer"] {padding:3.25rem .85rem 1.25rem!important;}
[data-testid="stHeader"] {height:3rem!important;min-height:3rem!important;}
[data-testid="stMain"] h1 {font-size:1.5rem;}
[data-testid="stHeader"] button,[data-testid="stSidebarHeader"] button {min-width:44px;min-height:44px;}
[data-testid="stSidebarHeader"] {width:44px;height:44px;min-height:44px;}
[data-testid="stSidebarUserContent"] {padding-top:3rem!important;}
[data-testid="stMain"] [data-testid^="stBaseButton"],
[data-testid="stSidebarUserContent"] [data-testid^="stBaseButton"],
[data-testid="stSidebarUserContent"] a {min-height:44px;}
[data-baseweb="select"]>div {min-height:44px;}
[role="radiogroup"] label,[data-testid="stSidebarUserContent"] label:has(input[type="checkbox"]) {min-height:44px;align-items:center;}
[data-testid="stSidebar"] summary {min-height:44px;}
[data-testid="stChatInput"],[data-testid="stChatInput"] textarea {min-height:44px;}
[data-testid="stChatInput"] textarea {font-size:16px;}
[data-testid="stChatInput"] button {min-width:44px;min-height:44px;}
.empty-reply {min-height:140px;}
}
@media(max-height:760px) and (min-width:801px) {.empty-reply {min-height:150px;}}

.support-intro {color:#596b82;font-size:.9rem;margin:0 0 .25rem;}
.st-key-case_column {min-width:0;}
.st-key-case_column [data-testid="stMarkdownContainer"] {overflow-wrap:anywhere;}
.st-key-next_step {background:#eef4ff;border:1px solid #d9e5fa;border-radius:16px;}
.st-key-next_step h3 {font-size:1rem!important;}
.case-label {font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#596b82;margin:0 0 7px;}
.case-status {display:inline-block;font-size:.78rem;font-weight:600;padding:5px 9px;border-radius:8px;background:#eaf0f8;color:#425975;margin-bottom:5px;}
.case-status.verified {background:#e8f5ef;color:#246447;}
.case-status.ticket {background:#eaf0ff;color:#294eb0;}
.case-value {font-size:.9rem;overflow-wrap:anywhere;margin:0 0 12px;}
.st-key-support_conversation [data-testid="stLayoutWrapper"]:has(> .st-key-conversation_history) {height:clamp(200px,calc(100dvh - 450px),320px)!important;flex:none!important;min-height:0!important;}
.st-key-conversation_history {height:100%!important;overflow-y:auto;overscroll-behavior:contain;}
.st-key-conversation_history .empty-reply {min-height:180px;margin-top:0;border:0;background:transparent;}
.st-key-input_mode [role="radiogroup"] {display:flex;flex-wrap:nowrap;gap:3px;width:fit-content;background:#eef3fb;border:1px solid #dce5f1;border-radius:12px;padding:3px;}
.st-key-input_mode [role="radiogroup"] label {padding:7px 12px;margin:0!important;min-height:38px;box-sizing:border-box;border-radius:9px;}
.st-key-input_mode [role="radiogroup"] label > div:first-child {display:none;}
.st-key-input_mode [role="radiogroup"] label:has(input:checked) {background:#fff;box-shadow:0 1px 4px #14243b16;}
.st-key-input_mode [role="radiogroup"] label p {font-size:.875rem!important;font-weight:600;}
.st-key-composer_toolbar {align-items:center;}
.st-key-composer_toolbar [data-testid="stElementContainer"] {min-width:0;}
.st-key-conversation_language {max-width:230px;}
.st-key-conversation_language [data-baseweb="select"] * {font-size:.82rem!important;}
.st-key-upload_audio {margin:0;}
.st-key-quick_questions button {font-size:.8rem;min-height:36px;}
@media(max-width:800px) {
.st-key-support_layout > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {flex-direction:column;gap:.8rem;}
.st-key-support_layout > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {width:100%!important;flex:1 1 auto!important;min-width:0!important;}
.st-key-case_column [data-testid="stVerticalBlock"] {gap:.45rem;}
.st-key-next_step {padding:0!important;}
.st-key-next_step [data-testid="stVerticalBlock"] {gap:.2rem;}
.st-key-support_conversation [data-testid="stLayoutWrapper"]:has(> .st-key-conversation_history) {height:180px!important;}
.st-key-conversation_history .empty-reply {min-height:120px;padding:.65rem;}
.st-key-input_mode [role="radiogroup"] label {min-height:44px;padding:9px 12px;}
.st-key-conversation_language {max-width:100%;}
.st-key-support_layout summary {min-height:44px;}
.st-key-quick_questions [data-testid="stHorizontalBlock"] {flex-wrap:wrap;gap:.4rem;}
}

/* Let the primary recording action stay in view, including short screens. */
.st-key-support_conversation > [data-testid="stLayoutWrapper"]:has(> .st-key-input_composer) {position:sticky;bottom:.5rem;z-index:3;background:#fff;border-radius:12px;}
.st-key-compact_case {max-width:100%;}
.st-key-support_conversation [data-testid="stLayoutWrapper"]:has(> .st-key-conversation_history) {height:clamp(90px,calc(100dvh - 580px),260px)!important;}
@media(max-height:760px) {
.st-key-conversation_history .empty-reply {min-height:70px;padding:.35rem;}
.st-key-conversation_history .wave {height:28px;}
.st-key-conversation_history .wave i {max-height:28px;}
.st-key-conversation_history .empty-reply p {font-size:.8rem;margin:3px 0 0;}
}
@media(max-width:800px) {
.st-key-support_conversation [data-testid="stLayoutWrapper"]:has(> .st-key-conversation_history) {height:clamp(72px,calc(100dvh - 620px),160px)!important;}
.st-key-support_layout:has(.st-key-case_column) .st-key-support_conversation [data-testid="stLayoutWrapper"]:has(> .st-key-conversation_history) {height:clamp(56px,calc(100dvh - 720px),100px)!important;}
.st-key-next_step [data-testid="stCaptionContainer"] {display:none;}
.st-key-next_step h3 {font-size:.85rem!important;}
.st-key-next_step p {font-size:.85rem;}
.st-key-conversation_history .empty-reply {min-height:64px;padding:.25rem;}
.st-key-conversation_history .empty-reply .wave {display:none;}
}
@media(max-width:800px) and (max-height:700px) {
.st-key-support_conversation [data-testid="stLayoutWrapper"]:has(> .st-key-conversation_history):has(.empty-reply) {display:none;}
.st-key-next_step h3 {display:none;}
}
</style>""", unsafe_allow_html=True)

@st.cache_resource
def shared():
    return resources()

r = shared()
if 'agent' not in st.session_state or 'messages' not in st.session_state:
    st.session_state.ui_version = 'support-console-v5'
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
    st.markdown(f'<div class="brand-lockup"><span class="brand-mark"><img src="{LOGO_DATA_URI}" alt="Resolvox voice support" width="44" height="44"></span><div><strong>Resolvox</strong><small>ZENTROMART SUPPORT</small></div></div>', unsafe_allow_html=True)
    st.button('New conversation', icon=':material/add:', use_container_width=True, on_click=reset_conversation)
    st.divider()
    with st.expander('Advanced options', expanded=True):
        live = st.toggle('AI policy answers', value=True, key='compose_live',
                         help='Generate from retrieved source text. Invalid output is repaired once, then answered with uncertainty. Turn off to inspect document excerpts without generation.')
        regional_preview = st.toggle('Extra languages', value=False, key='regional_preview', help='Experimental regional translation. Primary tested languages: English, Hindi and Hinglish.')
    st.link_button('Project documentation ↗', 'https://github.com/Pranay207/Resolvox', use_container_width=True)

st.session_state.agent.compose = live
st.title('How can we help?')
st.markdown('<p class="support-intro">ZentroMart customer support</p>', unsafe_allow_html=True)

def customer_policy_sources(out):
    """Select customer-facing references without altering saved agent evidence."""
    if out.get('decision') == 'clarify' or out.get('intent') in {'greeting', 'verification', 'repeat', 'unclear_audio'}:
        return []
    used_ids = set(out.get('retrieved_chunk_ids', []))
    return [source for source in out.get('sources', [])
            if source.get('id') in used_ids
            and source.get('doc_type') in {'policy', 'help', 'faq'}]


def evidence(out):
    sources = customer_policy_sources(out)
    if not sources:
        return
    with st.expander('View supporting policy'):
        for source in sources:
            st.markdown('**' + source.get('title', 'Supporting policy') + '**')
            text = source.get('text', '')
            body = text.partition('\n')[2] if text.startswith('## [') else text
            st.markdown(body)


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
        st.markdown('<div class="empty-reply"><div class="wave" aria-hidden="true"><i style="height:14px"></i><i style="height:28px"></i><i style="height:44px"></i><i style="height:32px"></i><i style="height:20px"></i></div><strong>Let’s sort it out.</strong><p>Record a message or type your question. Your replies and supporting policies stay here.</p></div>', unsafe_allow_html=True)
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
            st.write('Listening to your recorded message')
            selected = VOICE_LANGUAGES[spoken_language]
            heard = voice.transcribe(path, STT_CODES[selected])
            progress.update(label='Checking your question…')
            st.write('Checking your question against ZentroMart information')
            out = respond_in_language(heard, None if spoken_language == 'English / Hinglish' else selected)
            entry = {'output': out, 'audio': None, 'audio_error': None}
            st.session_state.messages.append(entry)
            progress.update(label='Preparing your voice reply…')
            st.write('Preparing your spoken reply')
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


def case_snapshot(agent, messages):
    """Build presentation state from confirmed tool activity, never model claims."""
    state = agent.state
    current_id = state.order_id
    calls = [call for entry in messages for call in entry['output'].get('tool_calls', [])]
    verified_call = any(
        call.get('name') == 'lookup_order'
        and call.get('arguments', {}).get('order_id') == current_id
        and call.get('result', {}).get('verified') is True
        for call in calls
    )
    verified = bool(current_id and state.order and verified_call
                    and str(state.order.get('order_id', '')) == str(current_id))
    order = state.order if verified else {}
    # Only a small allowlist reaches the case panel; proofs/contact fields never do.
    details = {key: order[key] for key in ('order_id', 'status', 'promised_date', 'payment_method') if order.get(key)}
    items = [{'sku': item.get('sku', ''), 'qty': item.get('qty', '')}
             for item in order.get('items', [])] if verified else []
    confirmed_tickets = [call.get('result', {}) for call in calls
                         if call.get('name') == 'create_ticket'
                         and call.get('arguments', {}).get('order_id') == current_id
                         and call.get('result', {}).get('created') is True
                         and call.get('result', {}).get('ticket_id')]
    ticket = confirmed_tickets[-1].get('ticket_id') if confirmed_tickets else None
    last = messages[-1]['output'] if messages else {}
    decision = last.get('decision')
    if not last:
        next_title = 'Tell us what happened'
        next_detail = 'Tell us about an order, return, refund or product.'
    elif decision == 'escalate' and ticket:
        next_title = 'Keep your ticket reference'
        next_detail = 'A human colleague will follow up. The conversation below records what was checked.'
    elif decision == 'escalate':
        next_title = 'Follow the support guidance'
        next_detail = 'No handover ticket is confirmed. Check the latest reply for how to continue.'
    elif decision == 'clarify':
        next_title = 'Answer the question below'
        next_detail = 'Share only the detail requested in the latest reply.'
    else:
        next_title = 'Review your support guidance'
        next_detail = 'Your latest reply explains the available next step. You can ask a follow-up here.'
    return {'verified': verified, 'order_linked': bool(current_id), 'show_next_step': bool(last and decision in {'clarify', 'escalate'}), 'details': details,
            'items': items, 'ticket_id': ticket, 'next_title': next_title, 'next_detail': next_detail}


def render_case(snapshot):
    with st.expander('Your case', expanded=snapshot['verified']):
        if snapshot['verified']:
            st.markdown('<span class="case-status verified">Order verified</span>', unsafe_allow_html=True)
            details = snapshot['details']
            st.write('**Order** · ' + str(details['order_id']))
            if details.get('status'):
                st.write('**Order status** · ' + str(details['status']).replace('_', ' ').capitalize())
            if details.get('promised_date'):
                try:
                    promised = date.fromisoformat(str(details['promised_date'])).strftime('%d %B %Y').lstrip('0')
                except ValueError:
                    promised = str(details['promised_date'])
                st.write('**Promised delivery** · ' + promised)
            if details.get('payment_method'):
                st.write('**Payment** · ' + str(details['payment_method']).replace('_', ' ').upper())
            if snapshot['items']:
                with st.expander('Order items', expanded=False):
                    for item in snapshot['items']:
                        product = r.data.products.get(item['sku'], {})
                        st.caption(str(product.get('title') or item['sku']) + ' · Qty ' + str(item['qty']))
        elif snapshot['order_linked']:
            st.write('Verification needed')
            st.caption('Order details stay hidden until the requested verification succeeds.')
        else:
            st.write('No order linked yet')
            st.caption('You can ask a general policy question without an order ID.')
        if snapshot['ticket_id']:
            st.markdown('<span class="case-status ticket">Ticket created</span>', unsafe_allow_html=True)
            st.write('**Reference** · ' + str(snapshot['ticket_id']))
    if snapshot['show_next_step']:
        with st.container(border=True, key='next_step'):
            st.subheader('Your next step')
            st.write('**' + snapshot['next_title'] + '**')
            st.caption(snapshot['next_detail'])


snapshot = case_snapshot(st.session_state.agent, st.session_state.messages)
has_case_context = snapshot['order_linked'] or snapshot['ticket_id'] or snapshot['show_next_step']
with st.container(key='support_layout'):
    if has_case_context:
        case_column, conversation_column = st.columns([.9, 2.1], gap='medium')
        with case_column:
            with st.container(key='case_column'):
                render_case(snapshot)
    else:
        with st.container(key='compact_case', width=280):
            render_case(snapshot)
        conversation_column = st.container()
    with conversation_column:
        with st.container(border=True, key='support_conversation'):
            st.subheader('Your conversation')
            with st.container(height=260, border=False, key='conversation_history'):
                render_conversation('support')
            with st.container(key='input_composer'):
                with st.container(horizontal=True, vertical_alignment='center', gap='small', key='composer_toolbar'):
                    mode = st.radio('Message input', ['Speak', 'Type'], horizontal=True,
                                    key='input_mode', label_visibility='collapsed')
                    language_choices = list(VOICE_LANGUAGES) if regional_preview else ['English / Hinglish', 'Hindi']
                    if st.session_state.get('conversation_language') not in language_choices:
                        st.session_state.conversation_language = language_choices[0]
                    spoken_language = st.selectbox('Language', language_choices, key='conversation_language',
                        help='English / Hinglish follows the language of your message. Choose Hindi or a preview language explicitly.', label_visibility='collapsed', width=160)
                if mode == 'Speak':
                    epoch = st.session_state.voice_epoch
                    audio = st.audio_input('Record a message', key=f'voice_recording_{epoch}')
                    send_action = st.container(key='send_voice_action')
                else:
                    example_prompt = None
                    if not st.session_state.messages:
                        with st.container(horizontal=True, gap='small', key='quick_questions'):
                            for label, question in [('Track an order', 'Where is my order?'),
                                                    ('Refund timing', 'How long does a UPI refund take?')]:
                                if st.button(label):
                                    example_prompt = question
                    prompt = st.chat_input('Type your question…', key='support_chat') or example_prompt
                    if prompt:
                        with st.spinner('Checking your question…'):
                            selected = None if spoken_language == 'English / Hinglish' else VOICE_LANGUAGES[spoken_language]
                            out = respond_in_language(prompt, selected)
                        st.session_state.messages.append({'output': out, 'audio': None, 'audio_error': None})
                        st.rerun()
            if mode == 'Speak':
                with st.expander('Upload an audio clip', expanded=False):
                    uploaded = st.file_uploader('Choose an audio clip', type=['wav', 'mp3', 'ogg', 'flac', 'aac', 'm4a'], key=f'voice_upload_{epoch}')
                selected_audio = uploaded if uploaded is not None else audio
                if uploaded is not None and audio is not None:
                    st.caption('The uploaded clip will be sent instead of the recording.')
                st.caption('Up to 60 seconds per message · Uploads up to 20 MB')
                if st.session_state.voice_error:
                    st.error('We could not process that recording. Try a clear, short clip or switch to Type.')
                with send_action:
                    send_voice = st.button('Send voice message', type='primary', use_container_width=True, disabled=selected_audio is None)
                if send_voice:
                    process_voice(selected_audio, spoken_language)
                    st.rerun()
