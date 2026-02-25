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
st.set_page_config(page_title="商品とインフレ", page_icon="🧱", layout="wide")
st.title("商品(コモディティ) & インフレ観測 🧱")
st.markdown("「ドクター・カッパー（銅）」による景気診断と、インフレの主役「原油・金」の動きを分析します。")


# --- AI要約機能 ---
def call_commodity_ai(df_current, df_hist):
    """コモディティ・インフレデータをClaude APIで分析"""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    data_text = "## コモディティ価格データ\n\n"
    for _, row in df_current.iterrows():
        diff = row['Price'] - row['Prev']
        pct = (diff / row['Prev']) * 100
        data_text += f"- {row['Name']}: ${row['Price']:.2f} (前日比: {diff:+.2f}, {pct:+.1f}%)\n"

    if not df_hist.empty:
        data_text += "\n## 期間別パフォーマンス\n"
        latest = df_hist.iloc[-1]
        for label, days in [("1週間", 5), ("1ヶ月", 20), ("3ヶ月", 60), ("6ヶ月", 120), ("1年", 250)]:
            if len(df_hist) > days:
                past = df_hist.iloc[-days]
                data_text += f"\n### {label}変化\n"
                for col in df_hist.columns:
                    if col in latest.index and col in past.index and past[col] > 0:
                        chg = ((latest[col] - past[col]) / past[col]) * 100
                        data_text += f"- {col}: {chg:+.1f}%\n"

        # 銅金レシオ
        if "Copper (銅)" in df_hist.columns and "Gold (金)" in df_hist.columns:
            ratio = df_hist["Copper (銅)"] / df_hist["Gold (金)"]
            current_ratio = ratio.iloc[-1]
            ma50 = ratio.rolling(50).mean().iloc[-1]
            data_text += f"\n## 銅金レシオ\n"
            data_text += f"- 現在: {current_ratio:.4f}\n"
            data_text += f"- 50日MA: {ma50:.4f}\n"
            data_text += f"- 判定: {'リスクオン（レシオ>MA50）' if current_ratio > ma50 else 'リスクオフ（レシオ<MA50）'}\n"

        # 原油トレンド
        if "Oil (原油)" in df_hist.columns:
            oil = df_hist["Oil (原油)"]
            ma200 = oil.rolling(200).mean().iloc[-1]
            data_text += f"\n## 原油トレンド\n"
            data_text += f"- 現在: ${oil.iloc[-1]:.2f}\n"
            data_text += f"- 200日MA: ${ma200:.2f}\n"
            data_text += f"- 判定: {'200日線上（インフレ警戒）' if oil.iloc[-1] > ma200 else '200日線下（インフレ沈静）'}\n"

    system_prompt = """あなたはブリッジウォーターやPIMCOで20年の経験を持つコモディティ・インフレ専門のマクロストラテジストです。

【重要】現在の日付は2026年2月です。全ての予測・見通しは2026年2月時点からの未来について述べてください。

提供されたデータを分析し、以下のJSON形式で回答してください。
機関投資家向けのコモディティ戦略レポートのように、具体的な数値と因果関係を明確にしてください。

【分析ルール】
1. 必ず具体的な数値を引用（価格、変動率、レシオ値）
2. 銅金レシオの意味を正確に解釈（上昇=リスクオン、下落=リスクオフ）
3. 原油→インフレ→金利→株価の波及メカニズムを説明
4. 金・銀・銅・原油それぞれの需給構造を区別
5. データにない事実を捏造しない

{
    "cycle_position": {
        "total_stages": 5,
        "current_stage": 3,
        "stage_name": "現在のステージ名",
        "stages_map": [
            {"stage": 1, "name": "デフレ・商品安", "description": "需要低迷、商品全面安、金だけ上昇"},
            {"stage": 2, "name": "リフレ初期", "description": "銅・原油底打ち、景気刺激策で実需回復"},
            {"stage": 3, "name": "インフレ加速", "description": "原油高騰、銅金レシオ上昇、CPI上昇"},
            {"stage": 4, "name": "スタグフレーション警戒", "description": "原油高+景気減速、金急騰、銅下落"},
            {"stage": 5, "name": "引き締め・調整", "description": "利上げで商品全面安、需要破壊"}
        ],
        "evidence": "現在のステージだと判断した根拠を2-3文で。具体数値必須"
    },
    "current_diagnosis": {
        "headline": "1行の見出し",
        "summary": "現在のコモディティ市況を4-5文で詳細に説明。各商品の価格と変動率を引用",
        "inflation_signal": "インフレの方向性を2文で（原油・銅の動きから判断）",
        "risk_appetite": "銅金レシオから読むリスク選好度を2文で"
    },
    "commodity_breakdown": {
        "gold": {
            "outlook": "金の見通しを2文で",
            "driver": "主な価格ドライバー",
            "signal": "強気/中立/弱気"
        },
        "oil": {
            "outlook": "原油の見通しを2文で",
            "driver": "主な価格ドライバー",
            "signal": "強気/中立/弱気"
        },
        "copper": {
            "outlook": "銅の見通しを2文で",
            "driver": "主な価格ドライバー",
            "signal": "強気/中立/弱気"
        },
        "silver": {
            "outlook": "銀の見通しを2文で",
            "driver": "主な価格ドライバー",
            "signal": "強気/中立/弱気"
        }
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "メインシナリオのタイトル",
            "next_3months": "今後3ヶ月に起きること",
            "next_6months": "その後3-6ヶ月に起きること",
            "next_12months": "6-12ヶ月後の状態",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "bull_case": {
            "probability": 25,
            "title": "商品高シナリオのタイトル",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "bear_case": {
            "probability": 25,
            "title": "商品安シナリオのタイトル",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        }
    },
    "inflation_impact": {
        "cpi_direction": "今後のCPIの方向性（上昇/横ばい/低下）と根拠",
        "fed_implication": "コモディティ価格からみたFRB政策への含意",
        "portfolio_hedge": "インフレヘッジとして今何を持つべきか"
    },
    "risk_monitor": {
        "watch_items": ["監視すべき指標やイベント1", "2", "3"],
        "next_inflection": "次の転換点はいつ・何がきっかけか"
    }
}"""

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": "claude-3-haiku-20240307",
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


