import os
import json
import urllib.parse
import requests
import feedparser
from datetime import datetime
import gspread
from google import genai
import yfinance as yf
import config

SLASH = chr(47)
SCHEME = "https:" + SLASH + SLASH

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip().strip('"').strip("'")
RAW_TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip().strip('"').strip("'")
if "bot" in RAW_TG_TOKEN and SLASH in RAW_TG_TOKEN:
    TELEGRAM_TOKEN = RAW_TG_TOKEN.split("bot")[-1].split(SLASH)
else:
    TELEGRAM_TOKEN = RAW_TG_TOKEN

GOOGLE_CREDENTIALS = os.environ["GOOGLE_CREDENTIALS"]
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "semsem_gold_kw_99").strip()

ai_client = genai.Client(api_key=GEMINI_API_KEY)

def call_gemini_safe(prompt):
    models_to_try = ["gemini-3.8-flash", "gemini-3-flash-preview", "gemini-2.5-flash"]
    try:
        for m in ai_client.models.list():
            name = m.name.replace("models" + SLASH, "")
            if "flash" in name and name not in models_to_try:
                models_to_try.append(name)
    except Exception:
        pass

    last_err = ""
    for model_name in models_to_try:
        try:
            res = ai_client.models.generate_content(model=model_name, contents=prompt)
            return res.text
        except Exception as e:
            last_err = str(e)
            continue
    raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")

def send_all_channels(title, html_message, is_urgent=False):
    if TELEGRAM_TOKEN and ":" in TELEGRAM_TOKEN:
        try:
            tg_url = SCHEME + "api.telegram.org" + SLASH + "bot" + TELEGRAM_TOKEN + SLASH + "sendMessage"
            requests.post(tg_url, json={"chat_id": config.CHAT_ID, "text": html_message, "parse_mode": "HTML"}, timeout=15)
        except Exception as e:
            print("Telegram warning:", e)

    try:
        clean_text = html_message.replace("<b>", "*").replace("</b>", "*")
        encoded_text = urllib.parse.quote(clean_text[:950])
        wa_url = SCHEME + "://callmebot.com" + SLASH + "whatsapp.php?phone=" + str(config.WHATSAPP_PHONE) + "&apikey=" + str(config.WHATSAPP_APIKEY) + "&text=" + encoded_text
        requests.get(wa_url, timeout=15)
    except Exception as e:
        print("WhatsApp warning:", e)

    if NTFY_TOPIC:
        try:
            plain_text = html_message.replace("<b>", "").replace("</b>", "")
            priority = "urgent" if is_urgent else "high"
            tags = "rotating_light,chart_with_upwards_trend" if is_urgent else "coin"
            ntfy_url = SCHEME + "ntfy.sh" + SLASH + NTFY_TOPIC
            requests.post(
                ntfy_url,
                data=plain_text.encode("utf-8"),
                headers={"Title": title.encode("utf-8"), "Priority": priority, "Tags": tags},
                timeout=15
            )
        except Exception as e:
            print("ntfy warning:", e)

