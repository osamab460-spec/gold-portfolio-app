import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import config
import services

st.set_page_config(page_title="دار السبائك AI", page_icon="🪙", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .main { direction: rtl; text-align: right; }
    .sabaek-top { display: flex; justify-content: space-between; align-items: center; padding: 8px 4px 12px 4px; border-bottom: 1px solid #E0E0E0; margin-bottom: 10px; }
    .sabaek-logo { color: #B8860B; font-size: 1.65rem; font-weight: 900; }
    .karats-grid { display: grid; grid-template-columns: repeat(4, 1fr); background-color: #1C1C1E; border: 1px solid #2E2E32; border-radius: 14px; padding: 12px 6px; margin-bottom: 14px; text-align: center; direction: rtl; }
    .karat-item { border-left: 1px solid #2E2E32; padding: 0 4px; }
    .karat-item:last-child { border-left: none; }
    .karat-name { color: #B0B0B0; font-size: 0.85rem; margin-bottom: 4px; }
    .karat-val { font-size: 1.02rem; font-weight: 800; }
    .price-up { color: #00E676; }
    .price-down { color: #FF3D00; }
    .price-same { color: #111111; background-color: #E0E0E0; padding: 1px 6px; border-radius: 6px; }

    div[data-testid="stMetric"] { background-color: #1C1C1E !important; border: 1px solid #2E2E32 !important; border-right: 4px solid #E6C25A !important; border-radius: 12px; padding: 10px 12px; }
    div[data-testid="stMetricLabel"] p, div[data-testid="stMetricLabel"] { color: #E6C25A !important; font-weight: 700 !important; }
    div[data-testid="stMetricValue"] div, div[data-testid="stMetricValue"] { color: #FFFFFF !important; font-weight: 800 !important; }

    div[role="radiogroup"] { direction: rtl; justify-content: center; background-color: #1C1C1E !important; padding: 8px; border-radius: 14px; border: 1px solid #333333; gap: 6px; }
    div[role="radiogroup"] label p, div[role="radiogroup"] label span { color: #FFFFFF !important; font-weight: 700 !important; }

    .stButton>button { width: 100%; border-radius: 12px; height: 3.1em; font-weight: 800; }
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

# ================= 1. الترويسة وأداة TradingView الرسمية المطابقة لدار السبائك =================
st.markdown('<div class="sabaek-top"><span class="sabaek-logo">🪙 دار السبائك AI</span><span style="color:#555555; font-size:0.8rem;">TradingView OANDA:XAUUSD</span></div>', unsafe_allow_html=True)

tv_ticker_html = """
<div class="tradingview-widget-container" style="border-radius:14px; overflow:hidden; border:1px solid #2E2E32;">
  <div class="tradingview-widget-container__widget"></div>
  <script type="text/javascript" src="https://tradingview.com" async>
  {
  "symbol": "OANDA:XAUUSD",
  "width": "100%",
  "isTransparent": false,
  "colorTheme": "dark",
  "locale": "ar_AE"
  }
  </script>
</div>
"""
components.html(tv_ticker_html, height=115)

# ================= 2. شريط العيارات الكويتي المتجدد تلقائياً كل 15 ثانية =================
@st.fragment(run_every=15)
def live_sabaek_karats():
    try:
        data = services.get_live_gold()
        ounce = data["ounce"]
        buy_24k, sell_24k = data["buy_24k"], data["sell_24k"]
        k22, k21, k18 = data["k22"], data["k21"], data["k18"]

        st.session_state["live_ounce"] = ounce
        st.session_state["live_buy_24k"] = buy_24k
        st.session_state["live_sell_24k"] = sell_24k

        prev_ounce = st.session_state.get("prev_tick_ounce", ounce)
        if ounce > prev_ounce:
            color_cls = "price-up"
        elif ounce < prev_ounce:
            color_cls = "price-down"
        else:
            color_cls = "price-same"
        st.session_state["prev_tick_ounce"] = ounce

        if ounce > 0:
            sheet_dashboard.update_acell("C5", ounce)

        st.markdown(f"""
        <div style="text-align:left; font-size:0.85rem; color:#B8860B; font-weight:800; margin-bottom:4px;">سعر بيع جرام ٢٤ (دار السبائك): {sell_24k:.3f} د.ك</div>
        <div class="karats-grid">
            <div class="karat-item"><div class="karat-name">شراء ٢٤</div><div class="karat-val {color_cls}">{buy_24k:.3f} د.ك</div></div>
            <div class="karat-item"><div class="karat-name">عيار ٢٢</div><div class="karat-val {color_cls}">{k22:.3f} د.ك</div></div>
            <div class="karat-item"><div class="karat-name">عيار ٢١</div><div class="karat-val {color_cls}">{k21:.3f} د.ك</div></div>
            <div class="karat-item"><div class="karat-name">عيار ١٨</div><div class="karat-val {color_cls}">{k18:.3f} د.ك</div></div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"خطأ في تحديث العيارات: {e}")

live_sabaek_karats()

ounce = st.session_state.get("live_ounce", 0.0)
buy_24k = st.session_state.get("live_buy_24k", 0.0)
sell_24k = st.session_state.get("live_sell_24k", 0.0)

gold_balance_str = sheet_dashboard.acell("A15").value or "0"
total_cost_str = sheet_dashboard.acell("B15").value or "0"
avg_cost_str = sheet_dashboard.acell("D15").value or "0"

try:
    curr_grams = float(gold_balance_str.replace(",", ""))
    curr_avg = float(avg_cost_str.replace(",", ""))
except ValueError:
    curr_grams, curr_avg = 0.0, 0.0

net_pnl_kwd = round((sell_24k - curr_avg) * curr_grams, 3) if (curr_grams > 0 and sell_24k > 0) else 0.0

page = st.radio("القائمة", ["🏠 الرئيسية والشموع", "🎯 مناطق الشراء", "🧮 الحاسبة والزكاة", "➕ صفقة", "📜 السجل"], horizontal=True, label_visibility="collapsed")
st.write("")

if page == "🏠 الرئيسية والشموع":
    c1, c2, c3 = st.columns(3)
    tf_label = c1.selectbox("الفاصل", ["1 دقيقة", "10 دقائق", "15 دقيقة", "ساعة", "يومي"])
    tf_map = {"1 دقيقة": "1m", "10 دقائق": "10m", "15 دقيقة": "15m", "ساعة": "1h", "يومي": "1d"}
    unit_label = c2.selectbox("العملة", ["دينار كويتي (د.ك)", "دولار ($)"])
    unit_code = "KWD" if "كويتي" in unit_label else "USD"
    chart_style = c3.selectbox("الرسم", ["شموع يابانية 🕯️", "خطي ذهبي 📈"])
    show_avg = st.checkbox("إظهار خط متوسط تكلفتي على الشارت", value=True)

    try:
        df_candles = services.get_candlestick_data(timeframe=tf_map[tf_label], unit=unit_code)
        if chart_style == "شموع يابانية 🕯️":
            trace = go.Candlestick(x=df_candles.index, open=df_candles["Open"], high=df_candles["High"], low=df_candles["Low"], close=df_candles["Close"], increasing_line_color="#00E676", decreasing_line_color="#FF3D00", name="السعر")
        else:
            trace = go.Scatter(x=df_candles.index, y=df_candles["Close"], mode="lines+markers", line=dict(color="#E6C25A", width=2.5), marker=dict(size=4, color="#FFD700"), fill="tozeroy", fillcolor="rgba(230, 194, 90, 0.12)", name="السعر")

        fig = go.Figure(data=[trace])
        if show_avg and unit_code == "KWD" and curr_avg > 0:
            fig.add_hline(y=curr_avg, line_dash="dash", line_color="#FFD700", line_width=1.8, annotation_text=f"متوسطك: {curr_avg:.3f}", annotation_position="top right", annotation_font_color="#FFD700")

        fig.update_layout(template="plotly_dark", paper_bgcolor="#1C1C1E", plot_bgcolor="#141416", height=360, margin=dict(l=8, r=8, t=25, b=8), xaxis_rangeslider_visible=False, dragmode="pan")
        plotly_cfg = {"displayModeBar": True, "scrollZoom": True, "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"]}
        st.plotly_chart(fig, use_container_width=True, config=plotly_cfg)
    except Exception as e:
        st.error(f"تعذر رسم الشارت: {e}")

    st.subheader("💼 ملخص محفظتي")
    m1, m2 = st.columns(2)
    m1.metric("رصيد الذهب", f"{gold_balance_str} جم")
    m2.metric("متوسط التكلفة", f"{avg_cost_str} د.ك")

    m3, m4 = st.columns(2)
    m3.metric("إجمالي التكلفة", f"{total_cost_str} د.ك")
    m4.metric("صافي الربح / الخسارة (بيع)", f"{net_pnl_kwd:+,.3f} د.ك", delta=f"{net_pnl_kwd:+,.3f} د.ك")

elif page == "🎯 مناطق الشراء":
    st.subheader("🎯 اقتراح أفضل أسعار الشراء")
    if st.button("🔍 استخرج أفضل 3 مناطق شراء الآن"):
        st.info("⏳ جاري تحليل الشارت والأخبار...")
        zones = services.suggest_best_buy_zones(ounce, buy_24k, curr_avg, curr_grams)
        st.success(zones)

    st.divider()
    st.subheader("🤖 اسأل المستشار الذكي")
    user_q = st.text_input("مثال: هل الوقت مناسب لشراء 20 جرام أم أنتظر؟")
    if st.button("احسب وحلّل"):
        if user_q:
            st.info("⏳ جاري الحساب...")
            portfolio_rows = sheet_dashboard.get("A13:I16")
            answer = services.ask_ai_advisor(user_q, ounce, buy_24k, sell_24k, portfolio_rows)
            st.success(answer)

    st.divider()
    if st.button("📢 إرسال التقرير الشامل لتيليجرام وواتساب"):
        st.info("⏳ جاري الإرسال...")
        rep = services.generate_and_send_report(sheet_dashboard, send_notifications=True)
        st.markdown(rep, unsafe_allow_html=True)

elif page == "🧮 الحاسبة والزكاة":
    st.subheader("🧮 محاكي تعديل المتوسط (ماذا لو اشتريت؟)")
    sim_grams = st.slider("الكمية المقترحة للشراء (بالجرام)", min_value=1, max_value=200, value=20, step=1)
    default_price = float(buy_24k) if buy_24k > 0 else 35.0
