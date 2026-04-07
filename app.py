import os
import requests
import logging
import time
from flask import Flask, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# === المتغيرات ===
FB_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
IG_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_verify_123")

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

# === دوال الإرسال الأساسية ===
def send_text(token, rid, text):
    url = "https://graph.facebook.com/v18.0/me/messages"
    data = {"recipient": {"id": rid}, "message": {"text": text}}
    requests.post(url, params={"access_token": token}, json=data)

def send_audio(token, rid, url):
    url = "https://graph.facebook.com/v18.0/me/messages"
    data = {"recipient": {"id": rid}, "message": {"attachment": {"type": "audio", "payload": {"url": url}}}}
    requests.post(url, params={"access_token": token}, json=data)

def send_text_in_chunks(token, rid, full_text, max_chunk=900):
    lines = full_text.split('\n')
    chunk = []
    current_len = 0
    for line in lines:
        line_with_space = len(line) + 1
        if current_len + line_with_space > max_chunk and chunk:
            send_text(token, rid, '\n'.join(chunk))
            time.sleep(1.2)
            chunk = []
            current_len = 0
        chunk.append(line)
        current_len += line_with_space
    if chunk:
        send_text(token, rid, '\n'.join(chunk))

def send_choice_buttons(token, rid, num, name):
    url = "https://graph.facebook.com/v18.0/me/messages"
    data = {
        "recipient": {"id": rid},
        "message": {
            "text": f"📖 سورة {name}\nاختر ما تفضل:",
            "quick_replies": [
                {"content_type": "text", "title": "🎧 الاستماع", "payload": f"LISTEN_{num}"},
                {"content_type": "text", "title": "📖 القراءة", "payload": f"READ_{num}"}
            ]
        }
    }
    requests.post(url, params={"access_token": token}, json=data)

def get_surah_text(num):
    try:
        res = requests.get(f"https://api.alquran.cloud/v1/surah/{num}").json()
        if res["code"] != 200: return None
        return "\n".join([f"{a['numberInSurah']}- {a['text']}" for a in res["data"]["ayahs"]])
    except Exception as e:
        logging.error(f"خطأ جلب النص: {e}")
        return None

def handle_quran_request(token, rid, input_val):
    num = int(input_val) if input_val.isdigit() else SURAH_NAMES.get(input_val)
    if not num or not (1 <= num <= 114):
        send_text(token, rid, "❌ يرجى كتابة رقم أو اسم سورة صحيح.")
        return
    name = list(SURAH_NAMES.keys())[list(SURAH_NAMES.values()).index(num)]
    send_choice_buttons(token, rid, num, name)

def handle_quran_action(token, rid, action, num):
    num = int(num)
    if action == "LISTEN":
        send_text(token, rid, "🎧 جاري إرسال التلاوة...")
        send_audio(token, rid, f"https://server8.mp3quran.net/afs/{num:03d}.mp3")
    elif action == "READ":
        text = get_surah_text(num)
        if text:
            send_text(token, rid, "📖 جاري إرسال النص جزءاً بجزء...")
            send_text_in_chunks(token, rid, text)
        else:
            send_text(token, rid, "❌ تعذر جلب النص حالياً.")

# === دوال التفاعل مع المنشورات والتعليقات ===
def like_post(post_id):
    """إضافة إعجاب للمنشور"""
    url = f"https://graph.facebook.com/v18.0/{post_id}/likes"
    requests.post(url, params={"access_token": FB_TOKEN})

def reply_to_comment(comment_id, text):
    """الرد على تعليق محدد"""
    url = f"https://graph.facebook.com/v18.0/{comment_id}/comments"
    requests.post(url, params={"access_token": FB_TOKEN}, json={"message": text})

def send_dm_to_user(user_id, text):
    """إرسال رسالة خاصة للمستخدم الذي علّق"""
    url = "https://graph.facebook.com/v18.0/me/messages"
    requests.post(url, params={"access_token": FB_TOKEN}, json={
        "recipient": {"id": user_id},
        "message": {"text": text}
    })

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

    # معالجة أحداث فيسبوك
    if payload["object"] == "page":
        token = FB_TOKEN
        for entry in payload.get("entry", []):
            # 1️⃣ معالجة الرسائل الخاصة (DMs)
            if "messaging" in entry:
                for event in entry["messaging"]:
                    try:
                        sender = event["sender"]["id"]
                        if "message" in event and "text" in event["message"]:
                            txt = event["message"]["text"]
                            action_payload = event.get("message", {}).get("quick_reply", {}).get("payload", txt)
                            
                            if action_payload.startswith("LISTEN_"):
                                handle_quran_action(token, sender, "LISTEN", action_payload.split("_")[1])
                            elif action_payload.startswith("READ_"):
                                handle_quran_action(token, sender, "READ", action_payload.split("_")[1])
                            elif txt in SURAH_NAMES or (txt.isdigit() and 1 <= int(txt) <= 114):
                                handle_quran_request(token, sender, txt)
                            else:
                                send_text(token, sender, "🌹 أهلاً بك! أرسل اسم أو رقم سورة للبدء.")
                    except Exception as e:
                        logging.error(f"DM Error: {e}")

            # 2️⃣ معالجة التعليقات على المنشورات (Feed)
            if "changes" in entry:
                for change in entry["changes"]:
                    if change.get("field") == "feed":
                        val = change.get("value", {})
                        # التأكد أن الحدث هو إضافة تعليق جديد
                        if val.get("item") == "comment" and val.get("verb") == "add":
                            post_id = val.get("post_id")
                            comment_id = val.get("comment_id")
                            sender_id = val.get("sender_id")
                            
                            try:
                                # ✅ أ. إعجاب بالمنشور
                                like_post(post_id)
                                logging.info(f"✅ تم الإعجاب بالمنشور: {post_id}")
                                
                                # ✅ ب. الرد على التعليق
                                reply_to_comment(comment_id, "شكراً لتفاعلك الجميل! 🌹 تم إرسال رسالة خاصة لك.")
                                logging.info(f"✅ تم الرد على التعليق: {comment_id}")
                                
                                # ✅ ج. إرسال رسالة خاصة
                                send_dm_to_user(sender_id, "أهلاً بك! 👋 شكراً لتعليقك على المنشور. كيف يمكنني مساعدتك اليوم؟")
                                logging.info(f"✅ تم إرسال رسالة خاصة للمستخدم: {sender_id}")
                            except Exception as e:
                                logging.error(f"Comment Action Error: {e}")

    # معالجة أحداث إنستغرام (الرسائل الخاصة فقط)
    elif payload["object"] == "instagram":
        token = IG_TOKEN
        for entry in payload.get("entry", []):
            if "messaging" in entry:
                for event in entry["messaging"]:
                    try:
                        sender = event["sender"]["id"]
                        if "message" in event and "text" in event["message"]:
                            txt = event["message"]["text"]
                            action_payload = event.get("message", {}).get("quick_reply", {}).get("payload", txt)
                            if action_payload.startswith("LISTEN_"):
                                handle_quran_action(token, sender, "LISTEN", action_payload.split("_")[1])
                            elif action_payload.startswith("READ_"):
                                handle_quran_action(token, sender, "READ", action_payload.split("_")[1])
                            elif txt in SURAH_NAMES or (txt.isdigit() and 1 <= int(txt) <= 114):
                                handle_quran_request(token, sender, txt)
                            else:
                                send_text(token, sender, "🌹 أهلاً بك! أرسل اسم أو رقم سورة للبدء.")
                    except Exception as e:
                        logging.error(f"IG DM Error: {e}")

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
