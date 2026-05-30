import os, io, json, time, random, requests, logging
from flask import Flask, request, abort
from groq import Groq
from dotenv import load_dotenv

# إعداد السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
app = Flask(__name__)

# ========== المتغيرات ==========
VERIFY_TOKEN = os.getenv('FACEBOOK_VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
APP_SECRET = os.getenv('FACEBOOK_APP_SECRET')
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
SIMSIMI_API_KEY = os.getenv('SIMSIMI_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
ELEVENLABS_VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')

CONAN_LINK = "https://exe.io/vLPHW2I"
POLICY_NOTE = "⚠️ ملاحظة: نحن لا ننشر حلقات كاملة، بل أجزاء مُقسَّمة من حلقات المحقق كونان فقط."
PAGE_URL = "https://www.facebook.com/mounirdjouid"
BOT_IDENTITY_REPLY = "لا أنا لست بوت، أنا Mounir صاحب الصفحة التي تنشر حلقات المحقق كونان، وأعتذر لعدم نشر الحلقات كاملة."

FALLBACK_IMAGES = [
    "https://upload.wikimedia.org/wikipedia/en/6/6e/Detective_Conan_logo.png",
    "https://upload.wikimedia.org/wikipedia/en/thumb/2/23/Conan_Edogawa_profile.jpg/440px-Conan_Edogawa_profile.jpg",
]

# تهيئة Groq
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ========== دوال الكشف ==========
def is_bot_question(t): return any(k in t.lower() for k in ['بوت','روبوت','ذكاء اصطناعي','ai','هل انت بوت','هل انت ذكاء'])
def is_image_request(t): return any(k in t.lower() for k in ['صورة','صور','صوره','اريد صورة','picture','photo'])
def is_conan_related(t): return any(k in t.lower() for k in ['كونان','المحقق كونان','حلقة','جزء','رابط','شاهد','episode'])

# ========== APIs مع تسجيل الأخطاء ==========
def get_groq_response(text):
    if not groq_client:
        logger.error("❌ Groq client not initialized - check GROQ_API_KEY")
        return None
    try:
        sys = f"""أنت Mounir، صاحب صفحة المحقق كونان. تحدث بشكل عفوي، مختصر، وودي.
القواعد: 1- لا تذكر أنك بوت أبداً. 2- إذا طُلب رابط: {CONAN_LINK} 3- سياسة النشر: {POLICY_NOTE} 4- شجّع على متابعة: {PAGE_URL} بشكل طبيعي.
هدفك: محادثة بشرية طبيعية 100%."""
        comp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content":sys},{"role":"user","content":text}],
            temperature=0.8, max_tokens=300, timeout=20
        )
        reply = comp.choices[0].message.content
        logger.info(f"✅ Groq reply: {reply[:50]}...")
        return reply
    except Exception as e:
        logger.error(f"❌ Groq Error: {e}")
        return None

def get_simsimi_response(text):
    if not SIMSIMI_API_KEY:
        logger.error("❌ SIMSIMI_API_KEY not set")
        return None
    try:
        res = requests.post("https://api.simsimi.vn/v2/simtalk",
            json={"text":text,"lc":"ar","key":SIMSIMI_API_KEY},
            headers={"Content-Type":"application/json"}, timeout=10)
        if res.status_code == 200:
            reply = res.json().get('message','')
            logger.info(f"✅ Simsimi reply: {reply[:50]}...")
            return reply
        logger.error(f"❌ Simsimi HTTP {res.status_code}: {res.text}")
        return None
    except Exception as e:
        logger.error(f"❌ Simsimi Error: {e}")
        return None

def get_random_pexels_image():
    if not PEXELS_API_KEY:
        logger.warning("⚠️ PEXELS_API_KEY not set - using fallback")
        return random.choice(FALLBACK_IMAGES)
    try:
        res = requests.get("https://api.pexels.com/v1/search",
            headers={"Authorization":PEXELS_API_KEY},
            params={"query":"Detective Conan anime","per_page":15,"orientation":"landscape"}, timeout=10)
        if res.status_code == 200:
            photos = [p['src']['medium'] for p in res.json().get('photos',[])]
            return random.choice(photos) if photos else random.choice(FALLBACK_IMAGES)
        logger.error(f"❌ Pexels HTTP {res.status_code}")
        return random.choice(FALLBACK_IMAGES)
    except Exception as e:
        logger.error(f"❌ Pexels Error: {e}")
        return random.choice(FALLBACK_IMAGES)

def transcribe_audio(url):
    if not ELEVENLABS_API_KEY: return None
    try:
        audio = requests.get(url, timeout=10).content
        res = requests.post("https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key":ELEVENLABS_API_KEY},
            files={"file":("audio.mp3",io.BytesIO(audio),"audio/mpeg")}, timeout=25)
        return res.json().get('text','') if res.status_code==200 else None
    except Exception as e:
        logger.error(f"❌ STT Error: {e}")
        return None

