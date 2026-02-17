
import streamlit as st
import json
import pandas as pd
from core.market_indicators import market_indicators
from core.agent_analysis import agent_analysis

st.set_page_config(page_title="AI Agent Analysis", page_icon="🤖", layout="wide")

st.title("🤖 AI Agent Teams: Strategic Market Analysis")
st.markdown("Claude 3.5 Sonnet (Agent) が市場指標を統合分析し、プロフェッショナルな投資判断を提供します。")

# サイドバー: APIキーの状態確認
import os
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    st.sidebar.error("⚠️ ANTHROPIC_API_KEY が設定されていません")
    st.warning("分析を開始するには `.env` ファイルに `ANTHROPIC_API_KEY` を設定してください。")
else:
    st.sidebar.success("✅ Agent Active (Claude-3.5-Sonnet)")

# メインアクション
if st.button("🧠 AIエージェントに分析を依頼する (Start Analysis)", type="primary", disabled=not api_key):
    with st.spinner("Agent is analyzing market structures... (Takes 10-20s)"):
        try:
            # 1. データ収集
            indicators = market_indicators.get_all_indicators()
            
            # 2. Agent分析実行
            result = agent_analysis.analyze_market(indicators)
            
            if result.get("success"):
                analysis = result.get("analysis", {})
                
                # --- 結果表示セクション ---
                st.divider()
                
                # 1. 市場評価 (Assessment)
                assess = analysis.get("market_assessment", {})
                col1, col2, col3 = st.columns(3)
                col1.metric("Overall Risk", assess.get("overall_risk", "N/A"))
                col2.metric("Confidence Score", f"{assess.get('confidence', 0)}/100")
                col3.markdown(f"**Key Concerns:**\n" + "\n".join([f"- {x}" for x in assess.get("key_concerns", [])]))

                # 2. 推奨ポートフォリオ (Recommendations)
                st.subheader("📊 Portfolio Allocation Strategy")
                recs = analysis.get("portfolio_recommendations", [])
                if recs:
                    rec_df = pd.DataFrame(recs)
                    st.dataframe(rec_df, use_container_width=True)
                
                # 3. 具体的なアクション (Specific Actions)
                st.subheader("⚡ Specific Actions")
                actions = analysis.get("specific_actions", [])
                for action in actions:
                    st.info(f"**{action.get('action')}**: {action.get('ticker', '')} - {action.get('rationale')}")

                # 4. 生の思考プロセス (Raw Summary)
                with st.expander("Show Agent's Full Summary"):
                    st.write(analysis.get("summary", ""))
                
            else:
                st.error(f"Analysis Failed: {result.get('error')}")
                
        except Exception as e:
            st.error(f"System Error: {str(e)}")

# 解説
st.divider()
st.caption("Powered by Anthropic Claude 3.5 Sonnet & Market Cycle AI")
