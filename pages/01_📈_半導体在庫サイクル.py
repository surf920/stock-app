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
st.set_page_config(page_title="半導体在庫サイクル", page_icon="📈", layout="wide")
st.title("半導体サイクル & 在庫トラッカー 2026 🚀")
st.markdown("現在値だけでなく、**「在庫が増えているか（悪化）」**、**「減っているか（改善）」**のトレンドを確認してください。")


# --- AI要約機能 ---
def call_semiconductor_ai(df_current, df_doi_hist):
    """半導体在庫データをClaude APIで分析"""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    # データをテキスト化
    data_text = "## 半導体企業 在庫データ (DOI = Days of Inventory)\n\n"
    for _, row in df_current.iterrows():
        doi_str = f"{row['DOI']:.1f}日" if row['DOI'] else "N/A"
        price_str = f"${row['Price']:.2f}" if row['Price'] else "N/A"
        data_text += f"- {row['Company']}: DOI={doi_str}, 株価={price_str}\n"

    if not df_doi_hist.empty:
        data_text += "\n## DOI推移 (四半期ごと)\n"
        for company in df_doi_hist["Company"].unique():
            hist = df_doi_hist[df_doi_hist["Company"] == company].sort_values("Date")
            vals = [f"{r['Date'].strftime('%Y-%m')}: {r['DOI']:.1f}日" for _, r in hist.iterrows()]
            data_text += f"- {company}: {' -> '.join(vals)}\n"

    system_prompt = """あなたはブリッジウォーターやルネサンステクノロジーズで20年の経験を持つ半導体セクター専門のシニアポートフォリオマネージャーです。

提供された在庫データ(DOI)を分析し、以下のJSON形式で回答してください。
ファンドの投資委員会に提出するレポートのように、具体的な数値と因果関係を明確にしてください。

【分析ルール】
1. 必ず具体的な数値を引用（例：「NVIDIAのDOIは117.5日で前期比+8.2日」）
2. DOI基準：>120日=在庫過多（警戒）、80-120日=適正、<80日=在庫不足
3. サイクルの「現在地」を明確にし、次に何が起きるか論理的に説明
4. 楽観・悲観の両シナリオを提示し、それぞれの確率と根拠を示す
5. データにない事実を捏造しない

【サイクル判定ルール（重要）】
- 複数企業でDOIが上昇傾向 → サイクル後半（Late Cycle）の可能性
- TSMCまたはNVIDIAのDOIが上昇転換 → 天井警戒シグナル（この2社は先行指標）
- メモリ企業（Micron）のDOI改善 → 回復の先行シグナル
- TXN（Texas Instruments）は遅行指標、最後に動く

【リスクレベル判定】
- Low: 過半数の企業がDOI<100日、上昇転換なし
- Medium: DOI 100-120日が中心、一部企業で上昇兆候
- High: 過半数がDOI>120日、NVIDIA/TSMCが上昇転換

【投資シグナル判定】
- BUY BIAS: DOI改善トレンド、サイクル初期〜中期
- HOLD: DOI横ばい、方向性不明確
- REDUCE RISK: DOI上昇トレンド、サイクル後期〜ピーク
{
    "cycle_position": {
        "total_stages": 6,
        "current_stage": 3,
        "stage_name": "在庫調整期",
        "stages_map": [
            {"stage": 1, "name": "需要急増・在庫枯渇", "description": "DOI<70日、供給不足でリードタイム長期化"},
            {"stage": 2, "name": "増産・設備投資拡大", "description": "DOI 70-90日、各社増産体制へ"},
            {"stage": 3, "name": "供給過剰・在庫積み上がり", "description": "DOI 90-130日、需要鈍化で在庫増"},
            {"stage": 4, "name": "在庫調整・減産", "description": "DOI>130日、減産・設備投資削減"},
            {"stage": 5, "name": "在庫消化・底打ち", "description": "DOI改善傾向、需要底入れ"},
            {"stage": 6, "name": "回復・新サイクル開始", "description": "DOI正常化、新規需要牽引"}
        ],
        "evidence": "現在のステージだと判断した根拠を2-3文で。具体数値必須"
    },
    "current_diagnosis": {
        "headline": "1行の見出し（例: 在庫調整の後半戦、底打ちの兆候も）",
        "summary": "現在の業況を4-5文で詳細に説明。各社のDOI数値を引用し、セクター全体の状態を診断",
        "demand_supply_balance": "需給バランスの現状を2文で",
        "leading_indicators": "先行指標（TSMCの在庫状況、メモリ価格動向など）の読み方を2文で"
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "メインシナリオのタイトル",
            "next_3months": "今後3ヶ月に起きること",
            "next_6months": "その後3-6ヶ月に起きること",
            "next_12months": "6-12ヶ月後の状態",
            "triggers": ["このシナリオが実現する条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "bull_case": {
            "probability": 25,
            "title": "楽観シナリオのタイトル",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文で",
            "triggers": ["このシナリオが実現する条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "bear_case": {
            "probability": 25,
            "title": "悲観シナリオのタイトル",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文で",
            "triggers": ["このシナリオが実現する条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        }
    },
    "company_positioning": [
        {
            "company": "企業名",
            "status": "最有望/有望/中立/注意/危険",
            "doi_assessment": "DOI数値とトレンドの評価を1文で",
            "cycle_role": "この企業がサイクルの中でどんな役割か（先行指標/遅行指標など）",
            "action": "買い/保有/売り/様子見"
        }
    ],
    "risk_monitor": {
        "watch_items": ["今後監視すべき指標やイベント1", "2", "3"],
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
        if response.status_code != 200:
            st.error(f"API HTTP {response.status_code}: {response.text[:300]}")
            return None
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
        if not text.strip():
            st.error("AIからの応答が空です。再試行してください。")
            return None
        return json.loads(text.strip())
    except Exception as e:
        st.error(f"AI分析エラー: {e}")
        return None


    # データをテキスト化
    data_text = "## 半導体企業 在庫データ (DOI = Days of Inventory)\n\n"
    for _, row in df_current.iterrows():
        doi_str = f"{row['DOI']:.1f}日" if row['DOI'] else "N/A"
        price_str = f"${row['Price']:.2f}" if row['Price'] else "N/A"
        data_text += f"- {row['Company']}: DOI={doi_str}, 株価={price_str}\n"

    if not df_doi_hist.empty:
        data_text += "\n## DOI推移 (四半期ごと)\n"
        for company in df_doi_hist["Company"].unique():
            hist = df_doi_hist[df_doi_hist["Company"] == company].sort_values("Date")
            vals = [f"{r['Date'].strftime('%Y-%m')}: {r['DOI']:.1f}日" for _, r in hist.iterrows()]
            data_text += f"- {company}: {' → '.join(vals)}\n"

    system_prompt = """あなたは半導体業界の専門アナリストです。
