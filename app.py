import os, io, json, time, random, requests, logging, hmac, hashlib, atexit, threading
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import Flask, request, abort
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()
app = Flask(__name__)

# ========== المتغيرات البيئية ==========
VERIFY_TOKEN = os.getenv('FACEBOOK_VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
APP_SECRET = os.getenv('FACEBOOK_APP_SECRET', '').strip()
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
ELEVENLABS_VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')

# 🔑 مفاتيح Claude (مفصولة بفاصلة)
RAW_CLAUDE_KEYS = os.getenv('CLAUDE_API_KEYS', '')
CLAUDE_API_KEYS = [k.strip() for k in RAW_CLAUDE_KEYS.split(',') if k.strip()]

# 🔄 توزيع ذكي للمفاتيح (Thread-Safe Round-Robin)
claude_key_index = 0
claude_lock = threading.Lock()
def get_next_claude_key():
    global claude_key_index
    with claude_lock:
        if not CLAUDE_API_KEYS: return None
        key = CLAUDE_API_KEYS[claude_key_index % len(CLAUDE_API_KEYS)]
        claude_key_index += 1
        return key

CONAN_LINK = "https://exe.io/vLPHW2I"
POLICY_NOTE = "⚠️ ملاحظة: نحن لا ننشر حلقات كاملة، بل أجزاء مُقسَّمة من حلقات المحقق كونان فقط."
PAGE_URL = "https://www.facebook.com/mounirdjouid"

# 🖼️ مكتبة صور متنوعة
CONAN_IMAGES = [
    "https://upload.wikimedia.org/wikipedia/en/6/6e/Detective_Conan_logo.png",
    "https://upload.wikimedia.org/wikipedia/en/thumb/2/23/Conan_Edogawa_profile.jpg/440px-Conan_Edogawa_profile.jpg",
    "https://upload.wikimedia.org/wikipedia/en/thumb/8/8d/Case_Closed_volume_1_cover.jpg/440px-Case_Closed_volume_1_cover.jpg",
    "https://upload.wikimedia.org/wikipedia/en/thumb/4/4c/Detective_Conan_The_Movie.png/440px-Detective_Conan_The_Movie.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/Detective_Conan_anime_logo.svg/1200px-Detective_Conan_anime_logo.svg.png",
    "https://upload.wikimedia.org/wikipedia/en/thumb/5/5a/Case_Closed_vol_1.jpg/440px-Case_Closed_vol_1.jpg",
    "https://upload.wikimedia.org/wikipedia/en/thumb/2/24/Detective_Conan_manga_volume_1.jpg/440px-Detective_Conan_manga_volume_1.jpg",
    "https://upload.wikimedia.org/wikipedia/en/thumb/9/9f/Case_Closed_vol_76.jpg/440px-Case_Closed_vol_76.jpg",
    "https://upload.wikimedia.org/wikipedia/en/thumb/7/72/Case_Closed_vol_90.jpg/440px-Case_Closed_vol_90.jpg",
    "https://upload.wikimedia.org/wikipedia/en/thumb/0/0e/Case_Closed_vol_100.jpg/440px-Case_Closed_vol_100.jpg",
    "https://upload.wikimedia.org/wikipedia/en/thumb/3/3e/Case_Closed_vol_50.jpg/440px-Case_Closed_vol_50.jpg",
    "https://upload.wikimedia.org/wikipedia/en/thumb/1/1a/Case_Closed_vol_25.jpg/440px-Case_Closed_vol_25.jpg",
    "https://upload.wikimedia.org/wikipedia/en/thumb/6/6c/Case_Closed_vol_70.jpg/440px-Case_Closed_vol_70.jpg",
    "https://upload.wikimedia.org/wikipedia/en/thumb/a/a9/Case_Closed_vol_85.jpg/440px-Case_Closed_vol_85.jpg",
    "https://upload.wikimedia.org/wikipedia/en/thumb/d/d0/Case_Closed_vol_95.jpg/440px-Case_Closed_vol_95.jpg",
]

# 🔄 ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=15)
FB_API_URL = "https://graph.facebook.com/v20.0/me/messages"

# ========== Retry Session ==========
def create_retry_session(retries=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504)):
    session = requests.Session()
    retry = Retry(total=retries, read=retries, connect=retries, backoff_factor=backoff_factor, status_forcelist=status_forcelist, allowed_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

anthropic_session = create_retry_session()
elevenlabs_session = create_retry_session()
generic_session = create_retry_session()

# ========== دوال الكشف ==========
def is_image_request(t): return any(k in t.lower() for k in ['صورة','صور','صوره','اريد صورة','picture','photo'])

# ========== Claude API ==========
def get_claude_response(text):
    api_key = get_next_claude_key()
    if not api_key: return None
    try:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        system_prompt = f"""أنت مساعد رسمي ودود لصفحة المحقق كونان التي يديرها Mounir.
مهمتك:
1- الرد على المستخدمين بلهجة عربية طبيعية، مختصرة، وودية.
2- إذا سُئلت عن هويتك: قل إنك مساعد ذكي لصفحة Mounir، صُممت لمساعدة المعجبين بكونان.
3- إذا طُلب رابط المشاهدة: أرسل: {CONAN_LINK}
4- إذا سُئلت عن سياسة النشر: وضّح بلطف: {POLICY_NOTE}
5- شجّع على متابعة الصفحة: {PAGE_URL} بشكل طبيعي غير متكرر.
6- استخدم إيموجيز خفيفة 🎬🔍✨ لجعل المحادثة ممتعة.
7- إذا خرج المستخدم عن الموضوع، أعد توجيهه بلطف لكونان.
هدفك: تجربة مستخدم سلسة، مفيدة، وإنسانية."""

        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": text}]
        }
        res = anthropic_session.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=25)
        if res.status_code == 200:
            return res.json()['content'][0]['text']
        return None
    except Exception as e:
        logger.error(f"❌ Claude API Error: {e}")
        return None

