
# -----------------------------------------------------------------------------
# Imports & Setup
# -----------------------------------------------------------------------------
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import datetime
import pytz
import ssl

# --- 🚨 Avoid SSL Errors ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# -----------------------------------------------------------------------------
# Page Config
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Alice Diagnosis",
    page_icon="🐇",
    layout="wide"
)

st.title("🐇 Alice Diagnosis: The Liquidity Meltdown Monitor")
st.markdown("---")

# -----------------------------------------------------------------------------
# Data Fetching
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_alice_data():
    tickers = {
        "BIZD": "BIZD",      # BDC/Credit
        "HYG": "HYG",        # Junk Bonds
        "DXY": "DX-Y.NYB",   # US Dollar Index
        "INTU": "INTU",      # SaaS
        "CRM": "CRM",        # SaaS
        "ADBE": "ADBE",      # SaaS
        "IGV": "IGV",        # SaaS ETF
        "SPX": "^GSPC",      # S&P 500
        "BTC": "BTC-USD"     # Bitcoin
    }
    
    data = {}
    for key, ticker in tickers.items():
        # Fetch 2 years to ensure 200MA is valid
        # Note: BIZD might have less history or gaps, so handle gracefully
        try:
            df = yf.Ticker(ticker).history(period="2y")
            if df.empty:
                continue
            # Timezone Alignment
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            data[key] = df['Close']
        except Exception:
            continue
    
    return pd.DataFrame(data)

try:
    df = fetch_alice_data()
    if df is None or df.empty:
        st.error("Failed to fetch data. Please check connection.")
        st.stop()
except Exception as e:
    st.error(f"Data fetch error: {e}")
    st.stop()

# Preprocessing
df.ffill(inplace=True)
df.dropna(inplace=True)

# -----------------------------------------------------------------------------
# Danger Zone Logic (Escape Hatch Trigger)
# -----------------------------------------------------------------------------
# Hardcoded Danger Zone: 2026-02-15 to 2026-03-20
tz_tokyo = pytz.timezone('Asia/Tokyo')
now = datetime.datetime.now(tz_tokyo)
danger_start = datetime.datetime(2026, 2, 15, tzinfo=tz_tokyo)
danger_end = datetime.datetime(2026, 3, 20, tzinfo=tz_tokyo)

# Check if today is in danger zone (ignoring time for simplicity if needed, but datetime comparison works)
is_danger_zone = danger_start <= now <= danger_end

if is_danger_zone:
    st.error("⚠️ MIGRATION EVENT: RED ALERT (Active: 2026/02/15 - 03/20)")
    st.caption("現在、市場は極めて脆弱な「流動性枯渇のリスク期間」に突入しています。")

# -----------------------------------------------------------------------------
# Metric Calculations (The Liquidity Domino)
# -----------------------------------------------------------------------------
# Ensure we have enough data points
if len(df) < 200:
    st.warning("Data insufficient for 200MA calculation.")
    st.stop()

# Moving Averages
# DXY
if 'DXY' in df.columns:
    df['DXY_MA20'] = df['DXY'].rolling(20).mean()
    df['DXY_STD20'] = df['DXY'].rolling(20).std()
    df['DXY_Upper'] = df['DXY_MA20'] + (2 * df['DXY_STD20'])
else:
    df['DXY'] = 0 # Dummy valid
    df['DXY_Upper'] = 999 

# Canary (BTC & SaaS Basket)
if {'INTU', 'CRM', 'ADBE'}.issubset(df.columns):
    df['SaaS_Basket'] = (df['INTU'] + df['CRM'] + df['ADBE']) / 3
else:
    df['SaaS_Basket'] = df['IGV'] if 'IGV' in df.columns else df['SPX'] # Fallback

df['SaaS_MA50'] = df['SaaS_Basket'].rolling(50).mean()
df['BTC_MA50'] = df['BTC'].rolling(50).mean()

# Credit (BIZD)
df['BIZD_MA200'] = df['BIZD'].rolling(200).mean()

# Market (SPX)
df['SPX_MA200'] = df['SPX'].rolling(200).mean()

# Latest Values
latest = df.iloc[-1]

# Step 1: DXY Spike
step1_trigger = latest['DXY'] > latest['DXY_Upper']
# Step 2: Canary Choke (BTC or SaaS < 50MA)
step2_trigger = (latest['BTC'] < latest['BTC_MA50']) or (latest['SaaS_Basket'] < latest['SaaS_MA50'])
# Step 3: Credit Crack (BIZD < 200MA) - CRITICAL
step3_trigger = latest['BIZD'] < latest['BIZD_MA200']
# Step 4: Meltdown (SPX < 200MA)
step4_trigger = latest['SPX'] < latest['SPX_MA200']

# -----------------------------------------------------------------------------
# UI: Liquidity Domino Gauge
# -----------------------------------------------------------------------------
st.subheader("1. 🌊 The Liquidity Domino (流動性のドミノ)")

c1, c2, c3, c4 = st.columns(4)

def get_status_card(col, title, triggered, condition_text):
    if triggered:
        col.metric(f"🔥 {title}", "CRITICAL", condition_text, delta_color="inverse")
    else:
        col.metric(f"✅ {title}", "SAFE", condition_text, delta_color="normal")

get_status_card(c1, "Step 1: DXY Spike", step1_trigger, "DXY > 20MA+2σ")
get_status_card(c2, "Step 2: Canary Choke", step2_trigger, "BTC/SaaS < 50MA")
get_status_card(c3, "Step 3: Credit Crack", step3_trigger, "BIZD < 200MA")
get_status_card(c4, "Step 4: Meltdown", step4_trigger, "S&P500 < 200MA")

