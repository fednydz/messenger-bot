import os
import requests
import logging
import time
from flask import Flask, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# === المتغيرات ===
PAGE_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_verify_123")

# === دالة إرسال الرسالة ===
def send_message(recipient_id, text):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_TOKEN}
    data = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    try:
        requests.post(url, params=params, json=data)
    except Exception as e:
        logging.error(f"فشل الإرسال: {e}")

# === دالة جلب الإعراب (محسنة مع إعادة المحاولة) ===
def get_i3rab(text: str) -> str:
    url = "https://tahlil.almaktaba.org/api/v1/tahlil"
    params = {"text": text.strip(), "type": "i3rab"}
    
    # نحاول مرتين للتغلب على بطء الشبكة المؤقت
    for attempt in range(2):
        try:
            response = requests.get(url, params=params, timeout=15) # زيادة الوقت لـ 15 ثانية
            response.raise_for_status()
            data = response.json()
            
            if "words" not in data or not data["words"]:
                return "❌ لم أتمكن من تحليل الجملة. تأكد أنها عربية واضحة."
            
            result = "📖 إعراب الجملة:\n" + "━" * 20 + "\n"
            for word in data["words"]:
                w_text = word.get("text", "—")
                w_i3rab = word.get("i3rab") or word.get("case") or "غير محدد"
                result += f"🔹 {w_text}: {w_i3rab}\n"
            
            return result + "━" * 20 + "\n✅ تم التحليل بنجاح"
            
        except requests.exceptions.Timeout:
            if attempt == 0:
                time.sleep(1) # انتظر ثانية ثم جرب مجدداً
                continue
            return "⏳ الموقع بطيء جداً حالياً. حاول مرة أخرى بعد قليل."
            
        except requests.exceptions.ConnectionError:
            if attempt == 0:
                time.sleep(1)
                continue
            return "❌ لا يمكن الاتصال بخدمة الإعراب حالياً. قد يكون الموقع تحت الصيانة."
            
        except Exception as e:
            return f"❌ خطأ غير متوقع: {str(e)[:50]}"

# === Webhook Verification ===
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logging.info("✅ Webhook verified successfully!")
        return challenge, 200
    return "Verification Failed", 403

# === Webhook Handling ===
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
                        
                        # تجاهل الأوامر مثل /start
                        if user_text.startswith("/"):
                            continue
                        
                        # إرسال رسالة "جاري التحليل"
                        send_message(sender_id, "⏳ جاري تحليل الجملة نحويًا...")
                        
                        # جلب الإعراب والرد به
                        i3rab_result = get_i3rab(user_text)
                        send_message(sender_id, i3rab_result)
                        
                except Exception as e:
                    logging.error(f"خطأ معالجة الرسالة: {e}")

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
