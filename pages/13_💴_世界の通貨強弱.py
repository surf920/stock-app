import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import ssl
import json
import requests

# --- 🚨 SSL Error Handling ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ----------------------


# --- AI要約機能 ---
def call_currency_ai(df_current):
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    data_text = "## 主要通貨の対円パフォーマンス\n\n"
    df_sorted = df_current.sort_values(by="Daily Change (%)", ascending=False)
    for _, row in df_sorted.iterrows():
        data_text += f"- {row['Currency']}: {row['Price']:.2f}円, 日次: {row['Daily Change (%)']:+.2f}%, 週次: {row['Weekly Change (%)']:+.2f}%\n"

    strongest = df_sorted.iloc[0]
    weakest = df_sorted.iloc[-1]
    data_text += f"\n最強通貨: {strongest['Currency']} ({strongest['Daily Change (%)']:+.2f}%)\n"
    data_text += f"最弱通貨: {weakest['Currency']} ({weakest['Daily Change (%)']:+.2f}%)\n"

    # 通貨分類
    data_text += """\n## 通貨分類
- リスクオン通貨: AUD, NZD, CAD（資源国・高金利）
- リスクオフ通貨: CHF, JPY（安全資産）
- 基軸通貨: USD（米ドル）
- 欧州通貨: EUR, GBP
- 新興国通貨: THB（タイバーツ）\n"""

    system_prompt = """あなたはゴールドマン・サックスやJPモルガンで20年の経験を持つG10通貨専門のチーフFXストラテジストです。

【重要】現在の日付は2026年2月です。全ての予測は2026年2月時点からの未来について述べてください。

提供されたデータを分析し、以下のJSON形式で回答してください。

【分析ルール】
1. 必ず具体的な数値を引用（各通貨のレート、変動率）
2. リスクオン/オフ通貨の強弱パターンから市場心理を読む
3. 円の全体的な強弱を判断（円高/円安トレンド）
4. 地政学・金融政策と通貨の連動を分析
5. データにない事実を捏造しない

{
    "market_regime": {
        "fx_sentiment": "リスクオン/リスクオフ/ドル独歩高/円独歩高/混在",
        "jpy_status": "円高/円安/中立",
        "headline": "通貨市場の状況を1行で"
    },
    "current_diagnosis": {
        "summary": "現在の通貨市場を4-5文で詳細に説明。各通貨のレート・変動率を引用",
        "risk_appetite": "リスクオン/オフ通貨の強弱から読むリスク選好度。2文で",
        "jpy_driver": "円の動きを決めている主要因。2文で"
    },
    "currency_groups": {
        "strongest_group": {
            "name": "最強グループ名（例: 資源国通貨）",
            "currencies": ["通貨1", "通貨2"],
            "reason": "なぜ強いか。2文で"
        },
        "weakest_group": {
            "name": "最弱グループ名",
            "currencies": ["通貨1", "通貨2"],
            "reason": "なぜ弱いか。2文で"
        }
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "メインシナリオ",
            "narrative": "今後1-3ヶ月の通貨市場の展開。3-4文",
            "jpy_outlook": "円の方向性",
            "investment_action": "具体的なFXポジション"
        },
        "bull_jpy": {
            "probability": 25,
            "title": "円高シナリオ",
            "narrative": "3-4文",
            "triggers": ["条件1", "条件2"],
            "investment_action": ""
        },
        "bear_jpy": {
            "probability": 25,
            "title": "円安シナリオ",
            "narrative": "3-4文",
            "triggers": ["条件1", "条件2"],
            "investment_action": ""
        }
    },
    "trade_ideas": [
        {"pair": "通貨ペア", "direction": "買い/売り", "rationale": "根拠1文"}
    ],
    "risk_monitor": {
        "watch_items": ["監視項目1", "2", "3"],
        "next_inflection": "次の転換点"
    }
}"""

    headers = {"x-api-key": api_key, "content-type": "application/json", "anthropic-version": "2023-06-01"}
    payload = {"model": "claude-sonnet-4-20250514", "max_tokens": 4096, "system": system_prompt, "messages": [{"role": "user", "content": data_text}]}
    try:
        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=90)
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


st.set_page_config(page_title="世界の通貨強弱", page_icon="💴", layout="wide")

st.title("💴 世界の通貨強弱ランキング (対円)")
st.caption("主要通貨が「円」に対して買われているか（強い）、売られているか（弱い）をランキング表示します。")

# --- 1. Data Fetching ---

