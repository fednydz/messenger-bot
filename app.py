import os
import io
import json
import time
import random
import requests
from flask import Flask, request, abort
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# ========== المتغيرات البيئية ==========
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

# ✅ رد الهوية الثابت
BOT_IDENTITY_REPLY = "لا أنا لست بوت، أنا Mounir صاحب الصفحة التي تنشر حلقات المحقق كونان، وأعتذر لعدم نشر الحلقات كاملة."

FALLBACK_IMAGES = [
    "https://upload.wikimedia.org/wikipedia/en/6/6e/Detective_Conan_logo.png",
    "https://upload.wikimedia.org/wikipedia/en/thumb/2/23/Conan_Edogawa_profile.jpg/440px-Conan_Edogawa_profile.jpg",
]

groq_client = Groq(api_key=GROQ_API_KEY)

# ========== دوال مساعدة للكشف ==========
def is_bot_question(text):
    text = text.lower()
    keywords = ['بوت', 'روبوت', 'ذكاء اصطناعي', 'ai', 'machine', 'هل انت بوت', 'هل انت ذكاء', 'هل تتكلم مع روبوت']
    return any(k in text for k in keywords)

def is_explicit_image_request(text):
    text = text.lower()
    keywords = ['صورة', 'صور', 'صوره', 'صورة كونان', 'اريد صورة', 'abغي صورة', 'send image', 'picture', 'photo', 'صورة حلقة']
    return any(k in text for k in keywords)

def is_conan_related(text):
    text = text.lower()
    keywords = ['كونان', 'المحقق كونان', 'حلقة', 'جزء', 'رابط', 'شاهد', 'episode', 'conan']
    return any(k in text for k in keywords)

# ========== APIs ==========
def get_simsimi_response(text):
    try:
        res = requests.post("https://api.simsimi.vn/v2/simtalk", 
                            json={"text": text, "lc": "ar", "key": SIMSIMI_API_KEY}, 
                            headers={"Content-Type": "application/json"}, timeout=8)
        return res.json().get('message', '') if res.status_code == 200 else None
    except: return None

def get_groq_response(text):
    sys_prompt = f"""أنت Mounir، صاحب صفحة المحقق كونان. تحدث بشكل عفوي، مختصر، وودي.
القواعد:
1- لا تذكر أنك بوت أو ذكاء اصطناعي أبداً.
2- إذا طُلب رابط المشاهدة، أرسل: {CONAN_LINK}
3- إذا سُئلت عن سياسة النشر: {POLICY_NOTE}
4- شجّع على متابعة: {PAGE_URL} بشكل طبيعي غير متكرر.
5- استخدم لهجة محبوبة وإيموجيز خفيفة.
هدفك: محادثة بشرية طبيعية 100%."""
    try:
        comp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": text}],
            temperature=0.8, max_tokens=300
        )
        return comp.choices[0].message.content
    except: return None

def get_random_pexels_image():
    try:
        res = requests.get("https://api.pexels.com/v1/search", 
                           headers={"Authorization": PEXELS_API_KEY},
                           params={"query": "Detective Conan anime", "per_page": 15, "orientation": "landscape"}, timeout=8)
        if res.status_code == 200:
            photos = [p['src']['medium'] for p in res.json().get('photos', [])]
            return random.choice(photos) if photos else random.choice(FALLBACK_IMAGES)
        return random.choice(FALLBACK_IMAGES)
    except: return random.choice(FALLBACK_IMAGES)

def transcribe_audio(audio_url):
    if not ELEVENLABS_API_KEY: return None
    try:
        audio_data = requests.get(audio_url, timeout=10).content
        res = requests.post("https://api.elevenlabs.io/v1/speech-to-text",
                            headers={"xi-api-key": ELEVENLABS_API_KEY},
                            files={"file": ("audio.mp3", io.BytesIO(audio_data), "audio/mpeg")}, timeout=20)
        return res.json().get('text', '') if res.status_code == 200 else None
    except: return None