# ========== ElevenLabs Speech-to-Text (بديل Whisper) ==========
def transcribe_audio_elevenlabs(audio_url):
    if not ELEVENLABS_API_KEY: return None
    try:
        # تحميل الصوت أولاً
        audio_res = generic_session.get(audio_url, timeout=20)
        if audio_res.status_code != 200: return None
        audio_data = audio_res.content
        
        # إرسال لـ ElevenLabs STT
        res = elevenlabs_session.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            files={"file": ("audio.mp3", io.BytesIO(audio_data), "audio/mpeg")},
            timeout=30
        )
        if res.status_code == 200:
            text = res.json().get('text', '').strip()
            logger.info(f"✅ ElevenLabs STT: {text[:60]}")
            return text if text else None
        return None
    except Exception as e:
        logger.error(f"❌ ElevenLabs STT Error: {e}")
        return None

# ========== ElevenLabs Text-to-Speech ==========
def generate_audio_elevenlabs(text):
    if not ELEVENLABS_API_KEY: return None
    try:
        res = elevenlabs_session.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
            headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
            json={"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
            timeout=25
        )
        return res.content if res.status_code == 200 else None
    except Exception as e:
        logger.error(f"❌ ElevenLabs TTS Error: {e}")
        return None

# ========== إرسال الرسائل ==========
def send_action(rid, act):
    params = {"access_token": PAGE_ACCESS_TOKEN}
    data = {"recipient": {"id": rid}, "sender_action": act}
    generic_session.post(FB_API_URL, params=params, json=data, timeout=10)

def send_text_message(rid, text):
    params = {"access_token": PAGE_ACCESS_TOKEN}
    data = {"recipient": {"id": rid}, "message": {"text": text}}
    return generic_session.post(FB_API_URL, params=params, json=data, timeout=10).status_code == 200

def send_image_attachment(rid, url):
    params = {"access_token": PAGE_ACCESS_TOKEN}
    data = {"recipient": {"id": rid}, "message": {"attachment": {"type": "image", "payload": {"url": url, "is_reusable": True}}}}
    return generic_session.post(FB_API_URL, params=params, json=data, timeout=10).status_code == 200

