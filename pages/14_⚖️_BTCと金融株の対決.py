import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl
import json
import requests
from api_helper import call_anthropic_api

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

# --- AI要約機能 ---
def call_btc_finance_ai(latest, latest_score, latest_raw_ratio, latest_ma200, latest_tnx, latest_tnx_ma20, latest_dxy, latest_dxy_ma20, macro_condition, status_title, df):
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    score_pct = (latest_score - 1.0) * 100
    tnx_trend = "低下中(BTC有利)" if latest_tnx < latest_tnx_ma20 else "上昇中(金融株有利)"
    dxy_trend = "弱含み(BTC有利)" if latest_dxy < latest_dxy_ma20 else "強含み(金融株有利)"

    data_text = f"""## BTC vs 金融株データ

### Strength Score（トレンド乖離率）
- 現在スコア: {latest_score:.2f} (トレンドから{score_pct:+.1f}%乖離)
- 判定: {status_title}
- BTC/XLFレシオ: {latest_raw_ratio:.2f}
- 200日MA: {latest_ma200:.2f}

### マクロ環境
- 米10年債: {latest_tnx:.2f}% (20日MA: {latest_tnx_ma20:.2f}%) → {tnx_trend}
- DXY: {latest_dxy:.2f} (20日MA: {latest_dxy_ma20:.2f}) → {dxy_trend}
- マクロ環境: {"BTC有利（金利低下+ドル安）" if macro_condition else "金融株有利（金利上昇orドル高）"}

### 過去レンジ (利用可能期間)
- Strength Score: {df['Strength_Score'].min():.2f} - {df['Strength_Score'].max():.2f}
- BTC/XLFレシオ: {df['Raw_Ratio'].min():.2f} - {df['Raw_Ratio'].max():.2f}

### ゾーン定義
- 緑ゾーン (>1.05): BTC圧倒的優位、Go Time
- 黄ゾーン (0.95-1.05): 膠着、Wait
- 赤ゾーン (<0.95): 金融株優位、Caution"""

    system_prompt = """あなたはARKインベストとギャラクシーデジタルで15年の経験を持つデジタル資産vs伝統金融の専門ストラテジストです。
BTCと金融セクター(XLF)の相対強弱から、マクロ環境と資金フローの方向を読み解きます。

【重要】現在の日付は2026年2月です。全ての予測は2026年2月時点からの未来について述べてください。

提供されたデータを分析し、以下のJSON形式で回答してください。

【分析ルール】
1. 必ず具体的な数値を引用（Strength Score、レシオ、金利、DXY）
2. BTC vs 金融株の相対強弱がマクロ環境の「リトマス試験紙」
3. 金利とドルの方向がBTC/XLFレシオの最大ドライバー
4. データにない事実を捏造しない

{
    "cycle_position": {
        "total_stages": 4,
        "current_stage": 2,
        "stage_name": "ステージ名",
        "stages_map": [
            {"stage": 1, "name": "BTC劣勢・金融株優位", "description": "金利上昇、ドル高、資金は伝統金融へ"},
            {"stage": 2, "name": "均衡・方向感模索", "description": "トレンド付近で膠着、次の触媒待ち"},
            {"stage": 3, "name": "BTC優勢・リスクオン", "description": "金利低下、ドル安、リスク資産選好"},
            {"stage": 4, "name": "BTC過熱・反転警戒", "description": "乖離拡大、利確圧力、マクロ変化注意"}
        ],
        "evidence": "判断根拠を2-3文で。具体数値必須"
    },
    "current_diagnosis": {
        "headline": "1行の見出し",
        "summary": "BTC vs 金融株の現在の力関係を4-5文で。Strength Score、金利、DXYを引用",
        "macro_alignment": "マクロ環境（金利・ドル）がどちらに有利か。2文で",
        "flow_direction": "資金フローの方向（デジタル資産→伝統金融、またはその逆）。2文で"
    },
    "asset_comparison": {
        "btc": {
            "outlook": "BTCの見通しを2文で",
            "key_driver": "主なドライバー",
            "signal": "強気/中立/弱気"
        },
        "xlf": {
            "outlook": "金融株の見通しを2文で",
            "key_driver": "主なドライバー",
            "signal": "強気/中立/弱気"
        }
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "メインシナリオ",
            "next_3months": "今後3ヶ月の展開",
            "score_direction": "Strength Scoreの方向（上昇/横ばい/低下）",
            "triggers": [],
            "investment_action": "BTC vs 金融株の配分"
        },
        "btc_bull": {
            "probability": 25,
            "title": "BTC優勢シナリオ",
            "narrative": "3-4文",
            "triggers": [],
            "investment_action": ""
        },
        "xlf_bull": {
            "probability": 25,
            "title": "金融株優勢シナリオ",
            "narrative": "3-4文",
            "triggers": [],
            "investment_action": ""
        }
    },
    "tactical_playbook": {
        "current_allocation": "現在のスコアに基づく推奨配分（例: BTC60%/金融株40%）",
        "entry_signal": "次のエントリーシグナル",
        "stop_signal": "撤退すべきシグナル"
    },
    "risk_monitor": {
        "watch_items": ["監視項目1", "2", "3"],
        "next_inflection": "次の転換点"
    }
}"""

    headers = {"x-api-key": api_key, "content-type": "application/json", "anthropic-version": "2023-06-01"}
    payload = {"model": "claude-sonnet-4-20250514", "max_tokens": 4096, "system": system_prompt, "messages": [{"role": "user", "content": data_text}]}
    try:
        result_data, api_error = call_anthropic_api(headers, payload)
        if api_error:
            return None
        return result_data
    except Exception as e:
        st.error(f"AI分析エラー: {e}")
        return None


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


