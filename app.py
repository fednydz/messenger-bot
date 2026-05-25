from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
import os
import logging
import requests
from groq import Groq
from datetime import datetime

# إعداد التطبيق
app = FastAPI(title="Facebook AI Bot")

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# إعدادات المتغيرات البيئية
class Settings:
    FACEBOOK_PAGE_TOKEN: str = os.getenv("FACEBOOK_PAGE_TOKEN", "")
    FACEBOOK_APP_SECRET: str = os.getenv("FACEBOOK_APP_SECRET", "")
    FACEBOOK_VERIFY_TOKEN: str = os.getenv("FACEBOOK_VERIFY_TOKEN", "201638725")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    PORT: int = int(os.getenv("PORT", 8000))

settings = Settings()

# تهيئة عميل Groq
groq_client = Groq(api_key=settings.GROQ_API_KEY)

# موجه النظام للذكاء الاصطناعي
SYSTEM_PROMPT = """
أنت مساعد ذكي لخدمة العملاء لصفحة فيسبوك.
- رد بلغة المستخدم (عربي/إنجليزي).
- كن مختصراً ومفيداً (2-3 جمل كحد أقصى).
- كن ودوداً ومهنياً.
- إذا كان السؤال خارج نطاقك، اعتذر بلطف واطلب التواصل عبر الرسالة الخاصة.
- لا تذكر أنك ذكاء اصطناعي إلا إذا سُئلت مباشرة.
- استخدم الإيموجي باعتدال 😊
"""

def generate_ai_reply(comment_text: str, post_context: str = "") -> str:
    """توليد رد ذكي باستخدام Groq API"""
    try:
        prompt = f"""
        سياق المنشور: {post_context}
        التعليق: {comment_text}
        
        الرد المناسب:
        """
        
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150,
            timeout=10
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        logger.error(f"❌ خطأ في Groq API: {e}")
        return "شكراً لتعليقك! 🙏 سيقوم فريقنا بالرد عليك قريباً."

def reply_to_facebook_comment(comment_id: str, reply_text: str) -> dict:
    """إرسال رد على تعليق في فيسبوك"""
    try:
        url = f"https://graph.facebook.com/v21.0/{comment_id}/comments"
        params = {
            "message": reply_text,
            "access_token": settings.FACEBOOK_PAGE_TOKEN
        }
        
        response = requests.post(url, params=params, timeout=10)
        result = response.json()
        
        if response.status_code == 200:
            logger.info(f"✅ تم الرد على التعليق {comment_id} بنجاح")
        else:
            logger.error(f"❌ فشل الرد على التعليق: {result}")
        
        return result
    
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال الرد: {e}")
        return {"error": str(e)}

@app.get("/")
async def root():
    """صفحة رئيسية للتحقق من عمل التطبيق"""
    return {
        "status": "🤖 Facebook AI Bot is running!",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token")
):
    """
    التحقق من Webhook عند الإعداد الأولي من فيسبوك
    """
    logger.info(f"🔍 Webhook verification: mode={hub_mode}, token={hub_verify_token}")
    
    if hub_mode == "subscribe" and hub_verify_token == settings.FACEBOOK_VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully")
        return PlainTextResponse(content=hub_challenge)
    else:
        logger.error("❌ Webhook verification failed")
        raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook")
async def handle_webhook(request: Request):
    """
    معالجة أحداث فيسبوك (تعليقات جديدة، رسائل، إلخ)
    """
    try:
        data = await request.json()
        logger.info(f"📥 Received webhook: {data}")
        
        # التحقق من أن الحدث من صفحة
        if data.get("object") != "page":
            return JSONResponse(content={"status": "ignored - not a page object"})
        
        # معالجة كل entry في البيانات
        for entry in data.get("entry", []):
            # معالجة التغييرات في الـ feed (تعليقات جديدة)
            for change in entry.get("changes", []):
                if change.get("field") == "feed":
                    value = change.get("value", {})
                    
                    # استخراج معلومات التعليق
                    comment_id = value.get("comment_id")
                    post_id = value.get("post_id")
                    message = value.get("message", "")
                    sender_info = value.get("from", {})
                    sender_name = sender_info.get("name", "Unknown")
                    
                    # تجاهل إذا كان التعليق من البوت نفسه
                    if "AI Bot" in sender_name or "Bot" in sender_name:
                        logger.info("⏭️ Skipping comment from bot itself")
                        continue
                    
                    # تجاهل التعليقات الفارغة
                    if not message or not comment_id:
                        logger.warning("⚠️ Empty message or comment_id")
                        continue
                    
                    logger.info(f"💬 New comment from {sender_name}: {message[:50]}...")
                    
                    # توليد الرد الذكي
                    ai_reply = generate_ai_reply(
                        comment_text=message,
                        post_context=f"Post ID: {post_id}"
                    )
                    
                    logger.info(f"🤖 AI Reply: {ai_reply}")
                    
                    # إرسال الرد إلى فيسبوك
                    if comment_id and ai_reply:
                        reply_result = reply_to_facebook_comment(comment_id, ai_reply)
                        logger.info(f"📤 Reply result: {reply_result}")
        
        return JSONResponse(content={"status": "success", "message": "Webhook processed"})
    
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """فحص صحة التطبيق"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "facebook-ai-bot"
    }

@app.get("/test-ai")
async def test_ai():
    """اختبار الذكاء الاصطناعي"""
    try:
        test_comment = "مرحباً، كيف يمكنني المساعدة؟"
        reply = generate_ai_reply(test_comment)
        return {
            "test_comment": test_comment,
            "ai_reply": reply,
            "status": "success"
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "failed"
        }

# تشغيل التطبيق
if __name__ == "__main__":
    import uvicorn
    logger.info(f"🚀 Starting server on port {settings.PORT}")
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=(settings.PORT == 8000),  # فقط في التطوير المحلي
        log_level="info"
    )
