import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
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
st.set_page_config(page_title="セクターローテーション", page_icon="🔄", layout="wide")
st.title("セクターローテーション & 景気サイクル 🔄")
st.markdown("「資金はどこへ向かっているか？」 米国株11セクターの強弱を分析し、**現在の景気サイクル（回復・好況・後退・不況）** を読み解きます。")


# --- AI要約機能 ---
def call_sector_ai(df_current, df_chart, period):
    """セクターローテーションデータをClaude APIで分析"""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    data_text = f"## 米国11セクター パフォーマンス (期間: {period})\n\n"
    df_sorted = df_current.sort_values(by="Change", ascending=False)
    for _, row in df_sorted.iterrows():
        data_text += f"- {row['Sector']}: {row['Change']:+.2f}% (価格: ${row['Price']:.2f})\n"

    top3 = df_sorted.head(3)["Sector"].tolist()
    bottom3 = df_sorted.tail(3)["Sector"].tolist()
    data_text += f"\n上位3セクター: {', '.join(top3)}\n"
    data_text += f"下位3セクター: {', '.join(bottom3)}\n"

    # セクター分類
    data_text += """\n## セクター分類\n
- シクリカル（景気敏感）: テクノロジー(XLK), 一般消費財(XLY), 資本財(XLI), 素材(XLB)
- ディフェンシブ（安定）: ヘルスケア(XLV), 生活必需品(XLP), 公益事業(XLU)
- インフレヘッジ: エネルギー(XLE), 金融(XLF)
- その他: 通信(XLC), 不動産(XLRE)\n"""

    # 分類別平均パフォーマンス
    cyclical = df_current[df_current["Ticker"].isin(["XLK","XLY","XLI","XLB"])]["Change"].mean()
    defensive = df_current[df_current["Ticker"].isin(["XLV","XLP","XLU"])]["Change"].mean()
    inflation = df_current[df_current["Ticker"].isin(["XLE","XLF"])]["Change"].mean()
    data_text += f"\n## 分類別平均パフォーマンス\n"
    data_text += f"- シクリカル平均: {cyclical:+.2f}%\n"
    data_text += f"- ディフェンシブ平均: {defensive:+.2f}%\n"
    data_text += f"- インフレヘッジ平均: {inflation:+.2f}%\n"
    data_text += f"- シクリカル vs ディフェンシブ差: {cyclical - defensive:+.2f}%\n"

    system_prompt = """あなたはフィデリティやキャピタルグループで20年の経験を持つセクターローテーション専門のシニアストラテジストです。
米国11セクターの相対強弱から景気サイクルの位置と今後の資金フローを予測します。

【重要】現在の日付は2026年2月です。2024年や2025年の話ではありません。全ての予測・見通しは2026年2月時点からの未来について述べてください。

提供されたデータを分析し、以下のJSON形式で回答してください。
機関投資家向けのセクター戦略レポートのように、具体的な数値と因果関係を明確にしてください。

【分析ルール】
1. 必ず具体的な数値を引用（各セクターの騰落率、分類別平均）
2. シクリカル vs ディフェンシブの強弱が景気サイクルの最重要指標
3. セクター間の「資金移動の方向」を読み取る
4. 景気サイクルの4局面（回復→好況→後退→不況）と各セクターの位置づけ
5. データにない事実を捏造しない

{
    "cycle_position": {
        "total_stages": 4,
        "current_stage": 2,
        "stage_name": "現在のステージ名",
        "stages_map": [
            {"stage": 1, "name": "回復期 (Recovery)", "description": "テクノロジー・一般消費財が主導、金融回復"},
            {"stage": 2, "name": "好況期 (Expansion)", "description": "幅広いセクターが上昇、資本財・素材も好調"},
            {"stage": 3, "name": "後期・過熱 (Late Cycle)", "description": "エネルギー・素材がリード、金融堅調"},
            {"stage": 4, "name": "後退期 (Contraction)", "description": "ヘルスケア・生活必需品・公益が相対的に強い"}
        ],
        "evidence": "現在のステージだと判断した根拠を2-3文で。具体数値必須"
    },
    "current_diagnosis": {
        "headline": "1行の見出し（例: テクノロジー主導の好況相場、但しディフェンシブに資金流入の兆し）",
        "summary": "現在のセクターローテーションを4-5文で詳細に説明。各セクター騰落率を引用",
        "money_flow": "資金がどこからどこへ移動しているか。2文で",
        "cyclical_vs_defensive": "シクリカル vs ディフェンシブの強弱が示す意味。2文で"
    },
    "rotation_map": {
        "overweight": [
            {"sector": "セクター名", "reason": "オーバーウェイトの理由を1文で"}
        ],
        "neutral": [
            {"sector": "セクター名", "reason": "中立の理由を1文で"}
        ],
        "underweight": [
            {"sector": "セクター名", "reason": "アンダーウェイトの理由を1文で"}
        ]
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "メインシナリオのタイトル",
            "next_3months": "今後3ヶ月のセクターローテーション予想",
            "next_6months": "3-6ヶ月後のセクター動向",
            "next_rotation": "次に資金が向かうセクターとその理由",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的なセクター配分アクション"
        },
        "bull_case": {
            "probability": 25,
            "title": "リスクオンシナリオのタイトル",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文",
            "winning_sectors": ["恩恵を受けるセクター1", "2"],
            "investment_action": "具体的な投資アクション"
        },
        "bear_case": {
            "probability": 25,
            "title": "リスクオフシナリオのタイトル",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文",
            "safe_sectors": ["逃避先セクター1", "2"],
            "investment_action": "具体的な投資アクション"
        }
    },
    "sector_pairs": {
        "most_telling_pair": "最も示唆的なセクターペアの比較（例: XLK vs XLPの動き）",
        "divergence_signal": "乖離から読み取れるシグナル"
    },
    "risk_monitor": {
        "watch_items": ["監視すべき指標やイベント1", "2", "3"],
        "next_inflection": "次のローテーション転換点はいつ・何がきっかけか"
    }
}"""

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": "claude-3-5-sonnet-20241022",
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


