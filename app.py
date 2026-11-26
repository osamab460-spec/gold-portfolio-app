import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
import config
import services

st.set_page_config(
    page_title="دار السبائك AI",
    page_icon="🪙",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ================= تصميم واجهة فخمة (Gold & Dark Theme) =================
st.markdown("""
<style>
    /* خلفية داكنة فخمة واتجاه عربي */
    .stApp {
        background-color: #0E1117;
        color: #F5F5F5;
    }
    .main { direction: rtl; text-align: right; }
    
    /* تنسيق العنوان الرئيسي */
    .gold-header {
        background: linear-gradient(135deg, #1E2129 0%, #14171F 100%);
        border: 1px solid #D4AF37;
        border-radius: 16px;
        padding: 16px;
        text-align: center;
        margin-bottom: 18px;
        box-shadow: 0 4px 15px rgba(212, 175, 55, 0.15);
    }
    .gold-header h1 {
        color: #FFD700;
        font-size: 1.65rem;
        margin: 0;
        font-weight: 800;
    }
    .gold-header p {
        color: #A0AAB5;
        font-size: 0.85rem;
        margin: 4px 0 0 0;
    }

    /* بطاقات المؤشرات */
    div[data-testid="stMetric"] {
        background-color: #161A23;
        border: 1px solid #2A303E;
        border-right: 4px solid #D4AF37;
        border-radius: 12px;
        padding: 12px 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetricLabel"] {
        color: #9BA3AF !important;
        font-size: 0.85rem !important;
    }
    div[data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-size: 1.3rem !important;
        font-weight: 700 !important;
    }

    /* الأزرار الذهبية */
    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #C59B27 0%, #E5C158 100%);
        color: #0E1117 !important;
        border: none;
        border-radius: 12px;
        height: 3.1em;
        font-weight: 800;
        font-size: 1rem;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(212, 175, 55, 0.4);
    }

    /* شريط التنقل */
    div[role="radiogroup"] {
        direction: rtl;
        justify-content: center;
        background-color: #161A23;
        padding: 8px;
        border-radius: 14px;
        border: 1px solid #2A303E;
        gap: 6px;
    }
</style>
""", unsafe_allow_html=True)

sheet_dashboard, sheet_log = services.init_sheets()

# ================= التحقق من رابط الجدولة التلقائية =================
if st.query_params.get("cron") == "run":
    services.generate_and_send_report(sheet_dashboard, send_notifications=True)
    st.success("CRON_OK")
    st.stop()

# ================= 1. شاشة قفل الحماية برقم سري (PIN) =================
APP_PIN = st.secrets.get("APP_PIN", "1234")
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("""
    <div class="gold-header">
        <h1>🔐 محفظة دار السبائك AI</h1>
        <p>نظام إدارة واستثمار الذهب الذكي • الكويت</p>
    </div>
    """, unsafe_allow_html=True)
    pin_input = st.text_input("أدخل الرقم السري للدخول", type="password", max_chars=8)
    if st.button("🔓 فتح المحفظة"):
        if pin_input == str(APP_PIN):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ الرقم السري غير صحيح")
    st.stop()

# ================= 2. الترويسة وشريط الأسعار الحية =================
st.markdown("""
<div class="gold-header">
    <h1>🪙 محفظة دار السبائك AI</h1>
    <p>متابعة لحظية • تحليل فني • إدارة سيولة</p>
</div>
""", unsafe_allow_html=True)

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

# قراءة بيانات المحفظة الأساسية
gold_balance_str = sheet_dashboard.acell("A15").value or "0"
total_cost_str = sheet_dashboard.acell("B15").value or "0"
market_val_str = sheet_dashboard.acell("C15").value or "0"
avg_cost_str = sheet_dashboard.acell("D15").value or "0"

try:
    curr_grams = float(gold_balance_str.replace(",", ""))
    curr_avg = float(avg_cost_str.replace(",", ""))
except ValueError:
    curr_grams, curr_avg = 0.0, 0.0

st.write("")

# ================= 3. شريط التنقل الاحترافي =================
page = st.radio(
    "اختر القسم:",
    ["📊 المحفظة والشموع", "🎯 مناطق الشراء", "🧮 الحاسبة والزكاة", "➕ صفقة", "📜 السجل"],
    horizontal=True,
    label_visibility="collapsed"
)

st.write("")

# --- الصفحة 1: موقف المحفظة وشارت الشموع التفاعلي ---
if page == "📊 المحفظة والشموع":
    c1, c2 = st.columns(2)
    c1.metric("رصيد الذهب", f"{gold_balance_str} جم")
    c2.metric("متوسط التكلفة", f"{avg_cost_str} د.ك")

    c3, c4 = st.columns(2)
    c3.metric("إجمالي التكلفة", f"{total_cost_str} د.ك")
    c4.metric("القيمة السوقية", f"{market_val_str}")

    st.subheader("🕯️ شارت الشموع اليابانية التفاعلي")
    
    # أدوات التحكم وتحرير الشارت
    ctrl1, ctrl2, ctrl3 = st.columns(3)
    with ctrl1:
        tf_label = st.selectbox("الإطار الزمني", ["يومي (شهرين)", "ساعي (7 أيام)", "ربع ساعة (يومين)"])
        tf_map = {"يومي (شهرين)": "1d", "ساعي (7 أيام)": "1h", "ربع ساعة (يومين)": "15m"}
    with ctrl2:
        unit_label = st.selectbox("العملة", ["دينار كويتي (جرام 24)", "دولار أمريكي (الأونصة)"])
        unit_code = "KWD" if "كويتي" in unit_label else "USD"
    with ctrl3:
        show_avg = st.checkbox("إظهار خط متوسط تكلفتي", value=True)
        show_sma = st.checkbox("إظهار المتوسط المتحرك (MA10)", value=True)

    try:
        df_candles = services.get_candlestick_data(timeframe=tf_map[tf_label], unit=unit_code)
        
        fig = go.Figure(data=[go.Candlestick(
            x=df_candles.index,
            open=df_candles["Open"],
            high=df_candles["High"],
            low=df_candles["Low"],
            close=df_candles["Close"],
            increasing_line_color="#00C853",
            decreasing_line_color="#FF3D00",
            name="السعر"
        )])

        # إضافة خط متوسط التكلفة إذا كانت العملة دينار كويتي
        if show_avg and unit_code == "KWD" and curr_avg > 0:
            fig.add_hline(
                y=curr_avg,
                line_dash="dash",
                line_color="#FFD700",
                line_width=2,
                annotation_text=f"متوسط تكلفتك: {curr_avg:.3f} د.ك",
                annotation_position="top right",
                annotation_font_color="#FFD700"
            )

        # إضافة خط المتوسط المتحرك السريع
        if show_sma and len(df_candles) >= 10:
            sma10 = df_candles["Close"].rolling(window=10).mean()
            fig.add_trace(go.Scatter(
                x=df_candles.index,
                y=sma10,
                mode="lines",
                line=dict(color="#29B6F6", width=1.5),
                name="MA 10"
            ))

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#161A23",
            plot_bgcolor="#0E1117",
            height=420,
            margin=dict(l=10, r=10, t=30, b=10),
            xaxis_rangeslider_visible=False,
            dragmode="pan",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        # تفعيل شريط أدوات التحرير والرسم فوق الشارت (رسم خطوط، تكبير، تصوير)
        plotly_config = {
            "displayModeBar": True,
            "scrollZoom": True,
            "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"]
        }
        st.plotly_chart(fig, use_container_width=True, config=plotly_config)
        st.caption("💡 يمكنك لمس الشموع لعرض التفاصيل، أو استخدام أدوات الرسم أعلى الشارت لرسم خطوط الدعم والمقاومة.")
    except Exception as e:
        st.info(f"جاري تحميل بيانات الشموع: {e}")

    if st.button("🔄 تحديث البيانات والأسعار"):
        st.rerun()

# --- الصفحة 2: مقترح أفضل مناطق الشراء والمستشار AI ---
elif page == "🎯 مناطق الشراء":
    st.subheader("🎯 اقتراح أفضل أسعار الشراء")
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

# --- الصفحة 3: حاسبة تعديل المتوسط + الزكاة ---
elif page == "🧮 الحاسبة والزكاة":
    st.subheader("🧮 محاكي تعديل المتوسط (ماذا لو اشتريت؟)")
    sim_grams = st.slider("الكمية المقترحة للشراء (بالجرام)", min_value=1, max_value=200, value=20, step=1)
    default_price = float(buy_24k) if buy_24k > 0 else 35.0
    sim_price = st.number_input("سعر الشراء المتوقع للجرام (د.ك)", value=default_price, step=0.1, format="%.3f")

    if curr_grams > 0 and curr_avg > 0:
        old_total = curr_grams * curr_avg
        new_total = old_total + (sim_grams * sim_price)
        new_grams = curr_grams + sim_grams
