from core.auth import require_auth
require_auth()

from api_helper import call_anthropic_api
import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="AI Agent Analysis", page_icon="🤖", layout="wide")

st.title("🤖 AI Agent 総合市場分析")
st.markdown("全ページの指標データを収集し、Claude APIで統合分析を行います。")

# --- API Key ---
ANTHROPIC_API_KEY = ""
try:
    ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Debug: show key status
if ANTHROPIC_API_KEY:
    st.sidebar.success(f"API Key: ...{ANTHROPIC_API_KEY[-8:]}")
else:
    st.sidebar.error("API Key not found")

if not ANTHROPIC_API_KEY:
    st.error("⚠️ ANTHROPIC_API_KEY が設定されていません。Streamlit secrets または環境変数に設定してください。")
    st.stop()


# --- データ収集 ---
from core.data_collector import collect_all, format_for_prompt, parse_portfolio_csv, analyze_portfolio_for_agent, format_portfolio_for_prompt


def call_claude_api(market_data_text):
    """Claude APIを直接呼び出して市場分析を取得"""
    import requests

    system_prompt = """あなたは世界トップクラスのヘッジファンドマネージャーです。
提供された市場データを分析し、以下のJSON形式で回答してください。
日本語で回答してください。

【最重要ルール】
1. 必ずデータの実際の数値を引用して分析すること。例:「原油は+7.75%上昇」のように具体的数値を使う
2. 一部の指標を全体に一般化しないこと。例: 天然ガスが-42%でも、金が+3.6%なら「資源全体が下落」とは書かない
3. 個別の指標ごとに方向性を正確に記述すること（プラスなのにマイナスと書かない）
4. 矛盾する記述をしないこと。懸念点と機会が矛盾する場合は理由を明記すること
5. データに存在しない事実を推測・捏造しないこと
6. 「信頼度」は統計モデルに基づかないため、代わりに「確度」として定性的に示すこと（高/中/低）

【重要：流動性ドミノ分析】
データに「流動性ドミノ（Alice Diagnosis入力）」セクションがある場合、
ドミノの点灯状況（DXY→BTC→Credit→S&P500の連鎖）を最優先で分析すること。
ドミノが2つ以上点灯している場合は、リスク評価を引き上げること。

【重要：シナリオ分析】
「答え」を出そうとするのではなく、必ず3つのシナリオを提示すること。
各シナリオには「発火条件（何が起きたらこのシナリオになるか）」を具体的数値で明示。

{
    "market_assessment": {
        "overall_risk": "低/中/高/極高",
        "confidence_level": "高/中/低",
        "confidence_reasoning": "確度の根拠（どのデータが明確でどこが不確実か）",
        "cycle_phase": "Early/Mid/Late/Recession",
        "key_concerns": ["懸念1", "懸念2", "懸念3"],
        "opportunities": ["機会1", "機会2", "機会3"],
        "market_regime": "リスクオン/リスクオフ/中立",
        "domino_status": "流動性ドミノの状態（N/4点灯、各ステップの状況）"
    },
    "scenario_analysis": {
        "scenario_a": {
            "name": "シナリオ名",
            "description": "概要",
            "trigger": "このシナリオが現実化する具体的条件（数値含む）",
            "portfolio_action": "このシナリオでの最適行動",
            "likelihood": "高/中/低"
        },
        "scenario_b": {
            "name": "シナリオ名",
            "description": "概要",
            "trigger": "このシナリオが現実化する具体的条件（数値含む）",
            "portfolio_action": "このシナリオでの最適行動",
            "likelihood": "高/中/低"
        },
        "scenario_c": {
            "name": "シナリオ名",
            "description": "概要",
            "trigger": "このシナリオが現実化する具体的条件（数値含む）",
            "portfolio_action": "このシナリオでの最適行動",
            "likelihood": "高/中/低"
        },
        "key_indicators_to_watch": ["監視すべき指標と閾値1", "監視すべき指標と閾値2"]
    },
    "sector_analysis": {
        "overweight": ["推奨セクター1", "推奨セクター2"],
        "underweight": ["回避セクター1", "回避セクター2"],
        "rotation_status": "セクターローテーションの現在地",
        "reasoning": "セクター判断の理由"
    },
    "portfolio_recommendations": [
        {
            "action": "買い/売り/ホールド/リバランス",
            "asset_class": "資産クラス",
            "target_allocation": "推奨配分%",
            "reasoning": "理由",
            "urgency": "高/中/低"
        }
    ],
    "portfolio_diagnosis": {
        "overall_health": "健全/注意/危険",
        "diversification_score": "分散度スコア(1-10)",
        "holdings_analysis": [
            {"symbol": "銘柄", "verdict": "継続保有/利確検討/損切り検討/買い増し検討", "reason": "理由"}
        ],
        "rebalance_suggestions": ["リバランス提案1", "リバランス提案2"],
        "dividend_outlook": "配当見通し"
    },
    "specific_actions": [
        {
            "action": "具体的なアクション",
            "ticker": "ティッカー",
            "confidence_level": "高/中/低",
            "rationale": "根拠（具体的データ数値を引用）",
            "timeframe": "期間"
        }
    ],
    "risk_management": {
        "stop_loss_level": "損切り基準",
        "position_sizing": "ポジションサイズの推奨",
        "hedge_recommendation": "ヘッジ推奨",
        "max_drawdown_warning": "最大ドローダウン警告"
    },
    "polymarket_insights": {
        "key_predictions": ["注目予測1", "注目予測2"],
        "market_implications": "予測市場から読み取れる市場への影響",
        "contrarian_opportunities": "逆張りの機会"
    },
    "contrarian_view": {
        "current_regime": "現在のレジーム（リスクオン/リスクオフ）",
        "regime_reversal_triggers": ["反転トリガー1（具体的数値）", "反転トリガー2", "反転トリガー3"],
        "early_signals_to_watch": ["注目すべき先行指標1", "注目すべき先行指標2"],
        "contrarian_trades": [
            {"trade": "具体的な逆張りトレード", "trigger": "エントリー条件", "risk": "リスク"}
        ],
        "timeline": "反転が起きうる時間軸の目安"
    },
    "summary": "200文字以内の総合サマリー"
}

重要な分析ポイント:
1. 各指標の相関関係を分析（例: VIXとセクターの関係、銅金レシオと景気サイクル）
2. 矛盾するシグナルがあれば明示
3. 流動性ドミノの状態（DXY→BTC→Credit→S&P500）を最優先で確認
4. 信用市場ストレス（HYG/LQD）とAIバブル指標（IGV/SPY比率）を必ず分析
5. Polymarket予測と市場データの整合性を確認
6. 具体的なティッカーと数値を含めた実行可能な推奨を提示
7. リスク管理を最優先に考える
8. 【シナリオ分析】3つのシナリオを必ず提示し、各シナリオの発火条件を具体的数値で明示
9. 【逆張り分析】現在のレジームが反転する条件を具体的に分析すること"""

    user_message = f"""以下の市場データを分析してください。
【指示】
- 各数値の符号（+/-）を正確に読み取ること
- change_1m_pct の数値がプラスなら上昇、マイナスなら下落
- 個別指標の動きを全体に一般化しないこと
- 全指標の相関関係を考慮し、統合的な投資判断を提示すること
- 流動性ドミノ（Alice Diagnosis）の点灯状況を最優先で確認すること
- 必ず3つのシナリオを提示すること（答えを出すな、場合分けを出せ）

{market_data_text}

上記データに基づいて、JSON形式で分析結果を返してください。"""

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 8192,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}]
    }

    result_data, api_error = call_anthropic_api(headers, payload)
    if api_error:
        return None
    return result_data


