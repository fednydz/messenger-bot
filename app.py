import os
import re
import time
import json
import requests
import threading
from datetime import datetime, timedelta
from flask import Flask, request, abort
from groq import Groq
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

app = Flask(__name__)

# المتغيرات
VERIFY_TOKEN = os.getenv('FACEBOOK_VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
APP_SECRET = os.getenv('FACEBOOK_APP_SECRET')
CONAN_LINK = "https://dz4link.com/mounirdjouida"
POLICY_NOTE = "⚠️ ملاحظة: نحن لا ننشر حلقات كاملة، بل أجزاء مُقسَّمة من حلقات المحقق كونان فقط."
PAGE_URL = "https://www.facebook.com/mounirdjouid"
CONAN_IMAGE_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/messenger-bot/main/mo.webp"

# ملف تخزين المستخدمين
USERS_DB = "users.json"

groq_client = Groq(api_key=GROQ_API_KEY)

# ========== إدارة المستخدمين ==========
def load_users():
    if os.path.exists(USERS_DB):
        with open(USERS_DB, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_DB, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def add_or_update_user(user_id):
    users = load_users()
    now = datetime.now().isoformat()
    if user_id not in users:
        users[user_id] = {"first_seen": now, "last_message": now, "followup_sent": False}
    else:
        users[user_id]["last_message"] = now
    save_users(users)

def get_users_due_for_followup():
    users = load_users()
    due = []
    now = datetime.now()
    for uid, data in users.items():
        last_msg = datetime.fromisoformat(data["last_message"])
        if not data.get("followup_sent") and (now - last_msg) >= timedelta(hours=24):
            due.append(uid)
    return due

def mark_followup_sent(user_id):
    users = load_users()
    if user_id in users:
        users[user_id]["followup_sent"] = True
        users[user_id]["followup_time"] = datetime.now().isoformat()
        save_users(users)

# ========== إرسال الرسائل ==========
def send_messenger_action(recipient_id, action):
    params = {
        "recipient": {"id": recipient_id},
        "sender_action": action,
        "access_token": PAGE_ACCESS_TOKEN
    }
    requests.post("https://graph.facebook.com/v20.0/me/messages", json=params)

def send_text_message(recipient_id, text, tag=None):
    params = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "access_token": PAGE_ACCESS_TOKEN
    }
    if tag:
        params["tag"] = tag  # للرسائل خارج نافذة 24 ساعة
    requests.post("https://graph.facebook.com/v20.0/me/messages", json=params)

def send_image_attachment(recipient_id, image_url):
    params = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {"url": image_url, "is_reusable": True}
            }
        },
        "access_token": PAGE_ACCESS_TOKEN
    }
    requests.post("https://graph.facebook.com/v20.0/me/messages", json=params)

def send_message_in_chunks(recipient_id, full_text, chunk_delay=1.2, typing_per_char=0.05):
    total_typing_time = min(len(full_text) * typing_per_char, 6)
    send_messenger_action(recipient_id, "typing_on")
    time.sleep(total_typing_time)
    chunks = [c.strip() for c in full_text.split('\n\n') if c.strip()]
    if not chunks:
        chunks = [full_text]
    for i, chunk in enumerate(chunks):
        params = {
            "recipient": {"id": recipient_id},
            "message": {"text": chunk},
            "access_token": PAGE_ACCESS_TOKEN
        }
        requests.post("https://graph.facebook.com/v20.0/me/messages", json=params)
        if i < len(chunks) - 1:
            time.sleep(chunk_delay)
    send_messenger_action(recipient_id, "typing_off")

def send_followup_message(user_id):
    """إرسال رسالة المتابعة بعد 24 ساعة"""
    followup_texts = [
        f"أهلاً وسهلاً! 👋 هل شفت الأجزاء الجديدة من المحقق كونان اللي نشرناها على الصفحة؟ 🔍\n{CONAN_LINK}",
        f"يا هلا! 😊 تذكير صغير: عندنا أجزاء جديدة من كونان، شوفتها ولا لا؟ 🎬\n{CONAN_LINK}",
        f"كيف حالك؟ 🤗 المحقق كونان ينتظرك! الأجزاء الجديدة متاحة: {CONAN_LINK}",
    ]
    import random
    message = random.choice(followup_texts) + f"\n\nتابع صفحتنا للمزيد: {PAGE_URL} ✨"
    
    # استخدام NON_PROMOTIONAL_SUBSCRIPTION tag للرسائل خارج 24 ساعة
    send_text_message(user_id, message, tag="NON_PROMOTIONAL_SUBSCRIPTION")
    mark_followup_sent(user_id)
    print(f"✓ تم إرسال متابعة للمستخدم: {user_id}")

def check_and_send_followups():
    """فحص المستخدمين وإرسال المتابعات المستحقة"""
    due_users = get_users_due_for_followup()
    for uid in due_users:
        try:
            send_followup_message(uid)
            time.sleep(2)  # فاصل بين الرسائل لتجنب الحد الأقصى
        except Exception as e:
            print(f"✗ خطأ في إرسال متابعة لـ {uid}: {e}")

