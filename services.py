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
    ounce = 0.0
    prev_close = 0.0
    source_label = "SPOT XAU/USD"

    # 1. المصدر المباشر الأول: TradingView Scanner API (OANDA:XAUUSD)
    try:
        tv_url = "https://" + "://tradingview.com" + "/cfd/scan"
        payload = {
            "symbols": {"tickers": ["OANDA:XAUUSD", "FX_IDC:XAUUSD"]},
            "columns": ["close", "open", "change", "change_abs"]
        }
        tv_res = requests.post(tv_url, json=payload, timeout=5).json()
        rows = tv_res.get("data", [])
        if rows:
            first_row = next(iter(rows))
            vals = first_row.get("d", [])
            if len(vals) >= 4:
                first_val = float(next(iter(vals)))
                if first_val > 0:
                    ounce = round(first_val, 3)
                    ch_abs = float(vals[-1])
                    prev_close = round(ounce - ch_abs, 3)
                    source_label = "TV OANDA:XAUUSD"
    except Exception:
        pass

    # 2. المصدر الفوري الاحتياطي الثاني: PAXG-USD (24/7)
    if ounce <= 0:
        try:
            paxg = yf.Ticker("PAXG-USD")
            hist_p = paxg.history(period="2d")
            if not hist_p.empty:
                ounce = round(float(hist_p["Close"].iloc[-1]), 3)
                prev_close = round(float(hist_p["Close"].iloc[-2]), 3) if len(hist_p) > 1 else ounce
                source_label = "SPOT GOLD (PAXG)"
        except Exception:
            pass

    # 3. الملاذ الأخير: Yahoo Finance
    if ounce <= 0:
        ticker = yf.Ticker("GC=F")
        hist_1d = ticker.history(period="2d")
        if not hist_1d.empty:
            ounce = round(float(hist_1d["Close"].iloc[-1]), 3)
            prev_close = round(float(hist_1d["Close"].iloc[-2]), 3) if len(hist_1d) > 1 else ounce
            source_label = "GC=F"

    if prev_close <= 0:
        prev_close = ounce

    ch = round(ounce - prev_close, 3)
    chp = round((ch / prev_close) * 100, 2) if prev_close else 0.0

    buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
    sell_24k = round(buy_24k - config.SELL_SPREAD_KWD, 3) if buy_24k > 0 else 0.0
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
    spot_data = get_live_gold()
    spot_ounce = spot_data["ounce"]

    ticker = yf.Ticker("GC=F")
    if timeframe == "1m":
        hist = ticker.history(period="1d", interval="1m").tail(60)
    elif timeframe == "10m":
        raw_5m = ticker.history(period="2d", interval="5m")
        if not raw_5m.empty:
            hist = raw_5m.resample("10min").agg({
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last"
            }).dropna().tail(48)
        else:
            hist = raw_5m
    elif timeframe == "15m":
        hist = ticker.history(period="2d", interval="15m").tail(60)
    elif timeframe == "1h":
        hist = ticker.history(period="7d", interval="1h")
    else:
        hist = ticker.history(period="2mo", interval="1d")

    if hist.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close"])

    df = hist[["Open", "High", "Low", "Close"]].dropna().copy()

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
    if hist.empty:
        return hist, "لا تتوفر بيانات تاريخية كافية حالياً."

    high_30d = round(float(hist["High"].max()), 2)
    low_30d = round(float(hist["Low"].min()), 2)
    sma_20 = round(float(hist["Close"].tail(20).mean()), 2)

    delta = hist["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    last_loss = float(loss.iloc[-1]) if not pd.isna(loss.iloc[-1]) else 0.0
    last_gain = float(gain.iloc[-1]) if not pd.isna(gain.iloc[-1]) else 0.0

    if last_loss == 0:
        rsi = 100.0 if last_gain > 0 else 50.0
    else:
        rs = last_gain / last_loss
        rsi = round(100 - (100 / (1 + rs)), 1)

    tech_summary = f"أعلى سعر 30 يوم: {high_30d}$ | أدنى سعر 30 يوم: {low_30d}$ | المتوسط المتحرك 20 يوم: {sma_20}$ | مؤشر القوة النسبية (RSI 14): {rsi}"
    return hist, tech_summary

@st.cache_data(ttl=600)
def _get_cached_news():
    try:
        res = requests.get(config.RSS_NEWS_URL, timeout=4)
        feed = feedparser.parse(res.content)
        return "\n".join([entry.title for entry in feed.entries[:6]])
    except Exception:
        return "لا توجد أخبار عاجلة حالياً."

def _call_gemini_safe(prompt):
    last_error = ""
    # الاتصال المباشر بأسرع نموذج مستقر دون إضاعة الوقت في البحث عن النماذج
    for model_name in ["gemini-2.5-flash", "gemini-2.0-flash"]:
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
    news_text = _get_cached_news()
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

    news_text = _get_cached_news()

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