# --- メイン UI ---

# --- ポートフォリオCSVアップロード（任意）---
st.markdown("---")
st.subheader("📂 ポートフォリオ連携（任意）")
uploaded_file = st.file_uploader("IB証券のCSVをアップロードすると、保有銘柄も含めて分析します", type=["csv"])
st.caption("※ CSVなしでも市場分析は実行できます")
st.markdown("---")

if st.button("🔍 全データ収集 → AI分析を実行", type="primary", use_container_width=True):

    # Step 1: データ収集
    with st.spinner("📊 全ページの指標データを収集中... (60-120秒)"):
        all_data = collect_all()

    # ポートフォリオ処理
    portfolio_data = None
    portfolio_text = ""
    if uploaded_file:
        with st.spinner("📂 ポートフォリオを解析中..."):
            df_portfolio, error = parse_portfolio_csv(uploaded_file)
            if error:
                st.error(f"CSV読み込みエラー: {error}")
            elif df_portfolio is not None:
                portfolio_data = analyze_portfolio_for_agent(df_portfolio)
                portfolio_text = format_portfolio_for_prompt(portfolio_data)
                st.success(f"✅ {portfolio_data['count']}銘柄のポートフォリオを解析完了")
                st.info(f"💰 配当計算: 年間¥{portfolio_data.get('total_annual_dividend_jpy', 0):,.0f} / 月間¥{portfolio_data.get('monthly_dividend_jpy', 0):,.0f}")

    # 収集結果サマリー
    collected_count = sum(1 for k, v in all_data.items()
                         if k != "timestamp" and isinstance(v, (dict, list))
                         and not (isinstance(v, dict) and "error" in v))
    extra = f" + ポートフォリオ{portfolio_data['count']}銘柄" if portfolio_data else ""
    st.success(f"✅ {collected_count}/20 カテゴリのデータを収集完了{extra}")

    # 流動性ドミノのクイックサマリー
    domino = all_data.get("liquidity_domino", {})
    if isinstance(domino, dict) and "_domino_total" in domino:
        dt = domino["_domino_total"]
        severity_color = {
            "CRITICAL": "🔴", "WARNING": "🟠", "CAUTION": "🟡", "NORMAL": "🟢"
        }.get(dt.get("severity", ""), "⚪")
        st.warning(f"{severity_color} 流動性ドミノ: {dt.get('signal', 'N/A')} ({dt.get('severity', '')})")

    # データプレビュー
    with st.expander("📋 収集したデータを確認"):
        market_text = format_for_prompt(all_data)
        st.text(market_text)

    # Step 2: Claude API分析
    with st.spinner("🤖 Claude APIが市場を分析中... (15-45秒)"):
        try:
            market_text = format_for_prompt(all_data)
            if portfolio_text:
                market_text += "\n" + portfolio_text
            analysis = call_claude_api(market_text)

            # --- 結果表示 ---
            st.markdown("---")

            # 市場評価
            st.subheader("📊 市場評価")
            ma = analysis.get("market_assessment", {})

            col1, col2, col3 = st.columns(3)
            with col1:
                risk = ma.get("overall_risk", "N/A")
                risk_color = {"低": "🟢", "中": "🟡", "高": "🟠", "極高": "🔴"}.get(risk, "⚪")
                st.metric("総合リスク", f"{risk_color} {risk}")
            with col2:
                conf = ma.get("confidence_level", "N/A")
                st.metric("確度", f"{conf}")
            with col3:
                st.metric("景気サイクル", ma.get("cycle_phase", "N/A"))

            col4, col5 = st.columns(2)
            with col4:
                regime = ma.get("market_regime", "N/A")
                st.info(f"📈 マーケットレジーム: **{regime}**")
            with col5:
                domino_status = ma.get("domino_status", "N/A")
                st.warning(f"🎯 ドミノ状態: **{domino_status}**")

            # 確度の根拠
            if ma.get("confidence_reasoning"):
                st.caption(f"📝 確度の根拠: {ma['confidence_reasoning']}")

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**⚠️ 主な懸念点:**")
                for c in ma.get("key_concerns", []):
                    st.warning(c)
            with col_b:
                st.markdown("**💡 投資機会:**")
                for o in ma.get("opportunities", []):
                    st.success(o)

            # === 新規: シナリオ分析 ===
            st.markdown("---")
            st.subheader("🎭 シナリオ分析（場合分け）")
            sa_scenarios = analysis.get("scenario_analysis", {})
            if sa_scenarios:
                scenario_cols = st.columns(3)
                for i, key in enumerate(["scenario_a", "scenario_b", "scenario_c"]):
                    sc = sa_scenarios.get(key, {})
                    if sc:
                        with scenario_cols[i]:
                            likelihood = sc.get("likelihood", "")
                            l_icon = {"高": "🔴", "中": "🟡", "低": "🟢"}.get(likelihood, "⚪")
                            st.markdown(f"### {l_icon} {sc.get('name', f'シナリオ{i+1}')}")
                            st.markdown(f"**可能性:** {likelihood}")
                            st.markdown(f"{sc.get('description', '')}")
                            st.info(f"**発火条件:** {sc.get('trigger', '')}")
                            st.success(f"**最適行動:** {sc.get('portfolio_action', '')}")

                if sa_scenarios.get("key_indicators_to_watch"):
                    st.markdown("**👁 監視すべき指標:**")
                    for ind in sa_scenarios["key_indicators_to_watch"]:
                        st.info(f"📡 {ind}")

            # セクター分析
            st.markdown("---")
            st.subheader("🔄 セクター分析")
            sa = analysis.get("sector_analysis", {})
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.markdown("**✅ オーバーウェイト推奨:**")
                for s in sa.get("overweight", []):
                    st.success(s)
            with col_s2:
                st.markdown("**❌ アンダーウェイト推奨:**")
                for s in sa.get("underweight", []):
                    st.error(s)
            if sa.get("rotation_status"):
                st.info(f"🔀 ローテーション状況: {sa['rotation_status']}")
            if sa.get("reasoning"):
                st.caption(sa["reasoning"])

            # ポートフォリオ診断（CSVアップロード時）
            pd_diag = analysis.get("portfolio_diagnosis", {})
            if pd_diag and portfolio_data:
                st.markdown("---")
                st.subheader("🩺 ポートフォリオ診断")

                col_h1, col_h2, col_h3, col_h4 = st.columns(4)
                with col_h1:
                    health = pd_diag.get("overall_health", "N/A")
                    health_icon = {"健全": "🟢", "注意": "🟡", "危険": "🔴"}.get(health, "⚪")
                    st.metric("ポートフォリオ健全度", f"{health_icon} {health}")
                with col_h2:
                    st.metric("分散度スコア", f"{pd_diag.get('diversification_score', 'N/A')}/10")
                with col_h3:
                    annual_div = portfolio_data.get("total_annual_dividend_jpy", 0)
                    st.metric("年間 配当金（予想）", f"¥{annual_div:,.0f}")
                with col_h4:
                    monthly_div = portfolio_data.get("monthly_dividend_jpy", 0)
                    st.metric("月間 不労所得", f"¥{monthly_div:,.0f}")


                # 配当リスト
                st.markdown("**💰 銘柄別 配当金リスト:**")
                
                div_rows = []
                for h in portfolio_data.get("holdings", []):
                    if "error" in h:
                        continue
                    annual_div = h.get("annual_dividend", 0)
                    qty = h.get("quantity", 0)
                    div_per_share = h.get("annual_div_per_share", 0)
                    is_jp = h.get("is_japan", False)
                    if is_jp:
                        annual_jpy = annual_div
                    else:
                        annual_jpy = annual_div * portfolio_data.get("usdjpy", 150)
                    div_rows.append({
                        "銘柄": h.get("symbol", ""),
                        "名前": h.get("name", ""),
                        "保有数": int(abs(qty)),
                        "1株配当": f"{div_per_share:.2f}",
                        "年間配当": f"¥{annual_jpy:,.0f}" if annual_jpy > 0 else "-",
                        "月間配当": f"¥{annual_jpy/12:,.0f}" if annual_jpy > 0 else "-",
                        "利回り": f"{h.get('div_yield', 0):.1f}%",
                    })
                if div_rows:
                    div_df = pd.DataFrame(div_rows)
                    div_df = div_df.sort_values("年間配当", ascending=False, key=lambda x: x.str.replace("[¥,\-]", "", regex=True).replace("", "0").astype(float))
                    st.dataframe(div_df, use_container_width=True, hide_index=True)

                st.markdown("**📋 保有銘柄の判定:**")
                for h in pd_diag.get("holdings_analysis", []):
                    verdict = h.get("verdict", "")
                    v_icon = {"継続保有": "🟢", "利確検討": "🟡", "損切り検討": "🔴", "買い増し検討": "🔵"}.get(verdict, "⚪")
                    st.markdown(f"{v_icon} **{h.get('symbol', '')}** - {verdict}: {h.get('reason', '')}")

                if pd_diag.get("rebalance_suggestions"):
                    st.markdown("**🔄 リバランス提案:**")
                    for suggestion in pd_diag["rebalance_suggestions"]:
                        st.info(suggestion)

                if pd_diag.get("dividend_outlook"):
                    st.caption(f"💰 配当見通し: {pd_diag['dividend_outlook']}")

            # ポートフォリオ推奨
            st.markdown("---")
            st.subheader("💼 ポートフォリオ推奨")
            for rec in analysis.get("portfolio_recommendations", []):
                action = rec.get("action", "")
                icon = {"買い": "🟢", "売り": "🔴", "ホールド": "🟡", "リバランス": "🔄"}.get(action, "📌")
                urgency = rec.get("urgency", "")
                urgency_icon = {"高": "🔥", "中": "⚡", "低": "💤"}.get(urgency, "")
                with st.expander(f"{icon} {action} - {rec.get('asset_class', '')} ({rec.get('target_allocation', '')}) {urgency_icon}"):
                    st.write(f"**理由:** {rec.get('reasoning', '')}")
                    st.write(f"**緊急度:** {urgency}")

            # 具体的アクション
            st.markdown("---")
            st.subheader("🎯 具体的アクション")
            for act in analysis.get("specific_actions", []):
                cl = act.get("confidence_level", "中")
                icon = {"高": "🟢", "中": "🟡", "低": "🔴"}.get(cl, "⚪")
                st.markdown(f"{icon} **{act.get('action', '')}** - {act.get('ticker', '')} (確度: {cl})")
                st.caption(f"{act.get('rationale', '')} | 期間: {act.get('timeframe', '')}")

            # Polymarket分析
            st.markdown("---")
            st.subheader("🔮 予測市場インサイト")
            pi = analysis.get("polymarket_insights", {})
            if pi:
                st.markdown("**注目予測:**")
                for pred in pi.get("key_predictions", []):
                    st.info(pred)
                if pi.get("market_implications"):
                    st.markdown(f"**市場への影響:** {pi['market_implications']}")
                if pi.get("contrarian_opportunities"):
                    st.markdown(f"**逆張り機会:** {pi['contrarian_opportunities']}")

            # 逆張り分析
            st.markdown("---")
            st.subheader("🔄 レジーム反転分析（逆張り視点）")
            cv = analysis.get("contrarian_view", {})
            if cv:
                regime = cv.get("current_regime", "N/A")
                next_regime = "リスクオン" if "オフ" in regime else "リスクオフ"
                st.info(f"📍 現在: **{regime}** → 次の **{next_regime}** への転換を分析")

                st.markdown("**🔑 反転トリガー（これが起きたら流れが変わる）:**")
                for i, trigger in enumerate(cv.get("regime_reversal_triggers", []), 1):
                    st.warning(f"{i}. {trigger}")

                st.markdown("**📡 先行シグナル（要ウォッチ）:**")
                for signal in cv.get("early_signals_to_watch", []):
                    st.info(f"👁 {signal}")

                st.markdown("**💡 逆張りトレード案:**")
                for trade in cv.get("contrarian_trades", []):
                    with st.expander(f"📌 {trade.get('trade', '')}"):
                        st.write(f"**エントリー条件:** {trade.get('trigger', '')}")
                        st.write(f"**リスク:** {trade.get('risk', '')}")

                if cv.get("timeline"):
                    st.caption(f"⏱ 反転の時間軸目安: {cv['timeline']}")

            # リスク管理
            st.markdown("---")
            st.subheader("🛡 リスク管理")
            rm = analysis.get("risk_management", {})
            c5, c6, c7 = st.columns(3)
            c5.info(f"**損切り:** {rm.get('stop_loss_level', 'N/A')}")
            c6.info(f"**サイズ:** {rm.get('position_sizing', 'N/A')}")
            c7.info(f"**ヘッジ:** {rm.get('hedge_recommendation', 'N/A')}")
            if rm.get("max_drawdown_warning"):
                st.warning(f"⚠️ {rm['max_drawdown_warning']}")

            # 総合サマリー
            st.markdown("---")
            st.subheader("📝 総合サマリー")
            st.info(analysis.get("summary", "N/A"))

            st.caption(f"分析時刻: {all_data.get('timestamp', '')}")

        except json.JSONDecodeError as e:
            st.error(f"⚠️ AI応答のパースに失敗しました: {e}")
            st.text(market_text[:500] if market_text else "No data")
        except Exception as e:
            st.error(f"❌ エラー: {str(e)}")

