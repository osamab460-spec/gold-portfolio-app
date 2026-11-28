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


# =================== تهيئة آمنة ===================
def _env(key, default=""):
    return str(os.environ.get(key, default)).strip().strip('"').strip("'")


GEMINI_API_KEY = _env("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY غير موجود في المتغيرات البيئية.")

RAW_TG_TOKEN = _env("TELEGRAM_TOKEN")
if "bot" in RAW_TG_TOKEN and "/" in RAW_TG_TOKEN:
    TELEGRAM_TOKEN = next(iter(RAW_TG_TOKEN.split("bot")[-1].split("/")))
else:
    TELEGRAM_TOKEN = RAW_TG_TOKEN

CHAT_ID = _env("CHAT_ID")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS", "")
if not GOOGLE_CREDENTIALS:
    raise RuntimeError("GOOGLE_CREDENTIALS غير موجود.")
NTFY_TOPIC = _env("NTFY_TOPIC", "semsem_gold_kw_99")

ai_client = genai.Client(api_key=GEMINI_API_KEY)


# =================== سبوت أونصة ===================
def get_spot_ounce():
    # 1) TradingView (GET الصحيح)
    try:
        tv_url = (
            "https://scanner.tradingview.com/symbol"
            "?symbol=OANDA%3AXAUUSD&fields=close"
        )
        headers = {
            "User-Agent": config.RSS_HEADERS["User-Agent"],
            "Accept": "application/json",
        }
        tv_res = requests.get(tv_url, headers=headers, timeout=6).json()
        if isinstance(tv_res, dict) and tv_res.get("close"):
            return round(float(tv_res["close"]), 3)
    except Exception:
        pass

    # 2) Yahoo GC=F
    try:
        h = yf.Ticker("GC=F").history(period="2d", interval="1m")
        if not h.empty:
            return round(float(h["Close"].iloc[-1]), 3)
    except Exception:
        pass
    return 0.0


# =================== Gemini ===================
def call_gemini_safe(prompt):
    last_err = ""
    for model_name in config.GEMINI_MODELS:
        try:
            res = ai_client.models.generate_content(model=model_name, contents=prompt)
            txt = getattr(res, "text", None)
            if txt:
                return txt
        except Exception as e:
            last_err = str(e)
            continue
    return f"⚠️ تعذر توليد التحليل حالياً. ({last_err or 'غير معروف'})"


# =================== إرسال القنوات ===================
def send_all_channels(title, html_message, is_urgent=False):
    # Telegram
    if TELEGRAM_TOKEN and ":" in TELEGRAM_TOKEN and CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            r = requests.post(
                tg_url,
                json={
                    "chat_id": CHAT_ID,
                    "text": html_message[:4000],
                    "parse_mode": "HTML",
                },
                timeout=15,
            )
            if r.status_code != 200:
                plain = re.sub(r"<[^>]+>", "", html_message)[:4000]
                r2 = requests.post(
                    tg_url, json={"chat_id": CHAT_ID, "text": plain}, timeout=15
                )
                print("Telegram fallback:", r2.status_code)
            else:
                print("Telegram sent OK")
        except Exception as e:
            print("Telegram warning:", e)

    # ntfy
    if NTFY_TOPIC:
        try:
            plain_text = re.sub(r"<[^>]+>", "", html_message)
            ntfy_url = f"https://ntfy.sh/{NTFY_TOPIC}"
            requests.post(
                ntfy_url,
                data=plain_text.encode("utf-8"),
                headers={
                    "Title": title.encode("utf-8"),
                    "Priority": "urgent" if is_urgent else "high",
                    "Tags": "rotating_light" if is_urgent else "coin",
                },
                timeout=15,
            )
        except Exception as e:
            print("ntfy warning:", e)


