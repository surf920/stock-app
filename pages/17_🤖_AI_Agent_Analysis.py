import streamlit as st
import requests

st.set_page_config(page_title="AI Agent Analysis", page_icon="🤖", layout="wide")

st.title("🤖 AI Agent 市場分析")
st.markdown("Claude APIを使用した総合市場分析")

API_URL = "https://stock-app-production-8365.up.railway.app"

if st.button("🔍 市場分析を実行", type="primary", use_container_width=True):
    with st.spinner("AI Agentが市場を分析中... (10-30秒かかります)"):
        try:
            response = requests.get(f"{API_URL}/api/agent/analyze", timeout=60)
            data = response.json()

            if data.get("success"):
                analysis = data.get("analysis", {})

                st.markdown("---")
                st.subheader("📊 市場評価")
                col1, col2 = st.columns(2)
                with col1:
                    risk = analysis.get("market_assessment", {}).get("overall_risk", "N/A")
                    st.metric("総合リスク", risk)
                with col2:
                    confidence = analysis.get("market_assessment", {}).get("confidence", "N/A")
                    st.metric("信頼度", f"{confidence}%")

                col3, col4 = st.columns(2)
                with col3:
                    st.markdown("**⚠️ 主な懸念点:**")
                    for c in analysis.get("market_assessment", {}).get("key_concerns", []):
                        st.warning(c)
                with col4:
                    st.markdown("**💡 投資機会:**")
                    for o in analysis.get("market_assessment", {}).get("opportunities", []):
                        st.success(o)

                st.markdown("---")
                st.subheader("💼 ポートフォリオ推奨")
                for rec in analysis.get("portfolio_recommendations", []):
                    action = rec.get("action", "")
                    icon = {"買い": "🟢", "売り": "🔴", "ホールド": "🟡", "リバランス": "🔄"}.get(action, "📌")
                    with st.expander(f"{icon} {action} - {rec.get('asset_class', '')} ({rec.get('target_allocation', '')})"):
                        st.write(f"**理由:** {rec.get('reasoning', '')}")
                        st.write(f"**緊急度:** {rec.get('urgency', '')}")

                st.markdown("---")
                st.subheader("🎯 具体的アクション")
                for act in analysis.get("specific_actions", []):
                    cv = act.get("confidence", 0)
                    icon = "🟢" if cv >= 80 else "🟡" if cv >= 60 else "🔴"
                    st.markdown(f"{icon} **{act.get('action', '')}** - {act.get('ticker', '')} (信頼度: {cv}%)")
                    st.caption(act.get("rationale", ""))

                st.markdown("---")
                st.subheader("🛡️ リスク管理")
                rm = analysis.get("risk_management", {})
                c5, c6, c7 = st.columns(3)
                c5.info(f"**損切り:** {rm.get('stop_loss_level', 'N/A')}")
                c6.info(f"**サイズ:** {rm.get('position_sizing', 'N/A')}")
                c7.info(f"**ヘッジ:** {rm.get('hedge_recommendation', 'N/A')}")

                st.markdown("---")
                st.subheader("📝 総合サマリー")
                st.info(analysis.get("summary", "N/A"))
                st.caption(f"分析時刻: {data.get('timestamp', '')}")
            else:
                st.error(f"分析エラー: {data.get('error', '不明')}")
        except requests.exceptions.ConnectionError:
            st.error("⚠️ APIサーバーに接続できません")
        except Exception as e:
            st.error(f"エラー: {str(e)}")

with st.sidebar:
    st.markdown("### 📡 API状態")
    try:
        h = requests.get(f"{API_URL}/", timeout=5)
        if h.status_code == 200:
            st.success("✅ Railway API稼働中")
        else:
            st.error("❌ APIエラー")
    except:
        st.error("❌ API未接続")
