# 🪙 دار السبائك AI — Gold Portfolio Assistant

نظام متكامل لإدارة ومتابعة محفظة الذهب في الكويت (تطبيق دار السبائك) مع:
- شريط أسعار حي (XAU/USD + عيارات 24/22/21/18 بالدينار الكويتي)
- شارت شموع يابانية تفاعلي (1m / 10m / 15m / 1h / 1d)
- مستشار ذكي (Gemini) لتحليل السوق واقتراح مناطق الشراء
- محاكي تعديل متوسط التكلفة + حاسبة زكاة تلقائية
- سجل صفقات (شراء/بيع) مع تحديث تلقائي للرصيد
- تنبيهات لحظية عبر **Telegram + ntfy + WhatsApp** (CallMeBot)
- مراقب تلقائي كل 15 دقيقة عبر **GitHub Actions**

---

## 📋 المتطلبات

- Python 3.11 أو أحدث
- حساب Google Cloud مع **Service Account** (لقراءة/كتابة Google Sheets)
- مفتاح **Gemini API** (Google AI Studio)
- بوت **Telegram** (BotFather) + `chat_id`
- (اختياري) **CallMeBot** لواتساب + **ntfy** للإشعارات الفورية

---

## 🚀 التشغيل المحلي

### 1. تثبيت الحزم
```bash
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# أو: .venv\Scripts\activate  (Windows)
pip install -r requirements.txt