def run_smart_monitor():
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open_by_key(config.SPREADSHEET_ID)
    sheet_dashboard = sh.worksheet(config.SHEET_DASHBOARD_NAME)

    # قراءة السعر اللحظي بدقة الدقيقة الواحدة (1m) لاكتشاف أي حركة سريعة في أقل من 15 دقيقة
    ticker = yf.Ticker("GC=F")
    hist_1m = ticker.history(period="1d", interval="1m")
    hist_1h = ticker.history(period="2d", interval="1h")
    hist_1d = ticker.history(period="2d")

    ounce = round(float(hist_1m["Close"].iloc[-1]), 2)
    prev_day_close = round(float(hist_1d["Close"].iloc[-2]), 2) if len(hist_1d) > 1 else ounce
    ch_day = round(ounce - prev_day_close, 2)
    chp_day = round((ch_day / prev_day_close) * 100, 2) if prev_day_close else 0.0

    buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
    sell_24k = round(buy_24k - config.SELL_SPREAD_KWD, 3)

    if ounce > 0:
        sheet_dashboard.update_acell("C5", ounce)

    # قراءة خلايا الذاكرة من الإكسل:
    # N5 = سعر الفحص السابق (قبل 5 دقائق) | K5 = سعر الساعة السابقة | L5 = الاتجاه السابق
    # O5 = سعر آخر تنبيه أُرسل (لمنع تفويت الصعود المتدرج) | P5 = رقم آخر ساعة مفحوصة
    try:
        last_step_price = float(sheet_dashboard.acell("N5").value or ounce)
        last_1h = float(sheet_dashboard.acell("K5").value or ounce)
        last_trend = sheet_dashboard.acell("L5").value or "NEUTRAL"
        last_alert_price = float(sheet_dashboard.acell("O5").value or ounce)
        last_checked_hour = str(sheet_dashboard.acell("P5").value or "")
    except Exception:
        last_step_price, last_1h, last_alert_price = ounce, ounce, ounce
        last_trend, last_checked_hour = "NEUTRAL", ""

    diff_fast = round(ounce - last_step_price, 2)
    diff_1h = round(ounce - last_1h, 2)
    diff_since_last_alert = round(ounce - last_alert_price, 2)

    sheet_dashboard.update_acell("N5", ounce)

    now_kw_dt = datetime.now(config.KUWAIT_TZ)
    now_kw = now_kw_dt.strftime("%A, %Y-%m-%d %H:%M")
    current_hour_str = now_kw_dt.strftime("%Y-%m-%d %H")
    current_hour = now_kw_dt.hour

    alert_header = ""

    # 1. فحص الحركة الفورية (25$ في دقائق معدودة) أو الحركة التراكمية (25$ منذ آخر تنبيه)
    if diff_fast >= 25.0:
        alert_header = f"⚡🚀 <b>قفزة صاروخية فورية: الذهب ارتفع +{diff_fast}$ خلال دقائق!</b>"
    elif diff_fast <= -25.0:
        alert_header = f"⚡🔻 <b>هبوط عنيف فوري: الذهب تراجع {diff_fast}$ خلال دقائق!</b>"
    elif diff_since_last_alert >= 25.0:
        alert_header = f"📈🚀 <b>موجة صعود قوية (+{diff_since_last_alert}$): الذهب يواصل الارتفاع منذ آخر تنبيه!</b>"
    elif diff_since_last_alert <= -25.0:
        alert_header = f"📉🔻 <b>موجة هبوط قوية ({diff_since_last_alert}$): الذهب يواصل التراجع منذ آخر تنبيه!</b>"

    # 2. فحص الانقلاب الساعي وسلسلة الشموع (يعمل مرة واحدة في كل ساعة جديدة)
    sma_12h = round(float(hist_1h["Close"].tail(12).mean()), 2)
    current_trend = "UP" if ounce > sma_12h else "DOWN"

    c_prev2 = float(hist_1h["Close"].iloc[-3]) if len(hist_1h) >= 3 else ounce
    c_prev1 = float(hist_1h["Close"].iloc[-2]) if len(hist_1h) >= 2 else ounce
    is_3_green = (ounce > c_prev1) and (c_prev1 > c_prev2) and ((ounce - c_prev2) >= 20.0)
    is_3_red = (ounce < c_prev1) and (c_prev1 < c_prev2) and ((c_prev2 - ounce) >= 20.0)

    is_new_hour = (current_hour_str != last_checked_hour)
    if is_new_hour:
        if not alert_header:
            if last_trend == "DOWN" and current_trend == "UP":
                alert_header = "🔄📈 <b>تنبيه انقلاب صعودي: الذهب يرتد ويخترق المتوسط الساعي!</b>"
            elif last_trend == "UP" and current_trend == "DOWN":
                alert_header = "🔄📉 <b>تنبيه انقلاب هبوطي: الذهب يكسر المتوسط الساعي ويتجه للهبوط!</b>"
            elif is_3_green:
                alert_header = "🟢🚀 <b>زخم صعودي متواصل: 3 شموع خضراء متتالية بقوة!</b>"
            elif is_3_red:
                alert_header = "🔴🔻 <b>ضغط بيعي متواصل: 3 شموع حمراء متتالية بقوة!</b>"

        sheet_dashboard.update_acell("K5", ounce)
        sheet_dashboard.update_acell("L5", current_trend)
        sheet_dashboard.update_acell("P5", current_hour_str)

    portfolio_rows = sheet_dashboard.get("A5:I18")
    portfolio_text = "\n".join([" | ".join(r) for r in portfolio_rows if r])
    targets_rows = sheet_dashboard.get("A19:B21")
    targets_text = "\n".join([" | ".join(r) for r in targets_rows if r])

    if alert_header:
        sheet_dashboard.update_acell("O5", ounce)
        alert_prompt = f"""أنت مستشاري المالي لأسواق الذهب في الكويت (دار السبائك).
حدث الآن تحرك سعري هام: {alert_header}
- السعر الحالي للأونصة: {ounce}$ (التغير التراكمي: {diff_since_last_alert:+}$ | تغير الساعة: {diff_1h:+}$)
- سعر شراء جرام 24 في دار السبائك: {buy_24k} د.ك | سعر البيع: {sell_24k} د.ك
- بيانات محفظتي: {portfolio_text}
- مستهدفات الشراء في ملفي: {targets_text}

اكتب تنبيهاً عاجلاً ومختصراً جداً (4 أسطر فقط) بتنسيق HTML لتيليجرام (استخدم <b> فقط ويُمنع Markdown) يوضح القرار المناسب الآن (شراء/تعزيز أم انتظار)."""

        alert_reply = call_gemini_safe(alert_prompt)
        full_alert = f"{alert_header}\n\n{alert_reply}"
        send_all_channels(f"تنبيه ذهب عاجل: {buy_24k} د.ك", full_alert, is_urgent=True)

    # 3. التقرير الدوري الشامل (10ص، 2ظ، 6م، 10م بتوقيت الكويت)
    report_hours = (10, 14, 18, 22)
    if (is_new_hour and current_hour in report_hours) or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        sheet_dashboard.update_acell("O5", ounce)
        feed = feedparser.parse(config.RSS_NEWS_URL)
        news_text = "\n".join([entry.title for entry in feed.entries[:7]])
        prompt = config.build_report_prompt(now_kw, ounce, ch_day, chp_day, buy_24k, portfolio_text, targets_text, news_text)
        report_reply = call_gemini_safe(prompt)
        send_all_channels(f"تقرير دار السبائك: {buy_24k} د.ك", report_reply, is_urgent=False)

    print(f"Checked at {now_kw} | Ounce: {ounce}$ | Since Alert: {diff_since_last_alert}$ | Trend: {current_trend}")

if __name__ == "__main__":
    run_smart_monitor()
