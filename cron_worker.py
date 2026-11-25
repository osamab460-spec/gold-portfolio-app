import os
import json
import requests
import feedparser
from datetime import datetime
import gspread
from google import genai
import yfinance as yf
import config

# قراءة المفاتيح من GitHub Secrets
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GOOGLE_CREDENTIALS = os.environ["GOOGLE_CREDENTIALS"]
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "semsem_gold_kw_99").strip()

ai_client = genai.Client(api_key=GEMINI_API_KEY)

def run_scheduled_task():
    # 1. الاتصال بالإكسل
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open_by_key(config.SPREADSHEET_ID)
    sheet_dashboard = sh.worksheet(config.SHEET_DASHBOARD_NAME)

    # 2. جلب السعر الحي
    ticker = yf.Ticker("GC=F")
    hist = ticker.history(period="2d")
    ounce = round(float(hist["Close"].iloc[-1]), 2)
    prev_close = round(float(hist["Close"].iloc[-2]), 2) if len(hist) > 1 else ounce
    ch = round(ounce - prev_close, 2)
    chp = round((ch / prev_close) * 100, 2) if prev_close else 0.0
    buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)

    if ounce > 0:
        sheet_dashboard.update_acell("C5", ounce)

    # 3. قراءة المحفظة والمستهدفات والأخبار
    portfolio_rows = sheet_dashboard.get("A5:I18")
    portfolio_text = "\n".join([" | ".join(r) for r in portfolio_rows if r])
    targets_rows = sheet_dashboard.get("A19:B21")
    targets_text = "\n".join([" | ".join(r) for r in targets_rows if r])

    feed = feedparser.parse(config.RSS_NEWS_URL)
    news_text = "\n".join([entry.title for entry in feed.entries[:7]])

    now_kw = datetime.now(config.KUWAIT_TZ).strftime("%A, %Y-%m-%d %H:%M")
    prompt = config.build_report_prompt(now_kw, ounce, ch, chp, buy_24k, portfolio_text, targets_text, news_text)

    # 4. توليد التقرير عبر Gemini
    res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    report_text = res.text

    # 5. الإرسال لتيليجرام
    if TELEGRAM_TOKEN:
        tg_url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
        requests.post(tg_url, json={"chat_id": config.CHAT_ID, "text": report_text, "parse_mode": "HTML"}, timeout=15)

    # 6. الإرسال لواتساب
    wa_url = f"https://callmebot.com{config.WHATSAPP_PHONE}&apikey={config.WHATSAPP_APIKEY}&text={requests.utils.quote(report_text[:900])}"
    requests.get(wa_url, timeout=15)

    # 7. إرسال إشعار منبثق للأندرويد عبر ntfy
    if NTFY_TOPIC:
        clean_title = f"ذهب دار السبائك: {buy_24k} د.ك | الأونصة {ounce}$"
        requests.post(
            f"https://ntfy.sh{NTFY_TOPIC}",
            data=report_text.replace("<b>", "").replace("</b>", "").encode("utf-8"),
            headers={"Title": clean_title.encode("utf-8"), "Priority": "high", "Tags": "coin,chart_with_upwards_trend"},
            timeout=15
        )
    print("Report sent successfully!")

if __name__ == "__main__":
    run_scheduled_task()
