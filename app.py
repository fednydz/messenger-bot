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

FALLBACK_IMAGES = [
    "https://upload.wikimedia.org/wikipedia/en/6/6e/Detective_Conan_logo.png",
    "https://upload.wikimedia.org/wikipedia/en/thumb/2/23/Conan_Edogawa_profile.jpg/440px-Conan_Edogawa_profile.jpg",
]

groq_client = Groq(api_key=GROQ_API_KEY)

# ========== Simsimi API ==========
def get_simsimi_response(user_message, sender_id):
    try:
        url = "https://api.simsimi.vn/v2/simtalk"
        data = {"text": user_message, "lc": "ar", "key": SIMSIMI_API_KEY}
        response = requests.post(url, json=data, headers={"Content-Type": "application/json"}, timeout=10)
        if response.status_code == 200:
            return response.json().get('message', '')
        return None
    except Exception as e:
        print(f"Simsimi Error: {e}")
        return None

# ========== ElevenLabs Text-to-Speech ==========
def generate_audio(text):
    if not ELEVENLABS_API_KEY:
        return None
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        response = requests.post(url, json=data, headers=headers, timeout=15)
        return response.content if response.status_code == 200 else None
    except Exception as e:
        print(f"ElevenLabs TTS Error: {e}")
        return None

# ========== ElevenLabs Speech-to-Text ==========
def transcribe_audio(audio_url):
    if not ELEVENLABS_API_KEY:
        return None
    try:
        # تحميل الصوت من URL
        audio_response = requests.get(audio_url, timeout=10)
        if audio_response.status_code != 200:
            return None
        
        # إرسال لـ ElevenLabs للتعرف على الكلام
        url = "https://api.elevenlabs.io/v1/speech-to-text"
        headers = {"xi-api-key": ELEVENLABS_API_KEY}
        files = {"file": ("audio.mp3", io.BytesIO(audio_response.content), "audio/mpeg")}
        
        response = requests.post(url, headers=headers, files=files, timeout=30)
        if response.status_code == 200:
            return response.json().get('text', '')
        return None
    except Exception as e:
        print(f"ElevenLabs STT Error: {e}")
        return None

def send_voice_message(recipient_id, audio_bytes):
    try:
        url = f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        payload = {
            "recipient": json.dumps({"id": recipient_id}),
            "message": json.dumps({
                "attachment": {"type": "audio", "payload": {"is_reusable": True}}
            })
        }
        files = {"filedata": ("voice.mp3", io.BytesIO(audio_bytes), "audio/mpeg")}
        response = requests.post(url, data=payload, files=files)
        return response.status_code == 200
    except Exception as e:
        print(f"FB Audio Upload Error: {e}")
        return False

# ========== جلب الصور من Pexels ==========
def get_random_pexels_image():
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": "Detective Conan anime", "per_page": "15", "orientation": "landscape"}
        response = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            photos = [p['src']['medium'] for p in response.json().get('photos', [])]
            return random.choice(photos) if photos else random.choice(FALLBACK_IMAGES)
        return random.choice(FALLBACK_IMAGES)
    except Exception as e:
        print(f"Pexels Error: {e}")
        return random.choice(FALLBACK_IMAGES)

# ========== إرسال الرسائل ==========
def send_messenger_action(recipient_id, action):
    params = {"recipient": {"id": recipient_id}, "sender_action": action, "access_token": PAGE_ACCESS_TOKEN}
    requests.post("https://graph.facebook.com/v20.0/me/messages", json=params)

def send_image_attachment(recipient_id, image_url):
    params = {
        "recipient": {"id": recipient_id},
        "message": {"attachment": {"type": "image", "payload": {"url": image_url, "is_reusable": True}}},
        "access_token": PAGE_ACCESS_TOKEN
    }
    requests.post("https://graph.facebook.com/v20.0/me/messages", json=params)

def send_message_in_chunks(recipient_id, full_text, chunk_delay=1.0, typing_per_char=0.04):
    total_typing_time = min(len(full_text) * typing_per_char, 5)
    send_messenger_action(recipient_id, "typing_on")
    time.sleep(total_typing_time)
    chunks = [c.strip() for c in full_text.split('\n\n') if c.strip()]
    if not chunks: chunks = [full_text]
    for i, chunk in enumerate(chunks):
        requests.post("https://graph.facebook.com/v20.0/me/messages", json={
            "recipient": {"id": recipient_id}, "message": {"text": chunk}, "access_token": PAGE_ACCESS_TOKEN
        })
        if i < len(chunks) - 1: time.sleep(chunk_delay)
    send_messenger_action(recipient_id, "typing_off")

# ========== كشف الطلبات ==========
def is_explicit_image_request(text):
    return any(k in text.lower() for k in ['صورة', 'صور', 'صوره', 'صورة كونان', 'اريد صورة', 'abغي صورة', 'send image', 'picture', 'photo'])

