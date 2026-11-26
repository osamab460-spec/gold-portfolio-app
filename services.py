import json
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

def _get_spot_ticker():
    # XAUUSD=X هو السعر الفوري للذهب (Spot Gold) المطابق لتسعيرة دار السبائك
    for sym in ["XAUUSD=X", "PAXG-USD", "GC=F"]:
        t = yf.Ticker(sym)
        h = t.history(period="2d")
        if not h.empty:
            return t
    return yf.Ticker("GC=F")

def get_live_gold():
    ticker = _get_spot_ticker()
    hist_1m = ticker.history(period="1d", interval="1m")
    hist_1d = ticker.history(period="2d")

    ounce = round(float(hist_1m["Close"].iloc[-1]), 3) if not hist_1m.empty else round(float(hist_1d["Close"].iloc[-1]), 3)
    prev_close = round(float(hist_1d["Close"].iloc[-2]), 3) if len(hist_1d) > 1 else ounce
    ch = round(ounce - prev_close, 3)
    chp = round((ch / prev_close) * 100, 2) if prev_close else 0.0

    buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
    sell_24k = round(buy_24k - config.SELL_SPREAD_KWD, 3)
    k22 = round(buy_24k * (22 / 24), 3)
    k21 = round(buy_24k * (21 / 24), 3)
    k18 = round(buy_24k * (18 / 24), 3)

    return {"ounce": ounce, "ch": ch, "chp": chp, "buy_24k": buy_24k, "sell_24k": sell_24k, "k22": k22, "k21": k21, "k18": k18}

def get_candlestick_data(timeframe="15m", unit="KWD"):
    ticker = _get_spot_ticker()
    if timeframe == "10m":
        hist = ticker.history(period="1d", interval="5m").tail(40)
    elif timeframe == "15m":
        hist = ticker.history(period="2d", interval="15m").tail(60)
    elif timeframe == "1h":
        hist = ticker.history(period="7d", interval="1h")
    else:
        hist = ticker.history(period="2mo", interval="1d")

    df = hist[["Open", "High", "Low", "Close"]].copy()
    if unit == "KWD":
        df = (df * (config.KUWAIT_FACTOR / config.OUNCE_TO_GRAM)).round(3)
    else:
        df = df.round(2)
    return df

def get_chart_and_technicals():
    ticker = _get_spot_ticker()
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
- سعر الشراء 24: {buy_24k} د.ك | سعر البيع 24: {sell_24k} د.ك | الأونصة: {ounce}$
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
        tg_token = st.secrets.get("TELEGRAM_TOKEN", "")
        if tg_token:
            tg_url = f"https://telegram.org{tg_token}/sendMessage"
            requests.post(tg_url, json={"chat_id": config.CHAT_ID, "text": report_text, "parse_mode": "HTML"}, timeout=15)

        wa_url = f"https://callmebot.com{config.WHATSAPP_PHONE}&apikey={config.WHATSAPP_APIKEY}&text={requests.utils.quote(report_text[:900])}"
        requests.get(wa_url, timeout=15)

    return report_text
