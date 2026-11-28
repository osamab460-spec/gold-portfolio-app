import re
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

# ================== Google Sheets ==================
@st.cache_resource
def init_sheets():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open_by_key(config.SPREADSHEET_ID)
    return sh.worksheet(config.SHEET_DASHBOARD_NAME), sh.worksheet(config.SHEET_LOG_NAME)

# ================== السعر الحي (مباشر من دار السبائك) ==================
@st.cache_data(ttl=15)
def get_live_gold():
    ounce = 0.0
    chp = 0.0
    buy_24k = 0.0
    sell_24k = 0.0
    source_label = "AlSabaek Website"

    # 1) جلب الأسعار مباشرة من رابط الـ API الخاص بموقع دار السبائك
    try:
        # هذا هو الرابط الخفي الذي يستخدمه الموقع لجلب الأسعار
        url = "https://www.alsabaek.com/api/gold-prices"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.alsabaek.com/"
        }
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            
            # البحث عن أسعار عيار 24 داخل الاستجابة (الاسم قد يكون مختلفاً قليلاً)
            # نقوم بالبحث الديناميكي عن كلمة 24 ثم سعر الشراء والبيع
            items = data if isinstance(data, list) else data.get('data', [])
            for item in items:
                name = str(item.get('name', item.get('karat', '')))
                if '24' in name:
                    buy_24k = float(item.get('buy_price', item.get('buy', 0.0)))
                    sell_24k = float(item.get('sell_price', item.get('sell', 0.0)))
                    break
                    
            # محاولة جلب سعر الأونصة إذا كان متوفراً
            if isinstance(data, dict) and 'ounce_price' in data:
                ounce = float(data['ounce_price'])
                
    except Exception as e:
        print(f"Scraping Error: {e}")

    # 2) خطة بديلة (Fallback) في حال تعطل الموقع
    if buy_24k <= 0 or sell_24k <= 0:
        source_label = "TradingView (Fallback)"
        try:
            tv_url = "https://scanner.tradingview.com/symbol?symbol=OANDA%3AXAUUSD&fields=close,change"
            tv_res = requests.get(tv_url, headers=config.RSS_HEADERS, timeout=6).json()
            if isinstance(tv_res, dict) and tv_res.get("close"):
                ounce = round(float(tv_res["close"]), 3)
                chp = round(float(tv_res.get("change") or 0.0), 2)
                buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
                sell_24k = round(buy_24k - config.SELL_SPREAD_KWD, 3)
        except Exception:
            pass

    # 3) حساب باقي العيارات بناءً على سعر عيار 24
    k22_buy = round(buy_24k * (22 / 24), 3)
    k21_buy = round(buy_24k * (21 / 24), 3)
    k18_buy = round(buy_24k * (18 / 24), 3)
    
    k22_sell = round(sell_24k * (22 / 24), 3)
    k21_sell = round(sell_24k * (21 / 24), 3)
    k18_sell = round(sell_24k * (18 / 24), 3)

    return {
        "ounce": ounce,
        "ch": 0.0,
        "chp": chp,
        "buy_24k": buy_24k,
        "sell_24k": sell_24k,
        "k22": k22_buy,
        "k21": k21_buy,
        "k18": k18_buy,
        "k22_sell": k22_sell,
        "k21_sell": k21_sell,
        "k18_sell": k18_sell,
        "source": source_label,
    }

# ================== الشموع ==================
@st.cache_data(ttl=30)
def get_candlestick_data(timeframe="1m", unit="KWD"):
    spot_data = get_live_gold()
    spot_ounce = spot_data["ounce"]

    ticker = yf.Ticker("GC=F")
    try:
        if timeframe == "1m":
            hist = ticker.history(period="1d", interval="1m").tail(60)
        elif timeframe == "10m":
            raw_5m = ticker.history(period="2d", interval="5m")
            if not raw_5m.empty:
                hist = (
                    raw_5m.resample("10min")
                    .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
                    .dropna()
                    .tail(48)
                )
            else:
                hist = raw_5m
        elif timeframe == "15m":
            hist = ticker.history(period="2d", interval="15m").tail(60)
        elif timeframe == "1h":
            hist = ticker.history(period="7d", interval="1h")
        else:
            hist = ticker.history(period="2mo", interval="1d")
    except Exception as e:
        print(f"YF Error: {e}")
        return pd.DataFrame(columns=["Open", "High", "Low", "Close"])

    if hist is None or hist.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close"])

    df = hist[["Open", "High", "Low", "Close"]].dropna().copy()

    if not df.empty and spot_ounce > 0:
        futures_last = float(df["Close"].iloc[-1])
        spread_offset = futures_last - spot_ounce
        if abs(spread_offset) < 50:
            df = df - spread_offset

    if unit == "KWD":
        df = (df * (config.KUWAIT_FACTOR / config.OUNCE_TO_GRAM)).round(3)
    else:
        df = df.round(2)

    return df

# ================== التحليل الفني ==================
@st.cache_data(ttl=300)
def get_chart_and_technicals():
    hist = yf.Ticker("GC=F").history(period="1mo")
    if hist is None or hist.empty:
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
        rsi = round(100 - (100 / (1 + last_gain / last_loss)), 1)

    tech_summary = (
        f"أعلى سعر 30 يوم: {high_30d}$ | أدنى سعر 30 يوم: {low_30d}$ | "
        f"المتوسط المتحرك 20 يوم: {sma_20}$ | مؤشر القوة النسبية (RSI 14): {rsi}"
    )
    return hist, tech_summary

