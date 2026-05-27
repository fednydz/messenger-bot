import os
import re
import time
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

# ✅ الرابط الجديد
CONAN_LINK = "https://exe.io/vLPHW2I"

POLICY_NOTE = "⚠️ ملاحظة: نحن لا ننشر حلقات كاملة، بل أجزاء مُقسَّمة من حلقات المحقق كونان فقط."
PAGE_URL = "https://www.facebook.com/mounirdjouid"
CONAN_IMAGE_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/messenger-bot/main/mo.webp"

groq_client = Groq(api_key=GROQ_API_KEY)

# ========== إرسال الرسائل ==========
def send_messenger_action(recipient_id, action):
    params = {
        "recipient": {"id": recipient_id},
        "sender_action": action,
        "access_token": PAGE_ACCESS_TOKEN
    }
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
    """إرسال الرسالة على أجزاء مع محاكاة الكتابة البشرية"""
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

# ========== استخراج المعلومات من رسالة المستخدم ==========
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
        return f"🎬 الجزء المتاح من الحلقة {info['number']} جاهز لك:"
    elif info["type"] == "جزء" and info["number"]:
        return f"📺 الجزء {info['number']} من كونان في الانتظار:"
    elif info["type"] == "حلقة":
        return "🎬 أجزاء حلقات كونان الجديدة متاحة:"
    elif info["type"] == "جزء":
        return "📺 أجزاء كونان اللي تحبها هنا:"
    else:
        return "👉 شاهد جميع الحلقات من هنا مباشرة 🔗"

def user_wants_conan_content(text):
    text = text.lower()
    keywords = ['كونان', 'المحقق كونان', 'حلقة', 'جزء', 'شاهد', 'رابط', 'أريد', 'اعطني', 'أعطني', 'من فضلك', 'episode', 'part', 'watch', 'link']
    return any(k in text for k in keywords)

# ========== الذكاء الاصطناعي التفاعلي ==========
def get_ai_response(user_message):
    try:
        system_prompt = f"""أنت صديق حقيقي ومحبوب 🎭 تدير صفحة المحقق كونان على فيسبوك.
لست بوتاً، بل شخص دمث الخلق، سريع البديهة، وتحب الضحك والمرح!

🎯 شخصيتك:
✨ مرح ودود: تستخدم النكت الخفيفة، الدعابات، والكلام المحبب.
💬 تفاعلي: تسأل المستخدم أسئلة بسيطة تشجعه على الاستمرار في الحديث.
🎨 عاطفي: تتفاعل مع مشاعر المستخدم (فرح، حزن، ملل) وتواسيه أو تفرح معه.
🔍 محب لكونان: تعرف كل شيء عن المحقق كونان وتشارك الحقائق الممتعة.
🎪 مبدع: تستخدم إيموجيز 🎬🔍😂✨🤩 بشكل طبيعي، وتغير أسلوبك لتجنب الملل.

🎯 قواعد المحادثة:
1️⃣ ابدأ ردك أحياناً بتحية دافئة أو نكتة خفيفة مرتبطة بالموضوع.
2️⃣ اسأل سؤالاً في نهاية ردك لتشجيع المستخدم على الرد (مثال: "وأنت شن رأيك؟"، "تبي نشوف جزء ثاني؟").
3️⃣ إذا بدا المستخدم مبتهجاً: شاركه الحماس! 🎉
4️⃣ إذا بدا المستخدم محبطاً: واسهِ بلطف وغيّر الموضوع لشيء ممتع عن كونان.
5️⃣ إذا قال كلمة غير لائقة: رد بابتسامة "لا حول ولا قوة إلا بالله 😊" وحوّل الحديث لكونان.
6️⃣ إذا طلب رابط/حلقة: أرسل: "شاهد جميع الحلقات من هنا مباشرة 🔗 {CONAN_LINK}" مع جملة محفزة.
7️⃣ وضّح بلطف: "{POLICY_NOTE}" عند الحاجة.
8️⃣ شجّع على المتابعة: "{PAGE_URL}" بطريقة لطيفة غير متكررة.
9️⃣ لا تكشف أبداً أنك بوت أو ذكاء اصطناعي!

💡 أمثلة على ردود تفاعلية:
- "ههه 😄 سؤالك هذا يذكرني بلحظة كونان لما اكتشف الجريمة! 🔍 تبي نشوف الجزء اللي فيه المفاجأة؟"
- "يا هلا وغلا! 🤩 كونان اليوم متحمس أكثر من المعتاد، عندك فضول تشوف إيش صار؟"
- "لا حول ولا قوة إلا بالله 🤲، خلنا نضحك شوي مع كونان، تبي جزء جديد يفرّج همك؟"
- "واو! 🎬 ذوقك راقي جداً، هذا الجزء من أحلى الأجزاء، شوفه وقلي رأيك بعد ما تشوفه 😉"
- "أهااا! 🤔 فهمت قصدك، بس خلنا نرجع لكونان، الجرائم ما تنتظر! 🔍 تبي الحلقة رقم كام؟"

🎲 تنويع الردود:
- غيّر بداية ردودك (أحياناً تحية، أحياناً نكتة، أحياناً سؤال).
- استخدم كلمات مختلفة لنفس المعنى لتجنب التكرار.
- أضف لمسة شخصية: "أنا شخصياً أحب هذا الجزء لأن..."

تذكر دائماً: هدفك أن يخرج المستخدم من المحادثة وهو مبتسم ويشعر أنه تحدث مع صديق حقيقي! ❤️"""

        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.85,  # زيادة الإبداع والتفاعلية
            max_tokens=512
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Groq Error: {e}")
        return "عذراً، تعثّرت شوي 🙏، لكن خلنا نكمل مع كونان! 🔍"

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
                    
                    if user_wants_conan_content(user_text):
                        info = extract_episode_info(user_text)
                        
                        # إرسال صورة أولاً مع تفاعل
                        send_messenger_action(sender_id, "typing_on")
                        time.sleep(2)
                        send_image_attachment(sender_id, CONAN_IMAGE_URL)
                        time.sleep(1.5)
                        
                        # تحضير وإرسال النص التفاعلي
                        prefix = generate_custom_prefix(info)
                        response_text = f"{prefix}\nشاهد جميع الحلقات من هنا مباشرة 🔗\n{CONAN_LINK}\n\n{POLICY_NOTE}\n\nاستمتع بالمشاهدة! 🎬🔍\nوقل لي رأيك بعد ما تشوف الجزء 😉"
                        send_message_in_chunks(sender_id, response_text)
                    else:
                        # محادثة تفاعلية مع الذكاء الاصطناعي
                        ai_reply = get_ai_response(user_text)
                        send_message_in_chunks(sender_id, ai_reply)
                        
        return "EVENT_RECEIVED", 200
    return "OK", 200

# ========== نقطة الصحة ==========
@app.route('/health', methods=['GET'])
def health():
    return {"status": "running"}, 200

# ========== التشغيل ==========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
