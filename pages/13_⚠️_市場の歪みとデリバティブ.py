
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import ssl

# --- 🚨 Avoid SSL Errors ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ----------------------

# Page Setup
st.set_page_config(
    page_title="市場の歪みとデリバティブ",
    page_icon="⚠️",
    layout="wide"
)

st.title("⚠️ 市場の歪みとデリバティブ分析")
st.markdown("デリバティブ市場における「異常（歪み）」を検知し、市場内部の「不信感」や「構造的な断層」を可視化します。")

# 1. Theoretical Background (Tsukaguchi's Explanation)
with st.expander("📖 理論的背景：デリバティブ市場の異常とは？（解説：塚口直史氏）"):
    st.markdown("""
    **市場には4つの「異常（歪み）」が存在します。これらが重なるとき、危機が発生します。**

    1.  **インターバンクの不信感 (Credit Stress)**
        *   銀行間や社債市場で「信用リスク」が高まると、国債に対して社債が売られます（スプレッド拡大）。
        *   これは「誰も信用できない」という市場の恐怖を示します。

    2.  **将来の織り込み (Yield Curve Distortion)**
        *   通常、長期金利は短期金利より高いはずです。
        *   しかし、将来の不況を織り込むと長短金利が逆転（逆イールド）し、その後の「急激な順イールド化」が危機の合図となります。

    3.  **ポジティブ・フィードバック (Volatility Feedback Loop)**
        *   市場が下がるとボラティリティ（VIX）が上がり、機械的な売り（リスクパリティなど）が誘発され、さらに下がる悪循環。
        *   VIXの急激なスパイクは、この自動売買の暴走を示唆します。

    4.  **政策ミスのリスク (Policy Error)**
        *   インフレが沈静化しているのに、過去のデータに基づいて引き締めを続ける（またはその逆）ことによる「実質金利の歪み」。
    """)

# 2. Data Acquisition
@st.cache_data(ttl=3600)
def get_derivative_data():
    tickers = {
        "HYG": "HYG",       # High Yield Bond ETF
        "IEF": "IEF",       # 7-10 Year Treasury ETF
        "TNX": "^TNX",      # 10 Year Treasury Yield
        "IRX": "^IRX",      # 13 Week Treasury Yield (Short term proxy)
        "VIX": "^VIX",      # Volatility Index
        "TIP": "TIP"        # Treasury Inflation Protected Securities
    }
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    data_frames = {}
    
    try:
        for key, ticker in tickers.items():
            t = yf.Ticker(ticker)
            hist = t.history(start=start_date, end=end_date)
            if not hist.empty:
                data_frames[key] = hist['Close']
            else:
                st.warning(f"Failed to fetch data for {ticker}")
                
        if not data_frames:
            return pd.DataFrame()
            
        df = pd.DataFrame(data_frames)
        df = df.ffill().dropna()
        return df

    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

df = get_derivative_data()

if df.empty:
    st.error("データの取得に失敗しました。時間をおいて再試行してください。")
    st.stop()

# 3. Metrics Calculation
# Credit Stress: HYG (Risky) / IEF (Safe) -> Lower means stress high (Flight to safety)
df['Credit_Stress_Ratio'] = df['HYG'] / df['IEF']

# Yield Curve: 10Y - 13W (Proxy for 10Y-3M)
df['Yield_Curve'] = df['TNX'] - df['IRX']

# Volatility Feedback: Bollinger Bands & Spike
df['VIX_MA5'] = df['VIX'].rolling(window=5).mean()
df['VIX_MA20'] = df['VIX'].rolling(window=20).mean()
df['VIX_STD20'] = df['VIX'].rolling(window=20).std()
df['VIX_Upper'] = df['VIX_MA20'] + (df['VIX_STD20'] * 2)
df['VIX_Lower'] = df['VIX_MA20'] - (df['VIX_STD20'] * 2)

# Latest Values
latest = df.iloc[-1]
prev = df.iloc[-2]

# 4. Visualizations & Metrics Display

