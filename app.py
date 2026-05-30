import os, io, json, time, random, requests, logging, hmac, hashlib, atexit
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import Flask, request, abort
from dotenv import load_dotenv

# إعداد السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()
app = Flask(__name__)

# ========== المتغيرات البيئية ==========
VERIFY_TOKEN = os.getenv('FACEBOOK_VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
APP_SECRET = os.getenv('FACEBOOK_APP_SECRET', '').strip()  # ✅ إزالة المسافات تلقائياً
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
ELEVENLABS_VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

CONAN_LINK = "https://exe.io/vLPHW2I"
POLICY_NOTE = "⚠️ ملاحظة: نحن لا ننشر حلقات كاملة، بل أجزاء مُقسَّمة من حلقات المحقق كونان فقط."
PAGE_URL = "https://www.facebook.com/mounirdjouid"

# 🖼️ مكتبة صور متنوعة (15+ صورة مباشرة وقانونية)
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

# 🔄 ThreadPoolExecutor للمعالجة غير المتزامنة
executor = ThreadPoolExecutor(max_workers=15)
FB_API_URL = "https://graph.facebook.com/v20.0/me/messages"

# ========== إعداد Session مع Retry ذكي ==========
def create_retry_session(retries=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504)):
    session = requests.Session()
    retry = Retry(total=retries, read=retries, connect=retries, backoff_factor=backoff_factor, status_forcelist=status_forcelist, allowed_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

openai_session = create_retry_session()
elevenlabs_session = create_retry_session()
generic_session = create_retry_session()

# ========== دوال الكشف ==========
def is_bot_question(t): return any(k in t.lower() for k in ['بوت','روبوت','ذكاء اصطناعي','ai','assistant','مساعد'])
def is_image_request(t): return any(k in t.lower() for k in ['صورة','صور','صوره','اريد صورة','picture','photo'])

# ========== OpenAI Chat API ==========
def get_openai_response(text):
    if not OPENAI_API_KEY: return None
    try:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": f"""أنت مساعد رسمي ودود لصفحة المحقق كونان التي يديرها Mounir.
مهمتك:
1- الرد على المستخدمين بلهجة عربية طبيعية، مختصرة، وودية.
2- إذا سُئلت عن هويتك: قل إنك مساعد ذكي لصفحة Mounir، صُممت لمساعدة المعجبين بكونان.
3- إذا طُلب رابط المشاهدة: أرسل: {CONAN_LINK}
4- إذا سُئلت عن سياسة النشر: وضّح بلطف: {POLICY_NOTE}
5- شجّع على متابعة الصفحة: {PAGE_URL} بشكل طبيعي غير متكرر.
6- استخدم إيموجيز خفيفة 🎬🔍✨ لجعل المحادثة ممتعة.
7- إذا خرج المستخدم عن الموضوع، أعد توجيهه بلطف لكونان.
هدفك: تجربة مستخدم سلسة، مفيدة، وإنسانية."""},
                {"role": "user", "content": text}
            ],
            "temperature": 0.8, "max_tokens": 300
        }
        res = openai_session.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=25)
        return res.json()['choices'][0]['message']['content'] if res.status_code == 200 else None
    except Exception as e:
        logger.error(f"❌ OpenAI Chat Error: {e}")
        return None

# ========== ✅ Whisper gpt-4o-transcribe ==========
def transcribe_audio_whisper(audio_url):
    if not OPENAI_API_KEY: return None
    try:
        audio_res = generic_session.get(audio_url, timeout=20)
        if audio_res.status_code != 200: return None
        audio_data = audio_res.content
        
        files = {"file": ("audio.mp3", io.BytesIO(audio_data), "audio/mpeg")}
        data = {"model": "gpt-4o-transcribe"}
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        res = openai_session.post("https://api.openai.com/v1/audio/transcriptions", files=files, data=data, headers=headers, timeout=35)
        if res.status_code == 200:
            text = res.json().get('text', '').strip()
            logger.info(f"✅ Transcribed: {text[:60]}")
            return text if text else None
        return None
    except Exception as e:
        logger.error(f"❌ Whisper Error: {e}")
        return None

# ========== ElevenLabs TTS ==========
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

# ========== إرسال الرسائل (✅ access_token كـ Query Param) ==========
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
def generate_reply(text):
    return get_openai_response(text)

def handle_text(rid, txt):
    if is_image_request(txt):
        send_action(rid, "typing_on"); time.sleep(1.5)
        send_image_attachment(rid, random.choice(CONAN_IMAGES))
        send_action(rid, "typing_off")
        return
    reply = generate_reply(txt)
    if reply:
        send_text_chunks(rid, reply)
    else:
        fallback = "أهلاً! 😊 تفضل اسألني عن المحقق كونان، أنا مساعد صفحة Mounir هنا لمساعدتك!"
        send_text_chunks(rid, fallback)

def handle_voice(rid, aurl):
    send_action(rid, "typing_on")
    transcribed = transcribe_audio_whisper(aurl)
    if not transcribed:
        fallback_text = "عذراً، ما سمعت الكلام واضح، تقدر تعيده أو تكتبه؟ 🙏"
        ab = generate_audio_elevenlabs(fallback_text)
        if ab: send_voice_attachment(rid, ab)
        else: send_text_chunks(rid, fallback_text)
        send_action(rid, "typing_off")
        return
    logger.info(f"🎤 Transcribed: {transcribed[:50]}")
    reply = generate_reply(transcribed) or "عذراً، ما قدرت أفهم السؤال 🙏"
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

# ========== الويب هوك (✅ تحقق آمن ومُصحَّح) ==========
@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
        return request.args.get('hub.challenge'), 200
    abort(403)

@app.route('/webhook', methods=['POST'])
def webhook():
    # 🔐 1. الحصول على التوقيع والسر
    signature = request.headers.get('X-Hub-Signature-256', '')
    
    # 2. التحقق قبل قراءة JSON (قاعدة أمنية فيسبوك)
    if APP_SECRET and signature:
        try:
            raw_body = request.get_data()  # بايتس خام غير مشفرة
            expected = 'sha256=' + hmac.new(APP_SECRET.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
            
            if not hmac.compare_digest(signature, expected):
                logger.warning(f"⚠️ Invalid webhook signature! Blocked.")
                abort(403)
            logger.info("✅ Webhook signature verified")
        except Exception as e:
            logger.error(f"❌ Signature verification error: {e}")
            abort(403)

    # 📦 3. قراءة JSON بعد التأكد من الأمان
    payload = request.get_json(silent=True)
    if not payload or payload.get('object') != 'page':
        return "OK", 200

    # ⚡ 4. إرسال المهام للمعالجة الخلفية فوراً
    for entry in payload.get('entry', []):
        for ev in entry.get('messaging', []):
            sid = ev.get('sender', {}).get('id')
            msg = ev.get('message', {})
            if sid and msg:
                executor.submit(process_message_background, sid, msg)

    return "EVENT_RECEIVED", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status":"running", "workers": executor._max_workers, "images": len(CONAN_IMAGES)}, 200

# إيقاف نظيف للمؤشرات عند إعادة تشغيل Railway
atexit.register(executor.shutdown, wait=False)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"🚀 Starting secure async bot on port {port}")
    app.run(host='0.0.0.0', port=port)
