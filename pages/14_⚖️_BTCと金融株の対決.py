import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# --- 🚨 Avoid SSL Errors ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ----------------------

# -----------------------------------------------------------------------------
# Page Config
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="BTC vs Financials",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ BTCと金融株の対決")

# -----------------------------------------------------------------------------
# Data Fetching
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_data():
    tickers = {
        "BTC": "BTC-USD",
        "XLF": "XLF",
        "TNX": "^TNX",
        "DXY": "DX-Y.NYB"
    }
    
    data = {}
    for key, ticker in tickers.items():
        # Fetch 2 years of data to ensure enough for 200MA
        df = yf.Ticker(ticker).history(period="2y")
        if df.empty:
            st.error(f"Failed to fetch data for {key}")
            return None
        
        # Timezone Alignment Fix: Convert to timezone-naive
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        data[key] = df['Close']
    
    return pd.DataFrame(data)

try:
    df = fetch_data()
except Exception as e:
    st.error(f"Data fetch error: {e}")
    st.stop()

if df is None:
    st.stop()

# -----------------------------------------------------------------------------
# Calculations
# -----------------------------------------------------------------------------
# Forward fill to handle weekends (BTC trades 24/7, Stocks don't)
# This allows comparing Sunday BTC to Friday XLF
df.ffill(inplace=True)

# Drop rows with NaN (early data might be missing)
df.dropna(inplace=True)

if df.empty:
    st.error("No overlapping data found. Please check data source.")
    st.stop()

# BTC/XLF Ratio (Raw)
df['Raw_Ratio'] = df['BTC'] / df['XLF']

# Moving Averages
df['Ratio_MA200'] = df['Raw_Ratio'].rolling(window=200).mean()
df['TNX_MA20'] = df['TNX'].rolling(window=20).mean()
df['DXY_MA20'] = df['DXY'].rolling(window=20).mean()

# Strength Score (Trend Deviation)
# Base = 1.0 (On Trend)
df['Strength_Score'] = df['Raw_Ratio'] / df['Ratio_MA200']

# Get latest values
latest = df.iloc[-1]
latest_score = latest['Strength_Score']
latest_raw_ratio = latest['Raw_Ratio']
latest_ma200 = latest['Ratio_MA200']
latest_tnx = latest['TNX']
latest_tnx_ma20 = latest['TNX_MA20']
latest_dxy = latest['DXY']
latest_dxy_ma20 = latest['DXY_MA20']

# -----------------------------------------------------------------------------
# Status Decision Logic
# -----------------------------------------------------------------------------
# Macro Conditions
# TNX Trend: Down is good (True)
tnx_trend_down = latest_tnx < latest_tnx_ma20
# DXY Trend: Down (Weak) is good (True)
dxy_trend_weak = latest_dxy < latest_dxy_ma20

macro_condition = tnx_trend_down and dxy_trend_weak

# Decision
status_title = ""
status_color = "gray"
status_comment = ""

# Decision Logic based on Strength Score
# Trend Deviation: > 1.05 (Strong), < 0.95 (Weak), 0.95-1.05 (Neutral)

status_title = ""
status_color = "gray"
status_comment = ""
score_pct = (latest_score - 1.0) * 100

if latest_score > 1.05:
    # Pattern A: Go Time (Strong Trend)
    status_title = f"🟢 Go Time (Score: {latest_score:.2f})"
    status_color = "green"
    status_comment = f"トレンドを {score_pct:.1f}% 上回る強さです。BTCが金融株を圧倒しており、攻めの刻です。"
    
    if not macro_condition:
        status_comment += " (ただしマクロ逆風には注意)"

elif 0.95 <= latest_score <= 1.05:
    # Pattern B: Wait (Neutral / Consensus)
    status_title = f"🟡 Wait (Score: {latest_score:.2f})"
    status_color = "orange"
    status_comment = f"トレンド付近（乖離 {score_pct:.1f}%）で膠着しています。次の方向感が出るまでエネルギーを溜めています。"

else: # latest_score < 0.95
    # Pattern C: Caution (Weak Trend)
    status_title = f"🔴 Caution (Score: {latest_score:.2f})"
    status_color = "red"
    status_comment = f"トレンドを {abs(score_pct):.1f}% 下回る弱さです。資金はBTCより『実需・株』を選んでいます。無理に攻める場面ではありません。"

# -----------------------------------------------------------------------------
# UI Display
# -----------------------------------------------------------------------------

st.header(status_title)
st.write(status_comment)

# Macro Indicators Display (Small check)
prev_day = df.iloc[-2]
prev_score = prev_day['Strength_Score']

