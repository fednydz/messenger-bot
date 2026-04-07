import os
import requests
import logging
from flask import Flask, request
from groq import Groq

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# === المتغيرات ===
FB_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
IG_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_verify_123")

client = Groq(api_key=GROQ_KEY)

# === قائمة السور ===
SURAH_NAMES = {
    "الفاتحة": 1, "البقرة": 2, "آل عمران": 3, "النساء": 4, "المائدة": 5,
    "الأنعام": 6, "الأعراف": 7, "الأنفال": 8, "التوبة": 9, "يونس": 10,
    "هود": 11, "يوسف": 12, "الرعد": 13, "إبراهيم": 14, "الحجر": 15,
    "النحل": 16, "الإسراء": 17, "الكهف": 18, "مريم": 19, "طه": 20,
    "الأنبياء": 21, "الحج": 22, "المؤمنون": 23, "النور": 24, "الفرقان": 25,
    "الشعراء": 26, "النمل": 27, "القصص": 28, "العنكبوت": 29, "الروم": 30,
    "لقمان": 31, "السجدة": 32, "الأحزاب": 33, "سبأ": 34, "فاطر": 35,
    "يس": 36, "الصافات": 37, "ص": 38, "الزمر": 39, "غافر": 40,
    "فصلت": 41, "الشورى": 42, "الزخرف": 43, "الدخان": 44, "الجاثية": 45,
    "الأحقاف": 46, "محمد": 47, "الفتح": 48, "الحجرات": 49, "ق": 50,
    "الذاريات": 51, "الطور": 52, "النجم": 53, "القمر": 54, "الرحمن": 55,
    "الواقعة": 56, "الحديد": 57, "المجادلة": 58, "الحشر": 59, "الممتحنة": 60,
    "الصف": 61, "الجمعة": 62, "المنافقون": 63, "التغابن": 64, "الطلاق": 65,
    "التحريم": 66, "الملك": 67, "القلم": 68, "الحاقة": 69, "المعارج": 70,
    "نوح": 71, "الجن": 72, "المزمل": 73, "المدثر": 74, "القيامة": 75,
    "الإنسان": 76, "المرسلات": 77, "النبأ": 78, "النازعات": 79, "عبس": 80,
    "التكوير": 81, "الإنفطار": 82, "المطففين": 83, "الإنشقاق": 84, "البروج": 85,
    "الطارق": 86, "الأعلى": 87, "الغاشية": 88, "الفجر": 89, "البلد": 90,
    "الشمس": 91, "الليل": 92, "الضحى": 93, "الشرح": 94, "التين": 95,
    "العلق": 96, "القدر": 97, "البينة": 98, "الزلزلة": 99, "العاديات": 100,
    "القارعة": 101, "التكاثر": 102, "العصر": 103, "الهمزة": 104, "الفيل": 105,
    "قريش": 106, "الماعون": 107, "الكوثر": 108, "الكافرون": 109, "النصر": 110,
    "المسد": 111, "الإخلاص": 112, "الفلق": 113, "الناس": 114
}

# === دوال الإرسال ===
def send_text(token, recipient_id, text):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": token}
    data = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    requests.post(url, params=params, json=data)

def send_media(token, recipient_id, media_type, url):
    url_api = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": token}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"attachment": {"type": media_type, "payload": {"url": url}}}
    }
    requests.post(url_api, params=params, json=data)

def send_buttons(token, recipient_id, surah_number):
    url_api = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": token}
    next_s = surah_number + 1 if surah_number < 114 else 1
    prev_s = surah_number - 1 if surah_number > 1 else 114
    data = {
        "recipient": {"id": recipient_id},
        "message": {
            "text": "📖 اختر ما تريد:",
            "quick_replies": [
                {"content_type": "text", "title": "⬅️ السابقة", "payload": f"SURAH_{prev_s}"},
                {"content_type": "text", "title": "التالية ➡️", "payload": f"SURAH_{next_s}"}
            ]
        }
    }
    requests.post(url_api, params=params, json=data)

# === جلب بيانات السورة ===
def get_surah_data(surah_number):
    try:
        api = f"https://api.alquran.cloud/v1/surah/{surah_number}"
        res = requests.get(api).json()
        if res["code"] != 200: return None
        
        info = res["data"]
        page = info["ayahs"][0]["page"]
        # روابط موثوقة ومجانية
        audio_url = f"https://server8.mp3quran.net/afs/{surah_number:03d}.mp3"
        image_url = f"https://cdn.islamic.network/quran/images/high-res/{page}.jpg"
        
        return {"name": info["name"], "number": surah_number, "audio": audio_url, "image": image_url, "page": page}
    except Exception as e:
        logging.error(f"خطأ جلب سورة: {e}")
        return None

# === معالجة طلب السورة ===
def handle_surah(token, recipient_id, surah_input):
    num = int(surah_input) if surah_input.isdigit() else SURAH_NAMES.get(surah_input)
    if not num or not (1 <= num <= 114):
        send_text(token, recipient_id, "❌ أدخل رقماً (1-114) أو اسم سورة صحيح.")
        return

    send_text(token, recipient_id, "⏳ جاري تحضير السورة...")
    data = get_surah_data(num)
    if not data:
        send_text(token, recipient_id, "❌ فشل تحميل البيانات.")
        return

    send_media(token, recipient_id, "image", data["image"])
    send_media(token, recipient_id, "audio", data["audio"])
    send_text(token, recipient_id, f"📖 سورة {data['name']} | رقم {num} | صفحة {data['page']}")
    send_buttons(token, recipient_id, num)

# === الذكاء الاصطناعي (Fallback) ===
def get_ai_reply(user_text):
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "أنت مساعد ذكي يتحدث العربية. رد بإيجاز وود."},
                {"role": "user", "content": user_text}
            ]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return "عذراً، حدث خطأ مؤقت."

# === Webhooks ===
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "فشل", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json()
    if not payload or "object" not in payload:
        return "EVENT_RECEIVED", 200

    token = FB_TOKEN if payload["object"] == "page" else IG_TOKEN
    if not token: return "EVENT_RECEIVED", 200

    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            try:
                sender = event["sender"]["id"]
                if "message" in event and "text" in event["message"]:
                    txt = event["message"]["text"].strip()
                    
                    # 1. أزرار التنقل
                    if txt.startswith("SURAH_"):
                        handle_surah(token, sender, txt.replace("SURAH_", ""))
                    # 2. طلب سورة برقم أو اسم
                    elif txt.isdigit() and 1 <= int(txt) <= 114:
                        handle_surah(token, sender, txt)
                    elif txt in SURAH_NAMES:
                        handle_surah(token, sender, txt)
                    # 3. أي شيء آخر ← ذكاء اصطناعي
                    else:
                        send_text(token, sender, get_ai_reply(txt))
            except Exception as e:
                logging.error(f"خطأ Webhook: {e}")

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
