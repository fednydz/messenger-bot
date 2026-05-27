import os
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

CONAN_LINK = "https://exe.io/vLPHW2I"
POLICY_NOTE = "⚠️ ملاحظة: نحن لا ننشر حلقات كاملة، بل أجزاء مُقسَّمة من حلقات المحقق كونان فقط."
PAGE_URL = "https://www.facebook.com/mounirdjouid"

FALLBACK_IMAGES = [
    "https://upload.wikimedia.org/wikipedia/en/6/6e/Detective_Conan_logo.png",
    "https://upload.wikimedia.org/wikipedia/en/thumb/2/23/Conan_Edogawa_profile.jpg/440px-Conan_Edogawa_profile.jpg",
]

groq_client = Groq(api_key=GROQ_API_KEY)

# ========== جلب الصور من Pexels ==========
def get_random_pexels_image():
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": "Detective Conan anime", "per_page": "15", "orientation": "landscape"}
        response = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            photos = [p['src']['medium'] for p in data.get('photos', [])]
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
            "recipient": {"id": recipient_id},
            "message": {"text": chunk},
            "access_token": PAGE_ACCESS_TOKEN
        })
        if i < len(chunks) - 1: time.sleep(chunk_delay)
    
    send_messenger_action(recipient_id, "typing_off")

# ========== كشف الطلبات ==========
def is_explicit_image_request(text):
    text = text.lower()
    keywords = ['صورة', 'صور', 'صوره', 'صورة كونان', 'اريد صورة', 'ابغي صورة', 'send image', 'picture', 'photo', 'صورة حلقة']
    return any(k in text for k in keywords)

# ========== الذكاء الاصطناعي ==========
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
8- اجعل المحادثة مستمرة بطرح سؤال بسيط أو مشاركة رأي شخصي أحياناً.
هدفك: محادثة إنسانية طبيعية 100%، كل مستخدم له حوار مستقل."""

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.85,
            max_tokens=400
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Groq Error: {e}")
        return "عذراً، عندي مشكلة صغيرة في الاتصال 🙏، حاول مرة ثانية!"

# ========== الويب هوك ==========
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        return challenge, 200
    abort(403)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    payload = request.get_json()
    if payload.get('object') == 'page':
        for entry in payload.get('entry', []):
            for messaging_event in entry.get('messaging', []):
                sender_id = messaging_event.get('sender', {}).get('id')
                message = messaging_event.get('message', {})
                
                if message and 'text' in message:
                    user_text = message['text']

                    # 1️⃣ طلب صورة صريح -> إرسال صورة مباشرة
                    if is_explicit_image_request(user_text):
                        img_url = get_random_pexels_image()
                        send_messenger_action(sender_id, "typing_on")
                        time.sleep(1.5)
                        send_image_attachment(sender_id, img_url)
                        send_messenger_action(sender_id, "typing_off")

                    # 2️⃣ أي محادثة أخرى -> ذكاء اصطناعي طبيعي (كل مستخدم منفصل)
                    else:
                        ai_reply = get_ai_response(user_text, sender_id)
                        send_message_in_chunks(sender_id, ai_reply)

        return "EVENT_RECEIVED", 200
    return "OK", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status": "running"}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