def generate_audio(text):
    if not ELEVENLABS_API_KEY: return None
    try:
        res = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
                            headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
                            json={"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}, timeout=15)
        return res.content if res.status_code == 200 else None
    except: return None

# ========== إرسال الرسائل ==========
def send_messenger_action(recipient_id, action):
    requests.post("https://graph.facebook.com/v20.0/me/messages", json={
        "recipient": {"id": recipient_id}, "sender_action": action, "access_token": PAGE_ACCESS_TOKEN
    })

def send_image_attachment(recipient_id, url):
    requests.post("https://graph.facebook.com/v20.0/me/messages", json={
        "recipient": {"id": recipient_id},
        "message": {"attachment": {"type": "image", "payload": {"url": url, "is_reusable": True}}},
        "access_token": PAGE_ACCESS_TOKEN
    })

def send_text_chunks(recipient_id, text, delay=1.0, per_char=0.04):
    send_messenger_action(recipient_id, "typing_on")
    time.sleep(min(len(text) * per_char, 4))
    parts = [p.strip() for p in text.split('\n\n') if p.strip()]
    for i, part in enumerate(parts):
        requests.post("https://graph.facebook.com/v20.0/me/messages", json={
            "recipient": {"id": recipient_id}, "message": {"text": part}, "access_token": PAGE_ACCESS_TOKEN
        })
        if i < len(parts) - 1: time.sleep(delay)
    send_messenger_action(recipient_id, "typing_off")

def send_voice_attachment(recipient_id, audio_bytes):
    url = f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": json.dumps({"id": recipient_id}),
        "message": json.dumps({"attachment": {"type": "audio", "payload": {"is_reusable": True}}})
    }
    files = {"filedata": ("reply.mp3", io.BytesIO(audio_bytes), "audio/mpeg")}
    res = requests.post(url, data=payload, files=files)
    return res.status_code == 200

# ========== معالجة المسارات المنفصلة ==========
def generate_reply_text(user_text):
    if is_bot_question(user_text):
        return BOT_IDENTITY_REPLY
    return get_groq_response(user_text) if is_conan_related(user_text) else get_simsimi_response(user_text)

def handle_text_message(sender_id, user_text):
    # مسار نصي فقط
    if is_explicit_image_request(user_text):
        send_messenger_action(sender_id, "typing_on")
        time.sleep(1.5)
        send_image_attachment(sender_id, get_random_pexels_image())
        send_messenger_action(sender_id, "typing_off")
        return

    reply = generate_reply_text(user_text) or "عذراً، ما قدرت أفهم السؤال 🙏"
    send_text_chunks(sender_id, reply)

def handle_voice_message(sender_id, audio_url):
    # مسار صوتي فقط
    send_messenger_action(sender_id, "typing_on")
    transcribed = transcribe_audio(audio_url)
    if not transcribed: transcribed = "ما سمعت الكلام واضح"
    
    reply = generate_reply_text(transcribed) or "عذراً، ما قدرت أفهم السؤال 🙏"
    audio_bytes = generate_audio(reply)
    
    time.sleep(1)
    if audio_bytes:
        send_voice_attachment(sender_id, audio_bytes)
    else:
        # Fallback نادر جداً إذا تعطل TTS
        send_text_chunks(sender_id, reply)
    send_messenger_action(sender_id, "typing_off")

# ========== الويب هوك ==========
@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
        return request.args.get('hub.challenge'), 200
    abort(403)

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_json()
    if payload.get('object') != 'page': return "OK", 200
    
    for entry in payload.get('entry', []):
        for event in entry.get('messaging', []):
            sender_id = event.get('sender', {}).get('id')
            msg = event.get('message', {})
            
            if not sender_id or not msg: continue

            # 📝 مسار نصي
            if 'text' in msg:
                handle_text_message(sender_id, msg['text'])
            
            # 🎤 مسار صوتي
            elif 'attachments' in msg:
                for att in msg['attachments']:
                    if att.get('type') == 'audio':
                        handle_voice_message(sender_id, att['payload']['url'])
                        break
                        
    return "EVENT_RECEIVED", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status": "running"}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