def is_voice_request(text):
    return any(k in text.lower() for k in ['صوت', 'رسالة صوتية', 'تحدث', 'ارسل صوت', 'تكلم', 'voice', 'audio', 'بصوتك'])

def is_conan_related(text):
    return any(k in text.lower() for k in ['كونان', 'المحقق كونان', 'حلقة', 'جزء', 'رابط', 'شاهد', 'episode', 'conan'])

# ========== الذكاء الاصطناعي (Groq) ==========
def get_ai_response(user_message, sender_id):
    system_prompt = f"""أنت شخص حقيقي وإداري لصفحة المحقق كونان. تحدث بشكل عفوي وودي.
🎯 قواعدك الصارمة:
1- لا تذكر أبداً أنك بوت أو ذكاء اصطناعي.
2- تحدث باللهجة الطبيعية المختصرة، واستخدم إيموجيز بشكل خفيف.
3- لا ترسل روابط أو ملاحظات ما لم يطلبها المستخدم صراحةً.
4- إذا سأل عن رابط للمشاهدة، أرسل: "{CONAN_LINK}" مع جملة قصيرة.
5- إذا سأل عن سياسة النشر، وضّح بلطف: "{POLICY_NOTE}"
6- شجّع على متابعة الصفحة "{PAGE_URL}" مرة واحدة فقط إذا كان الحديث طويلاً أو وداعاً.
7- إذا خرج المستخدم عن الموضوع، أعد توجيهه بلطف لكونان دون أن يشعر.
هدفك: محادثة إنسانية طبيعية 100%، كل مستخدم له حوار مستقل."""
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            temperature=0.85, max_tokens=400
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Groq Error: {e}")
        return None

# ========== معالجة الرد الصوتي ==========
def handle_voice_response(user_text, sender_id):
    """توليد رد نصي ثم تحويله لصوت"""
    # تحديد مصدر الرد
    if is_conan_related(user_text):
        reply = get_ai_response(user_text, sender_id)
    else:
        reply = get_simsimi_response(user_text, sender_id)
    
    reply = reply or "عذراً، ما قدرت أفهم السؤال 🙏"
    
    # تحويل النص لصوت
    send_messenger_action(sender_id, "typing_on")
    time.sleep(1)
    audio = generate_audio(reply)
    if audio:
        send_voice_message(sender_id, audio)
    else:
        # Fallback للنص إذا فشل الصوت
        send_message_in_chunks(sender_id, reply)
    send_messenger_action(sender_id, "typing_off")

# ========== الويب هوك ==========
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
        return request.args.get('hub.challenge'), 200
    abort(403)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    payload = request.get_json()
    if payload.get('object') == 'page':
        for entry in payload.get('entry', []):
            for messaging_event in entry.get('messaging', []):
                sender_id = messaging_event.get('sender', {}).get('id')
                message = messaging_event.get('message', {})
                
                # 1️⃣ رسالة نصية
                if message and 'text' in message:
                    user_text = message['text']

                    # طلب صورة
                    if is_explicit_image_request(user_text):
                        img_url = get_random_pexels_image()
                        send_messenger_action(sender_id, "typing_on")
                        time.sleep(1.5)
                        send_image_attachment(sender_id, img_url)
                        send_messenger_action(sender_id, "typing_off")

                    # طلب صوت
                    elif is_voice_request(user_text):
                        handle_voice_response(user_text, sender_id)

                    # محادثة عادية
                    else:
                        reply = (get_ai_response(user_text, sender_id) if is_conan_related(user_text) 
                                 else get_simsimi_response(user_text, sender_id))
                        if reply:
                            send_message_in_chunks(sender_id, reply)

                # 2️⃣ رسالة صوتية -> رد صوتي تلقائي
                elif message and 'attachments' in message:
                    for attachment in message['attachments']:
                        if attachment.get('type') == 'audio':
                            audio_url = attachment.get('payload', {}).get('url')
                            if audio_url:
                                # تحويل الصوت لنص
                                send_messenger_action(sender_id, "typing_on")
                                transcribed_text = transcribe_audio(audio_url)
                                
                                if transcribed_text:
                                    print(f"🎤 Audio transcribed: {transcribed_text}")
                                    # الرد صوتياً على الرسالة الصوتية
                                    handle_voice_response(transcribed_text, sender_id)
                                else:
                                    # إذا فشل التعرف، رد بصوت عام
                                    fallback_reply = "سمعت رسالتك الصوتية بس ما قدرت أفهمها تماماً، تقدر تعيد إرسالها كنص؟ 🙏"
                                    audio = generate_audio(fallback_reply)
                                    if audio:
                                        send_voice_message(sender_id, audio)
                                    else:
                                        send_message_in_chunks(sender_id, fallback_reply)
                                send_messenger_action(sender_id, "typing_off")

        return "EVENT_RECEIVED", 200
    return "OK", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status": "running", "features": ["Simsimi", "Groq", "Pexels", "ElevenLabs (TTS+STT)"]}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