# キャッシュ設定
@st.cache_data(ttl=3600)
def get_commodity_data():
    tickers = {
        "Gold (金)": "GLD",       # 安全資産
        "Copper (銅)": "CPER",    # 実体経済（景気）
        "Oil (原油)": "USO",      # インフレ・エネルギー
        "Silver (銀)": "SLV",     # 工業需要 & 貴金属
        "SP500": "^GSPC"          # 比較用
    }
    
    data_list = []
    hist_data = {}
    
    progress_text = "コモディティデータを取得中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(tickers)

    for name, ticker in tickers.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} のデータを取得中...")
            
            t = yf.Ticker(ticker)
            hist = t.history(period="2y")
            
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                
                # チャート用（正規化なしの実数データも保持）
                hist_data[name] = hist['Close']
                
                data_list.append({
                    "Name": name,
                    "Price": price,
                    "Prev": prev
                })
        except:
            pass
            
    my_bar.empty()
    return pd.DataFrame(data_list), pd.DataFrame(hist_data)

# --- メイン処理 ---
df, df_hist = get_commodity_data()

if df.empty:
    st.error("データ取得失敗")
else:
    # 1. 価格ボード
    st.subheader("📊 現在の価格")
    cols = st.columns(4)
    for i, row in df.iterrows():
        if row["Name"] != "SP500": # SP500はカード表示しない
            with cols[i % 4]:
                diff = row["Price"] - row["Prev"]
                st.metric(row["Name"], f"${row['Price']:.2f}", f"{diff:+.2f}")

    st.markdown("---")

    # 2. 銅金レシオ (Copper/Gold Ratio)
    st.subheader("👨‍⚕️ ドクター・カッパーの景気診断 (銅金レシオ)")
    
    if "Copper (銅)" in df_hist.columns and "Gold (金)" in df_hist.columns:
        # レシオ計算: 銅価格 ÷ 金価格
        # (ETF価格ベースなので絶対値より「トレンド」が重要)
        ratio = df_hist["Copper (銅)"] / df_hist["Gold (金)"]
        
        # SP500との比較のため、正規化
        sp500 = df_hist["SP500"]
        
        fig_ratio = go.Figure()
        
        # 左軸: 銅金レシオ
        fig_ratio.add_trace(go.Scatter(
            x=ratio.index, y=ratio,
            name="銅金レシオ (景気強度)",
            line=dict(color="#FF8C00", width=2),
            fill='tozeroy', # 下を塗りつぶす
            fillcolor='rgba(255, 140, 0, 0.1)'
        ))
        
        # 右軸: S&P500
        fig_ratio.add_trace(go.Scatter(
            x=sp500.index, y=sp500,
            name="S&P500 (株価)",
            line=dict(color="#00CC96", width=2, dash="dot"),
            yaxis="y2"
        ))
        
        fig_ratio.update_layout(
            title="銅金レシオ vs 株価 (連動性チェック)",
            yaxis=dict(title="銅金レシオ (Copper/Gold)"),
            yaxis2=dict(title="S&P500", overlaying="y", side="right", showgrid=False),
            hovermode="x unified",
            legend=dict(orientation="h", y=1.1, x=0)
        )
        
        st.plotly_chart(fig_ratio, use_container_width=True)
        
        # 診断コメント
        current_ratio = ratio.iloc[-1]
        ma50_ratio = ratio.rolling(50).mean().iloc[-1]
        
        c1, c2 = st.columns([2, 1])
        with c1:
            if current_ratio > ma50_ratio:
                st.success("✅ **リスクオン信号**\n\nレシオが上昇中。「不安（金）」より「実需（銅）」が買われています。景気回復への期待が強く、株価にはプラス要因です。")
            else:
                st.warning("⚠️ **リスクオフ信号**\n\nレシオが下落中。「実需（銅）」より「不安（金）」が買われています。景気後退への警戒が必要です。")
        with c2:
            st.info("💡 **銅金レシオとは？**\n\n「銅」は好景気で買われ、「金」は不景気（不安）で買われます。この比率が上がれば景気良し、下がれば景気悪しと判断します。")
            
    else:
        st.warning("銅または金のデータ不足でレシオ計算ができません。")

    st.markdown("---")

    # 3. 原油トレンド
    st.subheader("🛢️ 原油価格 (インフレの源)")
    if "Oil (原油)" in df_hist.columns:
        oil = df_hist["Oil (原油)"]
        ma200 = oil.rolling(200).mean()
        
        fig_oil = go.Figure()
        fig_oil.add_trace(go.Scatter(x=oil.index, y=oil, name="原油価格 (USO)", line=dict(color="#EF553B")))
        fig_oil.add_trace(go.Scatter(x=ma200.index, y=ma200, name="200日平均", line=dict(color="white", dash="dash")))
        
        fig_oil.update_layout(hovermode="x unified", yaxis_title="価格 ($)")
        st.plotly_chart(fig_oil, use_container_width=True)
        
        if oil.iloc[-1] > ma200.iloc[-1]:
            st.error("🔥 **インフレ警戒**：原油が長期トレンド(200日線)を超えています。物価上昇→金利高のリスクあり。")
        else:
            st.success("💧 **インフレ沈静化**：原油は落ち着いています。株価にはプラス材料です。")

    # --- AIコモディティ分析セクション ---
    st.markdown("---")
    st.subheader("🤖 AIコモディティ・インフレ分析")
    st.caption("マクロストラテジスト視点のコモディティ・インフレ分析")
    
    if st.button("🧠 AIでコモディティサイクルを分析", use_container_width=True):
        with st.spinner("🔄 Claude AIがコモディティ市況を分析中..."):
            ai_result = call_commodity_ai(df, df_hist)
        
        if ai_result:
            # --- サイクルポジション ---
            cp = ai_result.get("cycle_position", {})
            current = cp.get("current_stage", 1)
            total = cp.get("total_stages", 5)
            stage_name = cp.get("stage_name", "")
            stages = cp.get("stages_map", [])
            
            st.markdown("### 📍 コモディティサイクル 現在地")
            
            cols_cycle = st.columns(total)
            for i, stage in enumerate(stages):
                with cols_cycle[i]:
                    is_current = (i + 1 == current)
                    if is_current:
                        st.markdown(f"""<div style="background: linear-gradient(135deg, #5c3d0e, #8b6914); padding: 10px; border-radius: 8px; text-align: center; border: 2px solid #f0c040;">
                            <div style="font-size: 1.4em; font-weight: bold;">🧱</div>
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
            
            col_inf, col_risk = st.columns(2)
            with col_inf:
                st.markdown("**🔥 インフレシグナル:**")
                st.markdown(diag.get("inflation_signal", ""))
            with col_risk:
                st.markdown("**📊 リスク選好度:**")
                st.markdown(diag.get("risk_appetite", ""))
            
            st.markdown("---")
            
            # --- 商品別ブレイクダウン ---
            breakdown = ai_result.get("commodity_breakdown", {})
            if breakdown:
                st.markdown("### 📦 商品別見通し")
                cols_bd = st.columns(4)
                items = [
                    ("🥇 金", "gold", "#F7C948"),
                    ("🛢️ 原油", "oil", "#EF553B"),
                    ("🔧 銅", "copper", "#FF8C00"),
                    ("🥈 銀", "silver", "#C0C0C0")
                ]
                for idx, (label, key, color) in enumerate(items):
                    with cols_bd[idx]:
                        item = breakdown.get(key, {})
                        signal = item.get("signal", "中立")
                        signal_emoji = {"強気": "🟢", "中立": "🟡", "弱気": "🔴"}.get(signal, "⚪")
                        st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-top: 3px solid {color};">
                            <h4 style="color: {color}; margin: 0 0 8px 0;">{label}</h4>
                            <p style="color: #ddd; font-size: 0.85em; margin: 0 0 5px 0;">{item.get('outlook', '')}</p>
                            <p style="color: #888; font-size: 0.75em; margin: 0 0 5px 0;">📌 {item.get('driver', '')}</p>
                            <p style="margin: 0; font-size: 0.9em;">{signal_emoji} <b>{signal}</b></p>
                        </div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- シナリオ分析 ---
            st.markdown("### 🔮 フォワードシナリオ分析")
            
            scenarios = ai_result.get("forward_scenarios", {})
            
            base = scenarios.get("base_case", {})
            st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #f0c040; margin-bottom: 15px;">
                <h4 style="color: #f0c040; margin-top: 0;">🧱 メインシナリオ ({base.get('probability', 50)}%): {base.get('title', '')}</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px; color: #888; width: 120px;">3ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_3months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">6ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_6months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">12ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_12months', '')}</td></tr>
                </table>
                <p style="color: #f0c040; margin-bottom: 0;">💼 <b>アクション:</b> {base.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
            
            col_bull, col_bear = st.columns(2)
            
            bull = scenarios.get("bull_case", {})
            with col_bull:
                st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B; height: 100%;">
                    <h4 style="color: #09AB3B; margin-top: 0;">🟢 商品高 ({bull.get('probability', 25)}%): {bull.get('title', '')}</h4>
                    <p style="color: #ddd; font-size: 0.9em;">{bull.get('narrative', '')}</p>
                    <p style="color: #09AB3B; font-size: 0.85em; margin-bottom: 0;">💼 {bull.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            bear = scenarios.get("bear_case", {})
            with col_bear:
                st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B; height: 100%;">
                    <h4 style="color: #FF4B4B; margin-top: 0;">🔴 商品安 ({bear.get('probability', 25)}%): {bear.get('title', '')}</h4>
                    <p style="color: #ddd; font-size: 0.9em;">{bear.get('narrative', '')}</p>
                    <p style="color: #FF4B4B; font-size: 0.85em; margin-bottom: 0;">💼 {bear.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- インフレ影響 ---
            inflation = ai_result.get("inflation_impact", {})
            if inflation:
                st.markdown("### 🔥 インフレへの影響")
                col_i1, col_i2, col_i3 = st.columns(3)
                with col_i1:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #EF553B;">
                        <p style="color: #EF553B; font-weight: bold; margin: 0 0 5px 0;">📈 CPI方向性</p>
                        <p style="color: #ddd; font-size: 0.85em; margin: 0;">{inflation.get('cpi_direction', '')}</p>
                    </div>""", unsafe_allow_html=True)
                with col_i2:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #3498db;">
                        <p style="color: #3498db; font-weight: bold; margin: 0 0 5px 0;">🏛️ FRBへの含意</p>
                        <p style="color: #ddd; font-size: 0.85em; margin: 0;">{inflation.get('fed_implication', '')}</p>
                    </div>""", unsafe_allow_html=True)
                with col_i3:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #09AB3B;">
                        <p style="color: #09AB3B; font-weight: bold; margin: 0 0 5px 0;">🛡️ インフレヘッジ</p>
                        <p style="color: #ddd; font-size: 0.85em; margin: 0;">{inflation.get('portfolio_hedge', '')}</p>
                    </div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- リスクモニター ---
            rm = ai_result.get("risk_monitor", {})
            st.markdown("### ⚠️ リスクモニター")
            watch = rm.get("watch_items", [])
            if watch:
                for w in watch:
                    st.markdown(f"- 👁️ {w}")
            inflection = rm.get("next_inflection", "")
            if inflection:
                st.error(f"🔄 **次の転換点:** {inflection}")