# =================== المُراقب الرئيسي ===================
def run_quarter_hourly_monitor():
    gc = gspread.service_account_from_dict(json.loads(GOOGLE_CREDENTIALS))
    sh = gc.open_by_key(config.SPREADSHEET_ID)
    sheet_dashboard = sh.worksheet(config.SHEET_DASHBOARD_NAME)

    ticker = yf.Ticker("GC=F")
    # توسيع period لضمان وجود بيانات حتى في نهايات الأسبوع
    hist_15m = ticker.history(period="2d", interval="15m").tail(60)
    hist_1h = ticker.history(period="7d", interval="1h").tail(48)
    hist_1d = ticker.history(period="5d")

    if hist_15m.empty or hist_1h.empty or hist_1d.empty:
        print("⚠️ بيانات yfinance غير كافية، تم تخطي الدورة.")
        return

    spot = get_spot_ounce()
    ounce = spot if spot > 0 else round(float(hist_15m["Close"].iloc[-1]), 2)
    prev_day_close = (
        round(float(hist_1d["Close"].iloc[-2]), 2) if len(hist_1d) > 1 else ounce
    )
    ch_day = round(ounce - prev_day_close, 2)
    chp_day = round((ch_day / prev_day_close) * 100, 2) if prev_day_close else 0.0

    buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
    sell_24k = round(buy_24k - config.SELL_SPREAD_KWD, 3)
    if ounce > 0:
        try:
            sheet_dashboard.update_acell("C5", ounce)
        except Exception as e:
            print("update C5 warning:", e)

    # قراءة القيم المحسوبة (UNFORMATTED) لضمان أرقام لا صيغ
    try:
        curr_grams = float(
            str(
                sheet_dashboard.acell(
                    "A15", value_render_option="UNFORMATTED_VALUE"
                ).value
                or "0"
            ).replace(",", "")
        )
        curr_avg = float(
            str(
                sheet_dashboard.acell(
                    "D15", value_render_option="UNFORMATTED_VALUE"
                ).value
                or "0"
            ).replace(",", "")
        )
    except Exception:
        curr_grams, curr_avg = 0.0, 0.0

    # 1) تنبيهات مسجَّلة
    try:
        sheet_alerts = sh.worksheet(config.SHEET_ALERTS_NAME)
        alert_rows = sheet_alerts.get_all_values()
        for idx, row in enumerate(alert_rows[1:], start=2):
            if len(row) >= 4 and str(row[3]).strip().upper() == "ON":
                t_price = float(str(row[1]).replace(",", ""))
                direction = str(row[2]).strip().upper()
                hit = (direction == "DOWN" and ounce <= t_price) or (
                    direction == "UP" and ounce >= t_price
                )
                if hit:
                    plan_grams = (
                        float(str(row[4]).replace(",", ""))
                        if (len(row) > 4 and str(row[4]).strip())
                        else 0.0
                    )
                    note = str(row[5]) if len(row) > 5 else ""
                    dir_ar = (
                        "هبوطاً (فرصة شراء 📉)"
                        if direction == "DOWN"
                        else "صعوداً (مستهدف بيع 📈)"
                    )

                    avg_impact_txt = ""
                    if (
                        direction == "DOWN"
                        and plan_grams > 0
                        and curr_grams > 0
                        and curr_avg > 0
                    ):
                        new_avg = round(
                            (
                                (curr_grams * curr_avg)
                                + (plan_grams * buy_24k)
                            )
                            / (curr_grams + plan_grams),
                            3,
                        )
                        avg_impact_txt = (
                            f"\n• <b>تأثير شراء {plan_grams} جم:</b> "
                            f"ينخفض متوسطك من {curr_avg:.3f} إلى <b>{new_avg:.3f} د.ك</b>"
                        )

                    msg_target = (
                        f"🎯🚨 <b>تنبيه سعري: الذهب وصل إلى {t_price:,.2f}$ {dir_ar}!</b>\n\n"
                        f"• <b>الأونصة الفورية الآن:</b> {ounce:,.2f}$\n"
                        f"• <b>شراء جرام 24 (دار السبائك):</b> {buy_24k:.3f} د.ك\n"
                        f"• <b>بيع جرام 24:</b> {sell_24k:.3f} د.ك"
                        f"{avg_impact_txt}"
                        f"{(chr(10) + '• <b>ملاحظتك:</b> ' + note) if note else ''}"
                    )
                    send_all_channels(
                        f"🎯 الذهب وصل {ounce}$ ({buy_24k} د.ك)",
                        msg_target,
                        is_urgent=True,
                    )
                    sheet_alerts.update_acell(f"D{idx}", "TRIGGERED")
    except Exception as e:
        print("Alerts sheet check:", e)

    # 2) تحركات عنيفة
    try:
        val_15m = sheet_dashboard.acell("N5").value
        last_15m = float(val_15m) if val_15m else ounce
        val_1h = sheet_dashboard.acell("K5").value
        last_1h = float(val_1h) if val_1h else ounce
        last_trend = sheet_dashboard.acell("L5").value or "NEUTRAL"
    except Exception:
        last_15m, last_1h, last_trend = ounce, ounce, "NEUTRAL"

    diff_15m = round(ounce - last_15m, 2)
    diff_1h = round(ounce - last_1h, 2)
    try:
        sheet_dashboard.update_acell("N5", ounce)
    except Exception as e:
        print("update N5 warning:", e)

    now_kw_dt = datetime.now(config.KUWAIT_TZ)
    now_kw = now_kw_dt.strftime("%A, %Y-%m-%d %H:%M")
    hh, mm = now_kw_dt.hour, now_kw_dt.minute

    alert_header = ""
    if diff_15m >= 25.0:
        alert_header = (
            f"⚡🚀 <b>إنذار صعود عنيف (15 دقيقة): الذهب قفز +{diff_15m}$ في ربع ساعة!</b>"
        )
    elif diff_15m <= -25.0:
        alert_header = (
            f"⚡🔻 <b>إنذار هبوط عنيف (15 دقيقة): الذهب هبط {diff_15m}$ في ربع ساعة!</b>"
        )

    sma_12h = round(float(hist_1h["Close"].tail(12).mean()), 2)
    current_trend = "UP" if ounce > sma_12h else "DOWN"

    if mm < 15:
        if not alert_header:
            if last_trend == "DOWN" and current_trend == "UP" and diff_1h >= 6.0:
                alert_header = (
                    "🔄📈 <b>تنبيه انقلاب صعودي: الذهب يرتد ويخترق المقاومة الساعية!</b>"
                )
            elif last_trend == "UP" and current_trend == "DOWN" and diff_1h <= -6.0:
                alert_header = (
                    "🔄📉 <b>تنبيه انقلاب هبوطي: الذهب يكسر الدعم الساعي ويتجه للهبوط!</b>"
                )
            elif diff_1h >= 12.0:
                alert_header = (
                    f"🚀 <b>قفزة صعودية ساعية: الذهب ارتفع +{diff_1h}$ خلال ساعة!</b>"
                )
            elif diff_1h <= -12.0:
                alert_header = (
                    f"🔻 <b>هبوط ساعي سريع: الذهب تراجع {diff_1h}$ خلال ساعة!</b>"
                )
        try:
            sheet_dashboard.update_acell("K5", ounce)
            sheet_dashboard.update_acell("L5", current_trend)
        except Exception as e:
            print("update K5/L5 warning:", e)

    portfolio_text = "\n".join(
        [" | ".join(r) for r in sheet_dashboard.get("A5:I18") if r]
    )
    targets_text = "\n".join(
        [" | ".join(r) for r in sheet_dashboard.get("A20:B24") if r]
    )

    if alert_header:
        alert_prompt = (
            "أنت مستشاري المالي لأسواق الذهب في الكويت (دار السبائك).\n"
            f"حدث الآن تحرك سعري هام: {alert_header}\n"
            f"- السعر الحالي للأونصة: {ounce}$ (ربع ساعة: {diff_15m:+}$ | ساعة: {diff_1h:+}$)\n"
            f"- شراء 24: {buy_24k} د.ك | بيع 24: {sell_24k} د.ك\n"
            f"- محفظتي: {portfolio_text}\n"
            "اكتب تنبيهاً عاجلاً ومختصراً (4 أسطر) بتنسيق HTML (وسم <b> فقط)."
        )
        send_all_channels(
            f"إنذار ذهب عاجل: {buy_24k} د.ك",
            f"{alert_header}\n\n{call_gemini_safe(alert_prompt)}",
            is_urgent=True,
        )

    # 3) أخبار ماكرو 14:00
    if hh == 14 and mm < 15:
        for url in config.RSS_NEWS_URLS:
            try:
                res = requests.get(url, timeout=5, headers=config.RSS_HEADERS)
                feed = feedparser.parse(res.content)
                headlines = " | ".join([e.title for e in feed.entries[:8]])
                if not headlines:
                    continue
                keys = (
                    "CPI",
                    "FOMC",
                    "Fed",
                    "NFP",
                    "Non-Farm",
                    "Powell",
                    "Interest Rate",
                    "Inflation",
                )
                if any(k.lower() in headlines.lower() for k in keys):
                    macro_prompt = (
                        "أنت محلل أسواق الذهب. افحص عناوين الأخبار التالية "
                        f"اليوم ({now_kw}):\n{headlines}\n"
                        "إذا كان هناك بيان اقتصادي أمريكي هام اليوم (CPI/FOMC/NFP)، "
                        "اكتب تنبيهاً (3 أسطر) بتنسيق HTML (وسم <b> فقط) يوضح الموعد "
                        "بتوقيت الكويت وتأثيره على الذهب."
                    )
                    send_all_channels(
                        "⚠️ بيان اقتصادي أمريكي مؤثر اليوم",
                        "📅⚠️ <b>تنبيه أخبار اقتصادية هامة اليوم:</b>\n\n"
                        + call_gemini_safe(macro_prompt),
                        is_urgent=True,
                    )
                    break
            except Exception:
                continue

    # 4) التقرير الدوري (10, 14, 18, 22) أو Trigger يدوي
    is_manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    if (hh in (10, 14, 18, 22) and mm < 15) or is_manual:
        news_titles = []
        for url in config.RSS_NEWS_URLS:
            try:
                res = requests.get(url, timeout=5, headers=config.RSS_HEADERS)
                feed = feedparser.parse(res.content)
                news_titles.extend([e.title for e in feed.entries[:4]])
                if len(news_titles) >= 7:
                    break
            except Exception:
                continue
        news_text = "\n".join(news_titles[:7]) or "لا توجد أخبار حالياً."
        prompt = config.build_report_prompt(
            now_kw,
            ounce,
            ch_day,
            chp_day,
            buy_24k,
            portfolio_text,
            targets_text,
            news_text,
        )
        send_all_channels(
            f"تقرير دار السبائك: {buy_24k} د.ك",
            call_gemini_safe(prompt),
            is_urgent=False,
        )

    print(f"Checked at {now_kw} | Ounce: {ounce}$")


if __name__ == "__main__":
    run_quarter_hourly_monitor()
