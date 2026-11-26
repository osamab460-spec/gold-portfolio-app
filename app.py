import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
import config
import services

st.set_page_config(page_title="دار السبائك AI", page_icon="🪙", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #121212 !important; color: #FFFFFF !important; }
    .main { direction: rtl; text-align: right; }
    p, span, label, div, h1, h2, h3, h4 { color: #F5F5F5 !important; }
    div[data-testid="stAlert"] { background-color: #1C1C1E !important; border: 1px solid #E6C25A !important; border-radius: 12px; }
    div[data-baseweb="select"] > div, input, textarea { background-color: #1C1C1E !important; color: #FFFFFF !important; border-color: #333333 !important; }
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul[role="listbox"], li[role="option"] { background-color: #1C1C1E !important; color: #FFFFFF !important; }
    li[role="option"]:hover { background-color: #2E2E32 !important; }
    .sabaek-top { display: flex; justify-content: space-between; align-items: center; padding: 8px 4px 14px 4px; border-bottom: 1px solid #2A2A2A; margin-bottom: 14px; }
    .sabaek-logo { color: #E6C25A !important; font-size: 1.7rem !important; font-weight: 900 !important; }
    .gold-ticker-box { background-color: #1C1C1E; border: 1px solid #2E2E32; border-radius: 14px; padding: 14px 16px; margin-bottom: 12px; direction: ltr; text-align: left; }
    .gold-ticker-title { color: #E6C25A !important; font-weight: 800; font-size: 1.05rem; display: flex; align-items: center; gap: 8px; }
    .gold-ticker-price { font-size: 1.45rem; font-weight: 800; margin-top: 6px; }
    .karats-grid { display: grid; grid-template-columns: repeat(4, 1fr); background-color: #1C1C1E; border: 1px solid #2E2E32; border-radius: 14px; padding: 12px 6px; margin-bottom: 14px; text-align: center; direction: rtl; }
    .karat-item { border-left: 1px solid #2E2E32; padding: 0 4px; }
    .karat-item:last-child { border-left: none; }
    .karat-name { color: #B0B0B0 !important; font-size: 0.85rem; margin-bottom: 4px; }
    .karat-val { font-size: 1.02rem; font-weight: 800; }
    .price-up { color: #00E676 !important; }
    .price-down { color: #FF3D00 !important; }
    .price-same { color: #111111 !important; background-color: #E0E0E0 !important; padding: 1px 6px; border-radius: 6px; }
    div[data-testid="stMetric"] { background-color: #1C1C1E !important; border: 1px solid #2E2E32 !important; border-right: 4px solid #E6C25A !important; border-radius: 12px; padding: 10px 12px; }
    div[data-testid="stMetricLabel"] p { color: #E6C25A !important; font-size: 0.85rem !important; }
    div[data-testid="stMetricValue"] div { color: #FFFFFF !important; font-size: 1.25rem !important; }
    .stButton>button { width: 100%; background: linear-gradient(90deg, #D4AF37 0%, #F3D06B 100%) !important; border: none !important; border-radius: 12px; height: 3.1em; }
    .stButton>button p { color: #121212 !important; font-weight: 800 !important; font-size: 1rem !important; }
    div[role="radiogroup"] { direction: rtl; justify-content: center; background-color: #1C1C1E !important; padding: 8px; border-radius: 14px; border: 1px solid #333333; gap: 6px; }
    div[role="radiogroup"] label p { color: #FFFFFF !important; font-size: 0.9rem !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)

sheet_dashboard, sheet_log = services.init_sheets()

if st.query_params.get("cron") == "run":
    services.generate_and_send_report(sheet_dashboard, send_notifications=True)
    st.success("CRON_OK")
    st.stop()

APP_PIN = st.secrets.get("APP_PIN", "1234")
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown('<div style="text-align:center; padding:20px;"><span class="sabaek-logo">🪙 دار السبائك AI</span></div>', unsafe_allow_html=True)
    pin_input = st.text_input("أدخل الرقم السري للدخول", type="password", max_chars=8)
    if st.button("🔓 دخول المحفظة"):
        if pin_input == str(APP_PIN):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ الرقم السري غير صحيح")
    st.stop()

@st.fragment(run_every=15)
def live_sabaek_ticker():
    try:
        data = services.get_live_gold()
        ounce, chp = data["ounce"], data["chp"]
        buy_24k, sell_24k = data["buy_24k"], data["sell_24k"]
        k22, k21, k18 = data["k22"], data["k21"], data["k18"]

        st.session_state["live_ounce"] = ounce
        st.session_state["live_buy_24k"] = buy_24k
        st.session_state["live_sell_24k"] = sell_24k

        prev_ounce = st.session_state.get("prev_tick_ounce", ounce)
        if ounce > prev_ounce:
            color_cls, arrow = "price-up", "▲"
        elif ounce < prev_ounce:
            color_cls, arrow = "price-down", "▼"
        else:
            color_cls, arrow = "price-same", "•"
        st.session_state["prev_tick_ounce"] = ounce

        if ounce > 0:
            sheet_dashboard.update_acell("C5", ounce)

        st.markdown(f"""
        <div class="sabaek-top"><span class="sabaek-logo">🪙 دار السبائك AI</span><span style="color:#9E9E9E; font-size:0.8rem;">تحديث تلقائي 15ث ⏱️</span></div>
        <div class="gold-ticker-box">
            <div class="gold-ticker-title">🪙 GOLD SPOT <span style="font-size:0.75rem; color:#888; margin-left:auto;">XAU/USD Live</span></div>
            <div class="gold-ticker-price"><span class="{color_cls}">{ounce:,.3f}</span><span style="font-size:0.9rem; color:#BDBDBD;"> USD </span><span class="{color_cls}" style="font-size:0.95rem;">{arrow} {chp:+.2f}%</span></div>
        </div>
        <div class="karats-grid">
            <div class="karat-item"><div class="karat-name">عيار ٢٤</div><div class="karat-val {color_cls}">{buy_24k:.3f} د.ك</div></div>
            <div class="karat-item"><div class="karat-name">عيار ٢٢</div><div class="karat-val {color_cls}">{k22:.3f} د.ك</div></div>
            <div class="karat-item"><div class="karat-name">عيار ٢١</div><div class="karat-val {color_cls}">{k21:.3f} د.ك</div></div>
            <div class="karat-item"><div class="karat-name">عيار ١٨</div><div class="karat-val {color_cls}">{k18:.3f} د.ك</div></div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"جاري مزامنة السعر: {e}")

live_sabaek_ticker()

ounce = st.session_state.get("live_ounce", 0.0)
buy_24k = st.session_state.get("live_buy_24k", 0.0)
sell_24k = st.session_state.get("live_sell_24k", 0.0)

gold_balance_str = sheet_dashboard.acell("A15").value or "0"
total_cost_str = sheet_dashboard.acell("B15").value or "0"
market_val_str = sheet_dashboard.acell("C15").value or "0"
avg_cost_str = sheet_dashboard.acell("D15").value or "0"

try:
    curr_grams = float(gold_balance_str.replace(",", ""))
    curr_avg = float(avg_cost_str.replace(",", ""))
except ValueError:
    curr_grams, curr_avg = 0.0, 0.0

page = st.radio("القائمة", ["🏠 الرئيسية والشموع", "🎯 مناطق الشراء", "🧮 الحاسبة والزكاة", "➕ صفقة", "📜 السجل"], horizontal=True, label_visibility="collapsed")
st.write("")

if page == "🏠 الرئيسية والشموع":
    c_tf, c_unit, c_opt = st.columns(3)
    tf_label = c_tf.selectbox("الفاصل الزمني", ["15 دقيقة", "10 دقائق", "ساعة", "يومي"])
    tf_map = {"15 دقيقة": "15m", "10 دقائق": "10m", "ساعة": "1h", "يومي": "1d"}
    unit_label = c_unit.selectbox("العملة", ["دينار كويتي (د.ك)", "دولار أمريكي ($)"])
    unit_code = "KWD" if "كويتي" in unit_label else "USD"
    show_avg = c_opt.checkbox("خط متوسط تكلفتي", value=True)
    chart_style = c_opt.selectbox("نوع الرسم", ["شموع يابانية 🕯️", "خطي ذهبي 📈"])

    try:
        df_candles = services.get_candlestick_data(timeframe=tf_map[tf_label], unit=unit_code)
        if chart_style == "شموع يابانية 🕯️":
            trace = go.Candlestick(x=df_candles.index, open=df_candles["Open"], high=df_candles["High"], low=df_candles["Low"], close=df_candles["Close"], increasing_line_color="#00E676", decreasing_line_color="#FF3D00", name="السعر")
        else:
            trace = go.Scatter(x=df_candles.index, y=df_candles["Close"], mode="lines+markers", line=dict(color="#E6C25A", width=2.5), marker=dict(size=5, color="#FFD700"), fill="tozeroy", fillcolor="rgba(230, 194, 90, 0.12)", name="السعر")

        fig = go.Figure(data=[trace])
        if show_avg and unit_code == "KWD" and curr_avg > 0:
            fig.add_hline(y=curr_avg, line_dash="dash", line_color="#FFD700", line_width=1.8, annotation_text=f"متوسط تكلفتك: {curr_avg:.3f}", annotation_position="top right", annotation_font_color="#FFD700")

        fig.update_layout(template="plotly_dark", paper_bgcolor="#1C1C1E", plot_bgcolor="#141416", height=380, margin=dict(l=8, r=8, t=25, b=8), xaxis_rangeslider_visible=False, dragmode="pan")
        plotly_cfg = {"displayModeBar": True, "scrollZoom": True, "modeBarButtonsToAdd": ["drawline", "drawopenpath", "drawrect", "eraseshape"]}
        st.plotly_chart(fig, use_container_width=True, config=plotly_cfg)
        st.caption("✏️ استخدم شريط الأدوات أعلى الشارت لرسم خطوط الاتجاه والدعم، أو التبديل بين الشموع والرسم الخطي.")
    except Exception as e:
        st.warning(f"تنبيه الشارت: {e}")

    st.subheader("💼 ملخص محفظتي")
    m1, m2 = st.columns(2)
    m1.metric("رصيد الذهب", f"{gold_balance_str} جم")
    m2.metric("متوسط التكلفة", f"{avg_cost_str} د.ك")
    m3, m4 = st.columns(2)
    m3.metric("إجمالي التكلفة", f"{total_cost_str} د.ك")
    m4.metric("سعر البيع (دار السبائك)", f"{sell_24k:.3f} د.ك")

elif page == "🎯 مناطق الشراء":
    st.subheader("🎯 اقتراح أفضل أسعار الشراء")
    if st.button("🔍 استخرج أفضل 3 مناطق شراء الآن"):
        st.info("⏳ جاري تحليل الشارت والأخبار...")
        zones = services.suggest_best_buy_zones(ounce, buy_24k, curr_avg, curr_grams)
        st.success(zones)
    st.divider()
    st.subheader("🤖 اسأل المستشار الذكي")
