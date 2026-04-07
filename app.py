import os
import requests
import logging
from flask import Flask, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# === المتغيرات ===
FB_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
IG_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_verify_123")

# === تخزين حالة القراءة مؤقتاً (يمسح عند إعادة تشغيل البوت) ===
user_reading_state = {}

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
def send_msg(token, rid, text, quick_replies=None):
    url = "https://graph.facebook.com/v18.0/me/messages"
    data = {"recipient": {"id": rid}, "message": {"text": text}}
    if quick_replies:
        data["message"]["quick_replies"] = quick_replies
    requests.post(url, params={"access_token": token}, json=data)

def send_audio(token, rid, url):
    url = "https://graph.facebook.com/v18.0/me/messages"
    data = {
        "recipient": {"id": rid},
        "message": {"attachment": {"type": "audio", "payload": {"url": url}}}
    }
    requests.post(url, params={"access_token": token}, json=data)

# === جلب النص وتقسيمه لأجزاء ===
def get_surah_text(num):
    try:
        res = requests.get(f"https://api.alquran.cloud/v1/surah/{num}").json()
        if res["code"] != 200: return None
        return "\n".join([f"{a['numberInSurah']}- {a['text']}" for a in res["data"]["ayahs"]])
    except Exception as e:
        logging.error(f"خطأ جلب النص: {e}")
        return None

def split_into_parts(text, max_len=850):
    verses = text.split('\n')
    parts = []
    current = []
    curr_len = 0
    for v in verses:
        v_len = len(v) + 1
        if curr_len + v_len > max_len and current:
            parts.append('\n'.join(current))
            current = [v]
            curr_len = v_len
        else:
            current.append(v)
            curr_len += v_len
    if current:
        parts.append('\n'.join(current))
    return parts

# === بدء القراءة التفاعلية ===
def start_reading(token, rid, surah_num):
    text = get_surah_text(surah_num)
    if not text:
        send_msg(token, rid, "❌ تعذر جلب النص حالياً.")
        return
    
    parts = split_into_parts(text)
    # حفظ حالة المستخدم
    user_reading_state[rid] = {"surah": surah_num, "parts": parts, "idx": 0}
    
    # إرسال الجزء الأول مع الزر
    is_last = len(parts) == 1
    btn_title = "✅ انتهت السورة" if is_last else "الجزء التالي ➡️"
    payload = f"DONE_{surah_num}" if is_last else f"NEXT_{surah_num}_1"
    
    send_msg(token, rid, parts[0], [{"content_type": "text", "title": btn_title, "payload": payload}])

# === متابعة القراءة عند ضغط الزر ===
def continue_reading(token, rid, surah_num, next_idx):
    state = user_reading_state.get(rid)
    
    # إذا ضاعت الحالة أو تغيرت السورة، نعيد البدء
    if not state or str(state["surah"]) != str(surah_num):
        start_reading(token, rid, int(surah_num))
        return

    parts = state["parts"]
    if next_idx < len(parts):
        is_last = next_idx == len(parts) - 1
        btn_title = "✅ انتهت السورة" if is_last else "الجزء التالي ➡️"
        payload = f"DONE_{surah_num}" if is_last else f"NEXT_{surah_num}_{next_idx + 1}"
        
        send_msg(token, rid, parts[next_idx], [{"content_type": "text", "title": btn_title, "payload": payload}])
        state["idx"] = next_idx
    else:
        send_msg(token, rid, "🌹 تقبل الله طاعتكم وحسن خاتمتكم")
        if rid in user_reading_state:
            del user_reading_state[rid]

# === معالجة اختيار الاستماع/القراءة ===
def handle_choice(token, rid, action, surah_num):
    surah_num = int(surah_num)
    if action == "LISTEN":
        send_msg(token, rid, "🎧 جاري إرسال التلاوة...")
        audio_url = f"https://server8.mp3quran.net/afs/{surah_num:03d}.mp3"
        send_audio(token, rid, audio_url)
    elif action == "READ":
        start_reading(token, rid, surah_num)

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
                    txt = event["message"]["text"]
                    # نأخذ الـ payload من الزر إن وُجد، وإلا نأخذ النص العادي
                    action_payload = event.get("message", {}).get("quick_reply", {}).get("payload", txt)
                    
                    # 1. أزرار القراءة التفاعلية (الجزء التالي)
                    if action_payload.startswith("NEXT_"):
                        parts = action_payload.split("_")
                        continue_reading(token, sender, parts[1], int(parts[2]))
                    elif action_payload.startswith("DONE_"):
                        s_num = action_payload.split("_")[1]
                        send_msg(token, sender, "🌹 تقبل الله طاعتكم")
                        if sender in user_reading_state: del user_reading_state[sender]
                        
                    # 2. أزرار الاختيار الأولية (استماع / قراءة)
                    elif action_payload.startswith("LISTEN_") or action_payload.startswith("READ_"):
                        act, s_num = action_payload.split("_")
                        handle_choice(token, sender, act, s_num)
                        
                    # 3. طلب سورة جديد بالاسم أو الرقم
                    elif txt in SURAH_NAMES or (txt.isdigit() and 1 <= int(txt) <= 114):
                        num = int(txt) if txt.isdigit() else SURAH_NAMES[txt]
                        name = list(SURAH_NAMES.keys())[list(SURAH_NAMES.values()).index(num)]
                        send_msg(token, sender, f"📖 سورة {name}\nاختر ما تفضل:", [
                            {"content_type": "text", "title": "🎧 الاستماع", "payload": f"LISTEN_{num}"},
                            {"content_type": "text", "title": "📖 القراءة", "payload": f"READ_{num}"}
                        ])
                    else:
                        send_msg(token, sender, "🌹 أهلاً بك! أرسل اسم أو رقم سورة للبدء.")
                        
            except Exception as e:
                logging.error(f"خطأ Webhook: {e}")

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
