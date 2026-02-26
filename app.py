import streamlit as st
import numpy as np
import pandas as pd
from scipy.stats import norm
import yfinance as yf

# 1. APP CONFIGURATION
st.set_page_config(page_title="Nifty Sensei Analyzer", layout="wide")
st.title("🎯 Nifty Sensei: Options Income Scanner")

# 2026 Constants
LOT_SIZE_NIFTY = 65  # Updated for 2026
RISK_FREE_RATE = 0.07
TRADING_DAYS = 252

# 2. SIDEBAR INPUTS
st.sidebar.header("Market Controls")
EXPIRY_DAYS = st.sidebar.slider("Days to Expiry", 1, 30, 1)
PCR_MANUAL = st.sidebar.number_input("Live PCR (from NSE)", value=0.88)

# 3. CORE LOGIC
@st.cache_data(ttl=60) # Refreshes every minute
def fetch_live_data():
    nifty = yf.Ticker("^NSEI")
    vix = yf.Ticker("^INDIAVIX")
    spot = nifty.history(period="1d")['Close'].iloc[-1]
    vix_val = vix.history(period="1d")['Close'].iloc[-1] / 100
    return round(spot, 2), round(vix_val, 4)

def get_greeks(S, K, T, r, sigma, option_type="call"):
    T = max(T, 0.00001)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    pdf_d1 = norm.pdf(d1)
    
    if option_type == "call":
        price = (S * norm.cdf(d1)) - (K * np.exp(-r * T) * norm.cdf(d2))
        theta = (-(S * pdf_d1 * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)) / TRADING_DAYS
    else:
        price = (K * np.exp(-r * T) * norm.cdf(-d2)) - (S * norm.cdf(-d1))
        theta = (-(S * pdf_d1 * sigma) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)) / TRADING_DAYS

    return {
        "Strike": K,
        "Price": round(price, 2),
        "Theta_Daily": round(theta, 2),
        "Theta_Lot": round(theta * LOT_SIZE_NIFTY, 2),
        "Delta": round(norm.cdf(d1) if option_type == "call" else norm.cdf(d1) - 1, 3)
    }

# 4. EXECUTION & UI
try:
    LIVE_SPOT, LIVE_VIX = fetch_live_data()
    col1, col2, col3 = st.columns(3)
    col1.metric("Nifty Spot", LIVE_SPOT)
    col2.metric("India VIX", f"{round(LIVE_VIX*100, 2)}%")
    col3.metric("Mode", "PE Selling" if PCR_MANUAL < 0.9 else "CE Selling")

    scan_type = "PE" if PCR_MANUAL < 0.9 else "CE"
    atm_strike = round(LIVE_SPOT / 50) * 50
    strikes = [atm_strike + i for i in range(-200, 250, 50)]
    
    results = [get_greeks(LIVE_SPOT, k, EXPIRY_DAYS/365, RISK_FREE_RATE, LIVE_VIX, "put" if scan_type=="PE" else "call") for k in strikes]
    df = pd.DataFrame(results)
    
    st.subheader(f"Full Strategy Chain: {scan_type}")
    st.table(df)

    optimal = df.loc[df['Theta_Daily'].abs().idxmax()]
    st.success(f"🎯 **OPTIMAL ACTION:** Sell {optimal['Strike']} {scan_type} | Expected Decay: ₹{abs(optimal['Theta_Lot'])}/lot")

except Exception as e:
    st.error(f"Waiting for market data... Error: {e}")
