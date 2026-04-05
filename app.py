import os
import requests
from flask import Flask, request

app = Flask(__name__)

# متغيرات الماسنجر
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_verify_123")

# متغيرات انستقرام
INSTAGRAM_ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN")

# دالة إرسال رسائل الماسنجر
def send_messenger(recipient_id, text):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    data = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    requests.post(url, params=params, json=data)

# دالة إرسال رسائل انستقرام
def send_instagram(recipient_id, text):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}
    data = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    requests.post(url, params=params, json=data)

# التحقق من الـ Webhook (يعمل للمنصتين)
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "فشل التحقق", 403

# استقبال الأحداث
@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json()
    if not payload or "object" not in payload:
        return "EVENT_RECEIVED", 200

    obj = payload["object"]

    if obj == "page":
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                sid = event["sender"]["id"]
                if "message" in event and "text" in event["message"]:
                    txt = event["message"]["text"]
                    send_messenger(sid, f"📘 ماسنجر: استلمت: '{txt}'\n🤖 سأرد قريباً!")

    elif obj == "instagram":
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                sid = event["sender"]["id"]
                if "message" in event and "text" in event["message"]:
                    txt = event["message"]["text"]
                    send_instagram(sid, f"📸 انستقرام: استلمت: '{txt}'\n🤖 سأرد قريباً!")

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
