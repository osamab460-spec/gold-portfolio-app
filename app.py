import streamlit as st
from datetime import datetime
import plotly.graph_objects as go
import config
import services

st.set_page_config(page_title="دار السبائك Trading Desk", page_icon="🪙", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    header[data-testid="stHeader"], footer { display: none !important; }
    .block-container { padding-top: 0.8rem !important; padding-bottom: 2rem !important; max-width: 680px; }
    p, h1, h2, h3, h4, h5, label, .rtl-box { direction: rtl; text-align: right; }
    .trade-box-sell { background-color: #FFF2F4; border: 1px solid #FAD1D8; border-radius: 10px; padding: 10px; text-align: center; }
    .trade-box-buy { background-color: #EBF9F4; border: 1px solid #C2EEDF; border-radius: 10px; padding: 10px; text-align: center; }
    .sell-label { color: #F6465D; font-size: 0.8rem; font-weight: 800; }
    .sell-price { color: #F6465D; font-size: 1.25rem; font-weight: 800; }
    .buy-label { color: #00B87A; font-size: 0.8rem; font-weight: 800; }
    .buy-price { color: #00B87A; font-size: 1.25rem; font-weight: 800; }
    .light-card { background-color: #F8F9FA; border: 1px solid #EAECEF; border-radius: 12px; padding: 10px 12px; text-align: center; margin-bottom: 8px; }
    .light-title { color: #707A8A; font-size: 0.74rem; margin-bottom: 2px; font-weight: 600; }
    .light-val { color: #1E2329; font-size: 1.15rem; font-weight: 800; }
    .gold-badge { background-color: #FEF6D8; color: #C99400; padding: 3px 10px; border-radius: 8px; font-weight: 800; font-size: 0.85rem; }
    .ohlc-bar { background-color: #F8F9FA; border: 1px solid #EAECEF; border-radius: 8px; padding: 6px 10px; font-size: 0.75rem; color: #474D57; display: flex; justify-content: space-between; margin-bottom: 6px; direction: ltr; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; font-weight: 700; background-color: #FCD535 !important; color: #1E2329 !important; border: none !important; }
    button[data-baseweb="tab"] { font-size: 0.85rem !important; font-weight: 700 !important; }
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
    st.markdown("<h3 style='text-align:center; color:#1E2329; margin-top:2rem;'>🪙 دار السبائك Trading Desk</h3>", unsafe_allow_html=True)
    pin_input = st.text_input("الرقم السري", type="password", max_chars=8, placeholder="أدخل رمز الدخول...")
    if st.button("دخول المنصة"):
        if pin_input == str(APP_PIN):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ الرقم السري غير صحيح")
    st.stop()

try:
    ounce, ch, chp, buy_24k, sell_24k = services.get_live_gold()
    if ounce > 0:
        sheet_dashboard.update_acell("C5", ounce)

    ch_color = "#00B87A" if ch >= 0 else "#F6465D"
    st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; direction:rtl;">
        <div><span class="gold-badge">🪙 GOLD 24K • دار السبائك</span></div>
        <div style="font-size:0.85rem; font-weight:700; color:#1E2329;">الأونصة: ${ounce:,.2f} <span style="color:{ch_color};">({ch:+.2f}$)</span></div>
    </div>
    """, unsafe_allow_html=True)

    b1, b2 = st.columns(2)
    with b1:
        st.markdown(f'<div class="trade-box-buy"><div class="buy-label">شراء جرام 24 (Buy)</div><div class="buy-price">{buy_24k:.3f} د.ك</div></div>', unsafe_allow_html=True)
    with b2:
        st.markdown(f'<div class="trade-box-sell"><div class="sell-label">بيع جرام 24 (Sell)</div><div class="sell-price">{sell_24k:.3f} د.ك</div></div>', unsafe_allow_html=True)
except Exception as e:
    ounce, buy_24k, sell_24k = 0, 0, 0
    st.warning(f"تنبيه السعر الحي: {e}")

try:
    eco_alerts = services.get_economic_radar()
    if eco_alerts:
        with st.expander("🛡️ رادار الأخبار الاقتصادية الحية", expanded=False):
            for item in eco_alerts:
                st.caption(f"• {item}")
except Exception:
    pass

gold_balance_str = sheet_dashboard.acell("A15").value or "0"
total_cost_str = sheet_dashboard.acell("B15").value or "0"
market_val_str = sheet_dashboard.acell("C15").value or "0"
avg_cost_str = sheet_dashboard.acell("D15").value or "0"

try:
    curr_grams = float(gold_balance_str.replace(",", ""))
    curr_avg = float(avg_cost_str.replace(",", ""))
except ValueError:
    curr_grams, curr_avg = 0.0, 0.0

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Trading Chart", "🎯 القنص AI", "🧮 الحاسبة", "➕ صفقة", "📜 السجل"])

with tab1:
    tf_code = st.radio("Timeframe", ["15M", "1H", "4H", "1D", "1W"], index=3, horizontal=True, label_visibility="collapsed")

    try:
        df_chart, _, last_rsi = services.get_pro_chart_data(tf_code)
        last_row = df_chart.iloc[-1]
        last_dt = df_chart.index[-1].strftime("%Y-%m-%d %H:%M")

        st.markdown(f"""
        <div class="ohlc-bar">
            <span><b>{last_dt}</b></span>
            <span>O: <b>{last_row['Open']:.3f}</b></span>
            <span>H: <b>{last_row['High']:.3f}</b></span>
            <span>L: <b>{last_row['Low']:.3f}</b></span>
            <span>C: <b>{last_row['Close']:.3f}</b></span>
        </div>
        """, unsafe_allow_html=True)

        fig = go.Figure()

        fig.add_trace(go.Candlestick(
            x=df_chart.index,
            open=df_chart["Open"],
            high=df_chart["High"],
            low=df_chart["Low"],
            close=df_chart["Close"],
            increasing_line_color="#00B87A",
            increasing_fillcolor="#00B87A",
            decreasing_line_color="#F6465D",
            decreasing_fillcolor="#F6465D",
            name="سعر الجرام"
        ))

        hammers = df_chart[df_chart["Hammer"] == True]
        if not hammers.empty:
            fig.add_trace(go.Scatter(
                x=hammers.index,
                y=hammers["Low"] - 0.12,
                mode="markers+text",
                text="🔨",
                textposition="bottom center",
                marker=dict(symbol="diamond", size=8, color="#FCD535", line=dict(width=1, color="#1E2329")),
                name="مطرقة"
            ))

        if buy_24k > 0:
            fig.add_hline(
                y=buy_24k,
                line_dash="dot",
                line_color="#00B87A",
                line_width=1.2,
                annotation_text=f" {buy_24k:.3f} ",
                annotation_bgcolor="#00B87A",
                annotation_font_color="#FFFFFF",
                annotation_position="right"
            )

        if curr_avg > 0:
            fig.add_hline(
                y=curr_avg,
                line_dash="dash",
                line_color="#474D57",
                line_width=1.3,
                annotation_text=f" {curr_avg:.3f} ",
                annotation_bgcolor="#474D57",
                annotation_font_color="#FFFFFF",
                annotation_position="right"
            )

        fig.update_layout(
            template="plotly_white",
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            xaxis_rangeslider_visible=False,
            dragmode=False,
            height=340,
            margin=dict(l=5, r=60, t=10, b=10),
            showlegend=False
        )
        fig.update_xaxes(showgrid=True, gridcolor="#F0F2F5", linecolor="#EAECEF")
        fig.update_yaxes(showgrid=True, gridcolor="#F0F2F5", linecolor="#EAECEF", side="right")

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        bull_pct = int(min(max(last_rsi, 15), 85))
        bear_pct = 100 - bull_pct
        st.markdown(f"""
        <div style="margin-top:4px; margin-bottom:12px; direction:rtl;">
            <div style="display:flex; justify-content:space-between; font-size:0.78rem; font-weight:800; margin-bottom:3px;">
                <span style="color:#00B87A;">🐂 المشترون {bull_pct}%</span>
                <span style="color:#707A8A;">معنويات السوق (SENTIMENT)</span>
                <span style="color:#F6465D;">{bear_pct}% البائعون 🐻</span>
            </div>
            <div style="width:100%; height:7px; background-color:#F6465D; border-radius:5px; overflow:hidden;">
                <div style="width:{bull_pct}%; height:100%; background-color:#00B87A;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    except Exception as e:
        st.caption(f"جاري تحميل الشارت... ({e})")

    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.markdown(f'<div class="light-card"><div class="light-title">رصيد الذهب</div><div class="light-val">{gold_balance_str} جم</div></div>', unsafe_allow_html=True)
    with r1c2:
        st.markdown(f'<div class="light-card"><div class="light-title">متوسط التكلفة</div><div class="light-val">{avg_cost_str} د.ك</div></div>', unsafe_allow_html=True)

    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.markdown(f'<div class="light-card"><div class="light-title">إجمالي التكلفة</div><div class="light-val">{total_cost_str} د.ك</div></div>', unsafe_allow_html=True)
    with r2c2:
        st.markdown(f'<div class="light-card"><div class="light-title">القيمة السوقية</div><div class="light-val">{market_val_str}</div></div>', unsafe_allow_html=True)

    if st.button("🔄 تحديث الأسعار والبيانات"):
        st.rerun()

with tab2:
    st.markdown("#### 🎯 أفضل 3 مناطق شراء مقترحة")
    st.caption("تحليل فني + الأخبار الحية لتحديد نقاط تعزيز محفظتك.")
    if st.button("🔍 استخرج مناطق القنص الآن"):
        with st.spinner("جاري تحليل الشارت والأخبار..."):
            zones = services.suggest_best_buy_zones(ounce, buy_24k, curr_avg, curr_grams)
