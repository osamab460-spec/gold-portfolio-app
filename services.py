import re
import json
import urllib.parse
import requests
import feedparser
from datetime import datetime
import streamlit as st
import gspread
from google import genai
import yfinance as yf
import pandas as pd
import config

ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"].strip())

@st.cache_resource
def init_sheets():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open_by_key(config.SPREADSHEET_ID)
    return sh.worksheet(config.SHEET_DASHBOARD_NAME), sh.worksheet(config.SHEET_LOG_NAME)

@st.cache_data(ttl=15)
def get_live_gold():
    ounce = 0.0
    prev_close = 0.0
    source_label = "SPOT XAU/USD"

    try:
        tv_url = "https://tradingview.com"
        payload = {
            "symbols": {"tickers": ["OANDA:XAUUSD", "FX_IDC:XAUUSD"]},
            "columns": ["close", "open", "change", "change_abs"]
        }
        tv_res = requests.post(tv_url, json=payload, timeout=5).json()
        rows = tv_res.get("data", [])
        if rows:
            first_row = next(iter(rows))
            vals = first_row.get("d", [])
            if len(vals) >= 4:
                first_val = float(next(iter(vals)))
                if first_val > 0:
                    ounce = round(first_val, 3)
                    ch_abs = float(vals[-1])
                    prev_close = round(ounce - ch_abs, 3)
                    source_label = "TV OANDA:XAUUSD"
    except Exception:
        pass

    if ounce <= 0:
        try:
            paxg = yf.Ticker("PAXG-USD")
            hist_p = paxg.history(period="2d")
            if not hist_p.empty:
                ounce = round(float(hist_p["Close"].iloc[-1]), 3)
                prev_close = round(float(hist_p["Close"].iloc[-2]), 3) if len(hist_p) > 1 else ounce
                source_label = "SPOT GOLD (PAXG)"
        except Exception:
            pass

    if ounce <= 0:
        ticker = yf.Ticker("GC=F")
        hist_1d = ticker.history(period="2d")
        if not hist_1d.empty:
            ounce = round(float(hist_1d["Close"].iloc[-1]), 3)
            prev_close = round(float(hist_1d["Close"].iloc[-2]), 3) if len(hist_1d) > 1 else ounce
            source_label = "GC=F"

    if prev_close <= 0:
        prev_close = ounce

    ch = round(ounce - prev_close, 3)
    chp = round((ch / prev_close) * 100, 2) if prev_close else 0.0

    buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
    sell_24k = round(buy_24k - config.SELL_SPREAD_KWD, 3) if buy_24k > 0 else 0.0
    k22 = round(buy_24k * (22 / 24), 3)
    k21 = round(buy_24k * (21 / 24), 3)
    k18 = round(buy_24k * (18 / 24), 3)

    return {
        "ounce": ounce,
        "ch": ch,
        "chp": chp,
        "buy_24k": buy_24k,
        "sell_24k": sell_24k,
        "k22": k22,
        "k21": k21,
        "k18": k18,
        "source": source_label
    }

@st.cache_data(ttl=30)
def get_candlestick_data(timeframe="1m", unit="KWD"):
    spot_data = get_live_gold()
    spot_ounce = spot_data["ounce"]

    ticker = yf.Ticker("GC=F")
    if timeframe == "1m":
        hist = ticker.history(period="1d", interval="1m").tail(60)
    elif timeframe == "10m":
        raw_5m = ticker.history(period="2d", interval="5m")
        if not raw_5m.empty:
            hist = raw_5m.resample("10min").agg({
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last"
            }).dropna().tail(48)
        else:
            hist = raw_5m
    elif timeframe == "15m":
        hist = ticker.history(period="2d", interval="15m").tail(60)
    elif timeframe == "1h":
        hist = ticker.history(period="7d", interval="1h")
    else:
        hist = ticker.history(period="2mo", interval="1d")

    if hist.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close"])

    df = hist[["Open", "High", "Low", "Close"]].dropna().copy()

    if not df.empty and spot_ounce > 0:
        futures_last = float(df["Close"].iloc[-1])
        spread_offset = futures_last - spot_ounce
        df = df - spread_offset

    if unit == "KWD":
        df = (df * (config.KUWAIT_FACTOR / config.OUNCE_TO_GRAM)).round(3)
    else:
        df = df.round(2)
    return df
