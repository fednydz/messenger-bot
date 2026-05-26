import os
import hmac
import hashlib
import json
import requests
from flask import Flask, request, abort
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# تحميل المتغيرات من البيئة
VERIFY_TOKEN = os.getenv('FACEBOOK_VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
APP_SECRET = os.getenv('FACEBOOK_APP_SECRET')

# تهيئة Groq
groq_client = Groq(api_key=GROQ_API_KEY)

def get_ai_response(user_message):
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "أنت مساعد ذكي ودود يتحدث العربية بطلاقة. رد باختصار ووضوح."},
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
                    ai_reply = get_ai_response(user_text)
                    send_messenger_message(sender_id, ai_reply)
        return "EVENT_RECEIVED", 200
    return "OK", 200

@app.route('/health', methods=['GET'])
def health():
    return {"status": "running"}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