def generate_audio(text):
    if not ELEVENLABS_API_KEY: return None
    try:
        res = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
            headers={"xi-api-key":ELEVENLABS_API_KEY,"Content-Type":"application/json"},
            json={"text":text,"model_id":"eleven_multilingual_v2","voice_settings":{"stability":0.5,"similarity_boost":0.75}}, timeout=20)
        return res.content if res.status_code==200 else None
    except Exception as e:
        logger.error(f"❌ TTS Error: {e}")
        return None

# ========== إرسال الرسائل ==========
def send_action(rid, act):
    requests.post("https://graph.facebook.com/v20.0/me/messages", json={
        "recipient":{"id":rid},"sender_action":act,"access_token":PAGE_ACCESS_TOKEN})

def send_image(rid, url):
    requests.post("https://graph.facebook.com/v20.0/me/messages", json={
        "recipient":{"id":rid},
        "message":{"attachment":{"type":"image","payload":{"url":url,"is_reusable":True}}},
        "access_token":PAGE_ACCESS_TOKEN})

def send_text_chunks(rid, txt, delay=1.0, pchar=0.04):
    send_action(rid,"typing_on")
    time.sleep(min(len(txt)*pchar,4))
    parts=[p.strip() for p in txt.split('\n\n') if p.strip()] or [txt]
    for i,p in enumerate(parts):
        requests.post("https://graph.facebook.com/v20.0/me/messages", json={
            "recipient":{"id":rid},"message":{"text":p},"access_token":PAGE_ACCESS_TOKEN})
        if i<len(parts)-1: time.sleep(delay)
    send_action(rid,"typing_off")

def send_voice(rid, abytes):
    url=f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload={"recipient":json.dumps({"id":rid}),"message":json.dumps({"attachment":{"type":"audio","payload":{"is_reusable":True}}})}
    files={"filedata":("reply.mp3",io.BytesIO(abytes),"audio/mpeg")}
    return requests.post(url,data=payload,files=files).status_code==200

# ========== معالجة المسارات ==========
def generate_reply(text):
    if is_bot_question(text):
        logger.info("🎯 Identity question detected")
        return BOT_IDENTITY_REPLY
    # Groq أولاً (أكثر موثوقية للعربية)
    reply = get_groq_response(text)
    if reply: return reply
    # Fallback لـ Simsimi
    reply = get_simsimi_response(text)
    if reply: return reply
    logger.warning(f"⚠️ Both APIs failed for: {text[:30]}")
    return None

def handle_text(rid, txt):
    if is_image_request(txt):
        send_action(rid,"typing_on"); time.sleep(1.5)
        send_image(rid, get_random_pexels_image())
        send_action(rid,"typing_off")
        return
    reply = generate_reply(txt)
    if reply:
        send_text_chunks(rid, reply)
    else:
        # Fallback ودود بدلاً من "ما قدرت أفهم"
        fallback = "أهلاً! 😊 تفضل اسألني عن المحقق كونان أو أي شيء آخر، أنا هنا لمساعدتك!"
        logger.info(f"🔄 Using friendly fallback for: {txt[:30]}")
        send_text_chunks(rid, fallback)