提供された在庫データ(DOI: Days of Inventory)を分析し、以下のJSON形式で回答してください。
日本語で回答してください。

【ルール】
1. 必ず具体的な数値を引用すること（例: 「NVIDIAのDOIは117.5日」）
2. DOI > 120日は在庫過多（警戒）、DOI < 80日は在庫不足、80-120日は適正
3. 前回比でDOIが増加→在庫積み上がり（悪化）、減少→在庫消化（改善）
4. データにない事実を捏造しないこと

{
    "cycle_phase": "回復初期/回復中期/ピーク/調整/底打ち のいずれか",
    "summary": "3-4文で現在の半導体サイクル全体を要約",
    "company_insights": [
        {"company": "企業名", "status": "良好/注意/警戒", "comment": "1文コメント"}
    ],
    "investment_signal": "強気/やや強気/中立/やや弱気/弱気",
    "key_points": ["ポイント1", "ポイント2", "ポイント3"],
    "outlook": "今後3-6ヶ月の見通しを2-3文で"
}"""

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 2048,
        "system": system_prompt,
        "messages": [{"role": "user", "content": data_text}]
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=60
        )
        if response.status_code != 200:
            st.error(f"API HTTP {response.status_code}: {response.text[:300]}")
            return None
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
        if not text.strip():
            st.error("AIからの応答が空です。再試行してください。")
            return None
        return json.loads(text.strip())
    except Exception as e:
        st.error(f"AI分析エラー: {e}")
        return None


# キャッシュ設定
@st.cache_data(ttl=3600)
def get_semiconductor_data():
    tickers = {
        "NVIDIA": "NVDA", "Micron": "MU", "TSMC": "TSM", 
        "Samsung": "005930.KS", "Intel": "INTC", "AMD": "AMD",
        "Qualcomm": "QCOM", "Texas Instruments": "TXN"
    }
    
    current_data_list = []
    doi_history_list = [] # 過去の推移用データ
    stock_history_list = {} 
    
    # プログレスバー
    progress_text = "財務データと過去のトレンドを取得中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(tickers)

    for name, ticker in tickers.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} のデータを分析中...")
            
            stock = yf.Ticker(ticker)
            
            # 1. 株価チャート用データ (1ヶ月)
            hist = stock.history(period="1mo")
            if not hist.empty:
                norm_price = (hist['Close'] / hist['Close'].iloc[0]) * 100
                stock_history_list[name] = norm_price
                price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else price
            else:
                price = None; prev_price = None
            
            # 2. 財務データ（過去のDOI推移も取得）
            current_doi = None
            current_inv = None
            
            try:
                # 四半期ごとのデータを取得
                q_bs = stock.quarterly_balance_sheet
                q_fin = stock.quarterly_financials
                
                if not q_bs.empty and not q_fin.empty:
                    # 共通の日付（カラム）を探す
                    valid_dates = q_bs.columns.intersection(q_fin.columns)
                    
                    # 各四半期のDOIを計算してリストに追加
                    for date in valid_dates:
                        try:
                            inv_val = q_bs.loc["Inventory", date] if "Inventory" in q_bs.index else 0
                            
                            cogs = 0
                            if "Cost Of Revenue" in q_fin.index:
                                cogs = q_fin.loc["Cost Of Revenue", date]
                            elif "Cost Of Goods Sold" in q_fin.index:
                                cogs = q_fin.loc["Cost Of Goods Sold", date]
                            
                            if cogs > 0:
                                doi_val = (inv_val / cogs) * 90
                                # 推移データに追加
                                doi_history_list.append({
                                    "Company": name,
                                    "Date": date,
                                    "DOI": doi_val
                                })
                                
                                # 最新の日付なら現在値として保持
                                if date == valid_dates[0]: # 列の最初が最新
                                    current_doi = doi_val
                                    current_inv = inv_val
                        except:
                            pass
                            
            except:
                pass

            current_data_list.append({
                "Company": name, "Ticker": ticker,
                "Price": price, "PrevPrice": prev_price,
                "DOI": current_doi, "Inventory": current_inv
            })
            
        except Exception:
            pass
            
    my_bar.empty()
    
    # DataFrame化
    df_current = pd.DataFrame(current_data_list)
    df_doi_hist = pd.DataFrame(doi_history_list)
    df_stock_hist = pd.DataFrame(stock_history_list) if stock_history_list else pd.DataFrame()
    
    return df_current, df_doi_hist, df_stock_hist

# --- メイン処理 ---
df, df_doi_hist, df_stock_chart = get_semiconductor_data()

if df.empty:
    st.warning("データが取得できませんでした。")
else:
    # 1. 上部カードセクション
    st.subheader("🔥 主要企業の在庫状況 (最新)")
    cols = st.columns(4)
    for index, row in df.iterrows():
        with cols[index % 4]:
            p_str = f"${row['Price']:.2f}" if row['Price'] else "N/A"
            
            # --- 色分け & トレンド判定 ---
            trend_arrow = ""
            if row['DOI']:
                doi_val = row['DOI']
                
                # 直近のトレンドを確認（もし履歴があれば）
                if not df_doi_hist.empty:
                    company_hist = df_doi_hist[df_doi_hist["Company"] == row["Company"]].sort_values("Date")
                    # ここがエラーのあった箇所です。修正済みです。
                    if len(company_hist) >= 2:
                        prev_doi = company_hist.iloc[-2]["DOI"] # 前回のDOI
                        if doi_val > prev_doi:
                            trend_arrow = " ↗︎(増)" # 悪化
                        else:
                            trend_arrow = " ↘︎(減)" # 改善

                if doi_val > 120:
                    delta_msg = f"在庫過多{trend_arrow}"; color = "inverse" # 赤
                elif doi_val < 80:
                    delta_msg = f"在庫不足{trend_arrow}"; color = "normal" # 緑
                else:
                    delta_msg = f"適正{trend_arrow}"; color = "off"
                
                doi_str = f"{doi_val:.1f}日"
            else:
                doi_str = "-"
                delta_msg = None
                color = "off"
            
            st.metric(label=row['Company'], value=doi_str, delta=delta_msg, delta_color=color)
            st.caption(f"株価: {p_str}")
            st.markdown("---")

    # 2. 在庫サイクルの推移チャート
    st.subheader("📊 在庫サイクル (DOI) の推移")
    st.markdown("線の向きに注目してください。**右肩下がり（↘︎）なら在庫がはけている良い兆候**です。")
    
    if not df_doi_hist.empty:
        # 日付でソート
        df_doi_hist = df_doi_hist.sort_values("Date")
        
        # 折れ線グラフ
        fig_doi = px.line(
            df_doi_hist, 
            x="Date", 
            y="DOI", 
            color="Company",
            markers=True,
            title="過去1年の在庫日数 (DOI) の変化"
        )
        # 危険ラインと好機ラインを描画
        fig_doi.add_hline(y=120, line_dash="dot", line_color="red", annotation_text="警戒ライン (120日)")
        fig_doi.add_hline(y=80, line_dash="dot", line_color="green", annotation_text="好機ライン (80日)")
        
        st.plotly_chart(fig_doi, use_container_width=True)
    else:
        st.info("過去の財務データが取得できませんでした。")

    # 3. 株価パフォーマンス
    with st.expander("📈 株価の推移を見る (過去1ヶ月)", expanded=False):
        if not df_stock_chart.empty:
            fig_stock = px.line(df_stock_chart, x=df_stock_chart.index, y=df_stock_chart.columns)
            st.plotly_chart(fig_stock, use_container_width=True)

    # 4. データテーブル
    st.subheader("📊 詳細データ一覧")
    
    # 色付けロジック
    def highlight_doi(val):
        if val is None or pd.isna(val): return None
        if val > 120: return 'color: #FF4B4B; font-weight: bold;'
        elif val < 80: return 'color: #09AB3B; font-weight: bold;'
        return None

    # 並び替え
    df_display = df.sort_values(by="DOI", ascending=False)[['Company', 'Price', 'DOI', 'Inventory']]
    
    # テーブル表示
    st.dataframe(
        df_display.style.map(highlight_doi, subset=['DOI']).format({
            "Price": "${:.2f}", 
            "DOI": "{:.1f} 日", 
            "Inventory": "${:.2e}"
        }),
        hide_index=True,
        use_container_width=True
    )


    # 5. AI要約セクション
    st.markdown("---")
    st.subheader("🤖 AI半導体サイクル分析")
    st.caption("ブリッジウォーター流マクロ分析 × 半導体セクター専門知見")
    
    if st.button("🧠 AIで在庫サイクルを分析", use_container_width=True):
        with st.spinner("🔄 Claude AIが半導体サイクルを分析中..."):
            ai_result = call_semiconductor_ai(df, df_doi_hist)
        
        if ai_result:
            # --- サイクルポジション ---
            cp = ai_result.get("cycle_position", {})
            current = cp.get("current_stage", 1)
            total = cp.get("total_stages", 6)
            stage_name = cp.get("stage_name", "")
            stages = cp.get("stages_map", [])
            
            st.markdown("### 📍 半導体サイクル 現在地")
            
            # サイクルマップを視覚化
            cols_cycle = st.columns(total)
            for i, stage in enumerate(stages):
                with cols_cycle[i]:
                    is_current = (i + 1 == current)
                    if is_current:
                        st.markdown(f"""<div style="background: linear-gradient(135deg, #FF6B35, #F7C948); padding: 10px; border-radius: 8px; text-align: center; border: 2px solid #F7C948;">
                            <div style="font-size: 1.4em; font-weight: bold;">📍</div>
                            <div style="font-size: 0.75em; font-weight: bold; color: #000;">Stage {i+1}</div>
                            <div style="font-size: 0.65em; color: #000;">{stage.get('name', '')}</div>
                        </div>""", unsafe_allow_html=True)
                    else:
                        opacity = "0.4" if abs(i + 1 - current) > 1 else "0.7"
                        st.markdown(f"""<div style="background: #262730; padding: 10px; border-radius: 8px; text-align: center; opacity: {opacity}; border: 1px solid #41444C;">
                            <div style="font-size: 1.2em;">{"✅" if i + 1 < current else "⬜"}</div>
                            <div style="font-size: 0.7em; color: #888;">Stage {i+1}</div>
                            <div style="font-size: 0.6em; color: #888;">{stage.get('name', '')}</div>
                        </div>""", unsafe_allow_html=True)
            
            # 進捗バー
            progress_pct = current / total
            st.progress(progress_pct, text=f"サイクル進行度: Stage {current}/{total} - {stage_name}")
            
            # 判断根拠
            evidence = cp.get("evidence", "")
            if evidence:
                st.info(f"📋 **判断根拠:** {evidence}")
            
            st.markdown("---")
            
            # --- 現状診断 ---
            diag = ai_result.get("current_diagnosis", {})
            headline = diag.get("headline", "")
            st.markdown(f"### 🔍 現状診断: {headline}")
            st.markdown(diag.get("summary", ""))
            
            col_ds, col_li = st.columns(2)
            with col_ds:
                st.markdown(f"**⚖️ 需給バランス:**")
                st.markdown(diag.get("demand_supply_balance", ""))
            with col_li:
                st.markdown(f"**📡 先行指標の読み:**")
                st.markdown(diag.get("leading_indicators", ""))
            
            st.markdown("---")
            
            # --- シナリオ分析 ---
            st.markdown("### 🔮 フォワードシナリオ分析")
            
            scenarios = ai_result.get("forward_scenarios", {})
            
            # メインシナリオ
            base = scenarios.get("base_case", {})
            st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #4ECDC4; margin-bottom: 15px;">
                <h4 style="color: #4ECDC4; margin-top: 0;">📊 メインシナリオ ({base.get('probability', 50)}%): {base.get('title', '')}</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px; color: #888; width: 120px;">3ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_3months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">6ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_6months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">12ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_12months', '')}</td></tr>
                </table>
                <p style="color: #4ECDC4; margin-bottom: 0;">💼 <b>アクション:</b> {base.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
            
            # 楽観・悲観を横並び
            col_bull, col_bear = st.columns(2)
            
            bull = scenarios.get("bull_case", {})
            with col_bull:
                st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B; height: 100%;">
                    <h4 style="color: #09AB3B; margin-top: 0;">🟢 楽観 ({bull.get('probability', 25)}%): {bull.get('title', '')}</h4>
                    <p style="color: #ddd; font-size: 0.9em;">{bull.get('narrative', '')}</p>
                    <p style="color: #09AB3B; font-size: 0.85em; margin-bottom: 0;">💼 {bull.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            bear = scenarios.get("bear_case", {})
            with col_bear:
                st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B; height: 100%;">
                    <h4 style="color: #FF4B4B; margin-top: 0;">🔴 悲観 ({bear.get('probability', 25)}%): {bear.get('title', '')}</h4>
                    <p style="color: #ddd; font-size: 0.9em;">{bear.get('narrative', '')}</p>
                    <p style="color: #FF4B4B; font-size: 0.85em; margin-bottom: 0;">💼 {bear.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- 企業ポジショニング ---
            st.markdown("### 🏢 企業別ポジショニング")
            companies = ai_result.get("company_positioning", [])
            if companies:
                for comp in companies:
                    status = comp.get("status", "")
                    emoji_map = {"最有望": "🟢", "有望": "🟢", "中立": "🟡", "注意": "🟠", "危険": "🔴"}
                    action_map = {"買い": "🟢", "保有": "🟡", "売り": "🔴", "様子見": "⚪"}
                    e = emoji_map.get(status, "⚪")
                    a = action_map.get(comp.get("action", ""), "⚪")
                    
                    st.markdown(f"""**{e} {comp.get('company', '')}** | 判定: **{status}** | アクション: {a} **{comp.get('action', '')}**""")
                    st.caption(f"📊 {comp.get('doi_assessment', '')} | 🔄 {comp.get('cycle_role', '')}")
            
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


    # 凡例（Markdownで安全に表示）
    st.markdown("""
    <div style="background-color: #262730; padding: 15px; border-radius: 5px; border: 1px solid #41444C;">
        <b>💡 チャートの見方</b>
        <ul>
            <li><b>グラフが右肩上がり (↗︎)</b>: 在庫が積み上がっています。売れ残りリスク上昇（警戒）。</li>
            <li><b>グラフが右肩下がり (↘︎)</b>: 在庫が消化されています。需要回復のサイン（好感）。</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)