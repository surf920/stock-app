import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import ssl
import json
import requests

# --- 🚨 通信エラー回避 ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ----------------------

# ページ設定
st.set_page_config(page_title="為替と金利", page_icon="💴", layout="wide")
st.title("ドル円 & 日米金利差トラッカー 💴")
st.markdown("「お金は金利の高い国に流れる」。日米の**金利差（ギャップ）**とドル円レートの連動性を分析します。")


# --- AI要約機能 ---
def call_forex_ai(df):
    """為替・金利データをClaude APIで分析"""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # 各期間の変化を計算
    data_text = "## 為替・金利データ\n\n"
    data_text += f"### 最新値\n"
    data_text += f"- ドル円: {latest['USD/JPY']:.2f} (前日比: {latest['USD/JPY'] - prev['USD/JPY']:+.2f})\n"
    data_text += f"- 米国10年債利回り: {latest['US 10Y']:.2f}%\n"
    data_text += f"- 日米金利差: {latest['Spread']:.2f}%\n\n"

    # 期間別変化
    for label, days in [("1週間", 5), ("1ヶ月", 20), ("3ヶ月", 60), ("6ヶ月", 120), ("1年", 250)]:
        if len(df) > days:
            past = df.iloc[-days]
            data_text += f"### {label}前との比較\n"
            data_text += f"- ドル円: {past['USD/JPY']:.2f} -> {latest['USD/JPY']:.2f} ({latest['USD/JPY'] - past['USD/JPY']:+.2f})\n"
            data_text += f"- 金利差: {past['Spread']:.2f}% -> {latest['Spread']:.2f}% ({latest['Spread'] - past['Spread']:+.2f}%)\n\n"

    # 相関係数
    recent_corr = df.tail(60)["USD/JPY"].corr(df.tail(60)["Spread"])
    long_corr = df["USD/JPY"].corr(df["Spread"])
    data_text += f"### 相関分析\n"
    data_text += f"- 直近3ヶ月の相関係数: {recent_corr:.2f}\n"
    data_text += f"- 全期間の相関係数: {long_corr:.2f}\n"

    # レンジ
    data_text += f"\n### 過去1年のレンジ\n"
    yr = df.tail(250)
    data_text += f"- ドル円: {yr['USD/JPY'].min():.2f} - {yr['USD/JPY'].max():.2f}\n"
    data_text += f"- 金利差: {yr['Spread'].min():.2f}% - {yr['Spread'].max():.2f}%\n"

    system_prompt = """あなたはJPモルガンやゴールドマン・サックスで20年の経験を持つG10通貨専門のチーフストラテジストです。
ドル円と日米金利差の関係を専門としています。

提供されたデータを分析し、以下のJSON形式で回答してください。
機関投資家向けの為替戦略レポートのように、具体的な数値と因果関係を明確にしてください。

【分析ルール】
1. 必ず具体的な数値を引用（ドル円レート、金利差、変動幅）
2. 金利差とドル円の連動・乖離を定量的に分析
3. 日銀・FRBの政策スタンスを踏まえる
4. 実需（貿易収支）と投機（キャリートレード）の両面から分析
5. データにない事実を捏造しない

{
    "cycle_position": {
        "total_stages": 5,
        "current_stage": 3,
        "stage_name": "現在のステージ名",
        "stages_map": [
            {"stage": 1, "name": "円高・ドル安局面", "description": "FRB利下げ、日銀引締め、金利差縮小"},
            {"stage": 2, "name": "転換期・方向感模索", "description": "政策変更の織り込み、ボラ上昇"},
            {"stage": 3, "name": "円安・ドル高進行", "description": "金利差拡大、キャリートレード活発"},
            {"stage": 4, "name": "円安ピーク・介入警戒", "description": "行き過ぎた円安、当局介入リスク"},
            {"stage": 5, "name": "円安修正・リバーサル", "description": "ポジション巻き戻し、円高回帰"}
        ],
        "evidence": "現在のステージだと判断した根拠を2-3文で。具体数値必須"
    },
    "current_diagnosis": {
        "headline": "1行の見出し（例: 金利差縮小も円安持続、乖離が拡大中）",
        "summary": "現在の為替環境を4-5文で詳細に説明。ドル円レート、金利差の具体値を引用",
        "fair_value_assessment": "現在のドル円は金利差から見て割高/割安/適正か。具体的な根拠を2文で",
        "divergence_analysis": "金利差とドル円の連動が崩れている場合、その理由と含意を2文で"
    },
    "policy_outlook": {
        "fed": "FRBの今後の政策見通しとドル円への影響を2文で",
        "boj": "日銀の今後の政策見通しとドル円への影響を2文で",
        "policy_divergence_direction": "今後、金利差は拡大/縮小どちらに向かうか。1文で"
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "メインシナリオのタイトル",
            "usdjpy_range": "3ヶ月後の予想レンジ（例: 148-155円）",
            "next_3months": "今後3ヶ月に起きること",
            "next_6months": "その後3-6ヶ月に起きること",
            "next_12months": "6-12ヶ月後の状態",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的なヘッジ/ポジション戦略"
        },
        "bull_case": {
            "probability": 25,
            "title": "円高シナリオのタイトル",
            "usdjpy_target": "円高ターゲット",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "bear_case": {
            "probability": 25,
            "title": "円安シナリオのタイトル",
            "usdjpy_target": "円安ターゲット",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        }
    },
    "trade_flows": {
        "carry_trade_status": "キャリートレードの現状（活発/縮小/巻き戻し中）と根拠",
        "real_demand": "実需（貿易・投資フロー）の方向性"
    },
    "risk_monitor": {
        "watch_items": ["監視すべき指標やイベント1", "2", "3"],
        "intervention_risk": "為替介入リスクの評価（低/中/高）と根拠",
        "next_inflection": "次の転換点はいつ・何がきっかけか"
    }
}"""

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": data_text}]
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=90
        )
        response.raise_for_status()
        result = response.json()
        text = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                text += block["text"]
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
    except Exception as e:
        st.error(f"AI分析エラー: {e}")
        return None