def send_voice_attachment(rid, audio_bytes):
    url = f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": json.dumps({"id": rid}), "message": json.dumps({"attachment": {"type": "audio", "payload": {"is_reusable": True}}})}
    files = {"filedata": ("reply.mp3", io.BytesIO(audio_bytes), "audio/mpeg")}
    return generic_session.post(url, data=payload, files=files, timeout=15).status_code == 200

def send_text_chunks(rid, txt, delay=1.0, pchar=0.04):
    send_action(rid, "typing_on")
    time.sleep(min(len(txt) * pchar, 4))
    parts = [p.strip() for p in txt.split('\n\n') if p.strip()] or [txt]
    for i, p in enumerate(parts):
        send_text_message(rid, p)
        if i < len(parts) - 1: time.sleep(delay)
    send_action(rid, "typing_off")

# ========== معالجة المسارات ==========
def handle_text(rid, txt):
    if is_image_request(txt):
        send_action(rid, "typing_on"); time.sleep(1.5)
        send_image_attachment(rid, random.choice(CONAN_IMAGES))
        send_action(rid, "typing_off")
        return
    reply = get_claude_response(txt)
    if reply:
        send_text_chunks(rid, reply)
    else:
        fallback = "أهلاً! 😊 تفضل اسألني عن المحقق كونان، أنا مساعد صفحة Mounir هنا لمساعدتك!"
        send_text_chunks(rid, fallback)

def handle_voice(rid, aurl):
    send_action(rid, "typing_on")
    transcribed = transcribe_audio_elevenlabs(aurl)
    if not transcribed:
        fallback_text = "عذراً، ما سمعت الكلام واضح، تقدر تعيده أو تكتبه؟ 🙏"
        ab = generate_audio_elevenlabs(fallback_text)
        if ab: send_voice_attachment(rid, ab)
        else: send_text_chunks(rid, fallback_text)
        send_action(rid, "typing_off")
        return
    logger.info(f"🎤 Transcribed: {transcribed[:50]}")
    reply = get_claude_response(transcribed) or "عذراً، ما قدرت أفهم السؤال 🙏"
    ab = generate_audio_elevenlabs(reply)
    time.sleep(1)
    if ab: send_voice_attachment(rid, ab)
    else: send_text_chunks(rid, reply)
    send_action(rid, "typing_off")

# ========== المعالج الخلفي ==========
def process_message_background(sender_id, msg_data):
    try:
        if 'text' in msg_data:
            handle_text(sender_id, msg_data['text'])
        elif 'attachments' in msg_data:
            for att in msg_data['attachments']:
                if att.get('type') == 'audio':
                    handle_voice(sender_id, att['payload']['url'])
                    break
    except Exception as e:
        logger.error(f"❌ Background task failed for user {sender_id}: {e}")

# ========== الويب هوك (آمن) ==========
@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
        return request.args.get('hub.challenge'), 200
    abort(403)

@app.route('/webhook', methods=['POST'])
def webhook():
    signature = request.headers.get('X-Hub-Signature-256', '')
    if APP_SECRET and signature:
        try:
            raw_body = request.get_data()
            expected = 'sha256=' + hmac.new(APP_SECRET.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                logger.warning("⚠️ Invalid webhook signature! Blocked.")
                abort(403)
            logger.info("✅ Webhook signature verified")
        except Exception as e:
            logger.error(f"❌ Signature verification error: {e}")
            abort(403)

    payload = request.get_json(silent=True)
    if not payload or payload.get('object') != 'page':
        return "OK", 200

    for entry in payload.get('entry', []):
        for ev in entry.get('messaging', []):
            sid = ev.get('sender', {}).get('id')
            msg = ev.get('message', {})
            if sid and msg:
                executor.submit(process_message_background, sid, msg)

    return "EVENT_RECEIVED", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status":"running", "workers": executor._max_workers, "claude_keys": len(CLAUDE_API_KEYS), "images": len(CONAN_IMAGES)}, 200

atexit.register(executor.shutdown, wait=False)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"🚀 Starting Claude + ElevenLabs async bot on port {port}")
    app.run(host='0.0.0.0', port=port)
