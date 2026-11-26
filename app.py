import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import config
import services

st.set_page_config(page_title="دار السبائك AI", page_icon="🪙", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .main { direction: rtl; text-align: right; }
    .sabaek-top { display: flex; justify-content: space-between; align-items: center; padding: 8px 4px 12px 4px; border-bottom: 1px solid #2E2E32; margin-bottom: 12px; }
    .sabaek-logo { color: #E6C25A; font-size: 1.65rem; font-weight: 900; }
    .gold-ticker-box { background-color: #1C1C1E; border: 1px solid #2E2E32; border-radius: 14px; padding: 14px 16px; margin-bottom: 10px; direction: ltr; text-align: left; }
    .gold-ticker-title { color: #E6C25A; font-weight: 800; font-size: 1rem; display: flex; justify-content: space-between; }
    .gold-ticker-price { font-size: 1.45rem; font-weight: 800; margin-top: 6px; }
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

@st.cache_resource
def get_alerts_sheet():
    sh = sheet_dashboard.spreadsheet
    try:
        return sh.worksheet("التنبيهات")
    except Exception:
        ws = sh.add_worksheet(title="التنبيهات", rows=100, cols=6)
        ws.append_row(["التاريخ", "السعر المستهدف ($)", "الاتجاه", "الحالة", "الكمية (جم)", "ملاحظة"])
        return ws

sheet_alerts = get_alerts_sheet()

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
        ounce, chp, buy_24k, sell_24k = data["ounce"], data["chp"], data["buy_24k"], data["sell_24k"]
        k22, k21, k18 = data["k22"], data["k21"], data["k18"]
        st.session_state["live_ounce"], st.session_state["live_buy_24k"], st.session_state["live_sell_24k"] = ounce, buy_24k, sell_24k
        prev_ounce = st.session_state.get("prev_tick_ounce", ounce)
        color_cls, arrow = ("price-up", "▲") if ounce > prev_ounce else (("price-down", "▼") if ounce < prev_ounce else ("price-same", "•"))
        st.session_state["prev_tick_ounce"] = ounce
        if ounce > 0:
            sheet_dashboard.update_acell("C5", ounce)
        st.markdown(f"""
        <div class="sabaek-top"><span class="sabaek-logo">🪙 دار السبائك AI</span><span style="color:#9E9E9E; font-size:0.8rem;">تحديث تلقائي 15ث ⏱️</span></div>
        <div class="gold-ticker-box">
            <div class="gold-ticker-title"><span>🪙 GOLD SPOT (XAU/USD)</span><span style="color:#E6C25A;">بيع 24: {sell_24k:.3f} د.ك</span></div>
            <div class="gold-ticker-price"><span class="{color_cls}">{ounce:,.3f}</span><span style="font-size:0.9rem; color:#BDBDBD;"> USD </span><span class="{color_cls}" style="font-size:0.95rem;">{arrow} {chp:+.2f}%</span></div>
        </div>
        <div class="karats-grid">
            <div class="karat-item"><div class="karat-name">شراء ٢٤</div><div class="karat-val {color_cls}">{buy_24k:.3f} د.ك</div></div>
            <div class="karat-item"><div class="karat-name">عيار ٢٢</div><div class="karat-val {color_cls}">{k22:.3f} د.ك</div></div>
            <div class="karat-item"><div class="karat-name">عيار ٢١</div><div class="karat-val {color_cls}">{k21:.3f} د.ك</div></div>
            <div class="karat-item"><div class="karat-name">عيار ١٨</div><div class="karat-val {color_cls}">{k18:.3f} د.ك</div></div>
        </div>""", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"خطأ السعر: {e}")

live_sabaek_ticker()

ounce = st.session_state.get("live_ounce", 0.0)
buy_24k = st.session_state.get("live_buy_24k", 0.0)
sell_24k = st.session_state.get("live_sell_24k", 0.0)
gold_balance_str = sheet_dashboard.acell("A15").value or "0"
total_cost_str = sheet_dashboard.acell("B15").value or "0"
avg_cost_str = sheet_dashboard.acell("D15").value or "0"
try:
    curr_grams, curr_avg = float(gold_balance_str.replace(",", "")), float(avg_cost_str.replace(",", ""))
except ValueError:
    curr_grams, curr_avg = 0.0, 0.0

net_pnl_kwd = round((sell_24k - curr_avg) * curr_grams, 3) if (curr_grams > 0 and sell_24k > 0) else 0.0
page = st.radio("القائمة", ["🏠 الرئيسية والشموع", "🔔 التنبيهات", "🎯 مناطق الشراء", "🧮 الحاسبة والزكاة", "➕ صفقة", "📜 السجل"], horizontal=True, label_visibility="collapsed")
st.write("")

if page != "🏠 الرئيسية والشموع":
    st.markdown("""<style>
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #FFFFFF !important; color: #111111 !important; }
        h1, h2, h3, h4, p, span, label, div, .stMarkdown { color: #111111 !important; }
        .gold-ticker-box span, .karats-grid .karat-name { color: #E0E0E0 !important; }
        .gold-ticker-title span:first-child { color: #E6C25A !important; }
        .price-up { color: #00E676 !important; }
        .price-down { color: #FF3D00 !important; }
        div[role="radiogroup"] label p, div[role="radiogroup"] label span { color: #FFFFFF !important; }
        input, textarea, div[data-baseweb="input"] > div, div[data-baseweb="select"] > div { background-color: #F4F5F7 !important; color: #111111 !important; border: 1px solid #CCCCCC !important; }
        div[data-testid="stAlert"] { background-color: #F8F9FA !important; border: 1px solid #D4AF37 !important; }
        .stButton>button { background-color: #E6C25A !important; color: #111111 !important; }
    </style>""", unsafe_allow_html=True)

# ================= الصفحة 1: الرئيسية والشموع (مع خطوط التنبيهات على الشارت) =================
if page == "🏠 الرئيسية والشموع":
    c1, c2, c3 = st.columns(3)
    tf_label = c1.selectbox("الفاصل", ["1 دقيقة", "10 دقائق", "15 دقيقة", "ساعة", "يومي"])
    tf_map = {"1 دقيقة": "1m", "10 دقائق": "10m", "15 دقيقة": "15m", "ساعة": "1h", "يومي": "1d"}
    unit_label = c2.selectbox("العملة", ["دينار كويتي (د.ك)", "دولار ($)"])
    unit_code = "KWD" if "كويتي" in unit_label else "USD"
    chart_style = c3.selectbox("الرسم", ["شموع يابانية 🕯️", "خطي ذهبي 📈"])
    show_avg = st.checkbox("إظهار خط متوسط تكلفتي والتنبيهات على الشارت", value=True)
    try:
        df_candles = services.get_candlestick_data(timeframe=tf_map[tf_label], unit=unit_code)
        trace = go.Candlestick(x=df_candles.index, open=df_candles["Open"], high=df_candles["High"], low=df_candles["Low"], close=df_candles["Close"], increasing_line_color="#00E676", decreasing_line_color="#FF3D00", name="السعر") if chart_style == "شموع يابانية 🕯️" else go.Scatter(x=df_candles.index, y=df_candles["Close"], mode="lines+markers", line=dict(color="#E6C25A", width=2.5), fill="tozeroy", fillcolor="rgba(230, 194, 90, 0.12)", name="السعر")
        fig = go.Figure(data=[trace])
        if show_avg:
            if unit_code == "KWD" and curr_avg > 0:
                fig.add_hline(y=curr_avg, line_dash="dash", line_color="#FFD700", line_width=1.8, annotation_text=f"متوسطك: {curr_avg:.3f}", annotation_position="top right", annotation_font_color="#FFD700")
            # رسم خطوط التنبيهات النشطة على الشارت
            for r in sheet_alerts.get_all_values()[1:]:
                if len(r) >= 4 and str(r[3]).strip().upper() == "ON":
                    try:
                        t_usd = float(str(r[1]).replace(",", ""))
                        y_line = round((t_usd / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3) if unit_code == "KWD" else t_usd
                        l_color = "#00E676" if r[2] == "DOWN" else "#29B6F6"
                        fig.add_hline(y=y_line, line_dash="dot", line_color=l_color, line_width=1.4, annotation_text=f"🔔 {y_line}", annotation_position="bottom left", annotation_font_color=l_color)
                    except Exception:
                        pass

