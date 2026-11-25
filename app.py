import streamlit as st
from datetime import datetime
import config
import services

st.set_page_config(
    page_title="دار السبائك AI",
    page_icon="🪙",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .main { direction: rtl; text-align: right; }
    div[data-testid="stMetricValue"] { font-size: 1.3rem; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.1em; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

sheet_dashboard, sheet_log = services.init_sheets()

# ================= التحقق من رابط الجدولة التلقائية (Cron) قبل القفل =================
if st.query_params.get("cron") == "run":
    services.generate_and_send_report(sheet_dashboard, send_notifications=True)
    st.success("CRON_OK")
    st.stop()

# ================= 1. شاشة قفل الحماية برقم سري (PIN) =================
APP_PIN = st.secrets.get("APP_PIN", "1234")
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 محفظة دار السبائك AI")
    pin_input = st.text_input("أدخل الرقم السري للدخول", type="password", max_chars=8)
    if st.button("دخول المحفظة"):
        if pin_input == str(APP_PIN):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ الرقم السري غير صحيح")
    st.stop()

# ================= 2. شريط الأسعار الحية =================
st.title("🪙 محفظة دار السبائك AI")

try:
    ounce, ch, chp, buy_24k, sell_24k = services.get_live_gold()
    if ounce > 0:
        sheet_dashboard.update_acell("C5", ounce)

    col1, col2, col3 = st.columns(3)
    col1.metric("الأونصة ($)", f"{ounce:,.2f}", f"{ch:+.2f}$")
    col2.metric("شراء 24 (د.ك)", f"{buy_24k:.3f}")
    col3.metric("بيع 24 (د.ك)", f"{sell_24k:.3f}")
except Exception as e:
    ounce, buy_24k, sell_24k = 0, 0, 0
    st.warning(f"تنبيه السعر الحي: {e}")

st.divider()

# قراءة بيانات المحفظة الأساسية للاستخدام في التبويبات
gold_balance_str = sheet_dashboard.acell("A15").value or "0"
total_cost_str = sheet_dashboard.acell("B15").value or "0"
market_val_str = sheet_dashboard.acell("C15").value or "0"
avg_cost_str = sheet_dashboard.acell("D15").value or "0"

try:
    curr_grams = float(gold_balance_str.replace(",", ""))
    curr_avg = float(avg_cost_str.replace(",", ""))
except ValueError:
    curr_grams, curr_avg = 0.0, 0.0

# ================= 3. تبويبات التطبيق الخمسة =================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 المحفظة",
    "🎯 مناطق الشراء",
    "🧮 الحاسبة والزكاة",
    "➕ صفقة",
    "📜 السجل"
])

# --- التبويب 1: موقف المحفظة والرسم البياني ---
with tab1:
    c1, c2 = st.columns(2)
    c1.metric("رصيد الذهب", f"{gold_balance_str} جم")
    c2.metric("متوسط التكلفة", f"{avg_cost_str} د.ك")

    c3, c4 = st.columns(2)
    c3.metric("إجمالي التكلفة", f"{total_cost_str} د.ك")
    c4.metric("القيمة السوقية", f"{market_val_str}")

    st.subheader("📈 حركة سعر جرام 24 (آخر 30 يوماً)")
    try:
        chart_df, _ = services.get_chart_and_technicals()
        if curr_avg > 0:
            chart_df["متوسط تكلفتك (د.ك)"] = curr_avg
        st.line_chart(chart_df)
    except Exception:
        st.info("جاري تحميل بيانات الرسم البياني...")

    if st.button("🔄 تحديث البيانات والأسعار"):
        st.rerun()

# --- التبويب 2: مقترح أفضل مناطق الشراء والمستشار AI ---
with tab2:
    st.subheader("🎯 اقتراح أفضل أسعار الشراء (تحليل فني + أساسي)")
    st.caption("يحلل المؤشرات الفنية لـ 30 يوماً والأخبار الحية ليقترح 3 دفعات شراء لتخفيض متوسطك.")
    
    if st.button("🔍 استخرج أفضل 3 مناطق شراء الآن"):
        with st.spinner("جاري تحليل الشارت والأخبار واقتراح المستويات..."):
            zones = services.suggest_best_buy_zones(ounce, buy_24k, curr_avg, curr_grams)
            st.success(zones)

    st.divider()
    st.subheader("🤖 اسأل المستشار الذكي")
    user_q = st.text_input("مثال: هل الوقت مناسب لشراء 20 جرام أم أنتظر؟")
    if st.button("احسب وحلّل"):
        if user_q:
            with st.spinner("جاري الحساب..."):
                portfolio_rows = sheet_dashboard.get("A13:I16")
                answer = services.ask_ai_advisor(user_q, ounce, buy_24k, sell_24k, portfolio_rows)
                st.info(answer)

    st.divider()
    if st.button("📢 إرسال التقرير الشامل لتيليجرام وواتساب"):
        with st.spinner("جاري إعداد التقرير وإرساله..."):
            rep = services.generate_and_send_report(sheet_dashboard, send_notifications=True)
            st.markdown(rep, unsafe_allow_html=True)