# --- AI BTC vs 金融株分析セクション ---
st.markdown("---")
st.subheader("🤖 AI BTC vs 金融株 分析")
st.caption("デジタル資産 vs 伝統金融 専門ストラテジスト視点の分析")

if st.button("🧠 AIでBTC vs 金融株を分析", use_container_width=True):
    with st.spinner("🔄 Claude AIが分析中..."):
        ai_result = call_btc_finance_ai(latest, latest_score, latest_raw_ratio, latest_ma200, latest_tnx, latest_tnx_ma20, latest_dxy, latest_dxy_ma20, macro_condition, status_title, df)
    
    if ai_result:
        cp = ai_result.get("cycle_position", {})
        current = cp.get("current_stage", 1)
        total = cp.get("total_stages", 4)
        stage_name = cp.get("stage_name", "")
        stages = cp.get("stages_map", [])
        
        st.markdown("### 📍 BTC vs 金融株サイクル 現在地")
        cols_cycle = st.columns(total)
        for i, stage in enumerate(stages):
            with cols_cycle[i]:
                is_current = (i + 1 == current)
                if is_current:
                    st.markdown(f"""<div style="background: linear-gradient(135deg, #1a3a5c, #2471a3); padding: 10px; border-radius: 8px; text-align: center; border: 2px solid #5dade2;"><div style="font-size: 1.4em; font-weight: bold;">⚖️</div><div style="font-size: 0.75em; font-weight: bold; color: #fff;">Stage {i+1}</div><div style="font-size: 0.65em; color: #ddd;">{stage.get('name', '')}</div></div>""", unsafe_allow_html=True)
                else:
                    opacity = "0.4" if abs(i + 1 - current) > 1 else "0.7"
                    st.markdown(f"""<div style="background: #262730; padding: 10px; border-radius: 8px; text-align: center; opacity: {opacity}; border: 1px solid #41444C;"><div style="font-size: 1.2em;">{"✅" if i + 1 < current else "⬜"}</div><div style="font-size: 0.7em; color: #888;">Stage {i+1}</div><div style="font-size: 0.6em; color: #888;">{stage.get('name', '')}</div></div>""", unsafe_allow_html=True)
        st.progress(current / total, text=f"サイクル: Stage {current}/{total} - {stage_name}")
        evidence = cp.get("evidence", "")
        if evidence:
            st.info(f"📋 **判断根拠:** {evidence}")
        st.markdown("---")
        
        diag = ai_result.get("current_diagnosis", {})
        st.markdown(f"### 🔍 現状診断: {diag.get('headline', '')}")
        st.markdown(diag.get("summary", ""))
        col_ma, col_fl = st.columns(2)
        with col_ma:
            st.markdown("**🌍 マクロ環境:**")
            st.markdown(diag.get("macro_alignment", ""))
        with col_fl:
            st.markdown("**💰 資金フロー:**")
            st.markdown(diag.get("flow_direction", ""))
        st.markdown("---")
        
        comp = ai_result.get("asset_comparison", {})
        if comp:
            st.markdown("### ⚖️ 資産比較")
            col_btc, col_xlf = st.columns(2)
            btc_item = comp.get("btc", {})
            xlf_item = comp.get("xlf", {})
            btc_signal = btc_item.get("signal", "中立")
            xlf_signal = xlf_item.get("signal", "中立")
            signal_emoji = {"強気": "🟢", "中立": "🟡", "弱気": "🔴"}.get
            with col_btc:
                be = {"強気": "🟢", "中立": "🟡", "弱気": "🔴"}.get(btc_signal, "⚪")
                st.markdown(f"""<div style="background: #1a1a2e; padding: 15px; border-radius: 8px; border-top: 3px solid #F7931A;"><h4 style="color: #F7931A; margin: 0 0 8px 0;">₿ Bitcoin</h4><p style="color: #ddd; font-size: 0.85em;">{btc_item.get('outlook', '')}</p><p style="color: #888; font-size: 0.8em;">📌 {btc_item.get('key_driver', '')}</p><p style="margin: 0;">{be} <b>{btc_signal}</b></p></div>""", unsafe_allow_html=True)
            with col_xlf:
                xe = {"強気": "🟢", "中立": "🟡", "弱気": "🔴"}.get(xlf_signal, "⚪")
                st.markdown(f"""<div style="background: #1a1a2e; padding: 15px; border-radius: 8px; border-top: 3px solid #3498db;"><h4 style="color: #3498db; margin: 0 0 8px 0;">🏦 XLF (金融株)</h4><p style="color: #ddd; font-size: 0.85em;">{xlf_item.get('outlook', '')}</p><p style="color: #888; font-size: 0.8em;">📌 {xlf_item.get('key_driver', '')}</p><p style="margin: 0;">{xe} <b>{xlf_signal}</b></p></div>""", unsafe_allow_html=True)
        st.markdown("---")
        
        st.markdown("### 🔮 フォワードシナリオ分析")
        scenarios = ai_result.get("forward_scenarios", {})
        base = scenarios.get("base_case", {})
        st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #5dade2; margin-bottom: 15px;"><h4 style="color: #5dade2; margin-top: 0;">⚖️ メイン ({base.get('probability', 50)}%): {base.get('title', '')}</h4><p style="color: #F7C948;">📊 Score方向: <b>{base.get('score_direction', '')}</b></p><p style="color: #ddd;">{base.get('next_3months', '')}</p><p style="color: #5dade2; margin-bottom: 0;">💼 {base.get('investment_action', '')}</p></div>""", unsafe_allow_html=True)
        
        col_bull, col_bear = st.columns(2)
        btc_bull = scenarios.get("btc_bull", {})
        with col_bull:
            st.markdown(f"""<div style="background: #1a1a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #F7931A;"><h4 style="color: #F7931A; margin-top: 0;">₿ BTC優勢 ({btc_bull.get('probability', 25)}%): {btc_bull.get('title', '')}</h4><p style="color: #ddd; font-size: 0.9em;">{btc_bull.get('narrative', '')}</p><p style="color: #F7931A; font-size: 0.85em;">💼 {btc_bull.get('investment_action', '')}</p></div>""", unsafe_allow_html=True)
        xlf_bull = scenarios.get("xlf_bull", {})
        with col_bear:
            st.markdown(f"""<div style="background: #0a1a2a; padding: 15px; border-radius: 10px; border-left: 4px solid #3498db;"><h4 style="color: #3498db; margin-top: 0;">🏦 金融株優勢 ({xlf_bull.get('probability', 25)}%): {xlf_bull.get('title', '')}</h4><p style="color: #ddd; font-size: 0.9em;">{xlf_bull.get('narrative', '')}</p><p style="color: #3498db; font-size: 0.85em;">💼 {xlf_bull.get('investment_action', '')}</p></div>""", unsafe_allow_html=True)
        st.markdown("---")
        
        playbook = ai_result.get("tactical_playbook", {})
        if playbook:
            st.markdown("### 🎯 タクティカル・プレイブック")
            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #2ecc71;"><p style="color: #2ecc71; font-weight: bold; margin: 0 0 5px 0;">📊 推奨配分</p><p style="color: #ddd; font-size: 0.85em; margin: 0;">{playbook.get('current_allocation', '')}</p></div>""", unsafe_allow_html=True)
            with col_t2:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #3498db;"><p style="color: #3498db; font-weight: bold; margin: 0 0 5px 0;">🚀 エントリーシグナル</p><p style="color: #ddd; font-size: 0.85em; margin: 0;">{playbook.get('entry_signal', '')}</p></div>""", unsafe_allow_html=True)
            with col_t3:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #e74c3c;"><p style="color: #e74c3c; font-weight: bold; margin: 0 0 5px 0;">🛑 撤退シグナル</p><p style="color: #ddd; font-size: 0.85em; margin: 0;">{playbook.get('stop_signal', '')}</p></div>""", unsafe_allow_html=True)
        st.markdown("---")
        
        rm = ai_result.get("risk_monitor", {})
        st.markdown("### ⚠️ リスクモニター")
        watch = rm.get("watch_items", [])
        if watch:
            for w in watch:
                st.markdown(f"- 👁️ {w}")
        inflection = rm.get("next_inflection", "")
        if inflection:
            st.error(f"🔄 **次の転換点:** {inflection}")
