import os
import requests
import logging
from flask import Flask, request
from groq import Groq

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# === المتغيرات ===
FB_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_verify_123")

# تهيئة Groq
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
def send_text(recipient_id, text):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": FB_TOKEN}
    data = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    requests.post(url, params=params, json=data)

def send_image(recipient_id, image_url):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": FB_TOKEN}
    data = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {"url": image_url}
            }
        }
    }
    requests.post(url, params=params, json=data)

def send_audio(recipient_id, audio_url):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": FB_TOKEN}
    data = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "audio",
                "payload": {"url": audio_url}
            }
        }
    }
    requests.post(url, params=params, json=data)

def send_buttons(recipient_id, surah_number):
    """إرسال أزرار التنقل"""
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": FB_TOKEN}
    
    next_surah = surah_number + 1 if surah_number < 114 else 1
    prev_surah = surah_number - 1 if surah_number > 1 else 114
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {
            "text": "📖 اختر ما تريد:",
            "quick_replies": [
                {
                    "content_type": "text",
                    "title": "⬅️ السابقة",
                    "payload": f"SURAH_{prev_surah}"
                },
                {
                    "content_type": "text",
                    "title": "التالية ➡️",
                    "payload": f"SURAH_{next_surah}"
                }
            ]
        }
    }
    requests.post(url, params=params, json=data)

# === جلب بيانات السورة ===
def get_surah_data(surah_number):
    """جلب صورة وصوت السورة من API"""
    try:
        # جلب معلومات السورة
        api_url = f"https://api.alquran.cloud/v1/surah/{surah_number}"
        response = requests.get(api_url)
        data = response.json()
        
        if data["code"] != 200:
            return None
        
        surah_info = data["data"]
        surah_name = surah_info["name"]
        
        # رابط صورة الصفحة (من المصحف الإلكتروني)
        page_number = surah_info["ayahs"][0]["numberInSurah"]
        image_url = f"https://everyayah.com/data/Alafasy_128/{surah_number:03d}001.mp3"
        
        # رابط التلاوة (مشاري العفاسي)
        audio_url = f"https://server8.mp3quran.net/afs/{surah_number:03d}.mp3"
        
        # صورة المصحف (يمكن استخدام API آخر للصور)
        quran_image_url = f"https://quran-api.pages.dev/page/{surah_info['ayahs'][0]['page']}"
        
        return {
            "name": surah_name,
            "number": surah_number,
            "audio": audio_url,
            "image": quran_image_url,
            "page": surah_info["ayahs"][0]["page"]
        }
    except Exception as e:
        logging.error(f"خطأ في جلب السورة: {e}")
        return None

# === معالجة طلب السورة ===
def handle_surah_request(recipient_id, surah_input):
    """معالجة طلب السورة بالاسم أو الرقم"""
    surah_number = None
    
    # التحقق إذا كان رقماً
    if surah_input.isdigit():
        surah_number = int(surah_input)
    else:
        # البحث بالاسم
        surah_number = SURAH_NAMES.get(surah_input)
    
    if not surah_number or surah_number < 1 or surah_number > 114:
        send_text(recipient_id, "❌ السورة غير صحيحة. أرسل رقم السورة (1-114) أو اسمها.")
        return
    
    send_text(recipient_id, f"⏳ جاري تحميل سورة...")
    
    surah_data = get_surah_data(surah_number)
    
    if not surah_data:
        send_text(recipient_id, "❌ حدث خطأ في جلب السورة.")
        return
    
    # إرسال الصورة
    send_image(recipient_id, surah_data["image"])
    
    # إرسال الصوت
    send_audio(recipient_id, surah_data["audio"])
    
    # إرسال المعلومات
    send_text(recipient_id, f"📖 سورة {surah_data['name']} (رقم {surah_number})\nالصفحة: {surah_data['page']}")
    
    # إرسال أزرار التنقل
    send_buttons(recipient_id, surah_number)

# === الذكاء الاصطناعي ===
def get_ai_reply(user_text):
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "أنت مساعد ذكي يتحدث العربية. إذا سأل عن القرآن أو السور، وجهه لإرسال رقم أو اسم السورة."},
                {"role": "user", "content": user_text}
            ]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"خطأ Groq: {e}")
        return "عذراً، حدث خطأ."

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

    if payload["object"] == "page":
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                try:
                    sender_id = event["sender"]["id"]
                    
                    if "message" in event and "text" in event["message"]:
                        user_text = event["message"]["text"].strip()
                        
                        # التحقق من طلب السورة
                        if user_text.startswith("SURAH_"):
                            surah_num = int(user_text.replace("SURAH_", ""))
                            handle_surah_request(sender_id, str(surah_num))
                        elif user_text.isdigit() and 1 <= int(user_text) <= 114:
                            handle_surah_request(sender_id, user_text)
                        elif user_text in SURAH_NAMES:
                            handle_surah_request(sender_id, user_text)
                        else:
                            # رد الذكاء الاصطناعي
                            ai_reply = get_ai_reply(user_text)
                            send_text(sender_id, ai_reply)
                            
                except Exception as e:
                    logging.error(f"خطأ: {e}")

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
