
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import ssl
import json
import requests as req_lib

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


# --- AI要約機能 ---
def call_distortion_ai(latest, prev, df, flags, status, comments):
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    data_text = f"""## 市場の歪みデータ

### 最新値
- 信用ストレス (HYG/IEF): {latest['Credit_Stress_Ratio']:.4f} (前日比: {latest['Credit_Stress_Ratio'] - prev['Credit_Stress_Ratio']:+.4f})
- イールドカーブ (10Y-3M): {latest['Yield_Curve']:.2f}% (前日比: {latest['Yield_Curve'] - prev['Yield_Curve']:+.2f}%)
- VIX: {latest['VIX']:.2f} (前日比: {latest['VIX'] - prev['VIX']:+.2f})
- VIXボリンジャー上限: {latest['VIX_Upper']:.2f}
- TIP価格: ${latest['TIP']:.2f}
- 米10年債: {latest['TNX']:.2f}%

### 過去レンジ (1年)
- 信用ストレス: {df['Credit_Stress_Ratio'].min():.4f} - {df['Credit_Stress_Ratio'].max():.4f}
- イールドカーブ: {df['Yield_Curve'].min():.2f}% - {df['Yield_Curve'].max():.2f}%
- VIX: {df['VIX'].min():.2f} - {df['VIX'].max():.2f}

### 現在の診断
- フラグ数: {flags}
- 総合判定: {status}

### 各指標の診断
"""
    for c in comments:
        data_text += f"- {c}\n"

    system_prompt = """あなたはブリッジウォーターとAQRで20年の経験を持つシステマティック・リスク専門のCROです。
塚口直史氏の「市場の4つの歪み」理論に基づき、デリバティブ市場の構造的リスクを分析します。

【重要】現在の日付は2026年2月です。全ての予測は2026年2月時点からの未来について述べてください。

提供されたデータを分析し、以下のJSON形式で回答してください。

【分析ルール】
1. 必ず具体的な数値を引用
2. 4つの歪み（不信感・イールドカーブ・ボラフィードバック・政策ミス）を個別に評価
3. 歪みの「相互作用」が最も危険（複数が同時に悪化するとき）
4. データにない事実を捏造しない

{
    "cycle_position": {
        "total_stages": 5,
        "current_stage": 2,
        "stage_name": "ステージ名",
        "stages_map": [
            {"stage": 1, "name": "正常・低歪み", "description": "全指標正常、信用安定、VIX低位"},
            {"stage": 2, "name": "歪み蓄積", "description": "一部指標に異常、表面上は平穏"},
            {"stage": 3, "name": "発火寸前", "description": "複数指標悪化、トリガー待ち"},
            {"stage": 4, "name": "危機進行", "description": "連鎖反応開始、流動性枯渇"},
            {"stage": 5, "name": "暴落・修復", "description": "パニック売り後、政策介入で安定化"}
        ],
        "evidence": "判断根拠を2-3文で。具体数値必須"
    },
    "current_diagnosis": {
        "headline": "1行の見出し",
        "summary": "現在の市場の歪み状態を4-5文で。各指標の数値を引用",
        "most_dangerous_distortion": "4つの歪みの中で最も危険なものとその理由。2文で",
        "interaction_risk": "歪みの相互作用リスク。複数の歪みが同時に悪化する可能性。2文で"
    },
    "distortion_analysis": {
        "credit_stress": {
            "severity": "低/中/高/危険",
            "assessment": "信用ストレスの詳細評価を2文で",
            "trigger_level": "危険水準の目安"
        },
        "yield_curve": {
            "severity": "低/中/高/危険",
            "assessment": "イールドカーブの詳細評価を2文で",
            "trigger_level": "危険水準の目安"
        },
        "volatility_feedback": {
            "severity": "低/中/高/危険",
            "assessment": "ボラティリティフィードバックの詳細評価を2文で",
            "trigger_level": "VIXの危険水準"
        },
        "policy_error": {
            "severity": "低/中/高/危険",
            "assessment": "政策ミスリスクの詳細評価を2文で",
            "trigger_level": "何が起きたら政策ミスが顕在化するか"
        }
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "メインシナリオ",
            "next_3months": "今後3ヶ月",
            "next_6months": "3-6ヶ月後",
            "triggers": [],
            "investment_action": "具体的アクション"
        },
        "bull_case": {
            "probability": 25,
            "title": "歪み解消シナリオ",
            "narrative": "3-4文",
            "triggers": [],
            "investment_action": ""
        },
        "bear_case": {
            "probability": 25,
            "title": "危機発生シナリオ",
            "narrative": "3-4文",
            "triggers": [],
            "investment_action": ""
        }
    },
    "protection_playbook": {
        "current_hedge_priority": "今最も必要なヘッジは何か",
        "position_sizing": "ポジションサイズの推奨（フル/80%/50%/キャッシュ重視）と根拠",
        "early_warning": "次の危機の早期警戒シグナルとして何を監視すべきか"
    },
    "risk_monitor": {
        "watch_items": ["監視項目1", "2", "3"],
        "next_inflection": "次の転換点"
    }
}"""

    headers = {"x-api-key": api_key, "content-type": "application/json", "anthropic-version": "2023-06-01"}
    payload = {"model": "claude-3-haiku-20240307", "max_tokens": 4096, "system": system_prompt, "messages": [{"role": "user", "content": data_text}]}
    try:
        response = req_lib.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=90)
        response.raise_for_status()
        result = response.json()
        text = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                text += block["text"]
        text = text.strip()
        if text.startswith("```json"): text = text[7:]
        if text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        return json.loads(text.strip())
    except Exception as e:
        st.error(f"AI分析エラー: {e}")
        return None


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


