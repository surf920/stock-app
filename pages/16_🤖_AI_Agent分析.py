import streamlit as st
import requests
import json

st.set_page_config(page_title="AI Agent分析", page_icon="🤖", layout="wide")

st.title("🤖 AI Agent 市場分析")
st.markdown("Claude APIを使用した総合市場分析")

API_URL = "http://127.0.0.1:8001"

if st.button("🔍 市場分析を実行", type="primary", use_container_width=True):
    with st.spinner("AI Agentが市場を分析中... (10-30秒かかります)"):
        try:
            response = requests.get(f"{API_URL}/api/agent/analyze", timeout=60)
            data = response.json()

            if data.get("success"):
                analysis = data.get("analysis", {})

                # 市場評価
                st.markdown("---")
                st.subheader("📊 市場評価")
                col1, col2 = st.columns(2)
                with col1:
                    risk = analysis.get("market_assessment", {}).get("overall_risk", "N/A")
                    risk_color = {"低": "green", "中": "orange", "高": "red", "極高": "red"}.get(risk, "gray")
                    st.metric("総合リスク", risk)
                with col2:
                    confidence = analysis.get("market_assessment", {}).get("confidence", "N/A")
                    st.metric("信頼度", f"{confidence}%")

                # 懸念点と機会
                col3, col4 = st.columns(2)
                with col3:
                    st.markdown("**⚠️ 主な懸念点:**")
                    concerns = analysis.get("market_assessment", {}).get("key_concerns", [])
                    for c in concerns:
                        st.warning(c)
                with col4:
                    st.markdown("**💡 投資機会:**")
                    opportunities = analysis.get("market_assessment", {}).get("opportunities", [])
                    for o in opportunities:
                        st.success(o)

                # ポートフォリオ推奨
                st.markdown("---")
                st.subheader("💼 ポートフォリオ推奨")
                recommendations = analysis.get("portfolio_recommendations", [])
                for rec in recommendations:
                    action = rec.get("action", "")
                    icon = {"買い": "🟢", "売り": "🔴", "ホールド": "🟡", "リバランス": "🔄"}.get(action, "📌")
                    with st.expander(f"{icon} {action} - {rec.get('asset_class', '')} ({rec.get('target_allocation', '')})"):
                        st.write(f"**理由:** {rec.get('reasoning', '')}")
                        st.write(f"**緊急度:** {rec.get('urgency', '')}")

                # 具体的アクション
                st.markdown("---")
                st.subheader("🎯 具体的アクション")
                actions = analysis.get("specific_actions", [])
                for act in actions:
                    confidence_val = act.get("confidence", 0)
                    icon = "🟢" if confidence_val >= 80 else "🟡" if confidence_val >= 60 else "🔴"
                    st.markdown(f"{icon} **{act.get('action', '')}** - {act.get('ticker', '')} (信頼度: {confidence_val}%)")
                    st.caption(act.get("rationale", ""))

                # リスク管理
                st.markdown("---")
                st.subheader("🛡️ リスク管理")
                risk_mgmt = analysis.get("risk_management", {})
                col5, col6, col7 = st.columns(3)
                with col5:
                    st.info(f"**損切りレベル:** {risk_mgmt.get('stop_loss_level', 'N/A')}")
                with col6:
                    st.info(f"**ポジションサイズ:** {risk_mgmt.get('position_sizing', 'N/A')}")
                with col7:
                    st.info(f"**ヘッジ推奨:** {risk_mgmt.get('hedge_recommendation', 'N/A')}")

                # サマリー
                st.markdown("---")
                st.subheader("📝 総合サマリー")
                st.info(analysis.get("summary", data.get("summary", "N/A")))

                # タイムスタンプ
                st.caption(f"分析時刻: {data.get('timestamp', '')}")

            else:
                st.error(f"分析エラー: {data.get('error', '不明なエラー')}")

        except requests.exceptions.ConnectionError:
            st.error("⚠️ APIサーバーに接続できません。uvicornが起動しているか確認してください。")
        except Exception as e:
            st.error(f"エラー: {str(e)}")

# サイドバー
with st.sidebar:
    st.markdown("### 📡 API状態")
    try:
        health = requests.get(f"{API_URL}/", timeout=5)
        if health.status_code == 200:
            st.success("✅ API稼働中")
        else:
            st.error("❌ APIエラー")
    except:
        st.error("❌ API未接続")
