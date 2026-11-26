import re
import json
import requests
import feedparser
from datetime import datetime
import streamlit as st
import gspread
from google import genai
import yfinance as yf
import pandas as pd
import config

SLASH = chr(47)
SCHEME = "https:" + SLASH + SLASH

ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"].strip())

@st.cache_resource
def init_sheets():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open_by_key(config.SPREADSHEET_ID)
    return sh.worksheet(config.SHEET_DASHBOARD_NAME), sh.worksheet(config.SHEET_LOG_NAME)

def _scrape_daralsabaek():
    url = SCHEME + "daralsabaek.com"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ar,en;q=0.9"
    }
    resp = requests.get(url, headers=headers, timeout=6)
    if resp.status_code != 200:
        return None

    text = resp.text
    kwd_matches = re.findall(r'(\d{2}\.\d{3})\s*(?:د\.ك|KWD)', text)
    usd_matches = re.findall(r'(\d{1},?\d{3}\.\d{2,3})\s*USD', text)

    nums = [float(x) for x in kwd_matches if 20.0 <= float(x) <= 60.0]
    if len(nums) >= 8:
        ounce = float(usd_matches[0].replace(",", "")) if usd_matches else 0.0
        return {
            "ounce": ounce,
            "buy_24k": nums[0],
            "sell_24k": nums[1],
            "k22": nums[2],
            "k21": nums[4],
            "k18": nums[6],
            "source": "دار السبائك مباشر 🟢"
        }
    return None

@st.cache_data(ttl=15)
def get_live_gold():
    headers = {"User-Agent": "Mozilla/5.0"}
    ounce = 0.0
    source_label = "سوق فوري عالمي 🟡"

    # 1. محاولة السحب المباشر من موقع دار السبائك
    try:
        scraped = _scrape_daralsabaek()
        if scraped and scraped["buy_24k"] > 0:
            ticker = yf.Ticker("GC=F")
            hist_1d = ticker.history(period="2d")
            prev_close = round(float(hist_1d["Close"].iloc[-2]), 3) if len(hist_1d) > 1 else scraped["ounce"]
            ounce = scraped["ounce"] if scraped["ounce"] > 0 else round(float(hist_1d["Close"].iloc[-1]), 3)
            ch = round(ounce - prev_close, 3) if prev_close else 0.0
            chp = round((ch / prev_close) * 100, 2) if prev_close else 0.0
            return {
                "ounce": ounce, "ch": ch, "chp": chp,
                "buy_24k": scraped["buy_24k"], "sell_24k": scraped["sell_24k"],
                "k22": scraped["k22"], "k21": scraped["k21"], "k18": scraped["k18"],
                "source": scraped["source"]
            }
    except Exception:
        pass

    # 2. المصدر الفوري الأول: Swissquote Spot XAU/USD
    try:
        sq_url = SCHEME + "://swissquote.com" + SLASH + "public-quotes" + SLASH + "bboquotes" + SLASH + "instrument" + SLASH + "XAU" + SLASH + "USD"
        data = requests.get(sq_url, headers=headers, timeout=6).json()
        first_price = next(iter(next(iter(data)).get("spreadProfilePrices", [])))
        ounce = round((float(first_price["bid"]) + float(first_price["ask"])) / 2, 3)
        source_label = "Swissquote Spot 🟢"
    except Exception:
        pass

    # 3. المصدر الفوري الثاني: Gold-API Spot
    if ounce <= 0:
        try:
            g_url = SCHEME + "://gold-api.com" + SLASH + "price" + SLASH + "XAU"
            r_gold = requests.get(g_url, headers=headers, timeout=6).json()
            ounce = round(float(r_gold.get("price", 0)), 3)
            source_label = "Gold-API Spot 🟢"
        except Exception:
            pass

    ticker = yf.Ticker("GC=F")
    hist_1d = ticker.history(period="2d")
    prev_close = round(float(hist_1d["Close"].iloc[-2]), 3) if len(hist_1d) > 1 else ounce
    if ounce <= 0:
        ounce = round(float(hist_1d["Close"].iloc[-1]), 3)
        source_label = "عقود آجلة GC=F 🟡"

    ch = round(ounce - prev_close, 3) if prev_close else 0.0
    chp = round((ch / prev_close) * 100, 2) if prev_close else 0.0

    buy_24k = round((ounce / config.OUNCE_TO_GRAM) * config.KUWAIT_FACTOR, 3)
    sell_24k = round(buy_24k - config.SELL_SPREAD_KWD, 3)
    k22 = round(buy_24k * (22 / 24), 3)
    k21 = round(buy_24k * (21 / 24), 3)
    k18 = round(buy_24k * (18 / 24), 3)

    return {
        "ounce": ounce, "ch": ch, "chp": chp,
        "buy_24k": buy_24k, "sell_24k": sell_24k,
        "k22": k22, "k21": k21, "k18": k18,
        "source": source_label
    }
