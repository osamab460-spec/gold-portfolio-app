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

[data-testid="stMetric"] { background-color: #1C1C1E !important; border: 1px solid #2E2E32 !important; border-right: 4px solid #E6C25A !important; border-radius: 12px !important; padding: 12px 14px !important; }
[data-testid="stMetricLabel"] * { color: #E6C25A !important; font-weight: 700 !important; }
[data-testid="stMetricValue"] * { color: #FFFFFF !important; font-weight: 800 !important; }

div[role="radiogroup"] { direction: rtl; justify-content: center; background-color: #1C1C1E !important; padding: 8px; border-radius: 14px; border: 1px solid #333333; gap: 6px; }
div[role="radiogroup"] label * { color: #FFFFFF !important; font-weight: 700 !important; }
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
        ws.append_row(["التاريخ", "السعر ($)", "الاتجاه", "الحالة", "الكمية", "ملاحظة"])
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
    data = services.get_live_gold()
    ounce = data["ounce"]
    chp = data["chp"]
    buy_24k = data["buy_24k"]
    sell_24k = data["sell_24k"]
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
        <div class="gold-ticker-title"><span>🪙 GOLD SPOT (XAU/USD)</span><span style="color:#E6C25A;">بيع 24: {sell_24k:.3f} د.ك</span></div>
        <div class="gold-ticker-price"><span class="{color_cls}">{ounce:,.3f}</span><span style="font-size:0.9rem; color:#BDBDBD;"> USD </span><span class="{color_cls}" style="font-size:0.95rem;">{arrow} {chp:+.2f}%</span></div>
    </div>
    <div class="karats-grid">
        <div class="karat-item"><div class="karat-name">شراء ٢٤</div><div class="karat-val {color_cls}">{buy_24k:.3f} د.ك</div></div>
        <div class="karat-item"><div class="karat-name">عيار ٢٢</div><div class="karat-val {color_cls}">{k22:.3f} د.ك</div></div>
        <div class="karat-item"><div class="karat-name">عيار ٢١</div><div class="karat-val {color_cls}">{k21:.3f} د.ك</div></div>
        <div class="karat-item"><div class="karat-name">عيار ١٨</div><div class="karat-val {color_cls}">{k18:.3f} د.ك</div></div>
    </div>""", unsafe_allow_html=True)
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
    div[role="radiogroup"] label * { color: #FFFFFF !important; }
    [data-testid="stMetricLabel"] * { color: #E6C25A !important; }
    [data-testid="stMetricValue"] * { color: #FFFFFF !important; }
    input, textarea, div[data-baseweb="input"] > div, div[data-baseweb="select"] > div { background-color: #F4F5F7 !important; color: #111111 !important; border: 1px solid #CCCCCC !important; }
    div[data-testid="stAlert"] { background-color: #F8F9FA !important; border: 1px solid #D4AF37 !important; }
    .stButton>button { background-color: #E6C25A !important; color: #111111 !important; }
    </style>""", unsafe_allow_html=True)

if page == "🏠 الرئيسية والشموع":
    c1, c2, c3 = st.columns(3)
    tf_label = c1.selectbox("الفاصل", ["1 دقيقة", "10 دقائق", "15 دقيقة", "ساعة", "يومي"])
    tf_map = {"1 دقيقة": "1m", "10 دقائق": "10m", "15 دقيقة": "15m", "ساعة": "1h", "يومي": "1d"}
    unit_label = c2.selectbox("العملة", ["دينار كويتي (د.ك)", "دولار ($)"])
    unit_code = "KWD" if "كويتي" in unit_label else "USD"
    chart_style = c3.selectbox("الرسم", ["شموع يابانية 🕯️", "خطي ذهبي 📈"])
    show_avg = st.checkbox("إظهار خط متوسط تكلفتي والتنبيهات على الشارت", value=True)

    try:
        df_raw = services.get_candlestick_data(timeframe=tf_map[tf_label], unit=unit_code)
        df_candles = pd.DataFrame(df_raw).copy()
        if not df_candles.empty:
            target_now = buy_24k if unit_code == "KWD" else ounce
            if target_now > 0:
                last_close = float(df_candles["Close"].tail(1).item())
                diff_val = last_close - target_now
                for col in ["Open", "High", "Low", "Close"]:
                    df_candles[col] = (df_candles[col] - diff_val).round(3 if unit_code == "KWD" else 2)

        if chart_style == "شموع يابانية 🕯️":
            trace = go.Candlestick(x=df_candles.index, open=df_candles["Open"], high=df_candles["High"], low=df_candles["Low"], close=df_candles["Close"], increasing_line_color="#00E676", decreasing_line_color="#FF3D00", name="السعر")
        else:
            trace = go.Scatter(x=df_candles.index, y=df_candles["Close"], mode="lines+markers", line=dict(color="#E6C25A", width=2.5), fill="tozeroy", fillcolor="rgba(230, 194, 90, 0.12)", name="السعر")

        fig = go.Figure(data=[trace])
        if show_avg:
            if unit_code == "KWD" and curr_avg > 0:
                fig.add_hline(y=curr_avg, line_dash="dash", line_color="#FFD700", line_width=1.8, annotation_text=f"متوسطك: {curr_avg:.3f}", annotation_position="top right", annotation_font_color="#FFD700")
            for r in sheet_alerts.get_all_values()[1:]:
                if len(r) >= 4:
                    _, p_cell, d_cell, s_cell = r[:4]
                    if str(s_cell).strip().upper() == "ON":
                        t_usd = float(str(p_cell).replace(",", ""))
                        y_line = round((t_usd / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3) if unit_code == "KWD" else t_usd
                        l_color = "#00E676" if str(d_cell).strip() == "DOWN" else "#29B6F6"
                        fig.add_hline(y=y_line, line_dash="dot", line_color=l_color, line_width=1.4, annotation_text=f"🔔 {y_line}", annotation_position="bottom left", annotation_font_color=l_color)

        fig.update_layout(template="plotly_dark", paper_bgcolor="#1C1C1E", plot_bgcolor="#141416", height=360)
        fig.update_layout(margin=dict(l=8, r=8, t=25, b=8), xaxis_rangeslider_visible=False, dragmode="pan")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True, "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"]})
    except Exception as e:
        st.error(f"تنبيه الشارت: {e}")

    st.subheader("💼 ملخص محفظتي")
    m1, m2 = st.columns(2)
    m1.metric("رصيد الذهب", f"{gold_balance_str} جم")
    m2.metric("متوسط التكلفة", f"{avg_cost_str} د.ك")
    m3, m4 = st.columns(2)
    m3.metric("إجمالي التكلفة", f"{total_cost_str} د.ك")
    m4.metric("صافي الربح / الخسارة (بيع)", f"{net_pnl_kwd:+,.3f} د.ك", delta=f"{net_pnl_kwd:+,.3f} د.ك")
elif page == "🔔 التنبيهات":
    st.subheader("⚡ إضافة سريعة بالنسب المئوية")
    pct_choice = st.select_slider("اختر نسبة التحرك (%)", options=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0], value=1.5)
    q1, q2, q3 = st.columns(3)
    if q1.button(f"📉 شراء (-{pct_choice}%)") and ounce > 0:
        t_usd = round(ounce * (1 - pct_choice / 100.0), 2)
        sheet_alerts.append_row([datetime.now(config.KUWAIT_TZ).strftime("%Y-%m-%d %H:%M"), t_usd, "DOWN", "ON", 20, f"هبوط {pct_choice}%"], value_input_option="USER_ENTERED")
        st.rerun()
    if q2.button(f"📈 بيع (+{pct_choice}%)") and ounce > 0:
        t_usd = round(ounce * (1 + pct_choice / 100.0), 2)
        sheet_alerts.append_row([datetime.now(config.KUWAIT_TZ).strftime("%Y-%m-%d %H:%M"), t_usd, "UP", "ON", 0, f"صعود {pct_choice}%"], value_input_option="USER_ENTERED")
        st.rerun()
    if q3.button("⚖️ التعادل") and curr_avg > 0:
        be_usd = round((curr_avg * config.OUNCE_TO_GRAM) / config.KUWAIT_FACTOR, 2)
        sheet_alerts.append_row([datetime.now(config.KUWAIT_TZ).strftime("%Y-%m-%d %H:%M"), be_usd, "UP", "ON", 0, "نقطة التعادل"], value_input_option="USER_ENTERED")
        st.rerun()

    st.divider()
    st.subheader("🔔 إضافة تنبيه مخصص (دولار ↔ دينار)")
    if "alert_usd_val" not in st.session_state:
        st.session_state["alert_usd_val"] = 3450.00
        st.session_state["alert_kwd_val"] = round((3450.00 / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)

    def sync_from_usd():
        st.session_state["alert_kwd_val"] = round((st.session_state["alert_usd_val"] / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)

    def sync_from_kwd():
        st.session_state["alert_usd_val"] = round((st.session_state["alert_kwd_val"] * config.OUNCE_TO_GRAM) / config.KUWAIT_FACTOR, 2)

    col_a1, col_a2 = st.columns(2)
    new_target = col_a1.number_input("الأونصة ($)", min_value=1000.0, max_value=10000.0, step=5.0, format="%.2f", key="alert_usd_val", on_change=sync_from_usd)
    new_target_kwd = col_a2.number_input("جرام 24 (د.ك)", min_value=10.0, max_value=100.0, step=0.05, format="%.3f", key="alert_kwd_val", on_change=sync_from_kwd)
    col_b1, col_b2 = st.columns(2)
    plan_grams = col_b1.number_input("الكمية المخططة (جم)", min_value=0.0, max_value=500.0, value=20.0, step=5.0, format="%.1f")
    new_note = col_b2.text_input("ملاحظة", placeholder="مثال: الدفعة الأولى")

    if st.button("➕ إضافة وتفعيل التنبيه"):
        direction = "DOWN" if (ounce <= 0 or new_target <= ounce) else "UP"
        sheet_alerts.append_row([datetime.now(config.KUWAIT_TZ).strftime("%Y-%m-%d %H:%M"), new_target, direction, "ON", plan_grams, new_note], value_input_option="USER_ENTERED")
        st.rerun()

    st.divider()
    st.subheader("📋 إدارة التنبيهات المسجلة")
    alert_rows = sheet_alerts.get_all_values()
    if len(alert_rows) > 1:
        disp = []
        for idx, r in enumerate(alert_rows[1:], start=2):
            if len(r) >= 4:
                _, p_c, d_c, s_c = r[:4]
                q_c = r[4] if len(r) > 4 else "0"
                try:
                    u_v = float(str(p_c).replace(",", ""))
                    k_v = round((u_v / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
                    rem = round(((u_v - ounce) / ounce) * 100, 2) if ounce > 0 else 0.0
                except Exception:
                    u_v, k_v, rem = 0.0, 0.0, 0.0
                disp.append({
                    "رقم": idx,
                    "الأونصة": f"{u_v:,.2f}$",
                    "الجرام": f"{k_v:.3f}",
                    "المتبقي": f"{rem:+.1f}%",
                    "النوع": "📉 شراء" if str(d_c).strip() == "DOWN" else "📈 بيع",
                    "الحالة": "🟢 نشط" if str(s_c).strip().upper() == "ON" else "✅ منفّذ",
                    "الكمية": q_c
                })
        st.dataframe(pd.DataFrame(disp), use_container_width=True, hide_index=True)

        sel_row = st.number_input("رقم التنبيه للإجراء:", min_value=2, max_value=len(alert_rows), value=len(alert_rows), step=1)
        b1, b2, b3 = st.columns(3)
        if b1.button("🔄 إعادة تفعيل"):
            sheet_alerts.update_acell(f"D{int(sel_row)}", "ON")
            st.rerun()
        if b2.button("✅ تسجيل كصفقة"):
            rd = alert_rows[int(sel_row) - 1]
            _, p_c, d_c, _ = rd[:4]
            q_c = rd[4] if len(rd) > 4 else "10"
            t_k = round((float(str(p_c).replace(",", "")) / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
            t_g = float(str(q_c).replace(",", "")) if float(q_c or 0) > 0 else 10.0
            sheet_log.append_row([datetime.now(config.KUWAIT_TZ).strftime("%Y-%m-%d"), "شراء" if str(d_c).strip() == "DOWN" else "بيع", t_k, t_g], value_input_option="USER_ENTERED")
            sheet_alerts.update_acell(f"D{int(sel_row)}", "TRIGGERED")
            st.success("تم تسجيل الصفقة!")
        if b3.button("🗑️ حذف"):
            sheet_alerts.delete_rows(int(sel_row))
            st.rerun()
    else:
        st.info("لا توجد تنبيهات مسجلة حالياً.")

elif page == "🎯 مناطق الشراء":
    st.subheader("🎯 اقتراح أفضل أسعار الشراء")
    if st.button("🔍 استخرج أفضل 3 مناطق شراء الآن"):
        st.info("⏳ جاري تحليل الشارت والأخبار...")
        st.success(services.suggest_best_buy_zones(ounce, buy_24k, curr_avg, curr_grams))
    st.divider()
    st.subheader("🤖 اسأل المستشار الذكي")
    user_q = st.text_input("مثال: هل الوقت مناسب لشراء 20 جرام أم أنتظر؟")
    if st.button("احسب وحلّل") and user_q:
        st.info("⏳ جاري الحساب...")
        st.success(services.ask_ai_advisor(user_q, ounce, buy_24k, sell_24k, sheet_dashboard.get("A13:I16")))
    st.divider()
    if st.button("📢 إرسال التقرير الشامل لتيليجرام وواتساب"):
        st.info("⏳ جاري الإرسال...")
        st.markdown(services.generate_and_send_report(sheet_dashboard, send_notifications=True), unsafe_allow_html=True)

elif page == "🧮 الحاسبة والزكاة":
    st.subheader("🧮 محاكي تعديل المتوسط (ماذا لو اشتريت؟)")
    sim_grams = st.slider("الكمية المقترحة للشراء (بالجرام)", 1, 200, 20, 1)
    sim_price = st.number_input("سعر الشراء المتوقع للجرام (د.ك)", value=float(buy_24k) if buy_24k > 0 else 36.460, step=0.05, format="%.3f")
    if curr_grams > 0 and curr_avg > 0:
        new_grams = curr_grams + sim_grams
        new_avg = round(((curr_grams * curr_avg) + (sim_grams * sim_price)) / new_grams, 3)
        c1, c2 = st.columns(2)
        c1.metric("متوسط التكلفة الجديد", f"{new_avg:.3f} د.ك", f"{round(new_avg - curr_avg, 3):+.3f} د.ك", delta_color="inverse")
        c2.metric("الرصيد الإجمالي الجديد", f"{new_grams:.1f} جم", f"+{sim_grams} جم")
        st.info(f"💰 التكلفة الإجمالية للدفعة الجديدة: **{round(sim_grams * sim_price, 3):,.3f} د.ك**")
    st.divider()
    st.subheader("🕌 حاسبة زكاة الذهب التلقائية")
    nisab_val = getattr(config, "ZAKAT_NISAB_GRAMS", 85.0)
    if curr_grams >= nisab_val:
        z_grams = round(curr_grams * getattr(config, "ZAKAT_RATE", 0.025), 3)
        st.warning(f"رصيدك ({curr_grams} جم) بلغ النصاب الشرعي ({nisab_val} جم).")
        z1, z2 = st.columns(2)
        z1.metric("مقدار الزكاة (بالجرام)", f"{z_grams} جم")
        z2.metric("قيمة الزكاة النقدية", f"{round(z_grams * sell_24k, 3):,.3f} د.ك")
    else:
        st.success(f"رصيدك ({curr_grams} جم) لم يبلغ النصاب الشرعي ({nisab_val} جم) بعد.")

elif page == "➕ صفقة":
    st.subheader("➕ تسجيل صفقة في دار السبائك")
    op_type = st.radio("نوع العملية", ["شراء", "بيع"], horizontal=True, key="op_type_radio")
    grams = st.number_input("الوزن (بالجرام)", min_value=0.1, value=10.0, step=1.0, format="%.2f")
    price_input = st.number_input("سعر الجرام أو إجمالي الفاتورة (د.ك)", min_value=0.001, value=float(buy_24k) if buy_24k > 0 else 36.460, step=0.1, format="%.3f")
    if st.button("✅ تسجيل العملية الآن"):
        final_price = round(price_input / grams, 4) if price_input > 150 else price_input
        sheet_log.append_row([datetime.now(config.KUWAIT_TZ).strftime("%Y-%m-%d"), op_type, final_price, grams], value_input_option="USER_ENTERED")
        st.success(f"تم تسجيل {op_type} {grams} جم بسعر {final_price} د.ك بنجاح!")

elif page == "📜 السجل":
    st.subheader("📜 سجل صفقات محفظتي")
    all_rows = sheet_log.get_all_values()
    if len(all_rows) > 1:
        records = []
        for r in reversed(all_rows[1:]):
            if len(r) >= 4:
                d_s, t_s, p_s, w_s = r[:4]
                try:
                    tot = round(float(str(p_s).replace(",", "")) * float(str(w_s).replace(",", "")), 3)
                except ValueError:
                    tot = 0.0
                records.append({"التاريخ": d_s, "العملية": f"🟢 {t_s}" if "شراء" in str(t_s) else f"🔴 {t_s}", "السعر": p_s, "الوزن": w_s, "الإجمالي": f"{tot:,.3f}"})
        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد صفقات مسجلة حتى الآن.")
    st.divider()
    if st.button("🗑️ حذف آخر صفقة مسجلة") and len(all_rows) > 1:
        sheet_log.delete_rows(len(all_rows))
        st.warning("تم حذف آخر صفقة وتحديث الرصيد!")
        st.rerun()

live_sabaek_ticker()
