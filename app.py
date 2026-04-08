import os
import requests
import logging
from flask import Flask, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_verify_123")

def send_message(recipient_id, text):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    data = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    requests.post(url, params=params, json=data)

@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verified!")
        return challenge, 200
    return "Failed", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json()
    if not payload or payload.get("object") != "page":
        return "EVENT_RECEIVED", 200
    
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            sender = event["sender"]["id"]
            if "message" in event and "text" in event["message"]:
                text = event["message"]["text"]
                send_message(sender, f"🤖 استلمت: {text}")
    
    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