if step3_trigger:
    st.error("🚨 ALERT: Credit Crack Detected (BIZD < 200MA). S&P500 Meltdown probability > 80% within 6 weeks.")

# -----------------------------------------------------------------------------
# UI: SaaS Erosion Tracker
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("2. 📉 SaaS Erosion Tracker (IGV vs S&P500)")
st.caption("AIによる「SaaSの収益性破壊」を監視。グラフが下落トレンドならSaaSは『負け組』です。")

if 'IGV' in df.columns and 'SPX' in df.columns:
    df['SaaS_Rel'] = df['IGV'] / df['SPX']
    df['SaaS_Rel_MA50'] = df['SaaS_Rel'].rolling(50).mean()

    fig_saas = go.Figure()
    fig_saas.add_trace(go.Scatter(x=df.index, y=df['SaaS_Rel'], name="IGV / SPX Ratio", line=dict(color='orange')))
    fig_saas.add_trace(go.Scatter(x=df.index, y=df['SaaS_Rel_MA50'], name="50-day MA", line=dict(color='gray', dash='dot')))
    
    fig_saas.update_layout(height=400, title="IGV / SPX Relative Strength")

    latest_saas_rel = latest['SaaS_Rel']
    prev_saas_rel = df.iloc[-2]['SaaS_Rel']
    
    st.metric("SaaS Relative Strength (vs SPX)", f"{latest_saas_rel:.4f}", f"{latest_saas_rel - prev_saas_rel:.4f}")
    st.plotly_chart(fig_saas, use_container_width=True)

# -----------------------------------------------------------------------------
# UI: Escape Hatch Simulation
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("3. 🚪 The Escape Hatch (緊急避難シミュレーション)")

with st.expander("Show Simulation Controls", expanded=True):
    col_input, col_res = st.columns([1, 2])
    
    with col_input:
        current_assets = st.number_input("Current Portfolio Value ($)", value=100000, step=1000)
        crypto_ratio = st.slider("Crypto Allocation (%)", 0, 100, 90)
    
    # Assumptions
    crash_impact_crypto = 0.50 # -50%
    crash_impact_spx = 0.30 # -30%
    crash_impact_safe = 0.05 # -5% (Cash/Bonds/Defensive)
    
    # Logic
    crypto_amount = current_assets * (crypto_ratio / 100.0)
    other_amount = current_assets - crypto_amount
    
    # Scenario A: Do Nothing (Meltdown)
    # Crypto drops 50%, Other drops 30%
    final_a = (crypto_amount * (1.0 - crash_impact_crypto)) + (other_amount * (1.0 - crash_impact_spx))
    loss_a = current_assets - final_a
    
    # Scenario B: Escape 50% to Safety
    # Move 50% of TOTAL assets to Safety
    # Which 50%? Let's assume proportional sell-off of existing assets.
    move_amount = current_assets * 0.50
    
    # Remaining Portfolio (Risk) = 50% of original
    # Safe Portfolio (Safe) = 50% of original
    
    # Risk Part suffers crash
    risk_part_final = final_a * 0.50 
    
    # Safe Part suffers minor dip (currency/fees/safe asset drop)
    safe_part_final = move_amount * (1.0 - crash_impact_safe)
    
    final_b = risk_part_final + safe_part_final
    loss_b = current_assets - final_b
    
    saved_amount = loss_a - loss_b # Positive number = Saved
    
    with col_res:
        c1, c2 = st.columns(2)
        c1.metric("Expected Loss (Do Nothing)", f"-${loss_a:,.0f}", "Crash Scenario", delta_color="inverse")
        c2.metric("Loss Mitigation (Escape 50%)", f"+${saved_amount:,.0f}", "Amount Saved", delta_color="normal")
        
        st.info(f"💡 もし今日、資産の50%を『退避（USD/THBや高配当株）』させれば、計算上 **${saved_amount:,.0f}** の損失を回避できます。これは『利益』ではありませんが、『致命傷』を防ぐためのコストです。")

# -----------------------------------------------------------------------------
# UI: Alice Verdict
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("🐰 Alice's Verdict (アリスの判決)")

alice_verdict = ""
alice_color = "gray"
alice_desc = ""

if step3_trigger: # Credit Check Broken (Level 3)
    alice_verdict = "💀 SELL EVERYTHING immediately."
    alice_desc = "信用市場(BIZD)が崩壊しています。株価指数が高値でも関係ありません。機関投資家はすでに逃げ始めています。今すぐ脱出しなさい。"
    alice_color = "red"
elif step2_trigger: # Canary Dead (Level 2)
    alice_verdict = "⚠️ Prepare for Impact."
    alice_desc = "カナリア(BTC/SaaS)が死にました。炭鉱内の酸素が薄くなっています。まだ逃げられますが、窓口は混雑し始めています。"
    alice_color = "orange"
elif step1_trigger: # Dollar Spike (Level 1)
    alice_verdict = "👀 Watch the Dollar."
    alice_desc = "ドルが強すぎて、新興国やリスク資産の首を絞め始めています。まだ崩壊ではありませんが、パーティーは終わりが近いです。"
    alice_color = "yellow"
else:
    alice_verdict = "🌱 Keep Dancing (Carefully)."
    alice_desc = "今のところ、システムは正常です。ただし、音楽が止まったら即座に座れる椅子を確認しておいてください。"
    alice_color = "green"

st.markdown(f"### {alice_verdict}")
if alice_color == "red":
    st.error(alice_desc)
elif alice_color == "orange":
    st.warning(alice_desc)
elif alice_color == "yellow":
    st.info(alice_desc)
else:
    st.success(alice_desc)