# --- AI歪み分析セクション ---
st.markdown("---")
st.subheader("🤖 AI市場歪み詳細分析")
st.caption("システマティック・リスク専門CRO視点の分析")

if st.button("🧠 AIで市場の歪みを分析", use_container_width=True):
    with st.spinner("🔄 Claude AIが市場の歪みを分析中..."):
        ai_result = call_distortion_ai(latest, prev, df, flags, status, comments)
    
    if ai_result:
        cp = ai_result.get("cycle_position", {})
        current = cp.get("current_stage", 1)
        total = cp.get("total_stages", 5)
        stage_name = cp.get("stage_name", "")
        stages = cp.get("stages_map", [])
        
        st.markdown("### 📍 市場歪みサイクル 現在地")
        cols_cycle = st.columns(total)
        for i, stage in enumerate(stages):
            with cols_cycle[i]:
                is_current = (i + 1 == current)
                if is_current:
                    st.markdown(f"""<div style="background: linear-gradient(135deg, #5c1a0a, #8b2a1a); padding: 10px; border-radius: 8px; text-align: center; border: 2px solid #e74c3c;"><div style="font-size: 1.4em; font-weight: bold;">⚠️</div><div style="font-size: 0.75em; font-weight: bold; color: #fff;">Stage {i+1}</div><div style="font-size: 0.65em; color: #ddd;">{stage.get('name', '')}</div></div>""", unsafe_allow_html=True)
                else:
                    opacity = "0.4" if abs(i + 1 - current) > 1 else "0.7"
                    st.markdown(f"""<div style="background: #262730; padding: 10px; border-radius: 8px; text-align: center; opacity: {opacity}; border: 1px solid #41444C;"><div style="font-size: 1.2em;">{"✅" if i + 1 < current else "⬜"}</div><div style="font-size: 0.7em; color: #888;">Stage {i+1}</div><div style="font-size: 0.6em; color: #888;">{stage.get('name', '')}</div></div>""", unsafe_allow_html=True)
        st.progress(current / total, text=f"歪みサイクル: Stage {current}/{total} - {stage_name}")
        evidence = cp.get("evidence", "")
        if evidence:
            st.info(f"📋 **判断根拠:** {evidence}")
        st.markdown("---")
        
        diag = ai_result.get("current_diagnosis", {})
        st.markdown(f"### 🔍 現状診断: {diag.get('headline', '')}")
        st.markdown(diag.get("summary", ""))
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.markdown("**🔥 最も危険な歪み:**")
            st.markdown(diag.get("most_dangerous_distortion", ""))
        with col_d2:
            st.markdown("**🔗 相互作用リスク:**")
            st.markdown(diag.get("interaction_risk", ""))
        st.markdown("---")
        
        # 4つの歪み詳細
        dist = ai_result.get("distortion_analysis", {})
        if dist:
            st.markdown("### 🔬 4つの歪み 詳細分析")
            cols_d = st.columns(4)
            d_items = [
                ("🏦 信用ストレス", "credit_stress", "#e74c3c"),
                ("📈 イールドカーブ", "yield_curve", "#f39c12"),
                ("📉 ボラフィードバック", "volatility_feedback", "#9b59b6"),
                ("🏛️ 政策ミス", "policy_error", "#3498db")
            ]
            for didx, (dlabel, dkey, dcolor) in enumerate(d_items):
                with cols_d[didx]:
                    ditem = dist.get(dkey, {})
                    dsev = ditem.get("severity", "低")
                    demoji = {"低": "🟢", "中": "🟡", "高": "🟠", "危険": "🔴"}.get(dsev, "⚪")
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-top: 3px solid {dcolor};"><h4 style="color: {dcolor}; margin: 0 0 5px 0;">{dlabel}</h4><p style="margin: 0 0 5px 0;">{demoji} <b>{dsev}</b></p><p style="color: #ddd; font-size: 0.8em; margin: 0 0 5px 0;">{ditem.get('assessment', '')}</p><p style="color: #888; font-size: 0.75em; margin: 0;">⚡ 危険水準: {ditem.get('trigger_level', '')}</p></div>""", unsafe_allow_html=True)
        st.markdown("---")
        
        st.markdown("### 🔮 フォワードシナリオ分析")
        scenarios = ai_result.get("forward_scenarios", {})
        base = scenarios.get("base_case", {})
        st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #e74c3c; margin-bottom: 15px;"><h4 style="color: #e74c3c; margin-top: 0;">⚠️ メイン ({base.get('probability', 50)}%): {base.get('title', '')}</h4><table style="width: 100%;"><tr><td style="padding: 8px; color: #888;">3ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_3months', '')}</td></tr><tr><td style="padding: 8px; color: #888;">6ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_6months', '')}</td></tr></table><p style="color: #e74c3c; margin-bottom: 0;">💼 {base.get('investment_action', '')}</p></div>""", unsafe_allow_html=True)
        
        col_bull, col_bear = st.columns(2)
        bull = scenarios.get("bull_case", {})
        with col_bull:
            st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B;"><h4 style="color: #09AB3B; margin-top: 0;">🟢 歪み解消 ({bull.get('probability', 25)}%): {bull.get('title', '')}</h4><p style="color: #ddd; font-size: 0.9em;">{bull.get('narrative', '')}</p><p style="color: #09AB3B; font-size: 0.85em;">💼 {bull.get('investment_action', '')}</p></div>""", unsafe_allow_html=True)
        bear = scenarios.get("bear_case", {})
        with col_bear:
            st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B;"><h4 style="color: #FF4B4B; margin-top: 0;">🔴 危機発生 ({bear.get('probability', 25)}%): {bear.get('title', '')}</h4><p style="color: #ddd; font-size: 0.9em;">{bear.get('narrative', '')}</p><p style="color: #FF4B4B; font-size: 0.85em;">💼 {bear.get('investment_action', '')}</p></div>""", unsafe_allow_html=True)
        st.markdown("---")
        
        playbook = ai_result.get("protection_playbook", {})
        if playbook:
            st.markdown("### 🛡️ プロテクション・プレイブック")
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #e74c3c;"><p style="color: #e74c3c; font-weight: bold; margin: 0 0 5px 0;">🔒 最優先ヘッジ</p><p style="color: #ddd; font-size: 0.85em; margin: 0;">{playbook.get('current_hedge_priority', '')}</p></div>""", unsafe_allow_html=True)
            with col_p2:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #f39c12;"><p style="color: #f39c12; font-weight: bold; margin: 0 0 5px 0;">📊 ポジションサイズ</p><p style="color: #ddd; font-size: 0.85em; margin: 0;">{playbook.get('position_sizing', '')}</p></div>""", unsafe_allow_html=True)
            with col_p3:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #3498db;"><p style="color: #3498db; font-weight: bold; margin: 0 0 5px 0;">📡 早期警戒</p><p style="color: #ddd; font-size: 0.85em; margin: 0;">{playbook.get('early_warning', '')}</p></div>""", unsafe_allow_html=True)
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
