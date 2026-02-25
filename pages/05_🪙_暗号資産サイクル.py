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
st.set_page_config(page_title="暗号資産サイクル", page_icon="🪙", layout="wide")
st.title("暗号資産(クリプト) & リスクセンチメント 🪙")
st.markdown("「炭鉱のカナリア」であるビットコイン(BTC)の動きから、市場全体のリスク許容度を測ります。")


# --- AI要約機能 ---
def call_crypto_ai(df_current, df_chart):
    """暗号資産データをClaude APIで分析"""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    data_text = "## 暗号資産データ\n\n"
    data_text += "### 現在値・RSI\n"
    for _, row in df_current.iterrows():
        diff = row['Price'] - row['Prev']
        pct = (diff / row['Prev']) * 100 if row['Prev'] > 0 else 0
        rsi_status = "過熱" if row['RSI'] >= 70 else ("底値圏" if row['RSI'] <= 30 else "中立")
        data_text += f"- {row['Name']}: ${row['Price']:,.2f} (前日比: {pct:+.1f}%), RSI={row['RSI']:.1f} ({rsi_status})\n"

    if not df_chart.empty:
        data_text += "\n### 期間別パフォーマンス (正規化: 1年前=100)\n"
        latest = df_chart.iloc[-1]
        for label, days in [("1週間", 5), ("1ヶ月", 20), ("3ヶ月", 60), ("6ヶ月", 120)]:
            if len(df_chart) > days:
                past = df_chart.iloc[-days]
                data_text += f"\n{label}変化:\n"
                for col in df_chart.columns:
                    chg = latest[col] - past[col]
                    data_text += f"- {col}: {chg:+.1f}%\n"

        # BTC vs Nasdaq相関
        if "Bitcoin" in df_chart.columns and "Nasdaq100" in df_chart.columns:
            corr_3m = df_chart.tail(60)["Bitcoin"].corr(df_chart.tail(60)["Nasdaq100"])
            corr_full = df_chart["Bitcoin"].corr(df_chart["Nasdaq100"])
            data_text += f"\n### 相関分析\n"
            data_text += f"- BTC-Nasdaq 直近3ヶ月相関: {corr_3m:.2f}\n"
            data_text += f"- BTC-Nasdaq 全期間相関: {corr_full:.2f}\n"
        if "Bitcoin" in df_chart.columns and "Gold" in df_chart.columns:
            corr_gold = df_chart.tail(60)["Bitcoin"].corr(df_chart.tail(60)["Gold"])
            data_text += f"- BTC-Gold 直近3ヶ月相関: {corr_gold:.2f}\n"

        # 現在値レベル
        data_text += f"\n### 1年パフォーマンス\n"
        for col in df_chart.columns:
            data_text += f"- {col}: {latest[col]:.1f} (1年前=100, {latest[col]-100:+.1f}%)\n"

    system_prompt = """あなたはパンテラキャピタルやギャラクシーデジタルで10年の経験を持つ暗号資産専門のチーフストラテジストです。
ビットコインの半減期サイクル、オンチェーンデータ、マクロ環境の三位一体で分析します。

提供されたデータを分析し、以下のJSON形式で回答してください。
クリプトファンドの投資委員会に提出するレポートのように、具体数値と因果関係を明確にしてください。

【分析ルール】
1. 必ず具体的な数値を引用（BTC価格、RSI、変動率、相関係数）
2. RSI基準: >70=過熱、30-70=中立、<30=底値圏
3. BTC半減期サイクル（約4年周期）の現在地を意識
4. BTCとNasdaq/Goldの相関から「リスク資産 or 安全資産」性質を判断
5. データにない事実を捏造しない

{
    "cycle_position": {
        "total_stages": 6,
        "current_stage": 3,
        "stage_name": "現在のステージ名",
        "stages_map": [
            {"stage": 1, "name": "底値形成・蓄積期", "description": "弱気相場の底、長期投資家が蓄積"},
            {"stage": 2, "name": "回復・初期上昇", "description": "半減期前後、徐々に価格回復"},
            {"stage": 3, "name": "本格上昇・強気相場", "description": "機関投資家参入、史上最高値更新"},
            {"stage": 4, "name": "過熱・バブル形成", "description": "RSI高水準、一般投資家殺到、レバレッジ過大"},
            {"stage": 5, "name": "天井・分配期", "description": "大口が売り抜け、ボラティリティ急上昇"},
            {"stage": 6, "name": "暴落・弱気相場", "description": "パニック売り、レバレッジ崩壊、長期低迷"}
        ],
        "evidence": "現在のステージだと判断した根拠を2-3文で。具体数値必須",
        "halving_context": "直近の半減期（2024年4月）からの経過と、過去サイクルとの比較を1-2文で"
    },
    "current_diagnosis": {
        "headline": "1行の見出し",
        "summary": "現在の暗号資産市場を4-5文で詳細に説明。BTC/ETH/SOLの価格とRSIを引用",
        "risk_character": "現在BTCは「リスク資産」「安全資産」どちらの性質が強いか。相関データから判断。2文で",
        "momentum": "モメンタム（RSI・トレンド）の評価を2文で"
    },
    "asset_breakdown": {
        "btc": {
            "outlook": "BTCの見通しを2文で",
            "key_level": "注目すべき価格水準（サポート/レジスタンス）",
            "signal": "強気/中立/弱気"
        },
        "eth": {
            "outlook": "ETHの見通しを2文で",
            "vs_btc": "対BTC比率のトレンドと意味",
            "signal": "強気/中立/弱気"
        },
        "sol": {
            "outlook": "SOLの見通しを2文で",
            "narrative": "SOL固有の注目テーマ",
            "signal": "強気/中立/弱気"
        }
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "メインシナリオのタイトル",
            "btc_range": "3ヶ月後のBTC予想レンジ",
            "next_3months": "今後3ヶ月に起きること",
            "next_6months": "その後3-6ヶ月に起きること",
            "next_12months": "6-12ヶ月後の状態",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "bull_case": {
            "probability": 25,
            "title": "強気シナリオのタイトル",
            "btc_target": "BTCターゲット",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "bear_case": {
            "probability": 25,
            "title": "弱気シナリオのタイトル",
            "btc_target": "BTC下値ターゲット",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        }
    },
    "market_structure": {
        "institutional_flow": "機関投資家のフロー状況（ETF流入、CME建玉など）",
        "retail_sentiment": "個人投資家のセンチメント（過熱/冷静/恐怖）",
        "defi_health": "DeFi市場の健全性"
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


# キャッシュ設定
@st.cache_data(ttl=300) # クリプトは動きが速いのでキャッシュ短め
def get_crypto_data():
    tickers = {
        "Bitcoin": "BTC-USD",
        "Ethereum": "ETH-USD",
        "Solana": "SOL-USD",
        "Nasdaq100": "QQQ",    # 比較用（ハイテク株）
        "Gold": "GLD"          # 比較用（安全資産）
    }
    
    data_list = []
    hist_data = {} # チャート用データを一時保存
    
    progress_text = "暗号資産データを取得中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(tickers)

    for name, ticker in tickers.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} のデータを取得中...")
            
            t = yf.Ticker(ticker)
            
            # 過去1年分
            hist = t.history(period="1y")
            
            if not hist.empty:
                # 最新価格
                price = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2] if len(hist) > 1 else price
                
                # RSIの計算 (14日)
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                # ゼロ除算対策
                if not rs.empty and rs.iloc[-1] is not None:
                     rsi = 100 - (100 / (1 + rs)).iloc[-1]
                else:
                     rsi = 50 # 計算不能時は中立
                
                # チャート用データ（Seriesとして保存）
                # ここではまだ正規化せず、結合してから処理する
                hist_data[name] = hist['Close']

                data_list.append({
                    "Name": name,
                    "Price": price,
                    "Prev": prev,
                    "RSI": rsi
                })
        except:
            pass
            
    my_bar.empty()
    
    # --- チャートデータの整形処理 (ここを修正) ---
    if hist_data:
        # 1. 全てのSeriesを1つのDataFrameに結合（外部結合で日付を網羅）
        df_merged = pd.concat(hist_data.values(), axis=1, keys=hist_data.keys())
        
        # 2. データの隙間（土日など）を前日の値で埋める
        df_merged = df_merged.ffill()
        
        # 3. 欠損が残っている行（開始時点など）を削除
        df_merged = df_merged.dropna()
        
        # 4. 正規化（スタート地点を100にする）
        # 各列の最初の値で割って100を掛ける
        df_chart = df_merged.apply(lambda x: (x / x.iloc[0]) * 100)
    else:
        df_chart = pd.DataFrame()
        
    return pd.DataFrame(data_list), df_chart

# --- メイン処理 ---
df, df_chart = get_crypto_data()

if df.empty:
    st.error("データ取得失敗")
else:
    # 1. 価格 & RSIボード
    st.subheader("📊 現在の価格と過熱感 (RSI)")
    st.caption("RSIが **70以上** なら「買われすぎ（過熱）」、**30以下** なら「売られすぎ（底値圏）」です。")
    
    cols = st.columns(3)
    # 主要クリプト3種のみ表示
    crypto_list = ["Bitcoin", "Ethereum", "Solana"]
    
    for i, target_name in enumerate(crypto_list):
        # 該当する行を探す
        rows = df[df["Name"] == target_name]
        if not rows.empty:
            row = rows.iloc[0]
            with cols[i]:
                # 価格表示
                diff = row["Price"] - row["Prev"]
                st.metric(
                    label=row["Name"],
                    value=f"${row['Price']:,.2f}",
                    delta=f"{diff:+,.2f}"
                )
                
                # RSIメーター
                rsi_val = row["RSI"]
                rsi_color = "off"
                if rsi_val >= 70: rsi_color = "inverse" # 赤（危険）
                elif rsi_val <= 30: rsi_color = "normal" # 緑（チャンス）
                
                # プログレスバー（範囲外エラー防止）
                bar_val = max(0.0, min(rsi_val / 100, 1.0))
                st.progress(bar_val)
                st.caption(f"RSI: **{rsi_val:.1f}** ({'🔥 過熱' if rsi_val>=70 else ('🥶 底値' if rsi_val<=30 else '中立')})")
                st.markdown("---")

    # 2. 相関チャート (BTC vs Nasdaq vs Gold)
    st.subheader("📈 ビットコインは何と連動しているか？")
    st.markdown("BTC（青）が **Nasdaq（赤）** と一緒に動くなら「リスク資産」、**Gold（黄）** と動くなら「安全資産」としての性質が強まっています。")
    
    if not df_chart.empty:
        # 表示したい列だけを抽出（存在確認してから）
        target_cols = [c for c in ["Bitcoin", "Nasdaq100", "Gold"] if c in df_chart.columns]
        
        if target_cols:
            fig = px.line(
                df_chart, 
                x=df_chart.index, 
                y=target_cols,
                title="相対パフォーマンス比較 (1年前=100)",
                color_discrete_map={
                    "Bitcoin": "#00CC96",  # 青緑
                    "Nasdaq100": "#EF553B", # 赤
                    "Gold": "#FFD700"      # 金色
                }
            )
            # デザイン調整
            fig.update_layout(
                hovermode="x unified", 
                yaxis_title="騰落率 (スタート=100)",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#444")
            )
            # 線を少し太く
            fig.update_traces(line=dict(width=2))
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("比較用のデータ（BTC, Nasdaq, Gold）が揃っていません。")
    else:
        st.warning("チャートデータを作成できませんでした。")

    # 3. 投資判断のヒント
    st.info("""
    **💡 分析のポイント**
    * **BTCとNasdaqの乖離（デカップリング）**: 
        * 株が下がっているのにBTCだけ強い場合 ➡ 資金が「次世代の逃避先」として暗号資産に流れている可能性があります（強い買いシグナル）。
    * **RSIの逆張り**: 
        * 強い上昇トレンドでも、RSIが80を超えたら一旦調整（下落）することが多いです。
    """)

    # --- AI暗号資産分析セクション ---
    st.markdown("---")
    st.subheader("🤖 AI暗号資産サイクル分析")
    st.caption("クリプトファンド チーフストラテジスト視点の分析")
    
    if st.button("🧠 AIで暗号資産サイクルを分析", use_container_width=True):
        with st.spinner("🔄 Claude AIが暗号資産市場を分析中..."):
            ai_result = call_crypto_ai(df, df_chart)
        
        if ai_result:
            # --- サイクルポジション ---
            cp = ai_result.get("cycle_position", {})
            current = cp.get("current_stage", 1)
            total = cp.get("total_stages", 6)
            stage_name = cp.get("stage_name", "")
            stages = cp.get("stages_map", [])
            
            st.markdown("### 📍 暗号資産サイクル 現在地")
            
            cols_cycle = st.columns(total)
            for i, stage in enumerate(stages):
                with cols_cycle[i]:
                    is_current = (i + 1 == current)
                    if is_current:
                        st.markdown(f"""<div style="background: linear-gradient(135deg, #1a0a3e, #4a1a8e); padding: 10px; border-radius: 8px; text-align: center; border: 2px solid #9b59b6;">
                            <div style="font-size: 1.4em; font-weight: bold;">🪙</div>
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
            halving = cp.get("halving_context", "")
            if halving:
                st.warning(f"⛏️ **半減期サイクル:** {halving}")
            
            st.markdown("---")
            
            # --- 現状診断 ---
            diag = ai_result.get("current_diagnosis", {})
            st.markdown(f"### 🔍 現状診断: {diag.get('headline', '')}")
            st.markdown(diag.get("summary", ""))
            
            col_rc, col_mom = st.columns(2)
            with col_rc:
                st.markdown("**🔗 リスク資産 or 安全資産:**")
                st.markdown(diag.get("risk_character", ""))
            with col_mom:
                st.markdown("**📊 モメンタム:**")
                st.markdown(diag.get("momentum", ""))
            
            st.markdown("---")
            
            # --- 資産別ブレイクダウン ---
            breakdown = ai_result.get("asset_breakdown", {})
            if breakdown:
                st.markdown("### 💰 資産別見通し")
                cols_bd = st.columns(3)
                items = [
                    ("₿ Bitcoin", "btc", "#F7931A"),
                    ("Ξ Ethereum", "eth", "#627EEA"),
                    ("◎ Solana", "sol", "#9945FF")
                ]
                for idx, (label, key, color) in enumerate(items):
                    with cols_bd[idx]:
                        item = breakdown.get(key, {})
                        signal = item.get("signal", "中立")
                        signal_emoji = {"強気": "🟢", "中立": "🟡", "弱気": "🔴"}.get(signal, "⚪")
                        sub_text = item.get("key_level", item.get("vs_btc", item.get("narrative", "")))
                        st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-top: 3px solid {color};">
                            <h4 style="color: {color}; margin: 0 0 8px 0;">{label}</h4>
                            <p style="color: #ddd; font-size: 0.85em; margin: 0 0 5px 0;">{item.get('outlook', '')}</p>
                            <p style="color: #888; font-size: 0.75em; margin: 0 0 5px 0;">📌 {sub_text}</p>
                            <p style="margin: 0; font-size: 0.9em;">{signal_emoji} <b>{signal}</b></p>
                        </div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- シナリオ分析 ---
            st.markdown("### 🔮 フォワードシナリオ分析")
            
            scenarios = ai_result.get("forward_scenarios", {})
            
            base = scenarios.get("base_case", {})
            st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #9b59b6; margin-bottom: 15px;">
                <h4 style="color: #9b59b6; margin-top: 0;">🪙 メインシナリオ ({base.get('probability', 50)}%): {base.get('title', '')}</h4>
                <p style="color: #F7C948; font-size: 1.1em;">📊 BTC予想レンジ: <b>{base.get('btc_range', '')}</b></p>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px; color: #888; width: 120px;">3ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_3months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">6ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_6months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">12ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_12months', '')}</td></tr>
                </table>
                <p style="color: #9b59b6; margin-bottom: 0;">💼 <b>アクション:</b> {base.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
            
            col_bull, col_bear = st.columns(2)
            
            bull = scenarios.get("bull_case", {})
            with col_bull:
                st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B; height: 100%;">
                    <h4 style="color: #09AB3B; margin-top: 0;">🟢 強気 ({bull.get('probability', 25)}%): {bull.get('title', '')}</h4>
                    <p style="color: #F7C948;">🎯 BTC: <b>{bull.get('btc_target', '')}</b></p>
                    <p style="color: #ddd; font-size: 0.9em;">{bull.get('narrative', '')}</p>
                    <p style="color: #09AB3B; font-size: 0.85em; margin-bottom: 0;">💼 {bull.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            bear = scenarios.get("bear_case", {})
            with col_bear:
                st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B; height: 100%;">
                    <h4 style="color: #FF4B4B; margin-top: 0;">🔴 弱気 ({bear.get('probability', 25)}%): {bear.get('title', '')}</h4>
                    <p style="color: #F7C948;">🎯 BTC: <b>{bear.get('btc_target', '')}</b></p>
                    <p style="color: #ddd; font-size: 0.9em;">{bear.get('narrative', '')}</p>
                    <p style="color: #FF4B4B; font-size: 0.85em; margin-bottom: 0;">💼 {bear.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- マーケット構造 ---
            structure = ai_result.get("market_structure", {})
            if structure:
                st.markdown("### 🏗️ マーケット構造")
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #3498db;">
                        <p style="color: #3498db; font-weight: bold; margin: 0 0 5px 0;">🏦 機関投資家フロー</p>
                        <p style="color: #ddd; font-size: 0.85em; margin: 0;">{structure.get('institutional_flow', '')}</p>
                    </div>""", unsafe_allow_html=True)
                with col_s2:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #f39c12;">
                        <p style="color: #f39c12; font-weight: bold; margin: 0 0 5px 0;">👤 個人センチメント</p>
                        <p style="color: #ddd; font-size: 0.85em; margin: 0;">{structure.get('retail_sentiment', '')}</p>
                    </div>""", unsafe_allow_html=True)
                with col_s3:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #2ecc71;">
                        <p style="color: #2ecc71; font-weight: bold; margin: 0 0 5px 0;">🔗 DeFi健全性</p>
                        <p style="color: #ddd; font-size: 0.85em; margin: 0;">{structure.get('defi_health', '')}</p>
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
