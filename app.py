import streamlit as st
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import config
import services

st.set_page_config(
    page_title="دار السبائك AI Pro",
    page_icon="🪙",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .main { direction: rtl; text-align: right; background-color: #0E1117; }
    header[data-testid="stHeader"], footer { display: none !important; }
    .block-container { padding-top: 1.2rem !important; padding-bottom: 2rem !important; max-width: 650px; }

    .kpi-card {
        background: linear-gradient(145deg, #1A1F2C, #141821);
        border: 1px solid #2A3142;
        border-radius: 14px;
        padding: 14px 12px;
        text-align: center;
        margin-bottom: 10px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.25);
    }
    .kpi-title { color: #9BA3B4; font-size: 0.78rem; margin-bottom: 4px; font-weight: 500; }
    .kpi-value { color: #FFFFFF; font-size: 1.25rem; font-weight: 700; letter-spacing: 0.3px; }
    .kpi-gold { color: #F5C542; font-size: 1.25rem; font-weight: 700; }
    .kpi-sub-up { color: #00E676; font-size: 0.75rem; font-weight: 600; }
    .kpi-sub-down { color: #FF5252; font-size: 0.75rem; font-weight: 600; }

    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.1em;
        font-weight: 700;
        border: 1px solid #F5C54244;
    }
    button[data-baseweb="tab"] {
        font-size: 0.85rem !important;
        padding: 8px 10px !important;
        font-weight: 600 !important;
    }
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
    st.markdown("<h2 style='text-align:center; color:#F5C542; margin-top:2rem;'>🪙 دار السبائك AI</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#9BA3B4; font-size:0.9rem;'>منصة إدارة محفظة الذهب الذكية</p>", unsafe_allow_html=True)
    pin_input = st.text_input("الرقم السري", type="password", max_chars=8, placeholder="أدخل رمز الدخول...")
    if st.button("🔓 فتح المحفظة"):
        if pin_input == str(APP_PIN):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ الرقم السري غير صحيح")
    st.stop()

st.markdown("<h3 style='text-align:center; color:#F5C542; margin-bottom:0.8rem;'>🪙 محفظة دار السبائك AI</h3>", unsafe_allow_html=True)

try:
    ounce, ch, chp, buy_24k, sell_24k = services.get_live_gold()
    if ounce > 0:
        sheet_dashboard.update_acell("C5", ounce)

    ch_class = "kpi-sub-up" if ch >= 0 else "kpi-sub-down"
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">الأونصة ($)</div>
            <div class="kpi-value">{ounce:,.1f}</div>
            <div class="{ch_class}">{ch:+.2f}$ ({chp:+.1f}%)</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">شراء 24 (د.ك)</div>
            <div class="kpi-gold">{buy_24k:.3f}</div>
            <div class="kpi-title" style="margin:0;">سعر دار السبائك</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">بيع 24 (د.ك)</div>
            <div class="kpi-value">{sell_24k:.3f}</div>
            <div class="kpi-title" style="margin:0;">صافي البيع</div>
        </div>""", unsafe_allow_html=True)
except Exception as e:
    ounce, buy_24k, sell_24k = 0, 0, 0
    st.warning(f"تعذر تحديث السعر الحي: {e}")

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

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 المحفظة",
    "🎯 القنص AI",
    "🧮 الحاسبة",
    "➕ صفقة",
    "📜 السجل"
])

with tab1:
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">رصيد الذهب المحتفظ به</div>
            <div class="kpi-gold">{gold_balance_str} جم</div>
        </div>""", unsafe_allow_html=True)
    with r1c2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">متوسط التكلفة (نقطة التعادل)</div>
            <div class="kpi-value">{avg_cost_str} د.ك</div>
        </div>""", unsafe_allow_html=True)

    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">إجمالي التكلفة المستثمرة</div>
            <div class="kpi-value">{total_cost_str} د.ك</div>
        </div>""", unsafe_allow_html=True)
    with r2c2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">القيمة السوقية الحالية</div>
            <div class="kpi-value">{market_val_str}</div>
        </div>""", unsafe_allow_html=True)

    # مبدّل الإطار الزمني للشارت الاحترافي
    tf_choice = st.radio("الإطار الزمني للشموع:", ["يومي (1D)", "ساعي (1H)"], horizontal=True)
    tf_code = "1H" if "1H" in tf_choice else "1D"

    try:
        df_chart, _ = services.get_pro_chart_data(tf_code)
        
        # إنشاء شارت مزدوج (الشموع اليابانية في الأعلى 75% + مؤشر RSI في الأسفل 25%)
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.75, 0.25]
        )

        # 1. الشموع اليابانية بألوان احترافية
        fig.add_trace(go.Candlestick(
            x=df_chart.index,
            open=df_chart["Open"],
            high=df_chart["High"],
            low=df_chart["Low"],
            close=df_chart["Close"],
            increasing_line_color="#00E676",
            decreasing_line_color="#FF5252",
            name="سعر الجرام"
        ), row=1, col=1)

        # 2. المتوسط المتحرك السريع EMA 9 (خط ذهبي للزخم)
        fig.add_trace(go.Scatter(
            x=df_chart.index, y=df_chart["EMA9"],
            line=dict(color="#F5C542", width=1.4),
            name="زخم EMA 9"
        ), row=1, col=1)

        # 3. البولينجر باند المظلل (منطقة القنص والدعم)
        fig.add_trace(go.Scatter(
            x=df_chart.index, y=df_chart["UpperBB"],
            line=dict(color="rgba(100, 181, 246, 0.3)", width=1),
            name="حد علوي BB",
            showlegend=False
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df_chart.index, y=df_chart["LowerBB"],
            line=dict(color="rgba(100, 181, 246, 0.4)", width=1),
            fill="tonexty",
            fillcolor="rgba(100, 181, 246, 0.07)",
            name="نطاق بولينجر"
        ), row=1, col=1)

        # 4. خط متوسط تكلفتك الحالي (نقطة التعادل)
        if curr_avg > 0:
            fig.add_hline(
                y=curr_avg,
                line_dash="dash",
                line_color="#FF5252",
                annotation_text=f"متوسطك: {curr_avg:.3f}",
                annotation_position="top left",
                row=1, col=1
            )

        # 5. نقاط صفقات شرائك على الشارت اليومي
        if tf_code == "1D":
            log_rows = sheet_log.get_all_values()
            buy_dates, buy_prices = [], []
            chart_start = df_chart.index.min().strftime("%Y-%m-%d")
            for r in log_rows:
                if len(r) >= 4:
                    it = iter(r)
                    op_date = str(next(it, ""))
                    op_type_val = str(next(it, ""))
                    op_price_val = str(next(it, ""))
                    if "شراء" in op_type_val and op_date >= chart_start:
                        try:
                            buy_dates.append(op_date)
                            buy_prices.append(float(op_price_val))
                        except ValueError:
                            pass

            if buy_dates:
                fig.add_trace(go.Scatter(
                    x=buy_dates, y=buy_prices,
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=12, color="#00E676", line=dict(width=1, color="#0E1117")),
                    name="صفقاتك"
                ), row=1, col=1)

        # 6. مؤشر القوة النسبية RSI في اللوحة السفلية
        fig.add_trace(go.Scatter(
            x=df_chart.index, y=df_chart["RSI"],
            line=dict(color="#BA68C8", width=1.5),
            name="RSI 14",
            showlegend=False
        ), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="rgba(255,82,82,0.5)", row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="rgba(0,230,118,0.5)", row=2, col=1)

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(26,31,44,0.5)",
            xaxis_rangeslider_visible=False,
            dragmode="pan",
            height=450,
            margin=dict(l=5, r=5, t=25, b=5),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10))
        )
        fig.update_yaxes(title_text="د.ك", row=1, col=1)