# --- التبويب 3: حاسبة تعديل المتوسط + الزكاة ---
with tab3:
    st.subheader("🧮 محاكي تعديل المتوسط (ماذا لو اشتريت؟)")
    sim_grams = st.slider("الكمية المقترحة للشراء (بالجرام)", min_value=1, max_value=200, value=20, step=1)
    sim_price = st.number_input("سعر الشراء المتوقع للجرام (د.ك)", value=float(buy_24k) if buy_24k > 0 else 35.0, step=0.1, format="%.3f")

    if curr_grams > 0 and curr_avg > 0:
        old_total = curr_grams * curr_avg
        new_total = old_total + (sim_grams * sim_price)
        new_grams = curr_grams + sim_grams
        new_avg = round(new_total / new_grams, 3)
        diff_avg = round(new_avg - curr_avg, 3)

        m1, m2 = st.columns(2)
        m1.metric("متوسط التكلفة الجديد", f"{new_avg:.3f} د.ك", f"{diff_avg:+.3f} د.ك", delta_color="inverse")
        m2.metric("الرصيد الإجمالي الجديد", f"{new_grams:.1f} جم", f"+{sim_grams} جم")
        st.caption(f"التكلفة الإجمالية للدفعة الجديدة: **{round(sim_grams * sim_price, 3):,.3f} د.ك**")

    st.divider()
    st.subheader("🕌 حاسبة زكاة الذهب التلقائية")
    if curr_grams >= config.ZAKAT_NISAB_GRAMS:
        zakat_grams = round(curr_grams * config.ZAKAT_RATE, 3)
        zakat_kwd = round(zakat_grams * sell_24k, 3)
        st.warning(f"رصيدك ({curr_grams} جم) بلغ النصاب الشرعي (85 جم عيار 24).")
        z1, z2 = st.columns(2)
        z1.metric("مقدار الزكاة (بالجرام)", f"{zakat_grams} جم")
        z2.metric("قيمة الزكاة النقدية", f"{zakat_kwd:,.3f} د.ك")
    else:
        st.success(f"رصيدك ({curr_grams} جم) لم يبلغ النصاب الشرعي (85 جم) بعد.")

# --- التبويب 4: تسجيل صفقة جديدة ---
with tab4:
    st.subheader("تسجيل صفقة في دار السبائك")
    op_type = st.radio("نوع العملية", ["شراء", "بيع"], horizontal=True)
    grams = st.number_input("الوزن (بالجرام)", min_value=0.1, step=1.0, format="%.2f")
    price_input = st.number_input("سعر الجرام أو إجمالي الفاتورة (د.ك)", min_value=0.001, step=0.1, format="%.3f")

    if st.button("✅ تسجيل العملية الآن"):
        final_price = round(price_input / grams, 4) if price_input > 150 else price_input
        today_str = datetime.now(config.KUWAIT_TZ).strftime("%Y-%m-%d")
        sheet_log.append_row([today_str, op_type, final_price, grams], value_input_option="USER_ENTERED")
        st.success(f"تم تسجيل {op_type} {grams} جم بسعر {final_price} د.ك بنجاح!")

# --- التبويب 5: سجل العمليات والحذف ---
with tab5:
    all_rows = sheet_log.get_all_values()
    last_5 = list(reversed(all_rows))[:5]
    for r in last_5:
        if len(r) >= 4 and r != "التاريخ":
            st.write(" • ".join(r[:4]))

    st.divider()
    if st.button("🗑️ حذف آخر صفقة مسجلة"):
        if len(all_rows) > 1:
            sheet_log.delete_rows(len(all_rows))
            st.warning("تم حذف آخر صفقة وتحديث الرصيد!")
            st.rerun()
