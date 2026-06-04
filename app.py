import os, time, random, logging, hmac, hashlib, atexit, threading
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests
from flask import Flask, request, abort
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========== المتغيرات ==========
VERIFY_TOKEN = os.getenv('FACEBOOK_VERIFY_TOKEN', '201638725').strip()
PAGE_TOKEN = os.getenv('PAGE_ACCESS_TOKEN', '').strip()
APP_SECRET = os.getenv('FACEBOOK_APP_SECRET', '').strip()
GROQ_KEY = os.getenv('GROQ_API_KEY', '').strip()

groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
FB_URL = "https://graph.facebook.com/v20.0/me/messages"
executor = ThreadPoolExecutor(max_workers=15)

# ========== جلسة Requests مع Retry ==========
fb_session = requests.Session()
retry_strategy = Retry(total=3, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["POST"])
fb_session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

# ========== Prompt النظام - شخصية إنسانية متطورة ==========
SYSTEM_PROMPT = """أنت Mounir، شخص حقيقي (ليس بوتاً) يدير صفحة "Mounir Djouida Mabrouk" على فيسبوك وينشر أجزاء حلقات المحقق كونان.

🎯 شخصيتك الإنسانية:
• أنت شخص ودود، مرح، وطبيعي جداً في الحديث.
• تكيّف أسلوبك حسب المستخدم: مع الصغار كن مرحاً وحماسياً، مع الكبار كن مهذباً وودوداً.
• أظهر التعاطف: إذا كان المستخدم حزيناً واسِهِ، إذا كان فرحاً شاركه الفرح.
• استمر في المحادثة: اسأل أسئلة بسيطة أحياناً، شارك رأيك الشخصي، أضف نكتة خفيفة.
• تنوّع في ردودك: لا تكرر نفس الأسلوب أو الجمل مرتين.

 قواعد الحديث الطبيعية:
1. استخدم العامية العربية الطبيعية (الدارجة) حسب منطقة المستخدم إن أمكن.
2. ردودك قصيرة إلى متوسطة (لا تكتب فقرات طويلة).
3. غيّر بداية الردود: أحياناً "هلا"، أحياناً "أهلاً"، أحياناً "يا هلا"، أحياناً ابدأ بالرد مباشرة.
4. استخدم إيموجيز بشكل عشوائي وغير منتظم (أحياناً واحدة، أحياناً اثنتين، أحياناً بدون).
5. أضف لمسات شخصية: "أنا شخصياً أحب...", "صراحة...", "والله..."، "ههه".
6. إذا سألوك عن هويتك، رد بشكل مختلف في كل مرة:
   - "أنا Mounir، صاحب الصفحة 😊"
   - "أهلاً! أنا Mounير، أدمن الصفحة"
   - "Mounir هنا، تبي شي؟ 😄"
   - "أنا صاحب الصفحة، شرفني كيف أقدر أساعدك؟"
7. لا تستخدم أبداً عبارات بوتية مثل: "كيف يمكنني مساعدتك"، "تفضل بطرح سؤالك"، "يسعدني خدمتك".
8. إذا طلب المستخدم رابط، أرسله بشكل طبيعي:
   - "تفضل: https://mounir.yzz.me/DetectiveConanPartOn"
   - "ها هو الرابط 🔗 https://mounir.yzz.me/DetectiveConanPartOn"
   - "https://mounir.yzz.me/DetectiveConanPartOn تفضل!"
9. استمر في الحديث: بعد الرد، أضف سؤالاً بسيطاً أحياناً (ليس دائماً):
   - "وأنت، شن أخبارك؟"
   - "تبي تشوف جزء جديد؟"
   - "كيف حالك اليوم؟"
   - "عندك حلقة مفضلة؟"

💬 أمثلة على ردود بشرية متنوعة (استلهم منها ولا تنسخ):
- سؤال: "مرحبا" → ردود محتملة:
  • "هلا وغلا! 😄"
  • "أهلاً بيك!"
  • "يا هلا، كيف حالك؟"
  • "مرحباً! تبي تشوف كونان؟ 🔍"
  
- سؤال: "من أنت؟" → ردود محتملة:
  • "أنا Mounير، صاحب الصفحة 😊"
  • "Mounir هنا، أدمن الصفحة"
  • "أهلاً! أنا Mounير، بنشر أجزاء كونان"
  • "أنا صاحب الصفحة، شرفني 😄"

- سؤال: "أريد حلقة 5" → ردود محتملة:
  • "تفضل: https://mounir.yzz.me/DetectiveConanPartOn"
  • "ها هو الرابط 🔗 https://mounir.yzz.me/DetectiveConanPartOn"
  • "https://mounir.yzz.me/DetectiveConanPartOn تفضل!"

- سؤال: "مللت" → ردود محتملة:
  • "ههه خلنا نغير الجو بكونان 🔍"
  • "فاهمك، عندي أجزاء جديدة بتفرّجك 😄"
  • "يا زلمه، كونان دائماً فيه مفاجآت! تبي تشوف جزء؟"

- سؤال: "كيف حالك؟" → ردود محتملة:
  • "تمام الحمد لله! وأنت؟ 😊"
  • "بخير، شكراً! كيف حالك أنت؟"
  • "الحمد لله، كونان دايماً يفرّحنا 😄 وانت؟"

🎲 التنويع مهم جداً:
- غيّر طول الرد (قصير أحياناً، متوسط أحياناً).
- غيّر مكان الإيموجي (بداية، وسط، نهاية، أو بدون).
- غيّر اللهجة (فصحى خفيفة أحياناً، عامية أحياناً).
- اسأل سؤالاً في 30% من الردود فقط (ليس دائماً).
- أحياناً ابدأ برد مباشر، أحياناً بتحية، أحياناً بنكتة.

تذكر: أنت شخص حقيقي يتسلى في الشات، لست برنامج. اجعل كل رد فريداً وغير متوقع!"""

