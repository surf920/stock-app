import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import datetime

st.set_page_config(page_title="Alice Diagnosis", page_icon="🐇", layout="wide")

st.title("🐇 Alice Diagnosis: 信用収縮と流動性ドミノ")
st.markdown("市場の表面（株価）ではなく、裏側の「信用」と「流動性」の詰まりを監視するアリス・ロジックに基づく診断パネルです。")

# --- 関数: データ取得と整形 ---
@st.cache_data(ttl=3600)
def get_alice_data():
    # 取得リスト
    tickers = ['BIZD', 'HYG', 'DX-Y.NYB', 'IGV', '^GSPC', 'BTC-USD', 'INTU', 'CRM', 'ADBE']
    
    try:
        data = yf.download(tickers, period="1y", interval="1d")
        
        # yfinanceの仕様変更対応（MultiIndexのカラムをフラットにする）
        if isinstance(data.columns, pd.MultiIndex):
            try:
                data = data['Close'] # Closeのみ取得
            except KeyError:
                # Closeがない場合の保険
                data = data.xs('Close', level=0, axis=1, drop_level=True)
        
        # 欠損値の前方埋め
        data = data.ffill()
        return data
    except Exception as e:
        return pd.DataFrame()

try:
    df = get_alice_data()
    
    # データが空、または必要な列が足りない場合のチェック
    required_cols = ['^GSPC', 'BTC-USD']
    if df.empty or not all(col in df.columns for col in required_cols):
        st.warning("⚠️ 現在、一部のデータが取得できません（API接続エラー）。しばらく待ってからリロードしてください。")
        st.stop() # ここで安全に止める

    latest = df.iloc[-1]
    
    # --- 指標計算 (安全第一) ---
    # 移動平均
    ma_50 = df.rolling(window=50).mean().iloc[-1]
    ma_200 = df.rolling(window=200).mean().iloc[-1]
    
    # DXY (存在確認)
    if 'DX-Y.NYB' in df.columns:
        dxy_val = latest['DX-Y.NYB']
        dxy_mean = df['DX-Y.NYB'].rolling(window=20).mean().iloc[-1]
        dxy_std = df['DX-Y.NYB'].rolling(window=20).std().iloc[-1]
        dxy_spike = dxy_val > (dxy_mean + 2 * dxy_std)
    else:
        dxy_val = 0
        dxy_spike = False

    # SaaS相対強度 (存在確認)
    if 'IGV' in df.columns and '^GSPC' in df.columns:
        df['SaaS_Rel'] = df['IGV'] / df['^GSPC']
        latest_saas_rel = df['SaaS_Rel'].iloc[-1]
    else:
        df['SaaS_Rel'] = 0
        latest_saas_rel = 0

    # --- 機能1: 流動性ドミノ・ゲージ ---
    st.subheader("1. 🌊 流動性ドミノ・ゲージ (Liquidity Domino)")
    col1, col2, col3, col4 = st.columns(4)
    
    # Step 1: DXY Spike
    with col1:
        st.metric("Step 1: DXY Spike", f"{dxy_val:.2f}", delta="Risk On" if not dxy_spike else "ALERT", delta_color="inverse")

    # Step 2: Canary (BTC)
    btc_down = latest['BTC-USD'] < ma_50['BTC-USD']
    with col2:
        st.metric("Step 2: Canary Breath", "BTC Trend", delta="Alive" if not btc_down else "Suffocating", delta_color="inverse")

    # Step 3: Credit Crack (BIZD)
    if 'BIZD' in df.columns:
        bizd_crack = latest['BIZD'] < ma_200['BIZD']
        bizd_val = latest['BIZD']
    else:
        bizd_crack = False
        bizd_val = 0

    with col3:
        st.metric("Step 3: Credit Crack", f"{bizd_val:.2f}", delta="Safe" if not bizd_crack else "CRITICAL", delta_color="inverse")
        if bizd_crack:
            st.error("🔥 信用収縮 (Exit Signal)")

    # Step 4: Meltdown (S&P500)
    sp500_crack = latest['^GSPC'] < ma_200['^GSPC']
    with col4:
        st.metric("Step 4: Meltdown", f"{latest['^GSPC']:.0f}", delta="Bull" if not sp500_crack else "COLLAPSE", delta_color="inverse")

    st.divider()

    # --- 機能2: SaaSモデル崩壊トラッカー ---
    st.subheader("2. 📉 SaaS Erosion Tracker (IGV vs S&P500)")
    if 'SaaS_Rel' in df.columns and not df['SaaS_Rel'].empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df['SaaS_Rel'], mode='lines', name='IGV / SPX Ratio', line=dict(color='cyan')))
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("SaaSデータなし")


    # --- 機能3: AI総合診断 (Claude API) ---
    st.divider()
    st.subheader("3. 🤖 AI Alice診断")

    if st.button("🔍 AI診断を実行", type="primary", use_container_width=True):
        api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            st.error("ANTHROPIC_API_KEYが設定されていません")
        else:
            with st.spinner("Alice が市場の裏側を診断中... (10-30秒)"):
                import requests as req
                import json

                # 現在の指標をテキスト化
                diag_text = "## Alice Diagnosis 現在の指標\n\n"
                diag_text += f"DXY (ドル指数): {dxy_val:.2f}\n"
                diag_text += f"DXY スパイク判定: {'YES - Risk On' if dxy_spike else 'No'}\n"
                diag_text += f"BTC vs MA50: {'Below (Suffocating)' if btc_down else 'Above (Alive)'}\n"
                diag_text += f"BIZD (Credit): {bizd_val:.2f}, Crack={'YES' if bizd_crack else 'No'}\n"
                diag_text += f"S&P500: {latest['^GSPC']:.0f}, vs MA200: {'Below (Meltdown)' if sp500_crack else 'Above (Bull)'}\n"
                diag_text += f"SaaS相対強度 (IGV/SPX): {latest_saas_rel:.4f}\n"

                system_prompt = """あなたはブリッジウォーターやシタデルで15年の経験を持つマクロリスク・アナリストです。

提供された「Alice Diagnosis」の指標を分析し、以下のJSON形式で回答してください。
ファンドの投資委員会に提出するレポートのように、具体的な数値と因果関係を明確にしてください。
````json
{
    "overall_diagnosis": {
        "risk_level": "GREEN/YELLOW/ORANGE/RED",
        "title": "一言の診断タイトル",
        "confidence": 75
    },
    "domino_analysis": {
        "stage": "現在のドミノステージ (1-4)",
        "description": "どのドミノが倒れているか、次に何が来るか",
        "sequence": "DXY→BTC→Credit→S&P500の連鎖分析"
    },
    "scenarios": {
        "base_case": {"probability": 50, "title": "基本シナリオ", "narrative": "説明", "investment_action": "推奨アクション"},
        "bull_case": {"probability": 25, "title": "楽観シナリオ", "narrative": "説明", "investment_action": "推奨アクション"},
        "bear_case": {"probability": 25, "title": "悲観シナリオ", "narrative": "説明", "investment_action": "推奨アクション"}
    },
    "key_signals": ["注目すべきシグナル1", "シグナル2", "シグナル3"],
    "next_domino": "次に倒れる可能性のあるドミノとタイムライン"
}
```"""

                try:
                    headers = {
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    }
                    payload = {
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 2000,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": diag_text}]
                    }
                    resp = req.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=60)
                    result = resp.json()

                    if "content" in result:
                        raw = result["content"][0]["text"]
                        # JSON抽出
                        import re
                        json_match = re.search(r'\{[\s\S]*\}', raw)
                        if json_match:
                            ai_result = json.loads(json_match.group())
                        else:
                            ai_result = None

                        if ai_result:
                            # --- 総合診断 ---
                            diag = ai_result.get("overall_diagnosis", {})
                            risk = diag.get("risk_level", "YELLOW")
                            risk_colors = {"GREEN": "#00C853", "YELLOW": "#FFD600", "ORANGE": "#FF6D00", "RED": "#FF1744"}
                            risk_color = risk_colors.get(risk, "#FFD600")

                            st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 5px solid {risk_color};">
                                <h3 style="color: {risk_color}; margin-top: 0;">🏥 診断: {diag.get('title', '')}</h3>
                                <p style="color: #ddd;">リスクレベル: <b style="color: {risk_color};">{risk}</b> | 信頼度: {diag.get('confidence', 'N/A')}%</p>
                            </div>""", unsafe_allow_html=True)

                            # --- ドミノ分析 ---
                            domino = ai_result.get("domino_analysis", {})
                            st.markdown(f"""<div style="background: #1e1e2e; padding: 15px; border-radius: 10px; margin-top: 10px;">
                                <h4 style="color: #BB86FC;">🎯 ドミノステージ: {domino.get('stage', 'N/A')}</h4>
                                <p style="color: #ddd;">{domino.get('description', '')}</p>
                                <p style="color: #aaa; font-size: 0.9em;">🔗 {domino.get('sequence', '')}</p>
                            </div>""", unsafe_allow_html=True)

                            # --- シナリオ分析 ---
                            st.markdown("### 📊 シナリオ分析")
                            scenarios = ai_result.get("scenarios", {})
                            col_b, col_base, col_bear = st.columns(3)

                            base = scenarios.get("base_case", {})
                            with col_b:
                                st.markdown(f"""<div style="background: #1a3a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #4CAF50;">
                                    <h4 style="color: #4CAF50; margin-top: 0;">📈 基本 ({base.get('probability', 50)}%): {base.get('title', '')}</h4>
                                    <p style="color: #ddd; font-size: 0.9em;">{base.get('narrative', '')}</p>
                                    <p style="color: #4CAF50; font-size: 0.85em;">🎯 {base.get('investment_action', '')}</p>
                                </div>""", unsafe_allow_html=True)

                            bull = scenarios.get("bull_case", {})
                            with col_base:
                                st.markdown(f"""<div style="background: #0a2a3a; padding: 15px; border-radius: 10px; border-left: 4px solid #03A9F4;">
                                    <h4 style="color: #03A9F4; margin-top: 0;">🚀 楽観 ({bull.get('probability', 25)}%): {bull.get('title', '')}</h4>
                                    <p style="color: #ddd; font-size: 0.9em;">{bull.get('narrative', '')}</p>
                                    <p style="color: #03A9F4; font-size: 0.85em;">🎯 {bull.get('investment_action', '')}</p>
                                </div>""", unsafe_allow_html=True)

                            bear = scenarios.get("bear_case", {})
                            with col_bear:
                                st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B;">
                                    <h4 style="color: #FF4B4B; margin-top: 0;">🐻 悲観 ({bear.get('probability', 25)}%): {bear.get('title', '')}</h4>
                                    <p style="color: #ddd; font-size: 0.9em;">{bear.get('narrative', '')}</p>
                                    <p style="color: #FF4B4B; font-size: 0.85em;">🎯 {bear.get('investment_action', '')}</p>
                                </div>""", unsafe_allow_html=True)

                            # --- 注目シグナル ---
                            signals = ai_result.get("key_signals", [])
                            if signals:
                                st.markdown("### 🔔 注目シグナル")
                                for s in signals:
                                    st.markdown(f"- 👁 {s}")

                            # --- 次のドミノ ---
                            next_d = ai_result.get("next_domino", "")
                            if next_d:
                                st.error(f"⚡ **次のドミノ:** {next_d}")
                        else:
                            st.warning("AI応答のパースに失敗しました")
                            st.code(raw)
                    else:
                        st.error(f"APIエラー: {result}")
                except Exception as api_e:
                    st.error(f"AI診断エラー: {api_e}")


except Exception as e:
    st.error(f"⚠️ エラーが発生しました: {e}")
