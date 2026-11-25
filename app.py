import streamlit as st
import requests
import json
import feedparser
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
from google import genai

# ================= 1. إعدادات واجهة الموبايل =================
st.set_page_config(
    page_title="دار السبائك AI",
    page_icon="🪙",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .main { direction: rtl; text-align: right; }
    div[data-testid="stMetricValue"] { font-size: 1.35rem; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.1em; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ================= 2. المفاتيح والاتصال =================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
CHAT_ID = "7342639951"
WHATSAPP_PHONE = "96597894119"
WHATSAPP_APIKEY = "9510859"
SPREADSHEET_ID = "11s82rxEoX0TwGgzyp8LTYC2XeWJK9Jp3hk_KS14szuo"
KUWAIT_TZ = pytz.timezone("Asia/Kuwait")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

@st.cache_resource
def init_sheets():
    SCOPES = ["https://googleapis.com"]
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    return sh.worksheet("لوحة التحليل العام"), sh.worksheet("سجل العمليات")

sheet_dashboard, sheet_log = init_sheets()

# ================= 3. جلب الأسعار الحية =================
def get_live_gold():
    res = requests.get("https://gold-api.com", timeout=15).json()
    ounce = float(res.get("price", 0))
    ch = float(res.get("ch", 0))
    chp = float(res.get("chp", 0))
    buy_24k = round((ounce / 31.1035) * 0.3170, 3)
    sell_24k = round(buy_24k - 0.250, 3)
    return ounce, ch, chp, buy_24k, sell_24k

# ================= 4. دالة التقرير التلقائي (تعمل في الخلفية أو يدوياً) =================
def generate_and_send_report(send_notifications=False):
    ounce, ch, chp, buy_24k, sell_24k = get_live_gold()
    sheet_dashboard.update_acell("C5", ounce)

    portfolio_rows = sheet_dashboard.get("A5:I18")
    portfolio_text = "\n".join([
        f"{r if len(r)>0 else ''} {r if len(r)>2 else ''} {r if len(r)>5 else ''} {r if len(r)>7 else ''}"
        for r in portfolio_rows
    ])
    targets_rows = sheet_dashboard.get("A19:B21")
    targets_text = "\n".join([f"{r if len(r)>0 else ''} {r if len(r)>1 else ''}" for r in targets_rows])

    rss_url = "https://google.com"
    feed = feedparser.parse(rss_url)
    news_text = "\n".join([entry.title for entry in feed.entries[:7]])

    now_kw = datetime.now(KUWAIT_TZ).strftime("%A, %Y-%m-%d %H:%M")
    prompt = f"""أنت مستشاري المالي ومحلل أسواق الذهب في الكويت (تطبيق دار السبائك).
🗓️ اليوم والوقت الحالي بتوقيت الكويت: {now_kw}

قواعد صارمة وحسابية:
1. تنسيق الرسالة: اكتب التقرير بتنسيق HTML المتوافق مع تليجرام فقط. استخدم وسوم <b>العنوان</b> للخط العريض، ويُمنع تماماً استخدام النجوم ** أو علامات # أو أي رموز Markdown.
2. قاعدة التقرير الأسبوعي: إذا كان اسم اليوم هو "Sunday" وكانت الساعة حوالي "18"، اكتب "<b>التقرير الأسبوعي الشامل لما قبل افتتاح البورصة</b>". أما في باقي أيام الأسبوع فابدأ بالتقرير المعتاد مباشرة.
3. اعتمد دائماً على الأرقام الفعلية لرصيدي ومتوسط تكلفتي الموجودة في (بيانات محفظتي). إذا كان متوسط تكلفتي أعلى من سعر السوق الحالي، فأنا في حالة خسارة دفترية ويُمنع تماماً اقتراح البيع.
4. لدي سيولة نقدية مقسمة على 3 دفعات لخفض المتوسط، وأترقب استمرار الهبوط.
5. بروتوكول الطوارئ: إذا تحركت الأونصة صعوداً أو هبوطاً بأكثر من 35$ (أو أكثر من 1.2%) خلال اليوم، ابدأ بـ:
<b>⚠️🚨 إنذار طوارئ: حركة عنيفة في سوق الذهب الآن! 🚨⚠️</b>
6. تنبيهات القنص الذكية: قارن سعر جرام 24 المحسوب ({buy_24k} د.ك) بـ (مستهدفات الشراء الديناميكية من ملفي). إذا كان أقل من أو يساوي أياً من المستهدفات، ابدأ بـ:
<b>🎯🚨 تنبيه قنص ذكي: السعر وصل لمنطقة الشراء المستهدفة! 🚨🎯</b>

اكتب التقرير بالعربية بشكل منظم ومختصر جداً كالتالي:
<b>📉 تحليل السوق واتجاه الأسعار:</b>
<b>📅 الأخبار المنتظرة ومواعيدها:</b>
<b>🚨 قرار الشراء الآن (خطة السيولة):</b>
<b>📊 أسعار اللحظة والمحفظة:</b>

--- البيانات الحية ---
• السعر الحي للأونصة ($): {ounce}
• التغير اليومي ($): {ch} | نسبة التغير (%): {chp}%
• بيانات محفظتي: {portfolio_text}
• مستهدفات الشراء الديناميكية من ملفي: {targets_text}
• الأخبار والتحليلات الحية: {news_text}
"""
    res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    report_text = res.text

    if send_notifications:
        if TELEGRAM_TOKEN:
            tg_url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
            requests.post(tg_url, json={"chat_id": CHAT_ID, "text": report_text, "parse_mode": "HTML"}, timeout=15)
        wa_url = f"https://callmebot.com{WHATSAPP_PHONE}&apikey={WHATSAPP_APIKEY}&text={requests.utils.quote(report_text[:900])}"
        requests.get(wa_url, timeout=15)

    return report_text

# ================= 5. التحقق من رابط الجدولة التلقائية (Cron) =================
if st.query_params.get("cron") == "run":
    generate_and_send_report(send_notifications=True)
    st.success("CRON_OK")
    st.stop()

# ================= 6. واجهة التطبيق على الموبايل =================
st.title("🪙 محفظة دار السبائك AI")

try:
    ounce, ch, chp, buy_24k, sell_24k = get_live_gold()
    sheet_dashboard.update_acell("C5", ounce)

    col1, col2, col3 = st.columns(3)
    col1.metric("الأونصة ($)", f"{ounce:,.2f}", f"{ch:+.2f}$")
    col2.metric("شراء 24 (د.ك)", f"{buy_24k:.3f}")
    col3.metric("بيع 24 (د.ك)", f"{sell_24k:.3f}")
except Exception as e:
    st.error("تعذر جلب السعر الحي حالياً.")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["📊 المحفظة", "➕ صفقة جديدة", "🤖 المستشار AI", "📜 السجل"])

with tab1:
    rows = sheet_dashboard.get("A15:I15")
    row = rows if rows else ["0"]*9
    c1, c2 = st.columns(2)
    c1.metric("رصيد الذهب", f"{row} جم")
    c2.metric("متوسط التكلفة", f"{row} د.ك")

    c3, c4 = st.columns(2)
    c3.metric("القيمة السوقية", f"{row} د.ك")
    c4.metric("الربح / الخسارة", f"{row} د.ك")

    if st.button("🔄 تحديث البيانات والأسعار"):
        st.rerun()

with tab2:
    st.subheader("تسجيل صفقة في دار السبائك")
    op_type = st.radio("نوع العملية", ["شراء", "بيع"], horizontal=True)
    grams = st.number_input("الوزن (بالجرام)", min_value=0.1, step=1.0, format="%.2f")
    price_input = st.number_input("سعر الجرام أو إجمالي الفاتورة (د.ك)", min_value=0.001, step=0.1, format="%.3f")

    if st.button("✅ تسجيل العملية الآن"):
        final_price = round(price_input / grams, 4) if price_input > 150 else price_input
        today_str = datetime.now(KUWAIT_TZ).strftime("%Y-%m-%d")
        sheet_log.append_row([today_str, op_type, final_price, grams], value_input_option="USER_ENTERED")
        st.success(f"تم تسجيل {op_type} {grams} جم بسعر {final_price} د.ك بنجاح!")

with tab3:
    st.subheader("اسأل المستشار الذكي (ماذا لو؟)")
    user_q = st.text_input("مثال: شنو يصير لو شريت 10 جرام الحين؟")
    if st.button("احسب وحلّل"):
        if user_q:
            with st.spinner("جاري الحساب..."):
                rows = sheet_dashboard.get("A13:I16")
                prompt = f"""أنت حاسبة ذكية ومستشار مالي لمحفظة ذهب (دار السبائك - الكويت). أجب باختصار شديد وبالعربية:
- سعر الشراء 24: {buy_24k} د.ك | سعر البيع 24: {sell_24k} د.ك | الأونصة: {ounce}$
- بيانات المحفظة: {rows}
- سؤال المستخدم: {user_q}"""
                res = ai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                st.info(res.text)

    st.divider()
    if st.button("📢 توليد التقرير الشامل وإرساله لتيليجرام وواتساب"):
        with st.spinner("جاري إعداد التقرير وإرساله..."):
            rep = generate_and_send_report(send_notifications=True)
            st.markdown(rep, unsafe_allow_html=True)

with tab4:
    all_rows = sheet_log.get_all_values()
    last_5 = all_rows[-5:][::-1]
    for r in last_5:
        if len(r) >= 4:
            st.write(f"• **{r}** | {r}: {r} جم بسعر {r} د.ك")

    st.divider()
    if st.button("🗑️ حذف آخر صفقة مسجلة"):
        if len(all_rows) > 1:
            sheet_log.delete_rows(len(all_rows))
            st.warning("تم حذف آخر صفقة وتحديث الرصيد!")
            st.rerun()
