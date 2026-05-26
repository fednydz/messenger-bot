import os
import re
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

groq_client = Groq(api_key=GROQ_API_KEY)

# رسالة التوضيح الثابتة
POLICY_NOTE = "⚠️ ملاحظة: نحن لا ننشر حلقات كاملة، بل أجزاء مُقسَّمة من حلقات المحقق كونان فقط."

def extract_episode_info(text):
    """استخراج معلومات الحلقة/الجزء من رسالة المستخدم"""
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
    """توليد جملة مخصصة حسب نوع الطلب"""
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
    """التحقق مما إذا كان المستخدم يطلب محتوى المحقق كونان"""
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

def send_messenger_message(recipient_id, message_text):
    params = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text},
        "access_token": PAGE_ACCESS_TOKEN
    }
    response = requests.post("https://graph.facebook.com/v20.0/me/messages", json=params)
    return response.status_code == 200

def send_typing_indicator(recipient_id):
    params = {
        "recipient": {"id": recipient_id},
        "sender_action": "typing_on",
        "access_token": PAGE_ACCESS_TOKEN
    }
    requests.post("https://graph.facebook.com/v20.0/me/messages", json=params)

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
                    send_typing_indicator(sender_id)
                    
                    if user_wants_conan_content(user_text):
                        info = extract_episode_info(user_text)
                        prefix = generate_custom_prefix(info)
                        response_text = f"{prefix}\n{CONAN_LINK}\n\n{POLICY_NOTE}\n\nاستمتع بالمشاهدة! 🎬🔍"
                    else:
                        response_text = get_ai_response(user_text)
                    
                    send_messenger_message(sender_id, response_text)
        return "EVENT_RECEIVED", 200
    return "OK", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status": "running"}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