@st.cache_data(ttl=3600)
def fetch_forex_data():
    """Fetch 8 major currency pairs against JPY."""
    # Yahoo Finance Tickers for JPY pairs
    tickers = {
        "USD (米ドル)": "USDJPY=X",
        "EUR (ユーロ)": "EURJPY=X",
        "GBP (ポンド)": "GBPJPY=X",
        "AUD (豪ドル)": "AUDJPY=X",
        "CAD (カナダドル)": "CADJPY=X",
        "CHF (スイスフラン)": "CHFJPY=X",
        "NZD (NZドル)": "NZDJPY=X",
        "THB (タイバーツ)": "THBJPY=X"
    }
    
    data = []
    
    for label, symbol in tickers.items():
        try:
            t = yf.Ticker(symbol)
            # Fetch 5 days to calculate daily and weekly change roughly
            hist = t.history(period="5d")
            
            if len(hist) >= 2:
                curr = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2]
                
                # Daily Change
                change_pct = (curr - prev) / prev * 100
                
                # Weekly Change (approx, 5 days ago if avail)
                if len(hist) >= 5:
                    week_prev = hist["Close"].iloc[0]
                    week_change_pct = (curr - week_prev) / week_prev * 100
                else:
                    week_change_pct = 0.0
                
                data.append({
                    "Currency": label,
                    "Price": curr,
                    "Daily Change (%)": change_pct,
                    "Weekly Change (%)": week_change_pct
                })
        except Exception as e:
            # Error handling: continue even if one fails
            pass
            
    return pd.DataFrame(data)

# --- 2. Main Logic ---

df = fetch_forex_data()

if df.empty:
    st.error("データ取得に失敗しました。時間をおいて再読み込みしてください。")
