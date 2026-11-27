import os
import re
import json
import requests
import feedparser
from datetime import datetime
import gspread
from google import genai
import yfinance as yf
import config

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip().strip('"').strip("'")
RAW_TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip().strip('"').strip("'")
if "bot" in RAW_TG_TOKEN and "/" in RAW_TG_TOKEN:
    TELEGRAM_TOKEN = next(iter(RAW_TG_TOKEN.split("bot")[-1].split("/")))
else:
    TELEGRAM_TOKEN = RAW_TG_TOKEN

CHAT_ID = os.environ.get("CHAT_ID", "").strip()
GOOGLE_CREDENTIALS = os.environ["GOOGLE_CREDENTIALS"]
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "semsem_gold_kw_99").strip()

ai_client = genai.Client(api_key=GEMINI_API_KEY)

def get_spot_ounce():
    try:
        tv_url = "https://tradingview.com"
        payload = {"symbols": {"tickers": ["OANDA:XAUUSD"]}, "columns": ["close"]}
        tv_res = requests.post(tv_url, json=payload, timeout=6).json()
        rows = tv_res.get("data", [])
        if rows:
            vals = next(iter(rows)).get("d", [])
            if vals and float(next(iter(vals))) > 0:
                return round(float(next(iter(vals))), 3)
    except Exception:
        pass

    try:
        sq_url = "https://swissquote.com"
        data = requests.get(sq_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6).json()
        p = next(iter(next(iter(data)).get("spreadProfilePrices", [])))
        return round((float(p["bid"]) + float(p["ask"])) / 2, 3)
    except Exception:
        return 0.0

def call_gemini_safe(prompt):
    models_to_try = ["gemini-3.8-flash", "gemini-3-flash-preview", "gemini-2.5-flash"]
    for model_name in models_to_try:
        try:
            return ai_client.models.generate_content(model=model_name, contents=prompt).text
        except Exception:
            continue
    return "⚠️ تعذر توليد التحليل حالياً."

def send_all_channels(title, html_message, is_urgent=False):
    if TELEGRAM_TOKEN and ":" in TELEGRAM_TOKEN and CHAT_ID:
        try:
            tg_url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
            r = requests.post(tg_url, json={"chat_id": CHAT_ID, "text": html_message[:4000], "parse_mode": "HTML"}, timeout=15)
            if r.status_code != 200:
                plain_tg = re.sub(r"<[^>]+>", "", html_message)[:4000]
                r2 = requests.post(tg_url, json={"chat_id": CHAT_ID, "text": plain_tg}, timeout=15)
                print("Telegram fallback status:", r2.status_code, r2.text)
            else:
                print("Telegram sent OK")
        except Exception as e:
            print("Telegram warning:", e)

    if NTFY_TOPIC:
        try:
            plain_text = re.sub(r"<[^>]+>", "", html_message)
            ntfy_url = f"https://ntfy.sh{NTFY_TOPIC}"
            requests.post(
                ntfy_url,
                data=plain_text.encode("utf-8"),
                headers={
                    "Title": title.encode("utf-8"),
                    "Priority": "urgent" if is_urgent else "high",
                    "Tags": "rotating_light" if is_urgent else "coin"
                },
                timeout=15
            )
        except Exception as e:
            print("ntfy warning:", e)
