import re
import time
import streamlit as st
import services
import views

st.set_page_config(page_title="دار السبائك AI", page_icon="🪙", layout="centered", initial_sidebar_state="collapsed")

css_style = (
    "<style>"
    ".main { direction: rtl; text-align: right; }"
    ".sabaek-top { display: flex; justify-content: space-between; align-items: center; padding: 8px 4px 12px 4px; border-bottom: 1px solid #E0E0E0; margin-bottom: 10px; }"
    ".sabaek-logo { color: #B8860B; font-size: 1.65rem; font-weight: 900; }"
    ".gold-ticker-box { background-color: #1C1C1E; border: 1px solid #2E2E32; border-radius: 14px; padding: 14px 16px; margin-bottom: 10px; direction: ltr; text-align: left; }"
    ".gold-ticker-title { color: #E6C25A; font-weight: 800; font-size: 1rem; display: flex; justify-content: space-between; }"
    ".gold-ticker-price { font-size: 1.45rem; font-weight: 800; margin-top: 6px; }"
    ".karats-grid { display: grid; grid-template-columns: repeat(4, 1fr); background-color: #1C1C1E; border: 1px solid #2E2E32; border-radius: 14px; padding: 12px 6px; margin-bottom: 14px; text-align: center; direction: rtl; }"
    ".karat-item { border-left: 1px solid #2E2E32; padding: 0 4px; }"
    ".karat-item:last-child { border-left: none; }"
    ".karat-name { color: #B0B0B0; font-size: 0.85rem; margin-bottom: 4px; }"
    ".karat-val { font-size: 1.02rem; font-weight: 800; }"
    ".price-up { color: #00E676; }"
    ".price-down { color: #FF3D00; }"
    ".price-same { color: #111111; background-color: #E0E0E0; padding: 1px 6px; border-radius: 6px; }"
    'div[role="radiogroup"] { direction: rtl; justify-content: center; background-color: #1C1C1E !important; padding: 8px; border-radius: 14px; border: 1px solid #333333; gap: 6px; }'
    'div[role="radiogroup"] label, div[role="radiogroup"] label * { color: #FFFFFF !important; font-weight: 700 !important; }'
    ".stButton>button { width: 100%; border-radius: 12px; height: 3.1em; font-weight: 800; }"
    "</style>"
)
st.markdown(css_style, unsafe_allow_html=True)

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

@st.fragment(run_every=15)
def live_sabaek_karats():
    try:
        data = services.get_live_gold()
        ounce, chp = data["ounce"], data["chp"]
        buy_24k, sell_24k = data["buy_24k"], data["sell_24k"]
        k22, k21, k18 = data["k22"], data["k21"], data["k18"]
        src_lbl = data.get("source", "SPOT XAU/USD")

        st.session_state["live_ounce"] = ounce
        st.session_state["live_buy_24k"] = buy_24k
        st.session_state["live_sell_24k"] = sell_24k

        prev_ounce = st.session_state.get("prev_tick_ounce", ounce)
        color_cls = "price-up" if ounce > prev_ounce else ("price-down" if ounce < prev_ounce else "price-same")
        arrow = "▲" if ounce > prev_ounce else ("▼" if ounce < prev_ounce else "•")
        st.session_state["prev_tick_ounce"] = ounce

        now_ts = time.time()
        last_sync = st.session_state.get("last_sheet_sync", 0)
        if ounce > 0 and (now_ts - last_sync) >= 300:
            sheet_dashboard.update_acell("C5", ounce)
            st.session_state["last_sheet_sync"] = now_ts

        ticker_html = (
            f'<div class="sabaek-top"><span class="sabaek-logo">🪙 دار السبائك AI</span><span style="color:#555555; font-size:0.8rem;">{src_lbl} • 15ث ⏱️</span></div>'
            '<div class="gold-ticker-box">'
            f'<div class="gold-ticker-title"><span>🪙 GOLD SPOT (XAU/USD)</span><span style="color:#E6C25A;">بيع 24: {sell_24k:.3f} د.ك</span></div>'
            f'<div class="gold-ticker-price"><span class="{color_cls}">{ounce:,.3f}</span><span style="font-size:0.9rem; color:#BDBDBD;"> USD </span><span class="{color_cls}" style="font-size:0.95rem;">{arrow} {chp:+.2f}%</span></div>'
            '</div>'
            '<div class="karats-grid">'
            f'<div class="karat-item"><div class="karat-name">شراء ٢٤</div><div class="karat-val {color_cls}">{buy_24k:.3f} د.ك</div></div>'
            f'<div class="karat-item"><div class="karat-name">عيار ٢٢</div><div class="karat-val {color_cls}">{k22:.3f} د.ك</div></div>'
            f'<div class="karat-item"><div class="karat-name">عيار ٢١</div><div class="karat-val {color_cls}">{k21:.3f} د.ك</div></div>'
            f'<div class="karat-item"><div class="karat-name">عيار ١٨</div><div class="karat-val {color_cls}">{k18:.3f} د.ك</div></div>'
            '</div>'
        )
        st.markdown(ticker_html, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"خطأ في تحديث العيارات: {e}")

live_sabaek_karats()

ounce = st.session_state.get("live_ounce", 0.0)
buy_24k = st.session_state.get("live_buy_24k", 0.0)
sell_24k = st.session_state.get("live_sell_24k", 0.0)

def _extract_num(val_str):
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(val_str).replace(",", ""))
    return float(next(iter(nums))) if nums else 0.0

@st.cache_data(ttl=60)
def _get_portfolio_summary():
    row = sheet_dashboard.get("A15:D15")
    vals = next(iter(row)) if row else []
    padded = (list(vals) + ["0", "0", "0", "0"])[:4]
    b, c, _, a = padded
    return b, c, a

gold_balance_str, total_cost_str, avg_cost_str = _get_portfolio_summary()

curr_grams = _extract_num(gold_balance_str)
curr_total_cost = _extract_num(total_cost_str)
curr_avg = _extract_num(avg_cost_str)

if curr_avg <= 0 and curr_grams > 0 and curr_total_cost > 0:
    curr_avg = round(curr_total_cost / curr_grams, 3)
    avg_cost_str = f"{curr_avg:.3f}"

net_pnl_kwd = round((sell_24k - curr_avg) * curr_grams, 3) if (curr_grams > 0 and sell_24k > 0) else 0.0

page = st.radio("القائمة", ["🏠 الرئيسية والشموع", "🎯 مناطق الشراء", "🧮 الحاسبة والزكاة", "➕ صفقة", "📜 السجل"], horizontal=True, label_visibility="collapsed")
st.write("")

if page == "🏠 الرئيسية والشموع":
    views.render_home_and_chart(gold_balance_str, total_cost_str, avg_cost_str, curr_avg, net_pnl_kwd)
elif page == "🎯 مناطق الشراء":
    views.render_buy_zones(sheet_dashboard, ounce, buy_24k, sell_24k, curr_avg, curr_grams)
elif page == "🧮 الحاسبة والزكاة":
    views.render_calculator_and_zakat(buy_24k, sell_24k, curr_grams, curr_avg)
elif page == "➕ صفقة":
    views.render_add_trade(sheet_log)
elif page == "📜 السجل":
    views.render_trade_log(sheet_log)