# サイドバー設定（日本の金利は手動調整も可能に）
with st.sidebar:
    st.header("⚙️ パラメータ設定")
    # 日本の10年債利回りはデータ取得が難しいため、デフォルト値を設定しつつ調整可能にする
    jp_yield = st.slider("🇯🇵 日本国債10年利回り (%)", 0.0, 3.0, 1.05, 0.01, help="日本の長期金利。現状は約1.0%前後で推移しています。")
    st.caption("※ 日本の金利データはリアルタイム取得が難しいため、固定値または手動入力を使用します。")

# キャッシュ設定
@st.cache_data(ttl=3600)
def get_forex_data(jp_yield_val):
    tickers = {
        "USD/JPY": "JPY=X",   # ドル円レート
        "US 10Y": "^TNX"      # 米国10年債利回り
    }
    
    data_frames = []
    
    # データの取得
    try:
        # まとめて取得するとエラーになりやすいので個別に取得
        for name, ticker in tickers.items():
            t = yf.Ticker(ticker)
            hist = t.history(period="2y")
            
            if not hist.empty:
                df = hist[['Close']].rename(columns={'Close': name})
                data_frames.append(df)
        
        if data_frames:
            # データを結合
            df_merged = pd.concat(data_frames, axis=1)
            # 欠損値を埋める（休日のズレなどを補正）
            df_merged = df_merged.ffill().dropna()
            
            # 金利差の計算 (米金利 - 日本金利)
            df_merged["Spread"] = df_merged["US 10Y"] - jp_yield_val
            
            return df_merged
        else:
            return pd.DataFrame()

    except Exception as e:
        return pd.DataFrame()

# --- メイン処理 ---
df = get_forex_data(jp_yield)

if df.empty:
    st.error("データの取得に失敗しました。")
