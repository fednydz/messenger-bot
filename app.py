import os
import requests
import yt_dlp
from flask import Flask, request
from pathlib import Path

app = Flask(__name__)

# متغيرات الماسنجر
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_verify_123")

# دالة إرسال رسائل الماسنجر
def send_messenger(recipient_id, text):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    data = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    requests.post(url, params=params, json=data)

# دالة إرسال فيديو عبر الماسنجر
def send_video(recipient_id, video_path, caption=""):
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    
    # إرسال كـ video_url إذا كان رابط
    if video_path.startswith("http"):
        data = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "video",
                    "payload": {
                        "url": video_path
                    }
                }
            }
        }
    else:
        # إرسال كملف مرفوع
        data = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "video",
                    "payload": {}
                }
            }
        }
    
    try:
        response = requests.post(url, params=params, json=data)
        return response.json()
    except Exception as e:
        print(f"خطأ في إرسال الفيديو: {e}")
        return None

# التحقق من رابط Facebook Reel أو فيديو
def is_facebook_video(url):
    """التحقق إذا كان الرابط فيديو فيسبوك أو Reel"""
    facebook_patterns = [
        "facebook.com/reel/",
        "facebook.com/reels/",
        "fb.watch/",
        "facebook.com/watch/",
        "facebook.com/videos/",
        "m.facebook.com/reel/",
    ]
    return any(pattern in url for pattern in facebook_patterns)

# تحميل فيديو Facebook Reel
def download_facebook_video(url):
    """تحميل فيديو من فيسبوك باستخدام yt-dlp"""
    output_dir = Path("downloads")
    output_dir.mkdir(exist_ok=True)
    
    ydl_opts = {
        "outtmpl": f"{output_dir}/%(id)s.%(ext)s",
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            video_url = info.get("url", filename)
            return Path(filename), video_url
    except Exception as e:
        print(f"خطأ في التحميل: {e}")
        return None, None

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
                sender_id = event["sender"]["id"]
                
                # تجاهل الرسائل المرسلة من البوت نفسه
                if "message" in event and "text" in event["message"]:
                    user_text = event["message"]["text"].strip()
                    
                    # التحقق إذا كان رابط فيديو فيسبوك
                    if is_facebook_video(user_text):
                        # إرسال رسالة جاري التحميل
                        send_messenger(sender_id, "⏳ جاري تحميل الفيديو...")
                        
                        # تحميل الفيديو
                        file_path, video_url = download_facebook_video(user_text)
                        
                        if file_path and file_path.exists():
                            # إرسال الفيديو
                            send_messenger(sender_id, "✅ تم التحميل! إليك الفيديو:")
                            send_video(sender_id, str(file_path))
                            
                            # حذف الملف المؤقت
                            try:
                                file_path.unlink()
                            except:
                                pass
                        else:
                            send_messenger(sender_id, "❌ فشل تحميل الفيديو. تأكد من أن الرابط صحيح وأن الفيديو عام.")
                    else:
                        # رد عادي
                        send_messenger(sender_id, f"📘 ماسنجر: استلمت: '{user_text}'\n🤖 سأرد قريباً!\n\n💡 أرسل رابط Facebook Reel لتحميله!")

    elif obj == "instagram":
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event["sender"]["id"]
                if "message" in event and "text" in event["message"]:
                    user_text = event["message"]["text"]
                    send_instagram(sender_id, f"📸 انستقرام: استلمت: '{user_text}'\n🤖 سأرد قريباً!")

    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
