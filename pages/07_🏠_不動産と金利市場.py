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
st.set_page_config(page_title="不動産と金利市場", page_icon="🏠", layout="wide")
st.title("不動産市況 & 金利サイクル 🏠")
st.markdown("不動産は「金利」に支配されています。**住宅ローン金利（長期金利）**と**不動産株（REIT・建設）**のシーソー関係を分析します。")


# --- AI要約機能 ---
def call_realestate_ai(df_current, df_chart):
    """不動産・金利データをClaude APIで分析"""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    data_text = "## 不動産・金利データ\n\n"
    data_text += "### 最新値\n"
    for _, row in df_current.iterrows():
        diff = row['Price'] - row['Prev']
        if "10Y" in row['Name']:
            data_text += f"- {row['Name']}: {row['Price']:.2f}% (前日比: {diff:+.2f}%)\n"
        else:
            pct = (diff / row['Prev']) * 100 if row['Prev'] > 0 else 0
            data_text += f"- {row['Name']}: ${row['Price']:.2f} (前日比: {diff:+.2f}, {pct:+.1f}%)\n"

    if not df_chart.empty:
        data_text += "\n### 期間別パフォーマンス\n"
        latest = df_chart.iloc[-1]
        for label, days in [("1週間", 5), ("1ヶ月", 20), ("3ヶ月", 60), ("6ヶ月", 120)]:
            if len(df_chart) > days:
                past = df_chart.iloc[-days]
                data_text += f"\n{label}変化:\n"
                for col in df_chart.columns:
                    if "10Y" in col:
                        data_text += f"- {col}: {past[col]:.2f}% -> {latest[col]:.2f}% ({latest[col]-past[col]:+.2f}%)\n"
                    else:
                        chg = latest[col] - past[col]
                        data_text += f"- {col}: {chg:+.1f}%\n"

        # REIT vs 金利の相関
        reit_col = [c for c in df_chart.columns if "XLRE" in c]
        rate_col = [c for c in df_chart.columns if "10Y" in c]
        if reit_col and rate_col:
            corr = df_chart[reit_col[0]].corr(df_chart[rate_col[0]])
            data_text += f"\n### 相関分析\n"
            data_text += f"- XLRE vs 10Y金利 相関: {corr:.2f} ({'強い逆相関' if corr < -0.5 else '弱い逆相関' if corr < 0 else '正の相関'})\n"

    system_prompt = """あなたはブラックストーンやブルックフィールドで20年の経験を持つ不動産投資専門のシニアストラテジストです。
米国不動産市場と金利の関係を専門としています。

【重要】現在の日付は2026年2月です。全ての予測・見通しは2026年2月時点からの未来について述べてください。

提供されたデータを分析し、以下のJSON形式で回答してください。
機関投資家向けの不動産戦略レポートのように、具体的な数値と因果関係を明確にしてください。

【分析ルール】
1. 必ず具体的な数値を引用（金利水準、REIT騰落率、住宅建設株の動き）
2. 金利と不動産の逆相関メカニズムを説明
3. XLRE（REIT）、VNQ（広範不動産）、XHB（住宅建設）の違いを区別
4. XHBは先行指標としての役割を分析
5. データにない事実を捏造しない

{
    "cycle_position": {
        "total_stages": 5,
        "current_stage": 3,
        "stage_name": "現在のステージ名",
        "stages_map": [
            {"stage": 1, "name": "金利上昇・不動産下落", "description": "利上げ局面、REIT下落、住宅販売減少"},
            {"stage": 2, "name": "金利ピーク・底値形成", "description": "金利横ばい、不動産株底打ち、建設株先行上昇"},
            {"stage": 3, "name": "利下げ開始・回復初期", "description": "金利低下開始、REIT反発、住宅需要回復"},
            {"stage": 4, "name": "不動産好況・価格上昇", "description": "低金利恩恵、価格上昇、開発活発"},
            {"stage": 5, "name": "過熱・バブル警戒", "description": "価格高騰、レバレッジ拡大、次の引締め警戒"}
        ],
        "evidence": "現在のステージだと判断した根拠を2-3文で。具体数値必須"
    },
    "current_diagnosis": {
        "headline": "1行の見出し",
        "summary": "現在の不動産市況を4-5文で詳細に説明。金利水準、各ETF価格を引用",
        "rate_impact": "現在の金利水準が不動産に与える影響を2文で",
        "leading_signal": "XHB（住宅建設株）が発している先行シグナルを2文で"
    },
    "asset_breakdown": {
        "xlre": {
            "outlook": "REIT全体の見通しを2文で",
            "driver": "主な価格ドライバー",
            "signal": "強気/中立/弱気"
        },
        "vnq": {
            "outlook": "広範不動産の見通しを2文で",
            "driver": "主な価格ドライバー",
            "signal": "強気/中立/弱気"
        },
        "xhb": {
            "outlook": "住宅建設の見通しを2文で",
            "driver": "主な価格ドライバー",
            "signal": "強気/中立/弱気"
        }
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "メインシナリオのタイトル",
            "rate_path": "金利の予想パス（例: 4.3% -> 3.8%）",
            "next_3months": "今後3ヶ月に起きること",
            "next_6months": "その後3-6ヶ月に起きること",
            "next_12months": "6-12ヶ月後の状態",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "bull_case": {
            "probability": 25,
            "title": "不動産上昇シナリオのタイトル",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "bear_case": {
            "probability": 25,
            "title": "不動産下落シナリオのタイトル",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        }
    },
    "rate_sensitivity": {
        "mortgage_impact": "現在の金利水準での住宅ローン負担の評価",
        "cap_rate_spread": "キャップレートと国債利回りのスプレッドの評価",
        "rate_threshold": "不動産が本格回復するための金利水準の目安"
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
def get_real_estate_data():
    tickers = {
        "XLRE (不動産セクター)": "XLRE",     # 大型REIT
        "VNQ (全米不動産ETF)": "VNQ",       # より広い範囲の不動産
        "XHB (住宅建設業者)": "XHB",        # 家を建てる会社（景気に敏感）
        "US 10Y (長期金利)": "^TNX"        # 住宅ローン金利の目安
    }
    
    data_list = []
    hist_data = {}
    
    progress_text = "不動産データを取得中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(tickers)

    for name, ticker in tickers.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} のデータを取得中...")
            
            t = yf.Ticker(ticker)
            hist = t.history(period="1y")
            
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                
                # チャート用データ（金利以外は正規化）
                if "10Y" in name:
                    # 金利はそのままの値を使う（％表示のため）
                    hist_data[name] = hist['Close']
                else:
                    # 株価は1年前を100として正規化
                    start_val = hist['Close'].iloc[0]
                    hist_data[name] = (hist['Close'] / start_val) * 100
                
                data_list.append({
                    "Name": name,
                    "Price": price,
                    "Prev": prev
                })
        except:
            pass
            
    my_bar.empty()
    
    # データ整形（結合と欠損値埋め）
    if hist_data:
        df_chart = pd.concat(hist_data.values(), axis=1, keys=hist_data.keys())
        df_chart = df_chart.ffill().dropna()
    else:
        df_chart = pd.DataFrame()
        
    return pd.DataFrame(data_list), df_chart

# --- メイン処理 ---
df, df_chart = get_real_estate_data()

if df.empty:
    st.error("データ取得失敗")
else:
    # 1. 価格ボード
    st.subheader("📊 現在の不動産価格と金利")
    cols = st.columns(4)
    
    for i, row in df.iterrows():
        with cols[i % 4]:
            diff = row["Price"] - row["Prev"]
            
            # 金利の場合のフォーマット
            if "10Y" in row["Name"]:
                fmt = "{:.2f}%"
                val_str = fmt.format(row["Price"])
                delta_color = "inverse" # 金利上昇は赤（悪い）
            else:
                fmt = "${:.2f}"
                val_str = fmt.format(row["Price"])
                delta_color = "normal" # 株価上昇は緑（良い）
                
            st.metric(
                label=row["Name"],
                value=val_str,
                delta=f"{diff:+.2f}",
                delta_color=delta_color
            )
            
    st.markdown("---")

    # 2. 逆相関チャート
    st.subheader("📉 「金利」vs「不動産」の逆相関チャート")
    st.markdown("赤線（金利）が上がると、緑線（不動産）が下がる傾向にあります。**「赤線が天井を打って下がり始めた時」**が不動産の買い場です。")
    
    if not df_chart.empty:
        fig = go.Figure()
        
        # 左軸: 不動産株 (正規化)
        reit_col = "XLRE (不動産セクター)"
        home_col = "XHB (住宅建設業者)"
        
        if reit_col in df_chart.columns:
            fig.add_trace(go.Scatter(
                x=df_chart.index, y=df_chart[reit_col],
                name="XLRE (REIT)",
                line=dict(color="#00CC96", width=2.5)
            ))
        
        if home_col in df_chart.columns:
            fig.add_trace(go.Scatter(
                x=df_chart.index, y=df_chart[home_col],
                name="XHB (住宅建設)",
                line=dict(color="#FFA15A", width=2)
            ))

        # 右軸: 長期金利
        rate_col = "US 10Y (長期金利)"
        if rate_col in df_chart.columns:
            fig.add_trace(go.Scatter(
                x=df_chart.index, y=df_chart[rate_col],
                name="米国10年債金利 (逆風)",
                line=dict(color="#EF553B", width=2, dash="dot"),
                yaxis="y2"
            ))

        # レイアウト
        fig.update_layout(
            title="不動産株 vs 金利 (過去1年)",
            yaxis=dict(title="株価騰落率 (スタート=100)"),
            yaxis2=dict(
                title="金利 (%)",
                overlaying="y",
                side="right",
                showgrid=False
            ),
            hovermode="x unified",
            legend=dict(orientation="h", y=1.1, x=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False),
            yaxis1=dict(showgrid=True, gridcolor="#444")
        )
        
        st.plotly_chart(fig, use_container_width=True)

    # 3. 診断コメント
    st.subheader("🤖 AI不動産市況診断")
    
    # 最新の金利と不動産トレンド
    latest_rate = df[df["Name"].str.contains("10Y")].iloc[0]["Price"]
    latest_reit_diff = df[df["Name"].str.contains("XLRE")].iloc[0]["Price"] - df[df["Name"].str.contains("XLRE")].iloc[0]["Prev"]
    
    c1, c2 = st.columns([2, 1])
    with c1:
        if latest_rate > 4.5:
            st.error("🥶 **冬の時代 (High Rates)**\n\n金利が4.5%を超えており、不動産には非常に厳しい環境です。住宅ローンが高すぎて家が売れにくい状態です。無理に買わず、金利低下を待つのが賢明です。")
        elif latest_rate < 3.5:
            st.success("🌞 **春の到来 (Low Rates)**\n\n金利が落ち着いています。資金調達コストが安いため、不動産価格は上昇しやすいボーナスタイムです。")
        else:
            st.warning("☁️ **曇り (Neutral)**\n\n金利は歴史的平均レベルです。物件ごとの選別が必要です。")
            
    with c2:
        st.info("""
        **💡 注目ポイント: XHB (建設株)**
        実はREITよりも先に動くのが「住宅建設株(XHB)」です。
        「金利はまだ高いけど、建設株が上がり始めた」場合、市場は**将来の利下げ**を織り込み始めています。
        """)

    # --- AI不動産分析セクション ---
    st.markdown("---")
    st.subheader("🤖 AI不動産サイクル分析")
    st.caption("不動産投資シニアストラテジスト視点の分析")
    
    if st.button("🧠 AIで不動産サイクルを分析", use_container_width=True):
        with st.spinner("🔄 Claude AIが不動産市況を分析中..."):
            ai_result = call_realestate_ai(df, df_chart)
        
        if ai_result:
            # --- サイクルポジション ---
            cp = ai_result.get("cycle_position", {})
            current = cp.get("current_stage", 1)
            total = cp.get("total_stages", 5)
            stage_name = cp.get("stage_name", "")
            stages = cp.get("stages_map", [])
            
            st.markdown("### 📍 不動産サイクル 現在地")
            
            cols_cycle = st.columns(total)
            for i, stage in enumerate(stages):
                with cols_cycle[i]:
                    is_current = (i + 1 == current)
                    if is_current:
                        st.markdown(f"""<div style="background: linear-gradient(135deg, #1a3a5c, #2471a3); padding: 10px; border-radius: 8px; text-align: center; border: 2px solid #5dade2;">
                            <div style="font-size: 1.4em; font-weight: bold;">🏠</div>
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
            
            col_ri, col_ls = st.columns(2)
            with col_ri:
                st.markdown("**📈 金利の影響:**")
                st.markdown(diag.get("rate_impact", ""))
            with col_ls:
                st.markdown("**📡 XHB先行シグナル:**")
                st.markdown(diag.get("leading_signal", ""))
            
            st.markdown("---")
            
            # --- 資産別ブレイクダウン ---
            breakdown = ai_result.get("asset_breakdown", {})
            if breakdown:
                st.markdown("### 🏗️ 不動産セクター別見通し")
                cols_bd = st.columns(3)
                items = [
                    ("🏢 XLRE (REIT)", "xlre", "#5dade2"),
                    ("🏘️ VNQ (広範不動産)", "vnq", "#48c9b0"),
                    ("🏗️ XHB (住宅建設)", "xhb", "#f39c12")
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
            st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #5dade2; margin-bottom: 15px;">
                <h4 style="color: #5dade2; margin-top: 0;">🏠 メインシナリオ ({base.get('probability', 50)}%): {base.get('title', '')}</h4>
                <p style="color: #F7C948; font-size: 1.1em;">📊 金利パス: <b>{base.get('rate_path', '')}</b></p>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px; color: #888; width: 120px;">3ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_3months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">6ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_6months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">12ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_12months', '')}</td></tr>
                </table>
                <p style="color: #5dade2; margin-bottom: 0;">💼 <b>アクション:</b> {base.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
            
            col_bull, col_bear = st.columns(2)
            
            bull = scenarios.get("bull_case", {})
            with col_bull:
                st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B; height: 100%;">
                    <h4 style="color: #09AB3B; margin-top: 0;">🟢 上昇 ({bull.get('probability', 25)}%): {bull.get('title', '')}</h4>
                    <p style="color: #ddd; font-size: 0.9em;">{bull.get('narrative', '')}</p>
                    <p style="color: #09AB3B; font-size: 0.85em; margin-bottom: 0;">💼 {bull.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            bear = scenarios.get("bear_case", {})
            with col_bear:
                st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B; height: 100%;">
                    <h4 style="color: #FF4B4B; margin-top: 0;">🔴 下落 ({bear.get('probability', 25)}%): {bear.get('title', '')}</h4>
                    <p style="color: #ddd; font-size: 0.9em;">{bear.get('narrative', '')}</p>
                    <p style="color: #FF4B4B; font-size: 0.85em; margin-bottom: 0;">💼 {bear.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- 金利感応度 ---
            rate_sens = ai_result.get("rate_sensitivity", {})
            if rate_sens:
                st.markdown("### 📐 金利感応度分析")
                col_r1, col_r2, col_r3 = st.columns(3)
                with col_r1:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #EF553B;">
                        <p style="color: #EF553B; font-weight: bold; margin: 0 0 5px 0;">🏦 住宅ローン負担</p>
                        <p style="color: #ddd; font-size: 0.85em; margin: 0;">{rate_sens.get('mortgage_impact', '')}</p>
                    </div>""", unsafe_allow_html=True)
                with col_r2:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #f39c12;">
                        <p style="color: #f39c12; font-weight: bold; margin: 0 0 5px 0;">📊 キャップレートスプレッド</p>
                        <p style="color: #ddd; font-size: 0.85em; margin: 0;">{rate_sens.get('cap_rate_spread', '')}</p>
                    </div>""", unsafe_allow_html=True)
                with col_r3:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #09AB3B;">
                        <p style="color: #09AB3B; font-weight: bold; margin: 0 0 5px 0;">🎯 回復目安金利</p>
                        <p style="color: #ddd; font-size: 0.85em; margin: 0;">{rate_sens.get('rate_threshold', '')}</p>
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