def handle_voice(rid, aurl):
    send_action(rid,"typing_on")
    transcribed = transcribe_audio(aurl)
    if not transcribed:
        logger.warning("⚠️ STT failed - sending voice fallback")
        fallback = "عذراً، ما سمعت الكلام واضح، تقدر تعيده؟ 🙏"
        ab = generate_audio(fallback)
        if ab: send_voice(rid, ab)
        else: send_text_chunks(rid, fallback)
        send_action(rid,"typing_off")
        return
    logger.info(f"🎤 Transcribed: {transcribed[:50]}")
    reply = generate_reply(transcribed) or "عذراً، ما قدرت أفهم السؤال 🙏"
    ab = generate_audio(reply)
    time.sleep(1)
    if ab: send_voice(rid, ab)
    else: send_text_chunks(rid, reply)
    send_action(rid,"typing_off")

# ========== الويب هوك ==========
@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get('hub.mode')=='subscribe' and request.args.get('hub.verify_token')==VERIFY_TOKEN:
        return request.args.get('hub.challenge'), 200
    abort(403)

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_json()
    if payload.get('object')!='page': return "OK",200
    for entry in payload.get('entry',[]):
        for ev in entry.get('messaging',[]):
            sid = ev.get('sender',{}).get('id')
            msg = ev.get('message',{})
            if not sid or not msg: continue
            if 'text' in msg:
                logger.info(f"📝 Text from {sid}: {msg['text'][:50]}")
                handle_text(sid, msg['text'])
            elif 'attachments' in msg:
                for att in msg['attachments']:
                    if att.get('type')=='audio':
                        logger.info(f"🎤 Voice from {sid}")
                        handle_voice(sid, att['payload']['url'])
                        break
    return "EVENT_RECEIVED",200

# ========== نقاط الاختبار ==========
@app.route('/health', methods=['GET'])
def health():
    return {"status":"running","apis":{"groq":bool(GROQ_API_KEY),"simsimi":bool(SIMSIMI_API_KEY),"pexels":bool(PEXELS_API_KEY),"elevenlabs":bool(ELEVENLABS_API_KEY)}},200

@app.route('/test-apis', methods=['GET'])
def test_apis():
    results = {}
    # Test Groq
    if groq_client:
        try:
            r = groq_client.chat.completions.create(model="llama-3.3-70b-versatile",messages=[{"role":"user","content":"مرحبا"}],max_tokens=10,timeout=10)
            results["groq"] = "✅ OK"
        except Exception as e: results["groq"] = f"❌ {e}"
    else: results["groq"] = "❌ No API Key"
    # Test Simsimi
    if SIMSIMI_API_KEY:
        try:
            r = requests.post("https://api.simsimi.vn/v2/simtalk",json={"text":"مرحبا","lc":"ar","key":SIMSIMI_API_KEY},timeout=10)
            results["simsimi"] = "✅ OK" if r.status_code==200 else f"❌ HTTP {r.status_code}"
        except Exception as e: results["simsimi"] = f"❌ {e}"
    else: results["simsimi"] = "❌ No API Key"
    # Test Pexels
    if PEXELS_API_KEY:
        try:
            r = requests.get("https://api.pexels.com/v1/search",headers={"Authorization":PEXELS_API_KEY},params={"query":"anime","per_page":1},timeout=10)
            results["pexels"] = "✅ OK" if r.status_code==200 else f"❌ HTTP {r.status_code}"
        except Exception as e: results["pexels"] = f"❌ {e}"
    else: results["pexels"] = "❌ No API Key"
    return results, 200

if __name__ == '__main__':
    port = int(os.getenv('PORT',5000))
    logger.info(f"🚀 Starting bot on port {port}")
    app.run(host='0.0.0.0', port=port)