else:
    # 最新データの取得
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. メトリクス表示
    st.subheader("📊 現在のマーケット環境")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        diff = latest["USD/JPY"] - prev["USD/JPY"]
        st.metric("💴 ドル円レート", f"¥{latest['USD/JPY']:.2f}", f"{diff:+.2f}")
    
    with c2:
        diff = latest["US 10Y"] - prev["US 10Y"]
        st.metric("🇺🇸 米国10年債利回り", f"{latest['US 10Y']:.2f}%", f"{diff:+.2f}%")
    
    with c3:
        st.metric("🇯🇵 日本国債10年利回り", f"{jp_yield:.2f}%", "固定 (設定可)", help="サイドバーで変更可能です")
        
    with c4:
        # 金利差
        spread = latest["Spread"]
        prev_spread = prev["Spread"]
        diff = spread - prev_spread
        
        # 金利差が開くとドル高要因
        color = "normal" if diff > 0 else "inverse"
        st.metric("⚖️ 日米金利差", f"{spread:.2f}%", f"{diff:+.2f}%", delta_color=color, help="これが開く（プラス）と円安、縮まる（マイナス）と円高になりやすい")

    st.markdown("---")

    # 2. 2軸チャート
    st.subheader("📈 ドル円 vs 金利差 連動チャート")
    st.markdown("緑の線（ドル円）は、赤の点線（金利差）の後を追いかける傾向があります。")
    
    fig = go.Figure()

    # 左軸: ドル円
    fig.add_trace(go.Scatter(
        x=df.index, y=df["USD/JPY"],
        name="ドル円 (左軸)",
        line=dict(color="#00CC96", width=2.5)
    ))

    # 右軸: 金利差
    fig.add_trace(go.Scatter(
        x=df.index, y=df["Spread"],
        name="日米金利差 (右軸)",
        line=dict(color="#EF553B", width=2, dash="dot"),
        yaxis="y2"
    ))

    # レイアウト
    fig.update_layout(
        title="過去2年間の推移",
        yaxis=dict(title="ドル円 (JPY)", showgrid=False),
        yaxis2=dict(
            title="金利差 (%)",
            overlaying="y",
            side="right",
            showgrid=True,
            gridcolor="#444"
        ),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, use_container_width=True)

    # 3. 相関分析と解説
    st.subheader("🧠 AI分析: 今のレートは適正？")
    
    # 直近3ヶ月の相関係数を計算
    recent_df = df.tail(60) # 約3ヶ月
    correlation = recent_df["USD/JPY"].corr(recent_df["Spread"])
    
    c_col1, c_col2 = st.columns([1, 2])
    
    with c_col1:
        st.metric("直近3ヶ月の相関係数", f"{correlation:.2f}")
        if correlation > 0.7:
            st.success("✅ **非常に強い連動**\n\n現在は「金利差」に素直に反応しています。米金利が上がれば円安になります。")
        elif correlation > 0.3:
            st.info("ℹ️ **緩やかな連動**\n\n金利以外の要因（株価や地政学リスク）も影響しています。")
        else:
            st.warning("⚠️ **連動崩れ (乖離)**\n\n金利差とは無関係に動いています。投機的な動きや介入警戒の可能性があります。")

    with c_col2:
        st.info("""
        **💡 見方のポイント**
        * **赤の点線（金利差）が下がっているのに、緑（ドル円）が高いまま**
            * ➡ 「円安行き過ぎ」のサイン。いずれ修正（円高）が入る可能性が高いです。
        * **赤の点線が上がっているのに、緑がついてこない**
            * ➡ 「円安余地あり」。まだドル高になるエネルギーが残っています。
        """)

    # --- AI為替分析セクション ---
    st.markdown("---")
    st.subheader("🤖 AI為替ストラテジスト分析")
    st.caption("G10通貨チーフストラテジスト視点の分析")
    
    if st.button("🧠 AIで為替サイクルを分析", use_container_width=True):
        with st.spinner("🔄 Claude AIが為替市場を分析中..."):
            ai_result = call_forex_ai(df)
        
        if ai_result:
            # --- サイクルポジション ---
            cp = ai_result.get("cycle_position", {})
            current = cp.get("current_stage", 1)
            total = cp.get("total_stages", 5)
            stage_name = cp.get("stage_name", "")
            stages = cp.get("stages_map", [])
            
            st.markdown("### 📍 為替サイクル 現在地")
            
            cols_cycle = st.columns(total)
            for i, stage in enumerate(stages):
                with cols_cycle[i]:
                    is_current = (i + 1 == current)
                    if is_current:
                        st.markdown(f"""<div style="background: linear-gradient(135deg, #1a472a, #2d6a4f); padding: 10px; border-radius: 8px; text-align: center; border: 2px solid #52b788;">
                            <div style="font-size: 1.4em; font-weight: bold;">💴</div>
                            <div style="font-size: 0.75em; font-weight: bold; color: #fff;">Stage {i+1}</div>
                            <div style="font-size: 0.65em; color: #ddd;">{stage.get('name', '')}</div>
                        </div>""", unsafe_allow_html=True)
                    else:
                        opacity = "0.4" if abs(i + 1 - current) > 1 else "0.7"
                        st.markdown(f"""<div style="background: #262730; padding: 10px; border-radius: 8px; text-align: center; opacity: {opacity}; border: 1px solid #41444C;">
                            <div style="font-size: 1.2em;">{"✅" if i + 1 < current else "⬜"}</div>
                            <div style="font-size: 0.7em; color: #888;">Stage {i+1}</div>
                            <div style="font-size: 0.6em; color: #888;">{stage.get('name', '')}</div>
                        </div>""", unsafe_allow_html=True)
            
            progress_pct = current / total
            st.progress(progress_pct, text=f"サイクル進行度: Stage {current}/{total} - {stage_name}")
            
            evidence = cp.get("evidence", "")
            if evidence:
                st.info(f"📋 **判断根拠:** {evidence}")
            
            st.markdown("---")
            
            # --- 現状診断 ---
            diag = ai_result.get("current_diagnosis", {})
            st.markdown(f"### 🔍 現状診断: {diag.get('headline', '')}")
            st.markdown(diag.get("summary", ""))
            
            col_fv, col_div = st.columns(2)
            with col_fv:
                st.markdown("**💰 フェアバリュー評価:**")
                st.markdown(diag.get("fair_value_assessment", ""))
            with col_div:
                st.markdown("**📐 乖離分析:**")
                st.markdown(diag.get("divergence_analysis", ""))
            
            st.markdown("---")
            
            # --- 政策見通し ---
            policy = ai_result.get("policy_outlook", {})
            if policy:
                st.markdown("### 🏛️ 中央銀行の政策見通し")
                col_fed, col_boj = st.columns(2)
                with col_fed:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 15px; border-radius: 10px; border-left: 4px solid #3498db;">
                        <h4 style="color: #3498db; margin-top: 0;">🇺🇸 FRB</h4>
                        <p style="color: #ddd;">{policy.get('fed', '')}</p>
                    </div>""", unsafe_allow_html=True)
                with col_boj:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 15px; border-radius: 10px; border-left: 4px solid #e74c3c;">
                        <h4 style="color: #e74c3c; margin-top: 0;">🇯🇵 日銀</h4>
                        <p style="color: #ddd;">{policy.get('boj', '')}</p>
                    </div>""", unsafe_allow_html=True)
                
                direction = policy.get("policy_divergence_direction", "")
                if direction:
                    st.warning(f"📐 **金利差の方向:** {direction}")
            
            st.markdown("---")
            
            # --- シナリオ分析 ---
            st.markdown("### 🔮 フォワードシナリオ分析")
            
            scenarios = ai_result.get("forward_scenarios", {})
            
            base = scenarios.get("base_case", {})
            st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #4ECDC4; margin-bottom: 15px;">
                <h4 style="color: #4ECDC4; margin-top: 0;">💴 メインシナリオ ({base.get('probability', 50)}%): {base.get('title', '')}</h4>
                <p style="color: #F7C948; font-size: 1.1em;">📊 予想レンジ: <b>{base.get('usdjpy_range', '')}</b></p>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px; color: #888; width: 120px;">3ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_3months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">6ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_6months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">12ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_12months', '')}</td></tr>
                </table>
                <p style="color: #4ECDC4; margin-bottom: 0;">💼 <b>アクション:</b> {base.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
            
            col_bull, col_bear = st.columns(2)
            
            bull = scenarios.get("bull_case", {})
            with col_bull:
                st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B; height: 100%;">
                    <h4 style="color: #09AB3B; margin-top: 0;">🟢 円高 ({bull.get('probability', 25)}%): {bull.get('title', '')}</h4>
                    <p style="color: #F7C948;">🎯 ターゲット: <b>{bull.get('usdjpy_target', '')}</b></p>
                    <p style="color: #ddd; font-size: 0.9em;">{bull.get('narrative', '')}</p>
                    <p style="color: #09AB3B; font-size: 0.85em; margin-bottom: 0;">💼 {bull.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            bear = scenarios.get("bear_case", {})
            with col_bear:
                st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B; height: 100%;">
                    <h4 style="color: #FF4B4B; margin-top: 0;">🔴 円安 ({bear.get('probability', 25)}%): {bear.get('title', '')}</h4>
                    <p style="color: #F7C948;">🎯 ターゲット: <b>{bear.get('usdjpy_target', '')}</b></p>
                    <p style="color: #ddd; font-size: 0.9em;">{bear.get('narrative', '')}</p>
                    <p style="color: #FF4B4B; font-size: 0.85em; margin-bottom: 0;">💼 {bear.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- フロー分析 ---
            flows = ai_result.get("trade_flows", {})
            if flows:
                st.markdown("### 💱 フロー分析")
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    st.info(f"📊 **キャリートレード:** {flows.get('carry_trade_status', '')}")
                with col_f2:
                    st.info(f"🏭 **実需フロー:** {flows.get('real_demand', '')}")
            
            st.markdown("---")
            
            # --- リスクモニター ---
            rm = ai_result.get("risk_monitor", {})
            st.markdown("### ⚠️ リスクモニター")
            
            intervention = rm.get("intervention_risk", "")
            if intervention:
                risk_color = {"低": "🟢", "中": "🟡", "高": "🔴"}.get(intervention[:1], "⚪")
                st.metric("為替介入リスク", f"{risk_color} {intervention}")
            
            watch = rm.get("watch_items", [])
            if watch:
                for w in watch:
                    st.markdown(f"- 👁️ {w}")
            inflection = rm.get("next_inflection", "")
            if inflection:
                st.error(f"🔄 **次の転換点:** {inflection}")
