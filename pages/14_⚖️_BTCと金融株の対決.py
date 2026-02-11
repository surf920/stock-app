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

# BTC/XLF Ratio
df['Ratio'] = df['BTC'] / df['XLF']

# Moving Averages
df['Ratio_MA200'] = df['Ratio'].rolling(window=200).mean()
df['TNX_MA20'] = df['TNX'].rolling(window=20).mean()
df['DXY_MA20'] = df['DXY'].rolling(window=20).mean()

# Get latest values
latest = df.iloc[-1]
latest_ratio = latest['Ratio']
latest_ratio_ma200 = latest['Ratio_MA200']
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

# Pattern logic prioritization
if latest_ratio > 0.60:
    if latest_ratio > latest_ratio_ma200:
        if macro_condition:
            # Pattern A: Go Time (Green)
            status_title = "🟢 Go Time (確定・フルスロットル)"
            status_color = "green"
            status_comment = "全条件クリア。BTCが選好され、マクロ追い風も吹いています。攻めの刻です。"
        else:
            # Pattern B: Go Time (Yellow)
            status_title = "🟡 Go Time (準備・フライング注意)"
            status_color = "orange" # Using orange for yellow
            status_comment = "BTCは強いですが、逆風（金利高/ドル高）が吹いています。ダマシに注意しつつ打診買いの段階。"
    else:
         # Ratio > 0.60 but < MA200 (Technically Caution based on rule "Ratio < 200MA")
         status_title = "🔴 Caution (株優位・劣勢)"
         status_color = "red"
         status_comment = "資金はBTCより『実需・株』を選んでいます。無理に攻める場面ではありません。"

elif 0.55 <= latest_ratio <= 0.60:
    if latest_ratio > latest_ratio_ma200:
        # Pattern C: Wait
        status_title = "🟡 Wait (様子見・休憩)"
        status_color = "orange"
        status_comment = "ジェットコースターは停車中。方向感が出るまでエネルギーを溜めています。"
    else:
        # Ratio < 200MA override
        status_title = "🔴 Caution (株優位・劣勢)"
        status_color = "red"
        status_comment = "資金はBTCより『実需・株』を選んでいます。無理に攻める場面ではありません。"

else: # Ratio < 0.55
    # Pattern D: Caution
    status_title = "🔴 Caution (株優位・劣勢)"
    status_color = "red"
    status_comment = "資金はBTCより『実需・株』を選んでいます。無理に攻める場面ではありません。"

# Explicit override check for Ratio < 200MA (Priority: D)
if latest_ratio < latest_ratio_ma200:
    status_title = "🔴 Caution (株優位・劣勢)"
    status_color = "red"
    status_comment = "資金はBTCより『実需・株』を選んでいます。無理に攻める場面ではありません。"

# -----------------------------------------------------------------------------
# UI Display
# -----------------------------------------------------------------------------

st.header(status_title)
st.write(status_comment)

# Macro Indicators Display (Small check)
prev_day = df.iloc[-2]
col1, col2, col3, col4 = st.columns(4)
col1.metric("BTC/XLF Ratio", f"{latest_ratio:.4f}", delta=f"{latest_ratio - prev_day['Ratio']:.4f}")
col2.metric("Ratio 200MA", f"{latest_ratio_ma200:.4f}")
col3.metric("US10Y (TNX)", f"{latest_tnx:.2f}%", f"{'📉低下(Bull)' if tnx_trend_down else '📈上昇(Bear)'}", delta_color="inverse")
col4.metric("DXY Index", f"{latest_dxy:.2f}", f"{'📉弱含み(Bull)' if dxy_trend_weak else '📈強含み(Bear)'}", delta_color="inverse")


# -----------------------------------------------------------------------------
# Chart
# -----------------------------------------------------------------------------
fig = go.Figure()

# Background Regions
# We need min/max x and y to draw shapes.
x_min = df.index[0]
x_max = df.index[-1]
y_min = df['Ratio'].min() * 0.95
y_max = df['Ratio'].max() * 1.05

# Green Zone (> 0.60)
fig.add_shape(type="rect",
    x0=x_min, y0=0.60, x1=x_max, y1=y_max,
    line=dict(width=0),
    fillcolor="rgba(0, 255, 0, 0.1)",
    layer="below"
)

# Red Zone (< 0.55)
fig.add_shape(type="rect",
    x0=x_min, y0=y_min, x1=x_max, y1=0.55,
    line=dict(width=0),
    fillcolor="rgba(255, 0, 0, 0.1)",
    layer="below"
)

# Threshold Lines
fig.add_hline(y=0.60, line_dash="dot", line_color="green", annotation_text="0.60 (Bull Zone)", annotation_position="top left")
fig.add_hline(y=0.55, line_dash="dot", line_color="red", annotation_text="0.55 (Bear Zone)", annotation_position="bottom left")

# Ratio Line
fig.add_trace(go.Scatter(x=df.index, y=df['Ratio'], mode='lines', name='BTC/XLF Ratio', line=dict(color='blue', width=2)))

# 200MA Line
fig.add_trace(go.Scatter(x=df.index, y=df['Ratio_MA200'], mode='lines', name='200-day MA', line=dict(color='orange', width=2)))

fig.update_layout(
    title="BTC/XLF Ratio Trend (vs 200MA)",
    yaxis_title="Ratio",
    xaxis_title="Date",
    height=600,
    template="plotly_white",
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# Explanation Expander
# -----------------------------------------------------------------------------
with st.expander("💡 なぜこの指標を見るのか？（電車とジェットコースターの理論）"):
    st.markdown("""
    ### 電車（金融株） vs ジェットコースター（ビットコイン）
    
    市場には2つの乗り物があります。
    
    1.  **金融株 (XLF) = 普通の電車 🚃**
        *   金利が上がると銀行が儲かるため、調子が良くなります。
        *   実体経済に根差した「安定した動き」をします。
        
    2.  **ビットコイン (BTC) = ジェットコースター 🎢**
        *   金利が下がると（お金が溢れると）調子が良くなります。
        *   期待と流動性で動く「激しい動き」をします。
        
    ### このレシオ (BTC/XLF) の意味
    
    *   **レシオ上昇 ⤴️**: 投資家が「安定」を捨てて「リスク（ジェットコースター）」を選んでいます。**攻めの相場**です。
    *   **レシオ下落 ⤵️**: 投資家が「リスク」を嫌がり、「安定（電車）」に戻っています。これを「現金を増やす」動きと捉えるより、**「株（XLF）の方が選ばれている状態」**と定義する方が正確です。
    
    ### 0.60と0.55の壁
    *   **0.60超え**: 本格的なバブル/強気相場の入り口。
    *   **0.55割れ**: 明確な「リスクオフ」。無理して乗る必要はありません。
    """)
