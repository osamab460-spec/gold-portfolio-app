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

def get_live_gold():
    ticker = yf.Ticker("GC=F")
    hist = ticker.history(period="2d")
    
    ounce = round(float(hist["Close"].iloc[-1]), 2)
    prev_close = round(float(hist["Close"].iloc[-2]), 2) if len(hist) > 1 else ounce
    ch = round(ounce - prev_close, 2)
    chp = round((ch / prev_close) * 100, 2) if prev_close else 0.0

    buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
    sell_24k = round(buy_24k - config.SELL_SPREAD_KWD, 3)
    return ounce, ch, chp, buy_24k, sell_24k

def get_pro_chart_data(timeframe="1D"):
    ticker = yf.Ticker("GC=F")
    if timeframe == "1H":
        hist = ticker.history(period="5d", interval="1h")
    else:
        hist = ticker.history(period="2mo", interval="1d")
    
    df = pd.DataFrame(index=hist.index)
    factor = config.KUWAIT_FACTOR / config.OUNCE_TO_GRAM
    df["Open"] = (hist["Open"] * factor).round(3)
    df["High"] = (hist["High"] * factor).round(3)
    df["Low"] = (hist["Low"] * factor).round(3)
    df["Close"] = (hist["Close"] * factor).round(3)
    
    # المتوسط المتحرك الأسي السريع (EMA 9) والبولينجر باند (20)
    df["EMA9"] = df["Close"].ewm(span=9, adjust=False).mean().round(3)
    df["SMA20"] = df["Close"].rolling(window=20).mean().round(3)
    std20 = df["Close"].rolling(window=20).std()
    df["UpperBB"] = (df["SMA20"] + (std20 * 2)).round(3)
    df["LowerBB"] = (df["SMA20"] - (std20 * 2)).round(3)

    # حساب مؤشر القوة النسبية RSI (14) لكل شمعة للرسم البياني
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = (100 - (100 / (1 + rs))).round(1)

    # ملخص المؤشرات الفنية للذكاء الاصطناعي
    high_period = round(float(hist["High"].tail(30).max()), 2)
    low_period = round(float(hist["Low"].tail(30).min()), 2)
    sma_20_usd = round(float(hist["Close"].tail(20).mean()), 2)
    last_rsi = df["RSI"].iloc[-1] if not pd.isna(df["RSI"].iloc[-1]) else 50.0
    
    tech_summary = f"أعلى سعر (30 شمعة): {high_period}$ | أدنى سعر: {low_period}$ | المتوسط المتحرك 20: {sma_20_usd}$ | مؤشر القوة النسبية (RSI 14): {last_rsi}"
    return df, tech_summary

def get_economic_radar():
    feed = feedparser.parse(config.RSS_NEWS_URL)
    high_impact_keywords = ["FOMC", "CPI", "NFP", "Non-Farm", "Powell", "Interest Rate", "Inflation", "Fed "]
    alerts = []
    for entry in feed.entries[:10]:
        title = entry.title
        if any(kw.lower() in title.lower() for kw in high_impact_keywords):
            alerts.append(title)
    return alerts[:3]

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
    _, tech_summary = get_pro_chart_data("1D")
    feed = feedparser.parse(config.RSS_NEWS_URL)
    news_text = "\n".join([entry.title for entry in feed.entries[:6]])
    prompt = config.build_buy_zones_prompt(ounce, buy_24k, avg_cost, balance, tech_summary, news_text)
    return _call_gemini_safe(prompt)

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

    report_text = _call_gemini_safe(prompt)

    if send_notifications and not report_text.startswith("⚠️"):
        tg_token = st.secrets.get("TELEGRAM_TOKEN", "")
        if tg_token:
            tg_url = f"https://telegram.org{tg_token}/sendMessage"
            requests.post(tg_url, json={"chat_id": config.CHAT_ID, "text": report_text, "parse_mode": "HTML"}, timeout=15)

        wa_url = f"https://callmebot.com{config.WHATSAPP_PHONE}&apikey={config.WHATSAPP_APIKEY}&text={requests.utils.quote(report_text[:900])}"
        requests.get(wa_url, timeout=15)

    return report_text
