import os
import re
import time
import requests
from flask import Flask, request, abort
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# المتغيرات
VERIFY_TOKEN = os.getenv('FACEBOOK_VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
APP_SECRET = os.getenv('FACEBOOK_APP_SECRET')
CONAN_LINK = "https://dz4link.com/mounirdjouida"
POLICY_NOTE = "⚠️ ملاحظة: نحن لا ننشر حلقات كاملة، بل أجزاء مُقسَّمة من حلقات المحقق كونان فقط."

# رابط صورة الغلاف (يجب أن يكون رابط Raw مباشر من GitHub)
# مثال: https://raw.githubusercontent.com/YourUsername/messenger-bot/main/mo.webp
CONAN_IMAGE_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/messenger-bot/main/mo.webp" 

groq_client = Groq(api_key=GROQ_API_KEY)

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
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": f"""أنت مساعد رسمي لصفحة المحقق كونان على فيسبوك. 
مهمتك:
1- الرد بلطف وود باللغة العربية على استفسارات المستخدمين حول المحقق كونان.
2- إذا سأل المستخدم عن حلقة كاملة، وضّح له بلطف: "{POLICY_NOTE}"
3- كن مختصراً وودوداً في ردودك.
4- لا ترسل روابط إلا إذا طُلب منك ذلك صراحة."""},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=512
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Groq Error: {e}")
        return "عذراً، حدث خطأ تقني مؤقت. يرجى المحاولة لاحقاً."

def send_messenger_action(recipient_id, action):
    params = {
        "recipient": {"id": recipient_id},
        "sender_action": action,
        "access_token": PAGE_ACCESS_TOKEN
    }
    requests.post("https://graph.facebook.com/v20.0/me/messages", json=params)

def send_image_attachment(recipient_id, image_url):
    """إرسال صورة كمرفق"""
    params = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {
                    "url": image_url,
                    "is_reusable": True
                }
            }
        },
        "access_token": PAGE_ACCESS_TOKEN
    }
    requests.post("https://graph.facebook.com/v20.0/me/messages", json=params)

def send_message_in_chunks(recipient_id, full_text, chunk_delay=1.2, typing_per_char=0.05):
    """إرسال النص على أجزاء"""
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
                    
                    if user_wants_conan_content(user_text):
                        info = extract_episode_info(user_text)
                        
                        # 1. إظهار الكتابة قبل الصورة
                        send_messenger_action(sender_id, "typing_on")
                        time.sleep(2) # محاكاة البحث عن الصورة
                        
                        # 2. إرسال الصورة
                        send_image_attachment(sender_id, CONAN_IMAGE_URL)
                        time.sleep(1.5) # فاصل بعد إرسال الصورة
                        
                        # 3. تحضير وإرسال النص
                        prefix = generate_custom_prefix(info)
                        response_text = f"{prefix}\n{CONAN_LINK}\n\n{POLICY_NOTE}\n\nاستمتع بالمشاهدة! 🎬🔍"
                        
                        send_message_in_chunks(sender_id, response_text)
                        
                    else:
                        send_message_in_chunks(sender_id, get_ai_response(user_text))
                        
        return "EVENT_RECEIVED", 200
    return "OK", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status": "running"}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
