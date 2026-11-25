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
    div[data-testid="stMetricValue"] { font-size: 1.35rem; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.1em; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

sheet_dashboard, sheet_log = services.init_sheets()

# ================= التحقق من رابط الجدولة التلقائية (Cron) =================
if st.query_params.get("cron") == "run":
    services.generate_and_send_report(sheet_dashboard, send_notifications=True)
    st.success("CRON_OK")
    st.stop()

# ================= شريط الأسعار الحية =================
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

# ================= تبويبات التطبيق =================
tab1, tab2, tab3, tab4 = st.tabs(["📊 المحفظة", "➕ صفقة جديدة", "🤖 المستشار AI", "📜 السجل"])

with tab1:
    # قراءة كل خلية مباشرة لضمان دقة العرض 100%
    gold_balance = sheet_dashboard.acell("A15").value or "0"
    total_cost = sheet_dashboard.acell("B15").value or "0"
    market_val = sheet_dashboard.acell("C15").value or "0"
    avg_cost = sheet_dashboard.acell("D15").value or "0"

    c1, c2 = st.columns(2)
    c1.metric("رصيد الذهب", f"{gold_balance} جم")
    c2.metric("متوسط التكلفة", f"{avg_cost} د.ك")

    c3, c4 = st.columns(2)
    c3.metric("إجمالي التكلفة", f"{total_cost} د.ك")
    c4.metric("القيمة السوقية", f"{market_val}")

    if st.button("🔄 تحديث البيانات والأسعار"):
        st.rerun()

with tab2:
    st.subheader("تسجيل صفقة في دار السبائك")
    op_type = st.radio("نوع العملية", ["شراء", "بيع"], horizontal=True)
    grams = st.number_input("الوزن (بالجرام)", min_value=0.1, step=1.0, format="%.2f")
    price_input = st.number_input("سعر الجرام أو إجمالي الفاتورة (د.ك)", min_value=0.001, step=0.1, format="%.3f")

    if st.button("✅ تسجيل العملية الآن"):
        final_price = round(price_input / grams, 4) if price_input > 150 else price_input
        today_str = datetime.now(config.KUWAIT_TZ).strftime("%Y-%m-%d")
        sheet_log.append_row([today_str, op_type, final_price, grams], value_input_option="USER_ENTERED")
        st.success(f"تم تسجيل {op_type} {grams} جم بسعر {final_price} د.ك بنجاح!")

with tab3:
    st.subheader("اسأل المستشار الذكي (ماذا لو؟)")
    user_q = st.text_input("مثال: شنو يصير لو شريت 10 جرام الحين؟")
    if st.button("احسب وحلّل"):
        if user_q:
            with st.spinner("جاري الحساب..."):
                portfolio_rows = sheet_dashboard.get("A13:I16")
                answer = services.ask_ai_advisor(user_q, ounce, buy_24k, sell_24k, portfolio_rows)
                st.info(answer)

    st.divider()
    if st.button("📢 توليد التقرير الشامل وإرساله لتيليجرام وواتساب"):
        with st.spinner("جاري إعداد التقرير وإرساله..."):
            rep = services.generate_and_send_report(sheet_dashboard, send_notifications=True)
            st.markdown(rep, unsafe_allow_html=True)

with tab4:
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
