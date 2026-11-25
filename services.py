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

    try:
        # مصدر Swissquote المباشر (يعمل من أي خادم سحابي بدون حظر)
        url = "https://swissquote.com"
        data = requests.get(url, headers=headers, timeout=10).json()
        first_item = next(iter(data))
        prices = first_item.get("spreadProfilePrices", [])
        first_price = next(iter(prices))
        bid = float(first_price.get("bid", 0))
        ask = float(first_price.get("ask", 0))
        ounce = round((bid + ask) / 2, 2)
    except Exception:
        # مصدر احتياطي ثاني: Binance PAXG (مرتبط بسعر أونصة الذهب الحية 1:1)
        url2 = "https://binance.com"
        r2 = requests.get(url2, headers=headers, timeout=10).json()
        ounce = round(float(r2.get("lastPrice", 0)), 2)
        ch = round(float(r2.get("priceChange", 0)), 2)
        chp = round(float(r2.get("priceChangePercent", 0)), 2)

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
