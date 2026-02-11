
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
import json

st.set_page_config(page_title="予想市場とマクロ", page_icon="🔮", layout="wide")

st.title("🔮 予想市場 (Polymarket) とマクロ分析")
st.markdown("分散型予想市場 Polymarket のデータを活用し、市場が織り込んでいる「金利」「景気後退」「地政学リスク」の確率を可視化します。")
st.info("ℹ️ データ取得ロジックを一括取得方式に変更し、表示の安定性を向上させました。")

# --- 関数: Polymarketデータの取得 (一括取得) ---
@st.cache_data(ttl=600)  # 10分間キャッシュ
def fetch_top_markets():
    # キーワード指定なし、ボリューム順で上位50件を取得
    url = "https://gamma-api.polymarket.com/markets"
    
    params = {
        "limit": 50,
        "active": "true",
        "closed": "false",
        "order": "volume"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        st.error(f"Data Fetch Error: {e}")
        return []

# --- 関数: 確率バーの表示 ---
def display_market_probability(markets, title):
    st.subheader(title)
    
    if not markets:
        st.markdown(f"<span style='color:gray'>※ 現在、関連するトップ市場はありません。</span>", unsafe_allow_html=True)
        return

    # 上位3つを表示
    for m in markets[:3]:
        question = m.get('question', 'No Question')
        outcomes = m.get('outcomes', [])
        outcome_prices = m.get('outcomePrices', [])
        
        # JSON文字列のパース
        if isinstance(outcomes, str):
            try: outcomes = json.loads(outcomes)
            except: pass
        if isinstance(outcome_prices, str):
            try: outcome_prices = json.loads(outcome_prices)
            except: pass

        if not outcome_prices or not outcomes:
            continue

        # 一番確率が高い結果を取得
        try:
            prices = [float(p) for p in outcome_prices]
            max_price = max(prices)
            max_index = prices.index(max_price)
            top_outcome = outcomes[max_index]
            probability = max_price * 100
        except:
            continue

        with st.container():
            st.markdown(f"**{question}**")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.progress(int(probability))
            with col2:
                st.write(f"**{top_outcome}: {probability:.1f}%**")
            
            vol = float(m.get('volume', 0) or 0)
            st.caption(f"Volume: ${vol:,.0f}")
            st.divider()

# --- メイン処理 ---

# 1. データの取得
all_markets = fetch_top_markets()

# 2. フィルタリング（振り分け）
fed_keywords = ["Fed", "Rate", "Cut", "Hike"]
crypto_keywords = ["Bitcoin", "BTC", "Ethereum", "ETH"]
macro_keywords = ["Recession", "War", "Trump", "GDP", "Israel"]

filtered_fed = []
filtered_crypto = []
filtered_macro = []
filtered_other = []

# すでに分類された市場のIDを記録して重複を防ぐ（念のため）
displayed_ids = set()

for m in all_markets:
    q = m.get('question', '')
    m_id = m.get('id', '')
    
    # Check for categories
    is_categorized = False
    
    # FRB/Rates
    if any(k.lower() in q.lower() for k in fed_keywords):
        filtered_fed.append(m)
        is_categorized = True
        
    # Crypto
    elif any(k.lower() in q.lower() for k in crypto_keywords):
        filtered_crypto.append(m)
        is_categorized = True
        
    # Macro/Politics
    elif any(k.lower() in q.lower() for k in macro_keywords):
        filtered_macro.append(m)
        is_categorized = True
    
    # Others
    if not is_categorized:
        filtered_other.append(m)

# 3. 表示
display_market_probability(filtered_fed, "🏛️ FRB 金利・金融政策 (Fed)")
display_market_probability(filtered_macro, "📉 マクロ・政治・地政学 (Macro & Politics)")
display_market_probability(filtered_crypto, "🪙 暗号資産 (Crypto)")
display_market_probability(filtered_other, "🔥 その他トレンド (Trending)")

# 4. デバッグ用表示
st.markdown("---")
with st.expander("🛠️ 取得した生データ確認 (Debug)"):
    if all_markets:
        st.write(f"Total Fetched: {len(all_markets)} markets")
        st.json(all_markets[:3])
    else:
        st.warning("No data fetched.")