# セクター定義（SPDR ETFを使用）
SECTORS = {
    "テクノロジー (XLK)": "XLK",
    "一般消費財 (XLY)": "XLY",     # Amazon, Teslaなど（好況で強い）
    "通信サービス (XLC)": "XLC",   # Google, Metaなど
    "金融 (XLF)": "XLF",           # 金利上昇で強い
    "資本財 (XLI)": "XLI",         # 工場・防衛
    "エネルギー (XLE)": "XLE",     # 原油高で強い
    "素材 (XLB)": "XLB",
    "ヘルスケア (XLV)": "XLV",     # 不況に強い
    "生活必需品 (XLP)": "XLP",     # 不況に強い（P&G, CocaCola）
    "公益事業 (XLU)": "XLU",       # 不況に強い（電力）
    "不動産 (XLRE)": "XLRE"
}

# キャッシュ設定
@st.cache_data(ttl=3600)
def get_sector_data(period="3mo"):
    data_list = []
    hist_data = {}
    
    progress_text = "セクターデータを分析中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(SECTORS)

    for name, ticker in SECTORS.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} を取得中...")
            
            t = yf.Ticker(ticker)
            # 指定期間のデータを取得
            hist = t.history(period=period)
            
            if not hist.empty:
                # パフォーマンス計算（期間騰落率）
                start_price = hist['Close'].iloc[0]
                end_price = hist['Close'].iloc[-1]
                change_pct = ((end_price / start_price) - 1) * 100
                
                # チャート用データ（正規化）
                norm_price = (hist['Close'] / start_price) * 100
                hist_data[name] = norm_price

                data_list.append({
                    "Sector": name,
                    "Ticker": ticker,
                    "Change": change_pct,
                    "Price": end_price
                })
        except:
            pass
            
    my_bar.empty()
    return pd.DataFrame(data_list), pd.DataFrame(hist_data)

