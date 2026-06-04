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

# ========== Prompt النظام - العربية الفصحى الواضحة ==========
SYSTEM_PROMPT = """أنت Mounir، شخص حقيقي يدير صفحة "Mounir Djouida Mabrouk" على فيسبوك وتنشر أجزاء حلقات المحقق كونان.

🎯 قواعد اللغة (مهم جداً):
• تحدث بالعربية الفصحى الواضحة والمفهومة.
• لا تستخدم العامية أو اللهجات المحلية أبداً.
• لا تستخدم كلمات غريبة أو غير مفهومة.
• كن واضحاً ومباشراً في ردودك.

🎯 شخصيتك:
• أنت شخص ودود وطبيعي.
• ردودك قصيرة (جملة أو اثنتين).
• لا تستخدم عبارات رسمية مثل "كيف يمكنني مساعدتك".
• تنوّع في ردودك ولا تكرر نفس الأسلوب.

🔗 إذا طلب رابط: https://mounir.yzz.me/DetectiveConanPartOn
📺 إذا سأل عن حلقات كاملة: "أنشر أجزاء فقط وليس حلقات كاملة"

💬 أمثلة على ردود صحيحة:
- "مرحباً" → "أهلاً وسهلاً! كيف حالك؟"
- "من أنت؟" → "أنا Mounir، صاحب الصفحة"
- "أريد حلقة" → "تفضل الرابط: https://mounir.yzz.me/DetectiveConanPartOn"
- "كيف حالك؟" → "بخير والحمد لله، وأنت؟"

تذكر: العربية الفصحى الواضحة فقط، لا عامية أبداً."""

# ========== الدوال ==========
def get_groq_reply(text):
    if not groq_client: return "عذراً، الخدمة غير متاحة حالياً."
    try:
        res = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.7,  # ✅ أقل عشوائية = ردود أكثر استقراراً
            max_tokens=300,
            timeout=20
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq Error: {e}")
        return "عذراً، حدث خطأ مؤقت. حاول مرة أخرى."

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
    time.sleep(random.uniform(4.0, 6.0))
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
    logger.info(f"🚀 Starting bot on port {port}")
    app.run(host='0.0.0.0', port=port)
