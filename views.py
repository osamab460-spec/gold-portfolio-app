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
            st.info("بيانات الشموع غير متاحة حالياً.")
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
            if show_avg and unit_code == "KWD" and curr_avg > 0:
                fig.add_hline(
                    y=curr_avg, line_dash="dash", line_color="#FFD700", line_width=1.8,
                    annotation_text=f"متوسطك: {curr_avg:.3f}",
                    annotation_position="top right", annotation_font_color="#FFD700",
                )
            fig.update_layout(
                template="plotly_dark", paper_bgcolor="#1C1C1E", plot_bgcolor="#141416",
                height=360, margin=dict(l=8, r=8, t=25, b=8),
                xaxis_rangeslider_visible=False, dragmode="pan",
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

def render_buy_zones(sheet_dashboard, ounce, buy_24k, sell_24k,