# --- サイドバーで期間選択 ---
with st.sidebar:
    st.header("⚙️ 分析期間")
    period_opt = st.selectbox(
        "期間を選択", 
        ["1mo", "3mo", "6mo", "1y", "ytd"], 
        index=1,
        format_func=lambda x: {
            "1mo": "過去1ヶ月 (短期トレンド)",
            "3mo": "過去3ヶ月 (中期トレンド)", 
            "6mo": "過去6ヶ月 (長期トレンド)",
            "1y": "過去1年",
            "ytd": "年初来"
        }[x]
    )

# --- メイン処理 ---
df, df_chart = get_sector_data(period_opt)

if df.empty:
    st.error("データ取得失敗")
else:
    # 1. サイクル診断 (簡易ロジック)
    st.subheader("🤖 AI景気サイクル診断")
    
    # 上位3セクターと下位3セクターを抽出
    df_sorted = df.sort_values(by="Change", ascending=False)
    top_sectors = df_sorted.head(3)["Sector"].tolist()
    
    # 診断ロジック
    cycle_status = "不明"
    cycle_msg = ""
    cycle_color = "blue"
    
    # キーワード判定
    is_defensive_strong = any(s in str(top_sectors) for s in ["ヘルスケア", "生活必需品", "公益事業"])
    is_tech_strong = any(s in str(top_sectors) for s in ["テクノロジー", "一般消費財", "通信"])
    is_energy_strong = any(s in str(top_sectors) for s in ["エネルギー", "素材"])
    
    if is_tech_strong and not is_defensive_strong:
        cycle_status = "好況 (Early/Mid Cycle) 🚀"
        cycle_msg = "リスクオン相場です。投資家は成長を求めてテクノロジーや消費財を買っています。"
        cycle_color = "green"
    elif is_energy_strong:
        cycle_status = "インフレ / 後期 (Late Cycle) 🔥"
        cycle_msg = "景気サイクルの終盤、またはインフレ懸念があります。実物資産（エネルギー・素材）が強いです。"
        cycle_color = "orange"
    elif is_defensive_strong:
        cycle_status = "後退 / 防衛 (Recession Fear) 🛡️"
        cycle_msg = "リスクオフ相場です。投資家は不況を警戒し、ディフェンシブ銘柄（生活必需品・ヘルスケア）に逃げています。"
        cycle_color = "red"
    else:
        cycle_status = "循環物色 / 混在 🔄"
        cycle_msg = "明確なトレンドがなく、セクターが循環しています。"

    st.markdown(f"""
    <div style="padding: 15px; border-radius: 10px; border: 2px solid {cycle_color}; background-color: rgba(0,0,0,0.2);">
        <h3 style="color: {cycle_color}; margin:0;">現在のフェーズ: {cycle_status}</h3>
        <p style="margin-top: 10px;">{cycle_msg}</p>
        <p><b>現在の勝ち組セクター:</b> {', '.join([s.split(' ')[0] for s in top_sectors])}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # 2. パフォーマンスランキング (横棒グラフ)
    st.subheader(f"📊 セクター別パフォーマンス ({period_opt})")
    
    # 色分け（プラスは緑、マイナスは赤）
    df_sorted["Color"] = df_sorted["Change"].apply(lambda x: "#00CC96" if x >= 0 else "#EF553B")
    
    fig_bar = px.bar(
        df_sorted, 
        x="Change", 
        y="Sector", 
        orientation='h',
        text_auto='.2f',
        title="騰落率ランキング (%)"
    )
    fig_bar.update_traces(marker_color=df_sorted["Color"], textposition="outside")
    fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="騰落率 (%)")
    st.plotly_chart(fig_bar, use_container_width=True)

    # 3. 比較チャート
    st.subheader("📈 トレンド推移チャート")
    st.markdown("どのセクターが勢いよく伸びているか（角度）を確認してください。")
    
    if not df_chart.empty:
        # データ量が多いので、見やすくするために線は細めに
        fig_line = px.line(
            df_chart, 
            x=df_chart.index, 
            y=df_chart.columns,
            title="セクター相対比較 (開始日=100)"
        )
        fig_line.update_layout(hovermode="x unified", yaxis_title="正規化価格")
        st.plotly_chart(fig_line, use_container_width=True)


    # 5. AI セクター分析
    st.markdown("---")
    st.subheader("🤖 AIセクターローテーション分析")
    st.caption("シニアセクターストラテジスト視点の分析")
    
    if st.button("🧠 AIでセクターローテーションを分析", use_container_width=True):
        with st.spinner("🔄 Claude AIがセクター動向を分析中..."):
            ai_result = call_sector_ai(df, df_chart, period_opt)
        
        if ai_result:
            # --- サイクルポジション ---
            cp = ai_result.get("cycle_position", {})
            current = cp.get("current_stage", 1)
            total = cp.get("total_stages", 4)
            stage_name = cp.get("stage_name", "")
            stages = cp.get("stages_map", [])
            
            st.markdown("### 📍 景気サイクル 現在地")
            
            cols_cycle = st.columns(total)
            for i, stage in enumerate(stages):
                with cols_cycle[i]:
                    is_current = (i + 1 == current)
                    if is_current:
                        st.markdown(f"""<div style="background: linear-gradient(135deg, #1a3a1a, #2d6a2d); padding: 10px; border-radius: 8px; text-align: center; border: 2px solid #27ae60;">
                            <div style="font-size: 1.4em; font-weight: bold;">🔄</div>
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
            st.progress(progress_pct, text=f"景気サイクル: Stage {current}/{total} - {stage_name}")
            
            evidence = cp.get("evidence", "")
            if evidence:
                st.info(f"📋 **判断根拠:** {evidence}")
            
            st.markdown("---")
            
            # --- 現状診断 ---
            diag = ai_result.get("current_diagnosis", {})
            st.markdown(f"### 🔍 現状診断: {diag.get('headline', '')}")
            st.markdown(diag.get("summary", ""))
            
            col_mf, col_cd = st.columns(2)
            with col_mf:
                st.markdown("**💰 資金フロー:**")
                st.markdown(diag.get("money_flow", ""))
            with col_cd:
                st.markdown("**⚖️ シクリカル vs ディフェンシブ:**")
                st.markdown(diag.get("cyclical_vs_defensive", ""))
            
            st.markdown("---")
            
            # --- ローテーションマップ ---
            rm = ai_result.get("rotation_map", {})
            if rm:
                st.markdown("### 🗺️ セクター配分マップ")
                col_ow, col_n, col_uw = st.columns(3)
                
                with col_ow:
                    st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 8px; border-top: 3px solid #09AB3B;">
                        <h4 style="color: #09AB3B; margin-top: 0;">🟢 オーバーウェイト</h4>""", unsafe_allow_html=True)
                    for item in rm.get("overweight", []):
                        st.markdown(f"**{item.get('sector', '')}**")
                        st.caption(item.get("reason", ""))
                    st.markdown("</div>", unsafe_allow_html=True)
                
                with col_n:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 15px; border-radius: 8px; border-top: 3px solid #f39c12;">
                        <h4 style="color: #f39c12; margin-top: 0;">🟡 ニュートラル</h4>""", unsafe_allow_html=True)
                    for item in rm.get("neutral", []):
                        st.markdown(f"**{item.get('sector', '')}**")
                        st.caption(item.get("reason", ""))
                    st.markdown("</div>", unsafe_allow_html=True)
                
                with col_uw:
                    st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 8px; border-top: 3px solid #FF4B4B;">
                        <h4 style="color: #FF4B4B; margin-top: 0;">🔴 アンダーウェイト</h4>""", unsafe_allow_html=True)
                    for item in rm.get("underweight", []):
                        st.markdown(f"**{item.get('sector', '')}**")
                        st.caption(item.get("reason", ""))
                    st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- シナリオ分析 ---
            st.markdown("### 🔮 フォワードシナリオ分析")
            
            scenarios = ai_result.get("forward_scenarios", {})
            
            base = scenarios.get("base_case", {})
            st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #27ae60; margin-bottom: 15px;">
                <h4 style="color: #27ae60; margin-top: 0;">🔄 メインシナリオ ({base.get('probability', 50)}%): {base.get('title', '')}</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px; color: #888; width: 140px;">3ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_3months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">6ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_6months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">次のローテーション</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_rotation', '')}</td></tr>
                </table>
                <p style="color: #27ae60; margin-bottom: 0;">💼 <b>アクション:</b> {base.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
            
            col_bull, col_bear = st.columns(2)
            
            bull = scenarios.get("bull_case", {})
            with col_bull:
                winners = ", ".join(bull.get("winning_sectors", []))
                st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B; height: 100%;">
                    <h4 style="color: #09AB3B; margin-top: 0;">🟢 リスクオン ({bull.get('probability', 25)}%): {bull.get('title', '')}</h4>
                    <p style="color: #ddd; font-size: 0.9em;">{bull.get('narrative', '')}</p>
                    <p style="color: #F7C948; font-size: 0.85em;">🏆 恩恵セクター: <b>{winners}</b></p>
                    <p style="color: #09AB3B; font-size: 0.85em; margin-bottom: 0;">💼 {bull.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            bear = scenarios.get("bear_case", {})
            with col_bear:
                safes = ", ".join(bear.get("safe_sectors", []))
                st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B; height: 100%;">
                    <h4 style="color: #FF4B4B; margin-top: 0;">🔴 リスクオフ ({bear.get('probability', 25)}%): {bear.get('title', '')}</h4>
                    <p style="color: #ddd; font-size: 0.9em;">{bear.get('narrative', '')}</p>
                    <p style="color: #F7C948; font-size: 0.85em;">🛡️ 逃避先: <b>{safes}</b></p>
                    <p style="color: #FF4B4B; font-size: 0.85em; margin-bottom: 0;">💼 {bear.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- セクターペア分析 ---
            pairs = ai_result.get("sector_pairs", {})
            if pairs:
                st.markdown("### 🔗 注目セクターペア")
                st.info(f"📊 **{pairs.get('most_telling_pair', '')}**")
                st.warning(f"📡 **シグナル:** {pairs.get('divergence_signal', '')}")
            
            st.markdown("---")
            
            # --- リスクモニター ---
            risk = ai_result.get("risk_monitor", {})
            st.markdown("### ⚠️ リスクモニター")
            watch = risk.get("watch_items", [])
            if watch:
                for w in watch:
                    st.markdown(f"- 👁️ {w}")
            inflection = risk.get("next_inflection", "")
            if inflection:
                st.error(f"🔄 **次のローテーション転換点:** {inflection}")


    # 4. セクター分類表
    with st.expander("📚 セクター分類の基礎知識 (クリックで開く)"):
        st.markdown("""
        | 分類 | セクター | 特徴 | 強い時期 |
        | :--- | :--- | :--- | :--- |
        | **シクリカル (景気敏感)** | **テクノロジー (XLK)**<br>**一般消費財 (XLY)**<br>**資本財 (XLI)**<br>**素材 (XLB)** | 景気が良いと業績が伸びる。<br>金利上昇には弱いことが多い。 | **不況からの回復期**<br>**好景気** |
        | **ディフェンシブ (安定)** | **ヘルスケア (XLV)**<br>**生活必需品 (XLP)**<br>**公益事業 (XLU)** | 不況でも薬や電気は使うため安定。<br>配当利回りが高い。 | **景気後退期**<br>**暴落時** |
        | **インフレヘッジ** | **エネルギー (XLE)**<br>**金融 (XLF)** | 原油高や金利上昇が利益になる。 | **景気過熱期 (インフレ)**<br>**利上げ局面** |
        """)