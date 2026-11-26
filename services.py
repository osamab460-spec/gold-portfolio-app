import json
import urllib.parse
import requests
import feedparser
from datetime import datetime
import streamlit as st
import gspread
from google import genai
import yfinance as yf
import pandas as pd
import config

ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"].strip())

@st.cache_resource
def init_sheets():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open_by_key(config.SPREADSHEET_ID)
    return sh.worksheet(config.SHEET_DASHBOARD_NAME), sh.worksheet(config.SHEET_LOG_NAME)

@st.cache_data(ttl=15)
def get_live_gold():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://" + "goldprice.org/"
    }
    ounce = 0.0
    prev_close = 0.0
    source_label = "SPOT XAU/USD"

    # 1. المصدر الفوري الأول (GoldPrice API بالمسار الكامل)
    try:
        gp_url = "https://" + "data-asg.goldprice.org" + "/dbXRates/USD"
        gp_data = requests.get(gp_url, headers=headers, timeout=6).json()
        items = gp_data.get("items", [])
        if items:
            first_item = next(iter(items))
            ounce = round(float(first_item.get("xauPrice", 0)), 3)
            prev_close = round(float(first_item.get("xauClose", ounce)), 3)
    except Exception:
        pass

    # 2. المصدر الفوري الثاني (Swissquote Spot API بالمسار الكامل)
    if ounce <= 0:
        try:
            sq_url = "https://" + "://swissquote.com" + "/public-quotes/bboquotes/instrument/XAU/USD"
            sq_data = requests.get(sq_url, headers=headers, timeout=6).json()
            first_sq = next(iter(sq_data))
            prices = first_sq.get("spreadProfilePrices", [])
            first_price = next(iter(prices))
            ounce = round((float(first_price.get("bid", 0)) + float(first_price.get("ask", 0))) / 2, 3)
        except Exception:
            pass

    # 3. المصدر الفوري الثالث (Gold-API)
    if ounce <= 0:
        try:
            gapi_url = "https://" + "://gold-api.com" + "/price/XAU"
            r3 = requests.get(gapi_url, timeout=5).json()
            if float(r3.get("price", 0)) > 0:
                ounce = round(float(r3["price"]), 3)
        except Exception:
            pass

    # 4. الملاذ الأخير (Yahoo Finance)
    if ounce <= 0 or prev_close <= 0:
        ticker = yf.Ticker("GC=F")
        hist_1d = ticker.history(period="2d")
        if prev_close <= 0 and len(hist_1d) > 1:
            prev_close = round(float(hist_1d["Close"].iloc[-2]), 3)
        if ounce <= 0:
            ounce = round(float(hist_1d["Close"].iloc[-1]), 3)
            source_label = "GC=F"

    ch = round(ounce - prev_close, 3)
    chp = round((ch / prev_close) * 100, 2) if prev_close else 0.0

    # حساب أسعار الشراء والبيع المطابقة لدار السبائك
    buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
    sell_24k = round(buy_24k - config.SELL_SPREAD_KWD, 3)
    k22 = round(buy_24k * (22 / 24), 3)
    k21 = round(buy_24k * (21 / 24), 3)
    k18 = round(buy_24k * (18 / 24), 3)

    return {
        "ounce": ounce,
        "ch": ch,
        "chp": chp,
        "buy_24k": buy_24k,
        "sell_24k": sell_24k,
        "k22": k22,
        "k21": k21,
        "k18": k18,
        "source": source_label
    }

@st.cache_data(ttl=30)
def get_candlestick_data(timeframe="1m", unit="KWD"):
    # معايرة الشموع مع السعر الفوري لإزالة فجوة العقود الآجلة
    spot_data = get_live_gold()
    spot_ounce = spot_data["ounce"]

    ticker = yf.Ticker("GC=F")
    if timeframe == "1m":
        hist = ticker.history(period="1d", interval="1m").tail(60)
    elif timeframe == "10m":
        hist = ticker.history(period="1d", interval="5m").tail(48)
    elif timeframe == "15m":
        hist = ticker.history(period="2d", interval="15m").tail(60)
    elif timeframe == "1h":
        hist = ticker.history(period="7d", interval="1h")
    else:
        hist = ticker.history(period="2mo", interval="1d")

    df = hist[["Open", "High", "Low", "Close"]].dropna().copy()

    # خصم فارق العقود الآجلة تلقائياً لتتطابق الشموع مع السعر الفوري لدار السبائك
    if not df.empty and spot_ounce > 0:
        futures_last = float(df["Close"].iloc[-1])
        spread_offset = futures_last - spot_ounce
        df = df - spread_offset

    if unit == "KWD":
        df = (df * (config.KUWAIT_FACTOR / config.OUNCE_TO_GRAM)).round(3)
    else:
        df = df.round(2)
    return df

