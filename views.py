import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import config
import services


def _card(title, value, sub="", sub_color="#00E676"):
    sub_html = (
        f'<div style="color:{sub_color};font-size:0.85rem;font-weight:700;margin-top:2px;">{sub}</div>'
        if sub
        else ""
    )
    return (
        '<div style="background:#1C1C1E;border:1px solid #2E2E32;border-right:4px solid #E6C25A;'
        'border-radius:12px;padding:12px 14px;direction:rtl;text-align:right;">'
        f'<div style="color:#E6C25A;font-size:0.88rem;font-weight:800;margin-bottom:4px;">{title}</div>'
        f'<div style="color:#FFFFFF;font-size:1.35rem;font-weight:800;">{value}</div>'
        f'{sub_html}</div>'
    )


def _safe_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "").replace("$", "").replace("د.ك", "").strip())
    except (TypeError, ValueError):
        return default


def render_home_and_chart(
    gold_balance_str, total_cost_str, avg_cost_str, curr_avg, net_pnl_kwd
):
    c1, c2, c3 = st.columns(3)
    tf_label = c1.selectbox("الفاصل", ["1 دقيقة", "10 دقائق", "15 دقيقة", "ساعة", "يومي"])
    tf_map = {
        "1 دقيقة": "1m",
        "10 دقائق": "10m",
        "15 دقيقة": "15m",
        "ساعة": "1h",
        "يومي": "1d",
    }
    unit_label = c2.selectbox("العملة", ["دينار كويتي (د.ك)", "دولار ($)"])
    unit_code = "KWD" if "كويتي" in unit_label else "USD"
    chart_style = c3.selectbox("الرسم", ["شموع يابانية 🕯️", "خطي ذهبي 📈"])
    show_avg = st.checkbox("إظهار خط متوسط تكلفتي على الشارت", value=True)

    try:
        df_candles = services.get_candlestick_data(
            timeframe=tf_map[tf_label], unit=unit_code
        )
        if df_candles.empty:
            st.info("بيانات الشموع غير متاحة حالياً، يرجى تغيير الفاصل الزمني.")
        else:
            if chart_style == "شموع يابانية 🕯️":
                trace = go.Candlestick(
                    x=df_candles.index,
                    open=df_candles["Open"],
                    high=df_candles["High"],
                    low=df_candles["Low"],
                    close=df_candles["Close"],
                    increasing_line_color="#00E676",
                    decreasing_line_color="#FF3D00",
                    name="السعر",
                )
            else:
                trace = go.Scatter(
                    x=df_candles.index,
                    y=df_candles["Close"],
                    mode="lines+markers",
