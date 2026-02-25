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


    # --- 機能3: AI Alice総合診断 (Claude API) ---
    st.divider()
    st.subheader("3. 🤖 AI Alice 総合診断")

    # --- ドミノ状態サマリー（常時表示） ---
    domino_steps = {
        "Step 1: DXY Spike": {"active": dxy_spike, "value": f"{dxy_val:.2f}", "desc": "ドル急騰 → リスク資産圧迫"},
        "Step 2: BTC Canary": {"active": btc_down, "value": "Below MA50" if btc_down else "Above MA50", "desc": "暗号資産 = 流動性カナリア"},
        "Step 3: Credit Crack": {"active": bizd_crack, "value": f"{bizd_val:.2f}", "desc": "社債ETF崩壊 → 信用収縮"},
        "Step 4: S&P500 Meltdown": {"active": sp500_crack, "value": f"{latest['^GSPC']:.0f}", "desc": "最後のドミノ = 株式崩壊"},
    }
    active_count = sum(1 for v in domino_steps.values() if v["active"])

    if active_count == 0:
        auto_risk = "GREEN"
    elif active_count == 1:
        auto_risk = "YELLOW"
    elif active_count <= 2:
        auto_risk = "ORANGE"
    else:
        auto_risk = "RED"

    risk_config = {
        "GREEN": {"color": "#00C853", "label": "安全", "emoji": "🟢"},
        "YELLOW": {"color": "#FFD600", "label": "警戒", "emoji": "🟡"},
        "ORANGE": {"color": "#FF6D00", "label": "危険", "emoji": "🟠"},
        "RED": {"color": "#FF1744", "label": "崩壊", "emoji": "🔴"},
    }

    # --- リスクゲージ（4段階表示） ---
    gauge_html = '<div style="display:flex;gap:4px;margin:10px 0;">'
    for level, cfg in risk_config.items():
        is_current = (level == auto_risk)
        opacity = "1.0" if is_current else "0.25"
        border = "3px solid white" if is_current else "1px solid #555"
        gauge_html += f'<div style="flex:1;background:{cfg["color"]};opacity:{opacity};padding:12px;border-radius:8px;text-align:center;border:{border};"><span style="font-size:1.4em;">{cfg["emoji"]}</span><br><b style="color:#000;font-size:0.9em;">{cfg["label"]}</b><br><span style="color:#000;font-size:0.75em;">{level}</span></div>'
    gauge_html += '</div>'

    rc = risk_config[auto_risk]
    st.markdown(f"""<div style="background:#111;padding:15px;border-radius:10px;margin-bottom:15px;">
        <h4 style="color:{rc['color']};margin:0 0 5px 0;">{rc['emoji']} 現在のリスクレベル: {auto_risk} ({rc['label']}) — ドミノ {active_count}/4 点灯</h4>
        {gauge_html}
    </div>""", unsafe_allow_html=True)

    # --- ドミノ連鎖ビジュアル ---
    st.markdown("#### 🎯 ドミノ連鎖ステータス")
    domino_html = '<div style="display:flex;align-items:center;gap:0;margin:10px 0;">'
    for i, (step, info) in enumerate(domino_steps.items()):
        bg = "#FF1744" if info["active"] else "#1a3a1a"
        border_c = "#FF1744" if info["active"] else "#00C853"
        icon = "🔥" if info["active"] else "✅"
        status_text = "⚠️ 点灯" if info["active"] else "正常"
        domino_html += f'<div style="flex:1;background:{bg};padding:10px;border-radius:8px;border:2px solid {border_c};text-align:center;margin:0 2px;"><div style="font-size:1.2em;">{icon}</div><div style="color:white;font-size:0.75em;font-weight:bold;">{step}</div><div style="color:#ccc;font-size:0.85em;">{info["value"]}</div><div style="color:{"#FF6B6B" if info["active"] else "#69F0AE"};font-size:0.7em;">{status_text}</div></div>'
        if i < len(domino_steps) - 1:
            arrow_color = "#FF1744" if info["active"] else "#555"
            domino_html += f'<div style="font-size:1.5em;color:{arrow_color};">→</div>'
    domino_html += '</div>'
    st.markdown(domino_html, unsafe_allow_html=True)

    for step, info in domino_steps.items():
        if info["active"]:
            st.caption(f"🔥 **{step}**: {info['desc']}")

    st.markdown("---")

    if st.button("🔍 AI詳細診断を実行", type="primary", use_container_width=True):
        api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            st.error("ANTHROPIC_API_KEYが設定されていません")
        else:
            with st.spinner("Alice が流動性ドミノを詳細分析中... (10-30秒)"):
                import requests as req
                import json

                diag_text = "## Alice Diagnosis 詳細データ\n\n"
                diag_text += f"### ドミノ状態: {active_count}/4 点灯 → 自動判定リスク: {auto_risk}\n\n"

                diag_text += f"### Step 1: DXY (ドル指数)\n"
                diag_text += f"- 現在値: {dxy_val:.2f}\n"
                if 'DX-Y.NYB' in df.columns:
                    dxy_chg_5d = ((latest['DX-Y.NYB'] / df['DX-Y.NYB'].iloc[-6]) - 1) * 100 if len(df) > 6 else 0
                    dxy_chg_20d = ((latest['DX-Y.NYB'] / df['DX-Y.NYB'].iloc[-21]) - 1) * 100 if len(df) > 21 else 0
                    diag_text += f"- 5日変化率: {dxy_chg_5d:+.2f}%\n"
                    diag_text += f"- 20日変化率: {dxy_chg_20d:+.2f}%\n"
                    diag_text += f"- 20日平均: {dxy_mean:.2f}, 標準偏差: {dxy_std:.2f}\n"
                    diag_text += f"- スパイク判定 (>2σ): {'YES' if dxy_spike else 'No'}\n\n"

                diag_text += f"### Step 2: BTC (カナリア)\n"
                diag_text += f"- 現在値: ${latest['BTC-USD']:,.0f}\n"
                diag_text += f"- MA50: ${ma_50['BTC-USD']:,.0f}\n"
                btc_gap = ((latest['BTC-USD'] / ma_50['BTC-USD']) - 1) * 100
                diag_text += f"- MA50乖離率: {btc_gap:+.1f}%\n"
                diag_text += f"- 判定: {'Below MA50 (Suffocating)' if btc_down else 'Above MA50 (Alive)'}\n\n"

                diag_text += f"### Step 3: BIZD (信用)\n"
                diag_text += f"- 現在値: {bizd_val:.2f}\n"
                if 'BIZD' in df.columns:
                    diag_text += f"- MA200: {ma_200['BIZD']:.2f}\n"
                    bizd_gap = ((latest['BIZD'] / ma_200['BIZD']) - 1) * 100
                    diag_text += f"- MA200乖離率: {bizd_gap:+.1f}%\n"
                diag_text += f"- 信用収縮判定: {'YES - Credit Crack' if bizd_crack else 'No'}\n\n"

                if 'HYG' in df.columns:
                    diag_text += f"### 補助指標: HYG (ハイイールド債)\n"
                    diag_text += f"- 現在値: ${latest['HYG']:.2f}\n"
                    diag_text += f"- MA50: ${ma_50['HYG']:.2f}\n"
                    hyg_gap = ((latest['HYG'] / ma_50['HYG']) - 1) * 100
                    diag_text += f"- MA50乖離率: {hyg_gap:+.1f}%\n"
                    hyg_below = latest['HYG'] < ma_50['HYG']
                    diag_text += f"- 判定: {'Below MA50' if hyg_below else 'Above MA50'}\n\n"

                diag_text += f"### Step 4: S&P500\n"
                diag_text += f"- 現在値: {latest['^GSPC']:,.0f}\n"
                diag_text += f"- MA200: {ma_200['^GSPC']:,.0f}\n"
                sp_gap = ((latest['^GSPC'] / ma_200['^GSPC']) - 1) * 100
                diag_text += f"- MA200乖離率: {sp_gap:+.1f}%\n"
                diag_text += f"- 判定: {'Below MA200 (Meltdown)' if sp500_crack else 'Above MA200 (Bull)'}\n\n"

                diag_text += f"### SaaS相対強度 (IGV/SPX)\n"
                diag_text += f"- 現在値: {latest_saas_rel:.4f}\n"
                if 'SaaS_Rel' in df.columns and len(df) > 20:
                    saas_chg = ((latest_saas_rel / df['SaaS_Rel'].iloc[-21]) - 1) * 100
                    diag_text += f"- 20日変化率: {saas_chg:+.1f}%\n"

                saas_tickers = ['CRM', 'INTU', 'ADBE']
                saas_data = []
                for t in saas_tickers:
                    if t in df.columns:
                        chg = ((latest[t] / df[t].iloc[-21]) - 1) * 100 if len(df) > 21 else 0
                        saas_data.append(f"- {t}: ${latest[t]:.0f} (20d: {chg:+.1f}%)")
                if saas_data:
                    diag_text += "### SaaS個別銘柄\n" + "\n".join(saas_data) + "\n\n"

                system_prompt = "あなたはブリッジウォーターのPure Alpha戦略チームで15年の経験を持つマクロ流動性アナリストです。\n\nAlice Diagnosisは流動性ドミノ理論に基づく独自の市場診断フレームワークです：\n- DXYスパイク → BTC下落 → 信用収縮(BIZD) → S&P500崩壊 という連鎖を監視します\n- 各ステップが点灯するほど、システミックリスクが高まります\n\n提供されたデータを詳細に分析し、以下のJSON形式で回答してください。\n数値を必ず引用し、なぜそう判断したかの因果関係を明確にしてください。\n\n```json\n{\n    \"overall_diagnosis\": {\n        \"risk_level\": \"GREEN/YELLOW/ORANGE/RED\",\n        \"title\": \"一言の診断タイトル\",\n        \"confidence\": 75,\n        \"one_liner\": \"現在の状況を1文で要約\"\n    },\n    \"domino_deep_analysis\": {\n        \"current_stage\": \"ステージ1-4の説明\",\n        \"fallen_dominoes\": \"既に倒れたドミノの詳細分析（数値引用必須）\",\n        \"next_risk\": \"次に倒れそうなドミノとその根拠\",\n        \"chain_reaction\": \"DXY→BTC→Credit→S&P500の現在の連鎖状態を詳述\",\n        \"historical_parallel\": \"過去の類似局面\"\n    },\n    \"liquidity_assessment\": {\n        \"global_liquidity\": \"グローバル流動性の現状評価\",\n        \"credit_stress\": \"信用ストレスの度合い（BIZDとHYGの分析）\",\n        \"risk_appetite\": \"リスクアペタイトの状態（BTCとSaaSで判断）\",\n        \"dollar_impact\": \"ドル高の影響と今後の見通し\"\n    },\n    \"scenarios\": {\n        \"base_case\": {\"probability\": 50, \"title\": \"タイトル\", \"narrative\": \"詳細説明（数値引用）\", \"investment_action\": \"具体的アクション\"},\n        \"bull_case\": {\"probability\": 25, \"title\": \"タイトル\", \"narrative\": \"詳細説明\", \"investment_action\": \"具体的アクション\"},\n        \"bear_case\": {\"probability\": 25, \"title\": \"タイトル\", \"narrative\": \"詳細説明\", \"investment_action\": \"具体的アクション\"}\n    },\n    \"key_signals\": [\"次の1-2週間で注目すべきシグナル1\", \"シグナル2\", \"シグナル3\"],\n    \"action_items\": {\n        \"immediate\": \"今すぐやるべきこと\",\n        \"watch_for\": \"今後注視すべきトリガー\",\n        \"hedge\": \"推奨ヘッジ手段\"\n    }\n}\n```"

                try:
                    headers = {
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    }
                    payload = {
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 3000,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": diag_text}]
                    }
                    resp = req.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=60)
                    result = resp.json()

                    if "content" in result:
                        raw = result["content"][0]["text"]
                        import re
                        json_match = re.search(r'\{[\s\S]*\}', raw)
                        if json_match:
                            ai_result = json.loads(json_match.group())
                        else:
                            ai_result = None

                        if ai_result:
                            diag = ai_result.get("overall_diagnosis", {})
                            ai_risk = diag.get("risk_level", auto_risk)
                            arc = risk_config.get(ai_risk, risk_config["YELLOW"])

                            st.markdown(f"""<div style="background:linear-gradient(135deg,#0d1117,#161b22);padding:20px;border-radius:12px;border-left:6px solid {arc['color']};margin:15px 0;">
                                <h3 style="color:{arc['color']};margin:0 0 8px 0;">{arc['emoji']} {diag.get('title', '')}</h3>
                                <p style="color:#ddd;margin:5px 0;">AI判定: <b style="color:{arc['color']};font-size:1.2em;">{ai_risk}</b> | 信頼度: {diag.get('confidence', 'N/A')}%</p>
                                <p style="color:#aaa;font-style:italic;margin:5px 0;">💬 {diag.get('one_liner', '')}</p>
                            </div>""", unsafe_allow_html=True)

                            dd = ai_result.get("domino_deep_analysis", {})
                            st.markdown("### 🎯 ドミノ連鎖 深掘り分析")
                            st.markdown(f"""<div style="background:#1e1e2e;padding:15px;border-radius:10px;">
                                <p style="color:#BB86FC;"><b>📍 現在ステージ:</b> {dd.get('current_stage', '')}</p>
                                <p style="color:#ddd;"><b>🔥 点灯ドミノ:</b> {dd.get('fallen_dominoes', '')}</p>
                                <p style="color:#FF6B6B;"><b>⚡ 次のリスク:</b> {dd.get('next_risk', '')}</p>
                                <p style="color:#aaa;"><b>🔗 連鎖状態:</b> {dd.get('chain_reaction', '')}</p>
                                <p style="color:#78909C;"><b>📚 過去の類似:</b> {dd.get('historical_parallel', '')}</p>
                            </div>""", unsafe_allow_html=True)

                            la = ai_result.get("liquidity_assessment", {})
                            st.markdown("### 💧 流動性アセスメント")
                            la_c1, la_c2 = st.columns(2)
                            with la_c1:
                                st.markdown(f"""<div style="background:#162447;padding:12px;border-radius:8px;margin:4px 0;">
                                    <b style="color:#4FC3F7;">🌍 グローバル流動性</b><br><span style="color:#ddd;">{la.get('global_liquidity', 'N/A')}</span>
                                </div>""", unsafe_allow_html=True)
                                st.markdown(f"""<div style="background:#1b2a1b;padding:12px;border-radius:8px;margin:4px 0;">
                                    <b style="color:#81C784;">💰 リスクアペタイト</b><br><span style="color:#ddd;">{la.get('risk_appetite', 'N/A')}</span>
                                </div>""", unsafe_allow_html=True)
                            with la_c2:
                                st.markdown(f"""<div style="background:#2a1b1b;padding:12px;border-radius:8px;margin:4px 0;">
                                    <b style="color:#E57373;">📉 信用ストレス</b><br><span style="color:#ddd;">{la.get('credit_stress', 'N/A')}</span>
                                </div>""", unsafe_allow_html=True)
                                st.markdown(f"""<div style="background:#2a2a1b;padding:12px;border-radius:8px;margin:4px 0;">
                                    <b style="color:#FFD54F;">💵 ドル影響</b><br><span style="color:#ddd;">{la.get('dollar_impact', 'N/A')}</span>
                                </div>""", unsafe_allow_html=True)

                            st.markdown("### 📊 シナリオ分析")
                            scenarios = ai_result.get("scenarios", {})
                            sc1, sc2, sc3 = st.columns(3)
                            base = scenarios.get("base_case", {})
                            with sc1:
                                st.markdown(f"""<div style="background:#1a3a1a;padding:15px;border-radius:10px;border-left:4px solid #4CAF50;">
                                    <h4 style="color:#4CAF50;margin-top:0;">📈 基本 ({base.get('probability', 50)}%)</h4>
                                    <p style="color:#fff;font-weight:bold;">{base.get('title', '')}</p>
                                    <p style="color:#ddd;font-size:0.85em;">{base.get('narrative', '')}</p>
                                    <p style="color:#4CAF50;font-size:0.85em;">🎯 {base.get('investment_action', '')}</p>
                                </div>""", unsafe_allow_html=True)
                            bull = scenarios.get("bull_case", {})
                            with sc2:
                                st.markdown(f"""<div style="background:#0a2a3a;padding:15px;border-radius:10px;border-left:4px solid #03A9F4;">
                                    <h4 style="color:#03A9F4;margin-top:0;">🚀 楽観 ({bull.get('probability', 25)}%)</h4>
                                    <p style="color:#fff;font-weight:bold;">{bull.get('title', '')}</p>
                                    <p style="color:#ddd;font-size:0.85em;">{bull.get('narrative', '')}</p>
                                    <p style="color:#03A9F4;font-size:0.85em;">🎯 {bull.get('investment_action', '')}</p>
                                </div>""", unsafe_allow_html=True)
                            bear = scenarios.get("bear_case", {})
                            with sc3:
                                st.markdown(f"""<div style="background:#2a0a0a;padding:15px;border-radius:10px;border-left:4px solid #FF4B4B;">
                                    <h4 style="color:#FF4B4B;margin-top:0;">🐻 悲観 ({bear.get('probability', 25)}%)</h4>
                                    <p style="color:#fff;font-weight:bold;">{bear.get('title', '')}</p>
                                    <p style="color:#ddd;font-size:0.85em;">{bear.get('narrative', '')}</p>
                                    <p style="color:#FF4B4B;font-size:0.85em;">🎯 {bear.get('investment_action', '')}</p>
                                </div>""", unsafe_allow_html=True)

                            st.markdown("### 🔔 注目シグナル & アクション")
                            ac = ai_result.get("action_items", {})
                            signals = ai_result.get("key_signals", [])
                            ac_c1, ac_c2 = st.columns(2)
                            with ac_c1:
                                if signals:
                                    for s in signals:
                                        st.markdown(f"- 👁 {s}")
                            with ac_c2:
                                if ac.get("immediate"):
                                    st.error(f"🚨 **即時:** {ac['immediate']}")
                                if ac.get("watch_for"):
                                    st.warning(f"👀 **注視:** {ac['watch_for']}")
                                if ac.get("hedge"):
                                    st.info(f"🛡 **ヘッジ:** {ac['hedge']}")
                        else:
                            st.warning("AI応答のパースに失敗しました")
                            st.code(raw)
                    else:
                        st.error(f"APIエラー: {result}")
                except Exception as api_e:
                    st.error(f"AI診断エラー: {api_e}")

except Exception as e:
    st.error(f"⚠️ エラーが発生しました: {e}")