# ================== الأخبار ==================
@st.cache_data(ttl=600)
def _get_cached_news():
    titles = []
    for url in config.RSS_NEWS_URLS:
        try:
            res = requests.get(url, timeout=5, headers=config.RSS_HEADERS)
            if res.status_code != 200:
                continue
            feed = feedparser.parse(res.content)
            titles.extend([entry.title for entry in feed.entries[:4]])
            if len(titles) >= 6:
                break
        except Exception:
            continue
    return "\n".join(titles[:6]) if titles else "لا توجد أخبار عاجلة حالياً."

# ================== Gemini ==================
@st.cache_data(ttl=3600)
def _get_available_flash_models():
    models = list(config.GEMINI_MODELS)
    try:
        for m in ai_client.models.list():
            name = m.name.replace("models/", "")
            if "flash" in name and name not in models:
                models.append(name)
    except Exception:
        pass
    return models

def _call_gemini_safe(prompt):
    last_error = ""
    for model_name in _get_available_flash_models():
        try:
            res = ai_client.models.generate_content(model=model_name, contents=prompt)
            txt = getattr(res, "text", None)
            if txt:
                return txt
        except Exception as e:
            last_error = str(e)
            continue
    return f"⚠️ تعذر الاتصال بالذكاء الاصطناعي. السبب: {last_error or 'غير معروف'}"

def ask_ai_advisor(user_question, ounce, buy_24k, sell_24k, portfolio_rows):
    prompt = (
        "أنت حاسبة ذكية ومستشار مالي لمحفظة ذهب (دار السبائك - الكويت). أجب باختصار شديد وبالعربية:\n"
        f"- سعر الشراء 24: {buy_24k} د.ك | سعر البيع 24: {sell_24k} د.ك | الأونصة الفورية: {ounce}$\n"
        f"- بيانات المحفظة: {portfolio_rows}\n"
        f"- سؤال المستخدم: {user_question}"
    )
    return _call_gemini_safe(prompt)

def suggest_best_buy_zones(ounce, buy_24k, avg_cost, balance):
    _, tech_summary = get_chart_and_technicals()
    news_text = _get_cached_news()
    prompt = config.build_buy_zones_prompt(ounce, buy_24k, avg_cost, balance, tech_summary, news_text)
    return _call_gemini_safe(prompt)

# ================== التقارير ==================
def _clean_telegram_token(raw):
    raw = (raw or "").strip().strip('"').strip("'")
    if "bot" in raw and "/" in raw:
        return next(iter(raw.split("bot")[-1].split("/")))
    return raw

def generate_and_send_report(sheet_dashboard, send_notifications=False):
    data = get_live_gold()
    ounce, ch, chp, buy_24k = data["ounce"], data["ch"], data["chp"], data["buy_24k"]
    if ounce > 0:
        sheet_dashboard.update_acell("C5", ounce)

    portfolio_text = "\n".join([" | ".join(r) for r in sheet_dashboard.get("A5:I18") if r])
    targets_text = "\n".join([" | ".join(r) for r in sheet_dashboard.get("A20:B24") if r])
    news_text = _get_cached_news()

    now_kw = datetime.now(config.KUWAIT_TZ).strftime("%A, %Y-%m-%d %H:%M")
    prompt = config.build_report_prompt(now_kw, ounce, ch, chp, buy_24k, portfolio_text, targets_text, news_text)
    report_text = _call_gemini_safe(prompt)

    status_notes = []
    if send_notifications and not report_text.startswith("⚠️"):
        # ---------- Telegram ----------
        tg_token = _clean_telegram_token(st.secrets.get("TELEGRAM_TOKEN", ""))
        if not tg_token:
            status_notes.append("❌ تيليجرام: مفتاح TELEGRAM_TOKEN غير موجود.")
        else:
            tg_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            try:
                res = requests.post(
                    tg_url,
                    json={"chat_id": config.CHAT_ID, "text": report_text[:4000], "parse_mode": "HTML"},
                    timeout=15,
                )
                if res.status_code == 200:
                    status_notes.append("✅ تيليجرام: تم الإرسال.")
                else:
                    clean_text = re.sub(r"<[^>]+>", "", report_text)[:4000]
                    res2 = requests.post(tg_url, json={"chat_id": config.CHAT_ID, "text": clean_text}, timeout=15)
                    if res2.status_code == 200:
                        status_notes.append("✅ تيليجرام: تم الإرسال (نص عادي).")
                    else:
                        status_notes.append(f"❌ تيليجرام فشل ({res2.status_code}): {res2.text[:120]}")
            except Exception as e:
                status_notes.append(f"❌ تيليجرام: {e}")

        # ---------- WhatsApp (CallMeBot) ----------
        try:
            encoded_msg = urllib.parse.quote(re.sub(r"<[^>]+>", "", report_text)[:900])
            wa_url = (
                f"https://api.callmebot.com/whatsapp.php"
                f"?phone={config.WHATSAPP_PHONE}&apikey={config.WHATSAPP_APIKEY}&text={encoded_msg}"
            )
            wa_res = requests.get(wa_url, timeout=15)
            status_notes.append("✅ واتساب: تم الإرسال." if wa_res.status_code == 200 else f"⚠️ واتساب: كود {wa_res.status_code}")
        except Exception as e:
            status_notes.append(f"⚠️ واتساب: {e}")

    header_status = "<br>".join(status_notes) + "<hr>" if status_notes else ""
    return header_status + report_text