def run_quarter_hourly_monitor():
    gc = gspread.service_account_from_dict(json.loads(GOOGLE_CREDENTIALS))
    sh = gc.open_by_key(config.SPREADSHEET_ID)
    sheet_dashboard = sh.worksheet(config.SHEET_DASHBOARD_NAME)

    ticker = yf.Ticker("GC=F")
    hist_15m = ticker.history(period="1d", interval="15m")
    hist_1h = ticker.history(period="2d", interval="1h")
    hist_1d = ticker.history(period="2d")

    spot_ounce = get_spot_ounce()
    ounce = spot_ounce if spot_ounce > 0 else round(float(hist_15m["Close"].tail(1).item()), 2)
    prev_day_close = round(float(hist_1d["Close"].tail(2).head(1).item()), 2) if len(hist_1d) > 1 else ounce
    ch_day = round(ounce - prev_day_close, 2)
    chp_day = round((ch_day / prev_day_close) * 100, 2) if prev_day_close else 0.0

    buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
    sell_24k = round(buy_24k - config.SELL_SPREAD_KWD, 3)

    if ounce > 0:
        sheet_dashboard.update_acell("C5", ounce)

    try:
        curr_grams = float(str(sheet_dashboard.acell("A15").value or "0").replace(",", ""))
        curr_avg = float(str(sheet_dashboard.acell("D15").value or "0").replace(",", ""))
    except Exception:
        curr_grams, curr_avg = 0.0, 0.0

    # 1. فحص التنبيهات السعرية المسجلة في ورقة "التنبيهات"
    try:
        sheet_alerts = sh.worksheet("التنبيهات")
        alert_rows = sheet_alerts.get_all_values()
        for idx, row in enumerate(alert_rows[1:], start=2):
            if len(row) >= 4 and str(row[3]).strip().upper() == "ON":
                t_price = float(str(row[1]).replace(",", ""))
                direction = str(row[2]).strip().upper()
                hit = (direction == "DOWN" and ounce <= t_price) or (direction == "UP" and ounce >= t_price)
                if hit:
                    plan_grams = float(str(row[4]).replace(",", "")) if (len(row) > 4 and str(row[4]).strip()) else 0.0
                    note = str(row[5]) if len(row) > 5 else ""
                    dir_ar = "هبوطاً (فرصة شراء 📉)" if direction == "DOWN" else "صعوداً (مستهدف بيع 📈)"

                    avg_impact_txt = ""
                    if direction == "DOWN" and plan_grams > 0 and curr_grams > 0 and curr_avg > 0:
                        new_avg = round(((curr_grams * curr_avg) + (plan_grams * buy_24k)) / (curr_grams + plan_grams), 3)
                        avg_impact_txt = f"\n• <b>تأثير شراء {plan_grams} جم:</b> ينخفض متوسطك من {curr_avg:.3f} إلى <b>{new_avg:.3f} د.ك</b>"

                    msg_target = (
                        f"🎯🚨 <b>تنبيه سعري: الذهب وصل إلى {t_price:,.2f}$ {dir_ar}!</b>\n\n"
                        f"• <b>الأونصة الفورية الآن:</b> {ounce:,.2f}$\n"
                        f"• <b>شراء جرام 24 (دار السبائك):</b> {buy_24k:.3f} د.ك\n"
                        f"• <b>بيع جرام 24:</b> {sell_24k:.3f} د.ك"
                        f"{avg_impact_txt}"
                        f"{(chr(10) + '• <b>ملاحظتك:</b> ' + note) if note else ''}"
                    )
                    send_all_channels(f"🎯 الذهب وصل {ounce}$ ({buy_24k} د.ك)", msg_target, is_urgent=True)
                    sheet_alerts.update_acell(f"D{idx}", "TRIGGERED")
    except Exception as e:
        print("Alerts sheet check:", e)

    # 2. فحص التحركات العنيفة (25$ كل ربع ساعة) والانقلابات الساعية
    try:
        val_15m = sheet_dashboard.acell("N5").value
        last_ounce_15m = float(val_15m) if val_15m else ounce
        val_1h = sheet_dashboard.acell("K5").value
        last_ounce_1h = float(val_1h) if val_1h else ounce
        last_trend = sheet_dashboard.acell("L5").value or "NEUTRAL"
    except Exception:
        last_ounce_15m, last_ounce_1h, last_trend = ounce, ounce, "NEUTRAL"

    diff_15m = round(ounce - last_ounce_15m, 2)
    diff_1h = round(ounce - last_ounce_1h, 2)
    sheet_dashboard.update_acell("N5", ounce)

    now_kw_dt = datetime.now(config.KUWAIT_TZ)
    now_kw = now_kw_dt.strftime("%A, %Y-%m-%d %H:%M")
    current_hour, current_minute = now_kw_dt.hour, now_kw_dt.minute

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

    portfolio_text = "\n".join([" | ".join(r) for r in sheet_dashboard.get("A5:I18") if r])
    targets_text = "\n".join([" | ".join(r) for r in sheet_dashboard.get("A19:B21") if r])

    if alert_header:
        alert_prompt = (
            "أنت مستشاري المالي لأسواق الذهب في الكويت (دار السبائك).\n"
            f"حدث الآن تحرك سعري هام: {alert_header}\n"
            f"- السعر الحالي للأونصة: {ounce}$ (تغير ربع ساعة: {diff_15m:+}$ | تغير ساعة: {diff_1h:+}$)\n"
            f"- سعر شراء جرام 24 في دار السبائك: {buy_24k} د.ك | سعر البيع: {sell_24k} د.ك\n"
            f"- بيانات محفظتي: {portfolio_text}\n"
            "اكتب تنبيهاً عاجلاً ومختصراً جداً (4 أسطر فقط) بتنسيق HTML لتيليجرام (استخدم <b> فقط)."
        )
        full_alert = f"{alert_header}\n\n{call_gemini_safe(alert_prompt)}"
        send_all_channels(f"إنذار ذهب عاجل: {buy_24k} د.ك", full_alert, is_urgent=True)

    # 3. تنبيه استباقي للأخبار الاقتصادية الأمريكية الكبرى (الساعة 14:00 بتوقيت الكويت)
    if current_hour == 14 and current_minute < 15:
        feed = feedparser.parse(config.RSS_NEWS_URL)
        headlines = " | ".join([entry.title for entry in feed.entries[:8]])
        macro_keywords = ("CPI", "FOMC", "Fed", "NFP", "Non-Farm", "Powell", "Interest Rate", "Inflation")
        if any(k.lower() in headlines.lower() for k in macro_keywords):
            macro_prompt = (
                f"أنت محلل أسواق الذهب. افحص عناوين الأخبار التالية اليوم ({now_kw}):\n"
                f"{headlines}\n"
                "إذا كان هناك بيان اقتصادي أمريكي هام يصدر اليوم (مثل التضخم CPI، الفائدة الفيدرالية FOMC، أو الوظائف NFP)، "
                "اكتب تنبيهاً تحذيرياً من 3 أسطر فقط بتنسيق HTML (وسم <b> فقط) يوضح موعد الخبر المتوقع بتوقيت الكويت وتأثيره المحتمل على الذهب."
            )
            macro_msg = "📅⚠️ <b>تنبيه أخبار اقتصادية هامة اليوم:</b>\n\n" + call_gemini_safe(macro_prompt)
            send_all_channels("⚠️ بيان اقتصادي أمريكي مؤثر اليوم", macro_msg, is_urgent=True)

    # 4. التقرير الدوري الشامل
    if (current_hour in (10, 14, 18, 22) and current_minute < 15) or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        feed = feedparser.parse(config.RSS_NEWS_URL)
        news_text = "\n".join([entry.title for entry in feed.entries[:7]])
        prompt = config.build_report_prompt(now_kw, ounce, ch_day, chp_day, buy_24k, portfolio_text, targets_text, news_text)
        send_all_channels(f"تقرير دار السبائك: {buy_24k} د.ك", call_gemini_safe(prompt), is_urgent=False)

    print(f"Checked at {now_kw} | Ounce: {ounce}$")

if __name__ == "__main__":
    run_quarter_hourly_monitor()