# ========== الذكاء الاصطناعي ==========
def extract_episode_info(text):
    text = text.lower()
    info = {"type": None, "number": None}
    numbers = re.findall(r'\d+', text)
    if numbers:
        info["number"] = numbers[0]
    if any(k in text for k in ['حلقة', 'الحلقة', 'episode', 'ep']):
        info["type"] = "حلقة"
    elif any(k in text for k in ['جزء', 'الأجزاء', 'part', 'parts']):
        info["type"] = "جزء"
    elif 'كونان' in text or 'المحقق كونان' in text:
        info["type"] = "عام"
    return info

def generate_custom_prefix(info):
    if info["type"] == "حلقة" and info["number"]:
        return f"🎬 يمكنك مشاهدة الجزء المتاح من الحلقة {info['number']} من المحقق كونان من هنا:"
    elif info["type"] == "جزء" and info["number"]:
        return f"📺 الجزء {info['number']} من المحقق كونان متاح للمشاهدة من هنا:"
    elif info["type"] == "حلقة":
        return "🎬 يمكنك مشاهدة الأجزاء المتاحة من حلقات المحقق كونان من هنا:"
    elif info["type"] == "جزء":
        return "📺 أجزاء المحقق كونان متاحة للمشاهدة من هنا:"
    else:
        return "👉 شاهد محتوى المحقق كونان المتاح من هنا مباشرة:"

def user_wants_conan_content(text):
    text = text.lower()
    keywords = ['كونان', 'المحقق كونان', 'حلقة', 'جزء', 'شاهد', 'رابط', 'أريد', 'اعطني', 'أعطني', 'من فضلك', 'episode', 'part', 'watch', 'link']
    return any(k in text for k in keywords)

def get_ai_response(user_message):
    try:
        system_prompt = f"""أنت شخص حقيقي (ليس بوتاً) تدير صفحة فيسبوك للمحقق كونان. 
تحدث باللغة العربية العامية الودية والطبيعية جداً.

🎯 أهدافك:
1- الرد على استفسارات المستخدم حول المحقق كونان بودّ وحماس.
2- إذا طلب المستخدم حلقة أو رابط، أرسل له: "{CONAN_LINK}" مع جملة مناسبة.
3- وضّح بلطف عند الحاجة: "{POLICY_NOTE}"
4- شجّع المستخدم على متابعة صفحتنا: "{PAGE_URL}" ومشاركتها لنصل لـ 10 آلاف متابع، لكن بطريقة طبيعية غير مزعجة.
5- إذا قال المستخدم كلمة غير لائقة، رد بلطف مثل "لا حول ولا قوة إلا بالله" ثم غيّر الموضوع لكونان.
6- إذا خرج المستخدم عن الموضوع، أعد توجيهه بلطف للمحقق كونان.
7- لا تكشف أبداً أنك بوت أو ذكاء اصطناعي.
8- كن مختصراً، استخدم إيموجيز 🎬🔍✨ بشكل طبيعي.

💬 أمثلة:
- "أهلاً وسهلاً! 🔍 المحقق كونان دائماً معنا، تبي تشوف الأجزاء الجديدة؟"
- "لا حول ولا قوة إلا بالله 🤲، خلنا نركز على كونان، تبي تشوف جزء معين؟"
- "ههه 😄 كونان دايماً يفاجئنا! شوف الأجزاء الجديدة: {CONAN_LINK}"

تذكر: المستخدم يجب أن يشعر أنه يتحدث مع صديق."""

        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.8,
            max_tokens=512
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Groq Error: {e}")
        return "عذراً، حدث شيء طفيف 🙏، حاول مرة أخرى!"

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
                
                # حفظ/تحديث المستخدم
                if sender_id:
                    add_or_update_user(sender_id)
                
                message = messaging_event.get('message', {})
                if message and 'text' in message:
                    user_text = message['text']
                    
                    if user_wants_conan_content(user_text):
                        info = extract_episode_info(user_text)
                        send_messenger_action(sender_id, "typing_on")
                        time.sleep(2)
                        send_image_attachment(sender_id, CONAN_IMAGE_URL)
                        time.sleep(1.5)
                        prefix = generate_custom_prefix(info)
                        response_text = f"{prefix}\n{CONAN_LINK}\n\n{POLICY_NOTE}\n\nاستمتع بالمشاهدة! 🎬🔍"
                        send_message_in_chunks(sender_id, response_text)
                    else:
                        ai_reply = get_ai_response(user_text)
                        send_message_in_chunks(sender_id, ai_reply)
                        
        return "EVENT_RECEIVED", 200
    return "OK", 200

# ========== نقطة فحص المتابعات (تستدعى من Cron) ==========
@app.route('/cron/followup', methods=['GET'])
def trigger_followup():
    """نقطة نهاية لتشغيل متابعة المستخدمين (تُستدعى من Railway Cron)"""
    # التحقق من صحة الطلب (اختياري: أضف token سري)
    token = request.args.get('token')
    if token != os.getenv('CRON_TOKEN', 'default_secret'):
        abort(403)
    
    check_and_send_followups()
    return "Follow-up check completed", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status": "running", "users_count": len(load_users())}, 200

# ========== بدء الجدول الزمني ==========
def init_scheduler():
    scheduler = BackgroundScheduler()
    # فحص كل ساعة لإرسال المتابعات المستحقة
    scheduler.add_job(check_and_send_followups, 'interval', hours=1)
    scheduler.start()

if __name__ == '__main__':
    init_scheduler()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
