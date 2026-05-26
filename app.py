from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import os, logging, requests, sqlite3, uuid, json
from datetime import datetime

app = FastAPI(title="Facebook AI Bot (Converted from Telegram)")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# إعدادات المتغيرات
# ──────────────────────────────────────────────────────────────
class Settings:
    PAGE_TOKEN = os.getenv("FACEBOOK_PAGE_TOKEN", "")
    APP_SECRET = os.getenv("FACEBOOK_APP_SECRET", "")
    VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN", "fb_bot_verify_2024")
    PORT = int(os.getenv("PORT", 8000))

settings = Settings()

# ──────────────────────────────────────────────────────────────
# قاعدة البيانات
# ──────────────────────────────────────────────────────────────
conn = sqlite3.connect("fb_bot_data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.executescript("""
CREATE TABLE IF NOT EXISTS users (
    psid TEXT PRIMARY KEY,
    model TEXT DEFAULT 'auto',
    conv_state TEXT DEFAULT 'main_menu',
    last_active TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    psid TEXT,
    role TEXT,
    content TEXT,
    timestamp TEXT
);
""")
conn.commit()

SUPPORTED_MODELS = {
    "auto": "🤖 تلقائي",
    "gpt-4": "🚀 GPT-4",
    "gpt-4o": "🦾 GPT-4o",
    "gpt-3.5-turbo": "💨 GPT-3.5"
}

# ──────────────────────────────────────────────────────────────
# دوال فيسبوك الأساسية
# ──────────────────────────────────────────────────────────────
def send_fb_message(psid: str, text: str, quick_replies: list = None):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={settings.PAGE_TOKEN}"
    payload = {"recipient": {"id": psid}, "message": {"text": text}}
    if quick_replies:
        payload["message"]["quick_replies"] = quick_replies
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        logger.error(f"FB Send Error: {e}")

def send_typing(psid: str):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={settings.PAGE_TOKEN}"
    requests.post(url, json={"recipient": {"id": psid}, "sender_action": "typing"}, timeout=5)

def show_main_menu(psid: str):
    quick_replies = [
        {"content_type": "text", "title": "💬 محادثة جديدة", "payload": "NEW_CONV"},
        {"content_type": "text", "title": "🤖 تغيير النموذج", "payload": "CHANGE_MODEL"},
        {"content_type": "text", "title": "📜 محفوظاتي", "payload": "MY_PROMPTS"},
        {"content_type": "text", "title": "⚙️ الإعدادات", "payload": "SETTINGS"}
    ]
    send_fb_message(psid, "👋 مرحباً! اختر من القائمة أدناه:", quick_replies)

# ──────────────────────────────────────────────────────────────
# منطق الذكاء الاصطناعي (نفس منطق تيليجرام)
# ──────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "ChatGPT/1.2027.000 (Android 15; RMX3834; build 2700000)",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "oai-package-name": "com.Modderme",
    "oai-client-type": "android",
    "oai-device-id": "84329164059103383964",
    "Cookie": "__cflb=04dTod5Jcx9DYJeMeKbyj32ve2B3i9pLVRxJxEAaKD; ..." # ⚠️ حدّث هذا بقيمة حديثة
}

def get_conduit_token():
    try:
        res = requests.post("https://android.chat.openai.com/backend-api/f/conversation/prepare", 
                            json={"action": "next", "model": "auto"}, headers=HEADERS, timeout=15)
        return res.json().get("conduit_token") if res.status_code == 200 else None
    except: return None

def ask_ai(psid: str, user_msg: str):
    cursor.execute("SELECT model FROM users WHERE psid=?", (psid,))
    model = cursor.fetchone()[0] if cursor.fetchone() else "auto"
    
    token = get_conduit_token()
    if not token:
        send_fb_message(psid, "⚠️ فشل الاتصال بالخادم. حاول لاحقاً.")
        return

    headers = HEADERS.copy()
    headers["Conduit-Token"] = token
    
    payload = {
        "action": "next",
        "messages": [{"id": str(uuid.uuid4()), "author": {"role": "user"}, 
                      "content": {"content_type": "text", "parts": [user_msg]}}],
        "model": model,
        "stream": False
    }
    
    send_typing(psid)
    try:
        res = requests.post("https://android.chat.openai.com/backend-api/f/conversation", 
                            headers=headers, json=payload, timeout=30)
        if res.status_code == 200:
            data = res.json()
            reply = data.get("message", {}).get("content", {}).get("parts", [""])[0]
            send_fb_message(psid, reply)
            cursor.execute("INSERT INTO messages (psid, role, content, timestamp) VALUES (?,?,?,?)",
                           (psid, "bot", reply, datetime.now().isoformat()))
            conn.commit()
        else:
            send_fb_message(psid, f"❌ خطأ: {res.status_code}")
    except Exception as e:
        send_fb_message(psid, f"️ خطأ: {str(e)[:100]}")

# ──────────────────────────────────────────────────────────────
# معالجة الويب هوك
# ──────────────────────────────────────────────────────────────
@app.get("/webhook")
async def verify_webhook(mode: str, challenge: str, verify_token: str):
    if mode == "subscribe" and verify_token == settings.VERIFY_TOKEN:
        return challenge
    raise HTTPException(403, "Invalid token")

@app.post("/webhook")
async def handle_webhook(request: Request):
    data = await request.json()
    for entry in data.get("entry", []):
        for msg in entry.get("messaging", []):
            psid = msg["sender"]["id"]
            text = msg.get("message", {}).get("text", "")
            payload = msg.get("message", {}).get("quick_reply", {}).get("payload", "")
            
            # تسجيل/تحديث المستخدم
            cursor.execute("INSERT OR IGNORE INTO users (psid) VALUES (?)", (psid,))
            cursor.execute("UPDATE users SET last_active=? WHERE psid=?", (datetime.now().isoformat(), psid))
            conn.commit()
            
            if payload == "NEW_CONV":
                send_fb_message(psid, "✅ تم بدء محادثة جديدة. اكتب سؤالك:")
            elif payload == "CHANGE_MODEL":
                qr = [{"content_type": "text", "title": v, "payload": f"MODEL_{k}"} for k, v in SUPPORTED_MODELS.items()]
                send_fb_message(psid, "🤖 اختر النموذج:", qr)
            elif payload.startswith("MODEL_"):
                model = payload.split("_")[1]
                cursor.execute("UPDATE users SET model=? WHERE psid=?", (model, psid))
                conn.commit()
                send_fb_message(psid, f"✅ تم تفعيل النموذج: {SUPPORTED_MODELS.get(model, model)}")
            elif text:
                ask_ai(psid, text)
                
    return JSONResponse({"status": "ok"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
