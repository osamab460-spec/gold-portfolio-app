import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import config
import services

def render_home_and_chart(gold_balance_str, total_cost_str, avg_cost_str, curr_avg, net_pnl_kwd):
    c1, c2, c3 = st.columns(3)
    tf_label = c1.selectbox("الفاصل", ["1 دقيقة", "10 دقائق", "15 دقيقة", "ساعة", "يومي"])
    tf_map = {"1 دقيقة": "1m", "10 دقائق": "10m", "15 دقيقة": "15m", "ساعة": "1h", "يومي": "1d"}
    unit_label = c2.selectbox("العملة", ["دينار كويتي (د.ك)", "دولار ($)"])
    unit_code = "KWD" if "كويتي" in unit_label else "USD"
    chart_style = c3.selectbox("الرسم", ["شموع يابانية 🕯️", "خطي ذهبي 📈"])
    show_avg = st.checkbox("إظهار خط متوسط تكلفتي على الشارت", value=True)

    try:
        df_candles = services.get_candlestick_data(timeframe=tf_map[tf_label], unit=unit_code)
        if df_candles.empty:
            st.info("بيانات الشموع غير متاحة حالياً.")
        else:
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
    avg_display = f"{avg_cost_str} د.ك" if "د.ك" not in str(avg_cost_str) else f"{avg_cost_str}"
    pnl_color = "#00E676" if net_pnl_kwd >= 0 else "#FF3D00"
    pnl_arrow = "▲" if net_pnl_kwd >= 0 else "▼"

    st.markdown(f"""
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; direction:rtl; margin-top:6px;">
        <div style="background:#1C1C1E; border:1px solid #2E2E32; border-right:4px solid #E6C25A; border-radius:12px; padding:12px 14px;">
            <div style="color:#E6C25A; font-size:0.88rem; font-weight:800; margin-bottom:4px;">🪙 رصيد الذهب</div>
            <div style="color:#FFFFFF; font-size:1.35rem; font-weight:800;">{gold_balance_str} جم</div>
        </div>
        <div style="background:#1C1C1E; border:1px solid #2E2E32; border-right:4px solid #E6C25A; border-radius:12px; padding:12px 14px;">
            <div style="color:#E6C25A; font-size:0.88rem; font-weight:800; margin-bottom:4px;">⚖️ متوسط التكلفة</div>
            <div style="color:#FFFFFF; font-size:1.35rem; font-weight:800;">{avg_display}</div>
        </div>
        <div style="background:#1C1C1E; border:1px solid #2E2E32; border-right:4px solid #E6C25A; border-radius:12px; padding:12px 14px;">
            <div style="color:#E6C25A; font-size:0.88rem; font-weight:800; margin-bottom:4px;">💰 إجمالي التكلفة</div>
            <div style="color:#FFFFFF; font-size:1.35rem; font-weight:800;">{total_cost_str} د.ك</div>
        </div>
        <div style="background:#1C1C1E; border:1px solid #2E2E32; border-right:4px solid #E6C25A; border-radius:12px; padding:12px 14px;">
            <div style="color:#E6C25A; font-size:0.88rem; font-weight:800; margin-bottom:4px;">📊 صافي الربح / الخسارة (بيع)</div>
            <div style="color:{pnl_color}; font-size:1.35rem; font-weight:800;">{pnl_arrow} {net_pnl_kwd:+,.3f} د.ك</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_buy_zones(sheet_dashboard, ounce, buy_24k, sell_24k, curr_avg, curr_grams):
    st.subheader("🎯 اقتراح أفضل أسعار الشراء")
    if st.button("🔍 استخرج أفضل 3 مناطق شراء الآن"):
        st.info("⏳ جاري تحليل الشارت والأخبار...")
        zones = services.suggest_best_buy_zones(ounce, buy_24k, curr_avg, curr_grams)
        st.success(zones)

    st.divider()
    st.subheader("🤖 اسأل المستشار الذكي")
    user_q = st.text_input("مثال: هل الوقت مناسب لشراء 20 جرام أم أنتظر؟")
    if st.button("احسب وحلّل") and user_q:
        st.info("⏳ جاري الحساب...")
        portfolio_rows = sheet_dashboard.get("A13:I16")
        answer = services.ask_ai_advisor(user_q, ounce, buy_24k, sell_24k, portfolio_rows)
        st.success(answer)

    st.divider()
    if st.button("📢 إرسال التقرير الشامل لتيليجرام وواتساب"):
        st.info("⏳ جاري الإرسال...")
        rep = services.generate_and_send_report(sheet_dashboard, send_notifications=True)
        st.markdown(rep, unsafe_allow_html=True)

def render_calculator_and_zakat(buy_24k, sell_24k, curr_grams, curr_avg):
    st.subheader("🧮 محاكي تعديل المتوسط (ماذا لو اشتريت؟)")
    sim_grams = st.slider("الكمية المقترحة للشراء (بالجرام)", min_value=1, max_value=200, value=20, step=1)
    default_price = float(buy_24k) if buy_24k > 0 else 36.300
    sim_price = st.number_input("سعر الشراء المتوقع للجرام (د.ك)", value=default_price, step=0.05, format="%.3f")

    old_total = curr_grams * curr_avg
    new_total = old_total + (sim_grams * sim_price)
    new_grams = curr_grams + sim_grams
    new_avg = round(new_total / new_grams, 3) if new_grams > 0 else sim_price
    diff_avg = round(new_avg - curr_avg, 3) if curr_avg > 0 else 0.0
    diff_color = "#00E676" if diff_avg <= 0 else "#FF3D00"
    diff_arrow = "▼" if diff_avg < 0 else ("▲" if diff_avg > 0 else "•")

    st.markdown(f"""
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; direction:rtl; margin:8px 0 12px 0;">
        <div style="background:#1C1C1E; border:1px solid #2E2E32; border-right:4px solid #E6C25A; border-radius:12px; padding:12px 14px;">
            <div style="color:#E6C25A; font-size:0.88rem; font-weight:800; margin-bottom:4px;">⚖️ متوسط التكلفة الجديد</div>
            <div style="color:#FFFFFF; font-size:1.35rem; font-weight:800;">{new_avg:.3f} د.ك</div>
            <div style="color:{diff_color}; font-size:0.85rem; font-weight:700; margin-top:2px;">{diff_arrow} {diff_avg:+.3f} د.ك</div>
        </div>
        <div style="background:#1C1C1E; border:1px solid #2E2E32; border-right:4px solid #E6C25A; border-radius:12px; padding:12px 14px;">
            <div style="color:#E6C25A; font-size:0.88rem; font-weight:800; margin-bottom:4px;">🪙 الرصيد الإجمالي الجديد</div>
            <div style="color:#FFFFFF; font-size:1.35rem; font-weight:800;">{new_grams:.1f} جم</div>
            <div style="color:#00E676; font-size:0.85rem; font-weight:700; margin-top:2px;">▲ +{sim_grams} جم</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info(f"💰 التكلفة الإجمالية للدفعة الجديدة: **{round(sim_grams * sim_price, 3):,.3f} د.ك** | متوسطك الحالي: **{curr_avg:.3f} د.ك**")

    st.divider()
    st.subheader("🕌 حاسبة زكاة الذهب التلقائية")
    if curr_grams >= config.ZAKAT_NISAB_GRAMS:
        zakat_grams = round(curr_grams * config.ZAKAT_RATE, 3)
        zakat_kwd = round(zakat_grams * sell_24k, 3)
        st.warning(f"رصيدك ({curr_grams} جم) بلغ النصاب الشرعي (85 جم عيار 24).")
        st.markdown(f"""
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; direction:rtl; margin-top:8px;">
            <div style="background:#1C1C1E; border:1px solid #2E2E32; border-right:4px solid #E6C25A; border-radius:12px; padding:12px 14px;">
                <div style="color:#E6C25A; font-size:0.88rem; font-weight:800; margin-bottom:4px;">🕌 مقدار الزكاة (بالجرام)</div>
                <div style="color:#FFFFFF; font-size:1.35rem; font-weight:800;">{zakat_grams} جم</div>
            </div>
            <div style="background:#1C1C1E; border:1px solid #2E2E32; border-right:4px solid #E6C25A; border-radius:12px; padding:12px 14px;">
                <div style="color:#E6C25A; font-size:0.88rem; font-weight:800; margin-bottom:4px;">💵 قيمة الزكاة النقدية</div>
                <div style="color:#FFFFFF; font-size:1.35rem; font-weight:800;">{zakat_kwd:,.3f} د.ك</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.success(f"رصيدك ({curr_grams} جم) لم يبلغ النصاب الشرعي (85 جم) بعد.")

def render_add_trade(sheet_log):
    st.subheader("➕ تسجيل صفقة في دار السبائك")
    op_type = st.radio("نوع العملية", ["شراء", "بيع"], horizontal=True)
    grams = st.number_input("الوزن (بالجرام)", min_value=0.1, step=1.0, format="%.2f")
    price_input = st.number_input("سعر الجرام أو إجمالي الفاتورة (د.ك)", min_value=0.001, step=0.1, format="%.3f")

    if st.button("✅ تسجيل العملية الآن"):
        final_price = round(price_input / grams, 4) if price_input > 150 else price_input
        today_str = datetime.now(config.KUWAIT_TZ).strftime("%Y-%m-%d")
        sheet_log.append_row([today_str, op_type, final_price, grams], value_input_option="USER_ENTERED")
        st.success(f"تم تسجيل {op_type} {grams} جم بسعر {final_price} د.ك بنجاح!")

def render_trade_log(sheet_log):
    st.subheader("📜 سجل صفقات محفظتي")
    all_rows = sheet_log.get_all_values()
    if len(all_rows) > 1:
        records = []
        for r in reversed(all_rows[1:]):
            if len(r) >= 4:
                date_val, op_val, price_val, grams_val = r[:4]
                try:
                    p = float(str(price_val).replace(",", ""))
                    g = float(str(grams_val).replace(",", ""))
