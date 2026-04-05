import os
import requests
import logging
from flask import Flask, request
import google.generativeai as genai

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# === المتغيرات ===
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_verify_123")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# تهيئة Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# === إرسال رسالة للماسنجر ===
def send_messenger(recipient_id, text):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    data = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    try:
        requests.post(url, params=params, json=data)
    except Exception as e:
        logging.error(f"فشل الإرسال: {e}")

# === الذكاء الاصطناعي (Gemini) ===
def get_ai_reply(user_text):
    try:
        # توجيه النموذج ليرد بالعربية وبأسلوب ودود
        prompt = f"""أنت مساعد ذكي ومفيد يتحدث العربية بطلاقة.
رد بإيجاز وود على رسالة المستخدم التالية:
"{user_text}" """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"خطأ Gemini: {e}")
        return "عذراً، حدث خطأ مؤقت في الذكاء الاصطناعي. حاول لاحقاً."

# === Webhook ===
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "فشل التحقق", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json()
    if not payload or "object" not in payload:
        return "EVENT_RECEIVED", 200

    if payload["object"] == "page":
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                try:
                    sender_id = event["sender"]["id"]
                    if "message" in event and "text" in event["message"]:
                        user_text = event["message"]["text"].strip()
                        
                        send_messenger(sender_id, "🤔 لحظة أفكر...")
                        ai_reply = get_ai_reply(user_text)
                        send_messenger(sender_id, ai_reply)
                except Exception as e:
                    logging.error(f"خطأ Webhook: {e}")

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
