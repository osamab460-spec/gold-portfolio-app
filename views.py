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
        if not df_candles.empty:
            if chart_style == "شموع يابانية 🕯️":
                trace = go.Candlestick(
                    x=df_candles.index, open=df_candles["Open"], high=df_candles["High"],
                    low=df_candles["Low"], close=df_candles["Close"],
                    increasing_line_color="#00E676", decreasing_line_color="#FF3D00", name="السعر"
                )
            else:
                trace = go.Scatter(
                    x=df_candles.index, y=df_candles["Close"], mode="lines+markers",
                    line=dict(color="#E6C25A", width=2.5), marker=dict(size=4, color="#FFD700"),
                    fill="tozeroy", fillcolor="rgba(230, 194, 90, 0.12)", name="السعر"
                )

            fig = go.Figure(data=[trace])
            if show_avg and unit_code == "KWD" and curr_avg > 0:
                fig.add_hline(
                    y=curr_avg, line_dash="dash", line_color="#FFD700", line_width=1.8,
                    annotation_text=f"متوسطك: {curr_avg:.3f}", annotation_position="top right",
                    annotation_font_color="#FFD700"
                )

            fig.update_layout(
                template="plotly_dark", paper_bgcolor="#1C1C1E", plot_bgcolor="#141416",
                height=360, margin=dict(l=8, r=8, t=25, b=8),
                xaxis_rangeslider_visible=False, dragmode="pan"
            )
            plotly_cfg = {"displayModeBar": True, "scrollZoom": True, "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"]}
            st.plotly_chart(fig, use_container_width=True, config=plotly_cfg)
        else:
            st.info("بيانات الشموع غير متاحة حالياً.")
    except Exception as e:
        st.error(f"تعذر رسم الشارت: {e}")

    st.subheader("💼 ملخص محفظتي")

    avg_display = f"{avg_cost_str} د.ك" if "د.ك" not in str(avg_cost_str) else f"{avg_cost_str}"
    pnl_color = "#00E676" if net_pnl_kwd >= 0 else "#FF3D00"
    pnl_arrow = "▲" if net_pnl_kwd >= 0 else "▼"

    # بطاقات HTML مخصصة تضمن ظهور المسميات بالذهبي والأرقام بالأبيض 100%
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
