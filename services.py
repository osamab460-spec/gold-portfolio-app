import json
import requests
import feedparser
from datetime import datetime
import streamlit as st
import gspread
from google import genai
import config

ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

@st.cache_resource
def init_sheets():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open_by_key(config.SPREADSHEET_ID)
    return sh.worksheet(config.SHEET_DASHBOARD_NAME), sh.worksheet(config.SHEET_LOG_NAME)

def get_live_gold():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    ounce, ch, chp = 0.0, 0.0, 0.0

    # المصدر الأول: Yahoo Finance API (لا يحظر خوادم السحابة ومجاني 100%)
    try:
        url = "https://yahoo.com"
        r = requests.get(url, headers=headers, timeout=10).json()
        meta = r["chart"]["result"][0]["meta"]
        ounce = float(meta["regularMarketPrice"])
        prev_close = float(meta.get("chartPreviousClose", ounce))
        ch = round(ounce - prev_close, 2)
        chp = round((ch / prev_close) * 100, 2) if prev_close else 0.0
    except Exception:
        # المصدر الاحتياطي: Gold-API
        res = requests.get(config.GOLD_API_URL, headers=headers, timeout=10).json()
        ounce = float(res.get("price", 0))
        ch = float(res.get("ch", 0))
        chp = float(res.get("chp", 0))

    buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
    sell_24k = round(buy_24k - config.SELL_SPREAD_KWD, 3)
    return ounce, ch, chp, buy_24k, sell_24k

def ask_ai_advisor(user_question, ounce, buy_24k, sell_24k, portfolio_rows):
    prompt = f"""أنت حاسبة ذكية ومستشار مالي لمحفظة ذهب (دار السبائك - الكويت). أجب باختصار شديد وبالعربية:
- سعر الشراء 24: {buy_24k} د.ك | سعر البيع 24: {sell_24k} د.ك | الأونصة: {ounce}$
- بيانات المحفظة: {portfolio_rows}
- سؤال المستخدم: {user_question}"""
    res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return res.text

def generate_and_send_report(sheet_dashboard, send_notifications=False):
    ounce, ch, chp, buy_24k, sell_24k = get_live_gold()
    if ounce > 0:
        sheet_dashboard.update_acell("C5", ounce)

    portfolio_rows = sheet_dashboard.get("A5:I18")
    portfolio_text = "\n".join([" | ".join(r) for r in portfolio_rows if r])
    targets_rows = sheet_dashboard.get("A19:B21")
    targets_text = "\n".join([" | ".join(r) for r in targets_rows if r])

    feed = feedparser.parse(config.RSS_NEWS_URL)
    news_text = "\n".join([entry.title for entry in feed.entries[:7]])

    now_kw = datetime.now(config.KUWAIT_TZ).strftime("%A, %Y-%m-%d %H:%M")
    prompt = config.build_report_prompt(now_kw, ounce, ch, chp, buy_24k, portfolio_text, targets_text, news_text)

    res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    report_text = res.text

    if send_notifications:
        tg_token = st.secrets.get("TELEGRAM_TOKEN", "")
        if tg_token:
            tg_url = f"https://telegram.org{tg_token}/sendMessage"
            requests.post(tg_url, json={"chat_id": config.CHAT_ID, "text": report_text, "parse_mode": "HTML"}, timeout=15)

        wa_url = f"https://callmebot.com{config.WHATSAPP_PHONE}&apikey={config.WHATSAPP_APIKEY}&text={requests.utils.quote(report_text[:900])}"
        requests.get(wa_url, timeout=15)

    return report_text
