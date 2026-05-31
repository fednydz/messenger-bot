import os, time, logging, hmac, hashlib, atexit
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests
from flask import Flask, request, abort
from dotenv import load_dotenv
from groq import Groq

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()
app = Flask(__name__)

# ========== المتغيرات البيئية ==========
VERIFY_TOKEN = os.getenv('FACEBOOK_VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
APP_SECRET = os.getenv('FACEBOOK_APP_SECRET', '').strip()
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '').strip()

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
FB_API_URL = "https://graph.facebook.com/v20.0/me/messages"
executor = ThreadPoolExecutor(max_workers=15)

# ========== Session مع Retry ذكي ==========
def create_fb_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=["POST"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session

fb_session = create_fb_session()

# ========== Prompt النظام ==========
SYSTEM_PROMPT = """أنت مساعد رسمي ودود لصفحة المحقق كونان التي يديرها Mounir.
تحدث بلهجة عربية طبيعية، مختصرة، وودية.
لا تذكر أبداً أنك بوت أو ذكاء اصطناعي.
إذا طُلب رابط المشاهدة: أرسل https://exe.io/vLPHW2I
إذا سُئلت عن سياسة النشر: وضّح أننا ننشر أجزاء مُقسَّمة فقط وليس حلقات كاملة.
شجّع على متابعة الصفحة https://www.facebook.com/mounirdjouid بشكل طبيعي غير مزعج.
استخدم إيموجيز خفيفة 🎬🔍✨. هدفك: محادثة بشرية طبيعية 100%."""

# ========== Groq API ==========
def get_groq_response(text):
    if not groq_client: return None
    try:
        comp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
            temperature=0.8, max_tokens=512, timeout=20
        )
        return comp.choices[0].message.content
    except Exception as e:
        logger.error(f"❌ Groq Error: {e}")
        return None

# ========== إرسال الرسائل ==========
def send_action(rid, act):
    fb_session.post(FB_API_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json={"recipient": {"id": rid}, "sender_action": act}, timeout=10)

def send_text_chunks(rid, txt, delay=1.0, pchar=0.04):
    send_action(rid, "typing_on")
    time.sleep(min(len(txt) * pchar, 4))
    parts = [p.strip() for p in txt.split('\n\n') if p.strip()] or [txt]
    for i, p in enumerate(parts):
        fb_session.post(FB_API_URL, params={"access_token": PAGE_ACCESS_TOKEN}, json={"recipient": {"id": rid}, "message": {"text": p}}, timeout=10)
        if i < len(parts) - 1: time.sleep(delay)
    send_action(rid, "typing_off")

# ========== معالجة الخلفية ==========
def process_text(sender_id, text):
    reply = get_groq_response(text) or "عذراً، حدث خطأ مؤقت. حاول مرة أخرى لاحقاً."
    send_text_chunks(sender_id, reply)

# ========== الويب هوك ==========
@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
        return request.args.get('hub.challenge'), 200
    abort(403)

@app.route('/webhook', methods=['POST'])
def webhook():
    signature = request.headers.get('X-Hub-Signature-256', '')
    if APP_SECRET and signature:
        expected = 'sha256=' + hmac.new(APP_SECRET.encode('utf-8'), request.get_data(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("⚠️ Invalid webhook signature! Blocked.")
            abort(403)

    payload = request.get_json(silent=True)
    if not payload or payload.get('object') != 'page':
        return "OK", 200

    for entry in payload.get('entry', []):
        for ev in entry.get('messaging', []):
            sid = ev.get('sender', {}).get('id')
            msg = ev.get('message', {})
            # ✅ يعالج الرسائل النصية فقط ويتجاهل الباقي كما طلبت
            if sid and 'text' in msg:
                executor.submit(process_text, sid, msg['text'])

    return "EVENT_RECEIVED", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status": "running", "groq_active": bool(groq_client)}, 200

atexit.register(executor.shutdown, wait=False)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