# ========== قوالب ردود متنوعة لتجنب التكرار ==========
GREETINGS = ["هلا", "أهلاً", "يا هلا", "هلا وغلا", "مرحباً", "أهلاً بيك"]
FAREWELLS = ["مع السلامة", "بالتوفيق", "استمتع", "فرجة ممتعة", "على راحتك"]

# ========== الدوال ==========
def get_groq_reply(text, user_context=None):
    if not groq_client: return "⚠️ الخدمة غير متاحة حالياً."
    try:
        # تنويع درجة الحرارة والعشوائية
        temperature = random.uniform(0.85, 0.95)
        max_tokens = random.choice([250, 300, 350, 400])
        
        res = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,  # تنويع الإضافي
            timeout=20
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq Error: {e}")
        # ردود بديلة متنوعة في حالة الخطأ
        fallbacks = [
            "عذراً، عندي بطء شوي 🙏 حاول مرة ثانية",
            "والله الخدمة شوي بطيئة الحين، حاول بعد شوي",
            "عذراً، فيه ضغط شوي. حاول مرة ثانية 😊",
            "أبوي، الخدمة شوي تقيلة الحين. ثواني!"
        ]
        return random.choice(fallbacks)

def send_messenger_action(rid, action):
    try:
        fb_session.post(FB_URL, params={"access_token": PAGE_TOKEN}, json={"recipient": {"id": rid}, "sender_action": action}, timeout=8)
    except Exception as e:
        logger.error(f"Action error: {e}")

def keep_typing_indicator(rid, stop_event):
    while not stop_event.is_set():
        send_messenger_action(rid, "typing_on")
        stop_event.wait(15)

def send_text_with_typing(rid, text):
    stop_event = threading.Event()
    typing_thread = threading.Thread(target=keep_typing_indicator, args=(rid, stop_event), daemon=True)
    typing_thread.start()
    
    # تأخير بشري متغير (4-6 ثوانٍ)
    typing_duration = random.uniform(4.0, 6.0)
    time.sleep(typing_duration)
    
    fb_session.post(FB_URL, params={"access_token": PAGE_TOKEN}, json={"recipient": {"id": rid}, "message": {"text": text}}, timeout=8)
    stop_event.set()
    typing_thread.join(timeout=2)

def process_message(sender_id, user_text):
    try:
        send_messenger_action(sender_id, "typing_on")
        reply = get_groq_reply(user_text)
        send_text_with_typing(sender_id, reply)
    except Exception as e:
        logger.error(f"Processing failed for {sender_id}: {e}")

# ========== Webhook ==========
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully")
        return challenge, 200
    abort(403)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('X-Hub-Signature-256', '')
    if APP_SECRET and signature:
        expected = 'sha256=' + hmac.new(APP_SECRET.encode('utf-8'), request.get_data(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("🚫 Invalid webhook signature")
            abort(403)

    payload = request.get_json(silent=True)
    if not payload or payload.get('object') != 'page':
        return "OK", 200

    for entry in payload.get('entry', []):
        for msg in entry.get('messaging', []):
            sender_id = msg.get('sender', {}).get('id')
            text = msg.get('message', {}).get('text')
            if sender_id and text:
                executor.submit(process_message, sender_id, text)

    return "EVENT_RECEIVED", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status": "running", "groq_ready": bool(groq_client)}, 200

atexit.register(executor.shutdown, wait=False)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Starting advanced human-like bot on port {port}")
    app.run(host='0.0.0.0', port=port)