st.markdown("---")
st.subheader("📊 市場の健康状態ダッシュボード")

col1, col2, col3, col4 = st.columns(4)

# Metric 1: Credit Stress
with col1:
    stress_val = latest['Credit_Stress_Ratio']
    stress_delta = stress_val - prev['Credit_Stress_Ratio']
    st.metric("信用ストレス (HYG/IEF)", f"{stress_val:.4f}", f"{stress_delta:.4f}", delta_color="normal")
    if stress_delta < 0:
        st.caption("📉 リスク回避の動き (注意)")

# Metric 2: Yield Curve
with col2:
    curve_val = latest['Yield_Curve']
    curve_delta = curve_val - prev['Yield_Curve']
    st.metric("イールドカーブ (10Y-3M)", f"{curve_val:.2f}%", f"{curve_delta:.2f}%")
    if curve_val < 0:
        st.caption("⚠️ 逆イールド発生中")

# Metric 3: VIX
with col3:
    vix_val = latest['VIX']
    vix_delta = vix_val - prev['VIX']
    st.metric("VIX指数", f"{vix_val:.2f}", f"{vix_delta:.2f}", delta_color="inverse")
    if vix_val > 20:
        st.caption("🔥 ボラティリティ高")

# Metric 4: Real Yield Proxy (TIP/IEF ratio as rough proxy or just TIP price)
with col4:
    tip_val = latest['TIP']
    tip_delta = tip_val - prev['TIP']
    st.metric("期待インフレ (TIP価格)", f"${tip_val:.2f}", f"{tip_delta:.2f}")

st.markdown("---")

# --- Charts Section ---

# Chart 1: Credit Stress Visualization
st.subheader("1. 不信感の可視化 (HYG/IEF Ratio)")
st.markdown("数値が下落する＝安全資産（国債）へ資金が逃避し、ジャンク債（HYG）が売られている状態。**市場のクレジットリスク警戒**を示します。")

fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=df.index, y=df['Credit_Stress_Ratio'], mode='lines', name='Credit Stress Ratio', line=dict(color='#ff6347', width=2)))

# Add background color for danger zone (e.g., below recent average or arbitrary threshold)
# Determining a dynamic threshold for visual aid
threshold = df['Credit_Stress_Ratio'].mean() - df['Credit_Stress_Ratio'].std()
fig1.add_hrect(y0=df['Credit_Stress_Ratio'].min() * 0.99, y1=threshold, line_width=0, fillcolor="red", opacity=0.1, annotation_text="Danger Zone", annotation_position="bottom right")

fig1.update_layout(title="HYG/IEF Ratio (Credit Stress)", yaxis_title="Ratio", height=400)
st.plotly_chart(fig1, use_container_width=True)


# Chart 2: Yield Curve Deviation
st.subheader("2. 将来との乖離 (Yield Curve 10Y-3M)")
st.markdown("0を下回ると「逆イールド（景気後退シグナル）」です。**逆イールドからの急激な回復（スティープ化）**こそが、バブル崩壊の引き金になりやすいと言われます。")

fig2 = go.Figure()

# Color logic: Red for negative, Green for positive
colors = ['#ef553b' if val < 0 else '#00cc96' for val in df['Yield_Curve']]

fig2.add_trace(go.Bar(
    x=df.index, 
    y=df['Yield_Curve'],
    marker_color=colors,
    name='Yield Curve'
))
fig2.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)

fig2.update_layout(title="US Yield Curve (10Y - 13W)", yaxis_title="Basis Points (%)", height=400)
st.plotly_chart(fig2, use_container_width=True)


# Chart 3: Volatility Runaway
st.subheader("3. ボラティリティの暴走 (VIX + Bollinger Bands)")
st.markdown("VIXがボリンジャーバンド（2σ）を上抜けると、**「アルゴリズムによる機械的な売り」**が連鎖しやすい状態（パニック）です。")

