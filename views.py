import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import config
import services

def _card(title, value, sub="", sub_color="#00E676"):
    sub_html = (
        f'<div style="color:{sub_color};font-size:0.85rem;font-weight:700;margin-top:2px;">{sub}</div>'
        if sub else ""
    )
    return (
        '<div style="background:#1C1C1E;border:1px solid #2E2E32;border-right:4px solid #E6C25A;'
        'border-radius:12px;padding:12px 14px;">'
        f'<div style="color:#E6C25A;font-size:0.88rem;font-weight:800;margin-bottom:4px;">{title}</div>'
        f'<div style="color:#FFFFFF;font-size:1.35rem;font-weight:800;">{value}</div>'
        f'{sub_html}</div>'
    )

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
            st.info("بيانات الشموع غير متاحة حالياً، يرجى تغيير الفاصل الزمني.")
        else:
            if chart_style == "شموع يابانية 🕯️":
                trace = go.Candlestick(
                    x=df_candles.index, open=df_candles["Open"], high=df_candles["High"],
                    low=df_candles["Low"], close=df_candles["Close"],
                    increasing_line_color="#00E676", decreasing_line_color="#FF3D00", name="السعر",
                )
            else:
                trace = go.Scatter(
                    x=df_candles.index, y=df_candles["Close"], mode="lines+markers",
                    line=dict(color="#E6C25A", width=2.5),
                    marker=dict(size=4, color="#FFD700"),
                    fill="tozeroy", fillcolor="rgba(230, 194, 90, 0.12)", name="السعر",
                )
            fig = go.Figure(data=[trace])
            
            # إضافة خط متوسط التكلفة
            if show_avg and unit_code == "KWD" and curr_avg > 0:
                fig.add_hline(
                    y=curr_avg, line_dash="dash", line_color="#FFD700", line_width=1.8,
                    annotation_text=f"متوسطك: {curr_avg:.3f}",
                    annotation_position="top right", annotation_font_color="#FFD700",
                )
            
            # تحسين مظهر الشارت ليتكيف مع البيانات
            fig.update_layout(
                template="plotly_dark", paper_bgcolor="#1C1C1E", plot_bgcolor="#141416",
                height=360, margin=dict(l=8, r=8, t=25, b=8),
                xaxis_rangeslider_visible=False, dragmode="pan",
                yaxis=dict(autorange=True, fixedrange=False)
            )
            plotly_cfg = {
                "displayModeBar": True, "scrollZoom": True,
                "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"],
            }
            st.plotly_chart(fig, use_container_width=True, config=plotly_cfg)
    except Exception as e:
        st.error(f"تعذر رسم الشارت: {e}")

    st.subheader("💼 ملخص محفظتي")
    avg_display = avg_cost_str if "د.ك" in str(avg_cost_str) else f"{avg_cost_str} د.ك"
    pnl_color = "#00E676" if net_pnl_kwd >= 0 else "#FF3D00"
    pnl_arrow = "▲" if net_pnl_kwd >= 0 else "▼"

    grid_html = (
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;direction:rtl;margin-top:6px;">'
        + _card("🪙 رصيد الذهب", f"{gold_balance_str} جم")
        + _card("⚖️ متوسط التكلفة", avg_display)
        + _card("💰 إجمالي التكلفة", f"{total_cost_str} د.ك")
        + _card("📊 صافي الربح / الخسارة", f"{net_pnl_kwd:+,.3f} د.ك", f"{pnl_arrow} سعر البيع الحالي", pnl_color)
        + "</div>"
    )
    st.markdown(grid_html, unsafe_allow_html=True)

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
        portfolio_rows = sheet_dashboard.get("A5:I18")
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
    sim_price = st.number_input(
        "سعر الشراء المتوقع للجرام (د.ك)",
        value=float(default_price), step=0.05, format="%.3f",
    )

    old_total = curr_grams * curr_avg
    new_total = old_total + (sim_grams * sim_price)
    new_grams = curr_grams + sim_grams
    new_avg = round(new_total / new_grams, 3) if new_grams > 0 else sim_price
    diff_avg = round(new_avg - curr_avg, 3) if curr_avg > 0 else 0.0
    diff_color = "#00E676" if diff_avg <= 0 else "#FF3D00"
    diff_arrow = "▼" if diff_avg < 0 else ("▲" if diff_avg > 0 else "•")

    sim_html = (
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;direction:rtl;margin:8px 0 12px 0;">'
        + _card("⚖️ متوسط التكلفة الجديد", f"{new_avg:.3f} د.ك", f"{diff_arrow} {diff_avg:+.3f} د.ك", diff_color)
        + _card("🪙 الرصيد الإجمالي الجديد", f"{new_grams:.1f} جم", f"▲ +{sim_grams} جم", "#00E676")
        + "</div>"
    )
    st.markdown(sim_html, unsafe_allow_html=True)
    st.info(
        f"💰 التكلفة الإجمالية للدفعة الجديدة: **{round(sim_grams * sim_price, 3):,.3f} د.ك** | "
        f"متوسطك الحالي: **{curr_avg:.3f} د.ك**"
    )

    st.divider()
    st.subheader("🕌 حاسبة زكاة الذهب التلقائية")
    if curr_grams >= config.ZAKAT_NISAB_GRAMS:
        zakat_grams = round(curr_grams * config.ZAKAT_RATE, 3)
        zakat_kwd = round(zakat_grams * sell_24k, 3)
        st.warning(f"رصيدك ({curr_grams} جم) بلغ النصاب الشرعي (85 جم عيار 24).")
        zakat_html = (
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;direction:rtl;margin-top:8px;">'
            + _card("🕌 مقدار الزكاة (بالجرام)", f"{zakat_grams} جم")
            + _card("💵 قيمة الزكاة النقدية", f"{zakat_kwd:,.3f} د.ك")
            + "</div>"
        )
        st.markdown(zakat_html, unsafe_allow_html=True)
    else:
        st.success(f"رصيدك ({curr_grams} جم) لم يبلغ النصاب الشرعي (85 جم) بعد.")

def render_add_trade(sheet_log):
    st.subheader("➕ تسجيل صفقة في دار السبائك")
    op_type = st.radio("نوع العملية", ["شراء", "بيع"], horizontal=True)
    grams = st.number_input("الوزن (بالجرام)", min_value=0.1, step=1.0, format="%.2f")
    price_input = st.number_input(
        "سعر الجرام أو إجمالي الفاتورة (د.ك)", min_value=0.001, step=0.1, format="%.3f"
    )

    if st.button("✅ تسجيل العملية الآن"):
        final_price = round(price_input / grams, 4) if price_input > 150 else price_input
        today_str = datetime.now(config.KUWAIT_TZ).strftime("%Y-%m-%d")
        sheet_log.append_row([today