@st.cache_data(ttl=300)
def get_chart_and_technicals():
    ticker = yf.Ticker("GC=F")
    hist = ticker.history(period="1mo")
    high_30d = round(float(hist["High"].max()), 2)
    low_30d = round(float(hist["Low"].min()), 2)
    sma_20 = round(float(hist["Close"].tail(20).mean()), 2)
    delta = hist["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = round(float(100 - (100 / (1 + rs.iloc[-1]))), 1)
    tech_summary = f"أعلى سعر 30 يوم: {high_30d}$ | أدنى سعر 30 يوم: {low_30d}$ | المتوسط المتحرك 20 يوم: {sma_20}$ | مؤشر القوة النسبية (RSI 14): {rsi}"
    return hist, tech_summary

def _call_gemini_safe(prompt):
    models_to_try = ["gemini-3.8-flash", "gemini-3-flash-preview", "gemini-2.5-flash"]
    try:
        for m in ai_client.models.list():
            name = m.name.replace("models/", "")
            if "flash" in name and name not in models_to_try:
                models_to_try.append(name)
    except Exception:
        pass

    last_error = ""
    for model_name in models_to_try:
        try:
            res = ai_client.models.generate_content(model=model_name, contents=prompt)
            return res.text
        except Exception as e:
            last_error = str(e)
            continue
    return f"⚠️ تعذر الاتصال بالذكاء الاصطناعي. السبب: {last_error}"

def ask_ai_advisor(user_question, ounce, buy_24k, sell_24k, portfolio_rows):
    prompt = f"""أنت حاسبة ذكية ومستشار مالي لمحفظة ذهب (دار السبائك - الكويت). أجب باختصار شديد وبالعربية:
- سعر الشراء 24: {buy_24k} د.ك | سعر البيع 24: {sell_24k} د.ك | الأونصة الفورية: {ounce}$
- بيانات المحفظة: {portfolio_rows}
- سؤال المستخدم: {user_question}"""
    return _call_gemini_safe(prompt)

def suggest_best_buy_zones(ounce, buy_24k, avg_cost, balance):
    _, tech_summary = get_chart_and_technicals()
    feed = feedparser.parse(config.RSS_NEWS_URL)
    news_text = "\n".join([entry.title for entry in feed.entries[:6]])
    prompt = config.build_buy_zones_prompt(ounce, buy_24k, avg_cost, balance, tech_summary, news_text)
    return _call_gemini_safe(prompt)

def generate_and_send_report(sheet_dashboard, send_notifications=False):
    data = get_live_gold()
    ounce, ch, chp, buy_24k = data["ounce"], data["ch"], data["chp"], data["buy_24k"]
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

    report_text = _call_gemini_safe(prompt)

    if send_notifications and not report_text.startswith("⚠️"):
        tg_token = st.secrets.get("TELEGRAM_TOKEN", "").strip()
        if tg_token:
            tg_url = "https://" + "api.telegram.org" + "/bot" + tg_token + "/sendMessage"
            requests.post(tg_url, json={"chat_id": config.CHAT_ID, "text": report_text, "parse_mode": "HTML"}, timeout=15)

        encoded_msg = urllib.parse.quote(report_text[:900])
        wa_url = "https://" + "://callmebot.com" + "/whatsapp.php?phone=" + str(config.WHATSAPP_PHONE) + "&apikey=" + str(config.WHATSAPP_APIKEY) + "&text=" + encoded_msg
        requests.get(wa_url, timeout=15)

    return report_text