fig3 = go.Figure()
fig3.add_trace(go.Scatter(x=df.index, y=df['VIX_Upper'], name='Upper Band (2σ)', line=dict(color='gray', width=1, dash='dot')))
fig3.add_trace(go.Scatter(x=df.index, y=df['VIX_Lower'], name='Lower Band (2σ)', line=dict(color='gray', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(200,200,200,0.1)'))
fig3.add_trace(go.Scatter(x=df.index, y=df['VIX'], name='VIX', line=dict(color='#ab63fa', width=2)))

fig3.update_layout(title="VIX Index with Bollinger Bands (20D)", yaxis_title="VIX", height=400)
st.plotly_chart(fig3, use_container_width=True)

# 5. AI Analysis Verdict
st.markdown("---")
st.subheader("🤖 AIリスク診断レポート")

analysis_col1, analysis_col2 = st.columns([2, 1])

# Logic for comments
comments = []
flags = 0

# 1. Interbank Distrust (Credit Stress)
ma_credit_short = df['Credit_Stress_Ratio'].rolling(5).mean().iloc[-1]
ma_credit_long = df['Credit_Stress_Ratio'].rolling(20).mean().iloc[-1]

if latest['Credit_Stress_Ratio'] < ma_credit_short and ma_credit_short < ma_credit_long:
    comments.append("❌ **インターバンクの不信感**: クレジットレシオが短期・中期移動平均を下回っており、リスク回避（Safetyへの逃避）が進行しています。")
    flags += 1
else:
    comments.append("✅ **インターバンクの不信感**: クレジット市場に大きな動揺は見られません。")

# 2. Future Pricing (Yield Curve)
if latest['Yield_Curve'] < -0.5:
    comments.append("❌ **将来の織り込み**: 深い逆イールドが継続しており、市場は強い景気後退を織り込んでいます。")
    flags += 1
elif latest['Yield_Curve'] < 0:
    comments.append("⚠️ **将来の織り込み**: 逆イールド状態ですが、縮小傾向にある場合は順イールド化（Bull Steepening）への転換に警戒が必要です。")
else:
    comments.append("✅ **将来の織り込み**: イールドカーブは正常範囲（順イールド）ですが、急激な変動には注意してください。")

# 3. Positive Feedback (VIX)
if latest['VIX'] > latest['VIX_Upper']:
    comments.append("🔥 **ポジティブ・フィードバック**: VIXがバンドをブレイクしています。機械的な売りによる「暴落の連鎖」が発生しやすい危険な状態です。")
    flags += 2  # High weight
elif latest['VIX'] > 20:
    comments.append("⚠️ **ポジティブ・フィードバック**: VIXが20を超え、市場心理が不安定化しています。")
    flags += 0.5
else:
    comments.append("✅ **ポジティブ・フィードバック**: VIXは落ち着いており、パニック的な売り圧力は観測されません。")
    
# 4. Policy Mistake (Use TIP/IEF relative strength trend or simplistic proxy)
# Using TIP (Real Yield proxy) vs IEF (Nominal) ratio trend
tip_ief_ratio = latest['TIP'] / latest['IEF'] # If ratio drops, Real Yields rising faster than Nominal (Tightening stress)
comments.append("ℹ️ **政策リスク**: インフレ連動債と国債の比率を注視してください。（参考指標）")


# Determine Status
status = ""
status_color = ""

if flags >= 3:
    status = "崩壊進行中 (Meltdown)"
    status_color = "red"
elif flags >= 2:
    status = "発火寸前 (Trigger Ready)"
    status_color = "orange"
elif flags >= 1:
    status = "歪みの蓄積 (Accumulating Distortion)"
    status_color = "gold"
else:
    status = "正常 (Normal)"
    status_color = "green"

with analysis_col1:
    for c in comments:
        st.markdown(c)

with analysis_col2:
    st.markdown("### 総合判定")
    st.markdown(f"<h1 style='text-align: center; color: {status_color};'>{status}</h1>", unsafe_allow_html=True)
    st.info("※ この診断は、過去の市場構造データに基づく簡易的なものです。投資判断はご自身の責任で行ってください。")