col1, col2, col3, col4 = st.columns(4)
col1.metric("Strength Score", f"{latest_score:.2f}", delta=f"{latest_score - prev_score:.2f}", help="1.0 = トレンド(200MA)と同じ強さ")
col2.metric("Raw Ratio (BTC/XLF)", f"{latest_raw_ratio:.2f}")
col3.metric("US10Y (TNX)", f"{latest_tnx:.2f}%", f"{'📉低下(Bull)' if tnx_trend_down else '📈上昇(Bear)'}", delta_color="inverse")
col4.metric("DXY Index", f"{latest_dxy:.2f}", f"{'📉弱含み(Bull)' if dxy_trend_weak else '📈強含み(Bear)'}", delta_color="inverse")


# -----------------------------------------------------------------------------
# Chart
# -----------------------------------------------------------------------------
# Chart
# -----------------------------------------------------------------------------
fig = go.Figure()

# Background Regions (Strength Score based)
x_min = df.index[0]
x_max = df.index[-1]
# Y-axis range padding
y_values = df['Strength_Score']
y_min = min(y_values.min(), 0.90) * 0.98
y_max = max(y_values.max(), 1.10) * 1.02

# Green Zone (> 1.05)
fig.add_shape(type="rect",
    x0=x_min, y0=1.05, x1=x_max, y1=y_max,
    line=dict(width=0),
    fillcolor="rgba(0, 255, 0, 0.1)",
    layer="below"
)

# Red Zone (< 0.95)
fig.add_shape(type="rect",
    x0=x_min, y0=y_min, x1=x_max, y1=0.95,
    line=dict(width=0),
    fillcolor="rgba(255, 0, 0, 0.1)",
    layer="below"
)

# Threshold Lines & Center Line
fig.add_hline(y=1.05, line_dash="dot", line_color="green", annotation_text="1.05 (+5% Strength)", annotation_position="top left")
fig.add_hline(y=0.95, line_dash="dot", line_color="red", annotation_text="0.95 (-5% Weakness)", annotation_position="bottom left")
fig.add_hline(y=1.00, line_width=2, line_color="white", annotation_text="1.00 (Trend Zero)", annotation_position="right")

# Strength Score Line
fig.add_trace(go.Scatter(x=df.index, y=df['Strength_Score'], mode='lines', name='Strength Score', line=dict(color='blue', width=2)))

fig.update_layout(
    title="Strength Score Trend (Deviation from 200MA)",
    yaxis_title="Strength Score (1.0 = On Trend)",
    xaxis_title="Date",
    height=600,
    template="plotly_dark", # Switch to dark to verify white line visibility? Or stick to white and use black/grey line. 
    # Let's stick to what works. If template is plotly_white, white line is invisible.
    # Let's use a Dark Grey line for 1.0 if background is white, or just use plotly_dark if user prefers dark mode look.
    # The user didn't specify dark mode, but "White line" implies a dark background.
    # However, existing code used plotly_white.
    # I will change template to 'plotly_dark' to make "White Line" visible and look cool.
    hovermode="x unified"
)
# If using plotly_white, change neutral line to black/grey.
# User Logic said: "基準線: 1.0 の位置に太い白線を引く" -> "Draw a thick white line at 1.0"
# This strongly implies a dark background chart.
# So I will set template="plotly_dark".

st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# Explanation Expander
# -----------------------------------------------------------------------------
with st.expander("💡 なぜこの指標を見るのか？（電車とジェットコースターの理論）"):
    st.markdown("""
    ### モニターの見方：Strength Score (トレンド乖離率)
    
    従来の「単純な割り算」ではなく、**「200日移動平均線からどれだけ離れているか（乖離率）」**を表示しています。
    
    *   **基準値 1.0**: ちょうどトレンドライン（200MA）の上に乗っています。
    *   **Strength Score > 1.05 (緑ゾーン)**: トレンドを5%以上上回る「強い」状態です。Go Time.
    *   **Strength Score < 0.95 (赤ゾーン)**: トレンドを5%以上下回る「弱い」状態です。Caution.
    *   **0.95 〜 1.05 (黄色ゾーン)**: トレンド付近での攻防です。Wait.

    ### なぜこの指標を見るのか？
    
    *   **BTC/XLFレシオ**: ビットコイン（リスク）と金融株（実需・金利）のどちらが選好されているか?
    *   **トレンド乖離**: 単純な数値（0.6など）は時代の変化でズレますが、「トレンドとの距離」は常に一定の物差し（過熱感・売られすぎ）として機能します。
    """)