# サイドバー
with st.sidebar:
    st.markdown("### 📊 データソース (20カテゴリ)")
    st.markdown("""
    **既存 (11)**
    - 市場指数 (S&P500, NASDAQ, VIX, Russell2000...)
    - 金利・債券 (米国債利回り, イールドカーブ)
    - 為替 (USD/JPY, EUR/USD...)
    - 商品 (金, 銅, 原油, 天然ガス)
    - 暗号資産 (BTC, ETH, SOL)
    - セクターETF (11セクター)
    - 半導体 (SOX, SMH)
    - 海運 (BDRY, SBLK)
    - 不動産 (XLRE, ITB, MBB)
    - オプション (VIX)
    - 予測市場 (Polymarket)
    
    **新規 (9)**
    - 🏦 金利サイクル (TIP, RINF, SHV)
    - 💳 信用ストレス (HYG, LQD, JNK)
    - 🤖 AI/テックバブル (IGV, ARKK, IGV/SPY)
    - 📊 高度ボラティリティ (UVXY, SVXY, TLT)
    - 🌍 通貨強弱 (9通貨ペア)
    - 🎯 流動性ドミノ (Alice Diagnosis入力)
    - 🔀 セクターローテーション分析
    - ⚔️ BTC vs 金融株
    - ⚠️ 市場の歪み (TAIL, EMB, BKLN)
    """)
    st.markdown("---")
    st.markdown("### ⚙️ 設定")
    st.caption("モデル: Claude Sonnet 4")
    st.caption("データ: yfinance + Polymarket API")
    st.caption("max_tokens: 8192")
