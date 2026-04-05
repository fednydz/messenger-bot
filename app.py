import os
import requests
from flask import Flask, request

app = Flask(__name__)

# قراءة المتغيرات من البيئة
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_verify_123")

# دالة إرسال رد نصي عبر ماسنجر
def send_message(recipient_id, message_text):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    response = requests.post(url, params=params, headers=headers, json=data)
    return response.json()

# 🔹 route التحقق من Webhook (مطلوب من فيسبوك)
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ تم التحقق من Webhook بنجاح!")
        return challenge, 200
    else:
        return "فشل التحقق", 403

# 🔹 route استقبال الرسائل والأحداث
@app.route("/webhook", methods=["POST"])
def handle_webhook():
    payload = request.get_json()

    if payload.get("object") == "page":
        for entry in payload["entry"]:
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]
                
                # تجاهل الرسائل غير النصية أو رسائل البوت نفسه
                if "message" in messaging_event and "text" in messaging_event["message"]:
                    user_text = messaging_event["message"]["text"]
                    
                    # الرد التلقائي
                    reply = f"🤖 مرحباً! استلمت رسالتك: \"{user_text}\"\nسأرد عليك قريباً!"
                    send_message(sender_id, reply)

    return "EVENT_RECEIVED", 200

# تشغيل السيرفر
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
