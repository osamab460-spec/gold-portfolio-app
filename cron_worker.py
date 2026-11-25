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

def send_all_channels(title, html_message, is_urgent=False):
    if TELEGRAM_TOKEN:
        tg_url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
        requests.post(tg_url, json={"chat_id": config.CHAT_ID, "text": html_message, "parse_mode": "HTML"}, timeout=15)

    clean_text = html_message.replace("<b>", "*").replace("</b>", "*")
    wa_url = f"https://callmebot.com{config.WHATSAPP_PHONE}&apikey={config.WHATSAPP_APIKEY}&text={requests.utils.quote(clean_text[:950])}"
    requests.get(wa_url, timeout=15)

    if NTFY_TOPIC:
        plain_text = html_message.replace("<b>", "").replace("</b>", "")
        priority = "urgent" if is_urgent else "high"
        tags = "rotating_light,chart_with_upwards_trend" if is_urgent else "coin"
        requests.post(
            f"https://ntfy.sh{NTFY_TOPIC}",
            data=plain_text.encode("utf-8"),
            headers={"Title": title.encode("utf-8"), "Priority": priority, "Tags": tags},
            timeout=15
        )

def run_quarter_hourly_monitor():
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open_by_key(config.SPREADSHEET_ID)
    sheet_dashboard = sh.worksheet(config.SHEET_DASHBOARD_NAME)

    ticker = yf.Ticker("GC=F")
    hist_15m = ticker.history(period="1d", interval="15m")
    hist_1h = ticker.history(period="2d", interval="1h")
    hist_1d = ticker.history(period="2d")

    ounce = round(float(hist_15m["Close"].iloc[-1]), 2)
    prev_day_close = round(float(hist_1d["Close"].iloc[-2]), 2) if len(hist_1d) > 1 else ounce
    ch_day = round(ounce - prev_day_close, 2)
    chp_day = round((ch_day / prev_day_close) * 100, 2) if prev_day_close else 0.0

    buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
    sell_24k = round(buy_24k - config.SELL_SPREAD_KWD, 3)

    if ounce > 0:
        sheet_dashboard.update_acell("C5", ounce)

    try:
        val_15m = sheet_dashboard.acell("N5").value
        last_ounce_15m = float(val_15m) if val_15m else ounce

        val_1h = sheet_dashboard.acell("K5").value
        last_ounce_1h = float(val_1h) if val_1h else ounce
        last_trend = sheet_dashboard.acell("L5").value or "NEUTRAL"
    except Exception:
        last_ounce_15m = ounce
        last_ounce_1h = ounce
        last_trend = "NEUTRAL"

    diff_15m = round(ounce - last_ounce_15m, 2)
    diff_1h = round(ounce - last_ounce_1h, 2)

    sheet_dashboard.update_acell("N5", ounce)

    now_kw_dt = datetime.now(config.KUWAIT_TZ)
    now_kw = now_kw_dt.strftime("%A, %Y-%m-%d %H:%M")
    current_hour = now_kw_dt.hour
    current_minute = now_kw_dt.minute

    alert_header = ""
    if diff_15m >= 25.0:
        alert_header = f"⚡🚀 <b>إنذار صعود عنيف (15 دقيقة): الذهب قفز +{diff_15m}$ في ربع ساعة!</b>"
    elif diff_15m <= -25.0:
        alert_header = f"⚡🔻 <b>إنذار هبوط عنيف (15 دقيقة): الذهب هبط {diff_15m}$ في ربع ساعة!</b>"

    sma_12h = round(float(hist_1h["Close"].tail(12).mean()), 2)
    current_trend = "UP" if ounce > sma_12h else "DOWN"

    if current_minute < 15:
        if not alert_header:
            if last_trend == "DOWN" and current_trend == "UP" and diff_1h >= 6.0:
                alert_header = "🔄📈 <b>تنبيه انقلاب صعودي: الذهب يرتد ويخترق المقاومة الساعية!</b>"
            elif last_trend == "UP" and current_trend == "DOWN" and diff_1h <= -6.0:
                alert_header = "🔄📉 <b>تنبيه انقلاب هبوطي: الذهب يكسر الدعم الساعي ويتجه للهبوط!</b>"
            elif diff_1h >= 12.0:
                alert_header = f"🚀 <b>قفزة صعودية ساعية: الذهب ارتفع +{diff_1h}$ خلال ساعة!</b>"
            elif diff_1h <= -12.0:
                alert_header = f"🔻 <b>هبوط ساعي سريع: الذهب تراجع {diff_1h}$ خلال ساعة!</b>"

        sheet_dashboard.update_acell("K5", ounce)
        sheet_dashboard.update_acell("L5", current_trend)

    portfolio_rows = sheet_dashboard.get("A5:I18")
    portfolio_text = "\n".join([" | ".join(r) for r in portfolio_rows if r])
    targets_rows = sheet_dashboard.get("A19:B21")
    targets_text = "\n".join([" | ".join(r) for r in targets_rows if r])

    if alert_header:
        alert_prompt = f"""أنت مستشاري المالي لأسواق الذهب في الكويت (دار السبائك).
حدث الآن تحرك سعري هام: {alert_header}
- السعر الحالي للأونصة: {ounce}$ (تغير ربع ساعة: {diff_15m:+}$ | تغير ساعة: {diff_1h:+}$)
- سعر شراء جرام 24 في دار السبائك: {buy_24k} د.ك | سعر البيع: {sell_24k} د.ك
- بيانات محفظتي: {portfolio_text}
- مستهدفات الشراء في ملفي: {targets_text}

اكتب تنبيهاً عاجلاً ومختصراً جداً (4 أسطر فقط) بتنسيق HTML لتيليجرام (استخدم <b> فقط ويُمنع Markdown) يوضح القرار المناسب الآن (شراء/تعزيز أم انتظار)."""

        res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=alert_prompt)
        full_alert = f"{alert_header}\n\n{res.text}"
        send_all_channels(f"إنذار ذهب عاجل: {buy_24k} د.ك", full_alert, is_urgent=True)

    report_hours = (10, 14, 18, 22)
    is_scheduled_report_hour = (current_hour in report_hours) and (current_minute < 15)
    if is_scheduled_report_hour or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        feed = feedparser.parse(config.RSS_NEWS_URL)
        news_text = "\n".join([entry.title for entry in feed.entries[:7]])
        prompt = config.build_report_prompt(now_kw, ounce, ch_day, chp_day, buy_24k, portfolio_text, targets_text, news_text)
        res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        send_all_channels(f"تقرير دار السبائك: {buy_24k} د.ك", res.text, is_urgent=False)

    print(f"Checked at {now_kw} | Ounce: {ounce}$ | 15m Diff: {diff_15m}$ | 1h Diff: {diff_1h}$")

if __name__ == "__main__":
    run_quarter_hourly_monitor()