else:
    # Sort by Daily Change
    df_sorted = df.sort_values(by="Daily Change (%)", ascending=True) # Ascending for bar chart (bottom to top)
    
    # Identify Strongest/Weakest
    strongest = df_sorted.iloc[-1]
    weakest = df_sorted.iloc[0]
    
    # --- Top Metrics ---
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.metric(
            label="🏆 本日の最強通貨 (vs JPY)",
            value=f"{strongest['Currency']}",
            delta=f"{strongest['Daily Change (%)']:+.2f}%"
        )
    with c2:
        st.metric(
            label="📉 本日の最弱通貨 (vs JPY)",
            value=f"{weakest['Currency']}",
            delta=f"{weakest['Daily Change (%)']:+.2f}%",
            delta_color="inverse"
        )
    st.divider()

    # --- Chart Area ---
    st.subheader("📊 通貨騰落率ランキング (前日比)")
    
    # Set colors: Green for positive, Red for negative
    df_sorted["Color"] = df_sorted["Daily Change (%)"].apply(lambda x: "Up" if x >= 0 else "Down")
    
    fig = px.bar(
        df_sorted,
        x="Daily Change (%)",
        y="Currency",
        orientation="h",
        text_auto=".2f",
        color="Daily Change (%)",
        color_continuous_scale=["red", "gray", "green"],
        range_color=[-1.5, 1.5] # Fix range to make colors comparable roughly
    )
    
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # --- Detailed Table ---
    with st.expander("📋 詳細データ一覧を見る", expanded=False):
        st.dataframe(
            df.sort_values(by="Daily Change (%)", ascending=False).set_index("Currency").style.format({
                "Price": "{:.2f}",
                "Daily Change (%)": "{:+.2f}%",
                "Weekly Change (%)": "{:+.2f}%"
            })
        )

    # --- AI Analysis Comment ---
    st.subheader("🦁 市場環境分析")
    
    strong_currency = strongest['Currency']
    
    comment = ""
    
    # Logic based analysis
    if "USD" in strong_currency:
        comment = """
        **【ドル高・円安トレンド】**
        米ドルが最も強く推移しています。米国の金利先高観や、根強いインフレ懸念が背景にある可能性があります。
        市場全体として「ドル1強」になりやすい地合いです。
        """
    elif "AUD" in strong_currency or "NZD" in strong_currency or "CAD" in strong_currency:
        comment = """
        **【資源国通貨買い = リスクオン】**
        豪ドルやカナダドルなどの資源国通貨が選好されています。
        原油や金属価格の上昇、あるいは中国経済への期待感が支援材料になっている可能性があります。
        株式市場にとってもポジティブなサイン（リスクオン）と言えます。
        """
    elif "CHF" in strong_currency:
        comment = """
        **【スイスフラン高 = リスク回避】**
        安全資産の代表格であるスイスフランが買われています。
        地政学リスクの高まりや、金融不安など、投資家がリスク回避姿勢（リスクオフ）を強めている可能性があります。
        """
    elif strongest['Daily Change (%)'] < 0:
        comment = """
        **【全面的円高】**
        全ての通貨が前日比でマイナス、つまり「円」が最強の状態です。
        日銀の政策修正観測や、急速な円の買い戻し（巻き戻し）が起きています。
        クロス円のショートポジションがワークしやすい局面です。
        """
    else:
        comment = f"""
        **【選別色の強い展開】**
        本日は {strong_currency} が相対的に強い動きを見せています。
        通貨ごとの個別の材料（経済指標や要人発言）に反応している可能性があります。
        """
        
    st.info(comment)


    # --- AI通貨分析セクション ---
    st.markdown("---")
    st.subheader("🤖 AI通貨ストラテジスト分析")
    st.caption("G10通貨チーフFXストラテジスト視点の分析")
    
    if st.button("🧠 AIで通貨市場を分析", use_container_width=True):
        with st.spinner("🔄 Claude AIが通貨市場を分析中..."):
            ai_result = call_currency_ai(df)
        
        if ai_result:
            regime = ai_result.get("market_regime", {})
            sentiment = regime.get("fx_sentiment", "混在")
            jpy_status = regime.get("jpy_status", "中立")
            jpy_emoji = {"円高": "💪", "円安": "📉", "中立": "➡️"}.get(jpy_status, "⚪")
            
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.metric("FXセンチメント", sentiment)
            with col_r2:
                st.metric("円の状態", f"{jpy_emoji} {jpy_status}")
            
            headline = regime.get("headline", "")
            if headline:
                st.info(f"📋 **市場の結論:** {headline}")
            st.markdown("---")
            
            diag = ai_result.get("current_diagnosis", {})
            st.markdown("### 🔍 現状診断")
            st.markdown(diag.get("summary", ""))
            col_ra, col_jd = st.columns(2)
            with col_ra:
                st.markdown("**📊 リスク選好度:**")
                st.markdown(diag.get("risk_appetite", ""))
            with col_jd:
                st.markdown("**💴 円のドライバー:**")
                st.markdown(diag.get("jpy_driver", ""))
            st.markdown("---")
            
            groups = ai_result.get("currency_groups", {})
            if groups:
                st.markdown("### 💪 通貨グループ分析")
                col_sg, col_wg = st.columns(2)
                sg = groups.get("strongest_group", {})
                with col_sg:
                    currencies = ", ".join(sg.get("currencies", []))
                    st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B;">
                        <h4 style="color: #09AB3B; margin-top: 0;">🏆 {sg.get('name', '最強グループ')}</h4>
                        <p style="color: #F7C948;">{currencies}</p>
                        <p style="color: #ddd; font-size: 0.9em;">{sg.get('reason', '')}</p>
                    </div>""", unsafe_allow_html=True)
                wg = groups.get("weakest_group", {})
                with col_wg:
                    currencies = ", ".join(wg.get("currencies", []))
                    st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B;">
                        <h4 style="color: #FF4B4B; margin-top: 0;">📉 {wg.get('name', '最弱グループ')}</h4>
                        <p style="color: #F7C948;">{currencies}</p>
                        <p style="color: #ddd; font-size: 0.9em;">{wg.get('reason', '')}</p>
                    </div>""", unsafe_allow_html=True)
            st.markdown("---")
            
            st.markdown("### 🔮 フォワードシナリオ分析")
            scenarios = ai_result.get("forward_scenarios", {})
            base = scenarios.get("base_case", {})
            st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #4ECDC4; margin-bottom: 15px;">
                <h4 style="color: #4ECDC4; margin-top: 0;">💴 メイン ({base.get('probability', 50)}%): {base.get('title', '')}</h4>
                <p style="color: #ddd;">{base.get('narrative', '')}</p>
                <p style="color: #F7C948;">📊 円の方向: <b>{base.get('jpy_outlook', '')}</b></p>
                <p style="color: #4ECDC4; margin-bottom: 0;">💼 {base.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
            
            col_bull, col_bear = st.columns(2)
            bull = scenarios.get("bull_jpy", {})
            with col_bull:
                st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B;">
                    <h4 style="color: #09AB3B; margin-top: 0;">💪 円高 ({bull.get('probability', 25)}%): {bull.get('title', '')}</h4>
                    <p style="color: #ddd; font-size: 0.9em;">{bull.get('narrative', '')}</p>
                    <p style="color: #09AB3B; font-size: 0.85em;">💼 {bull.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            bear = scenarios.get("bear_jpy", {})
            with col_bear:
                st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B;">
                    <h4 style="color: #FF4B4B; margin-top: 0;">📉 円安 ({bear.get('probability', 25)}%): {bear.get('title', '')}</h4>
                    <p style="color: #ddd; font-size: 0.9em;">{bear.get('narrative', '')}</p>
                    <p style="color: #FF4B4B; font-size: 0.85em;">💼 {bear.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            st.markdown("---")
            
            trades = ai_result.get("trade_ideas", [])
            if trades:
                st.markdown("### 💡 トレードアイデア")
                for t in trades:
                    direction_emoji = "🟢" if t.get("direction") == "買い" else "🔴"
                    st.markdown(f"- {direction_emoji} **{t.get('pair', '')}** ({t.get('direction', '')}): {t.get('rationale', '')}")
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
