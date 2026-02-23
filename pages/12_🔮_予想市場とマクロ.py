import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
import json

st.set_page_config(page_title="予想市場とマクロ", page_icon="🔮", layout="wide")

st.title("🔮 予想市場（Polymarket）とマクロ分析")
st.markdown("分散型予想市場 Polymarket のデータを活用し、市場が織り込んでいる「金利」「景気後退」「地政学リスク」の確率を可視化します。")

# --- カテゴリ定義 ---
CATEGORIES = {
    "🏛 FRB 金利・金融政策 (Fed)": {
        "keywords": ["fed", "rate", "cut", "hike", "fomc", "interest", "powell", "inflation", "cpi", "pce", "monetary"],
        "markets": []
    },
    "📉 マクロ・政治・地政学 (Macro & Politics)": {
        "keywords": ["recession", "war", "trump", "gdp", "tariff", "china", "russia", "ukraine", "israel", "iran", "election", "congress", "senate", "macron", "eu", "nato", "deport", "immigration", "trade"],
        "markets": []
    },
    "🪙 暗号資産 (Crypto)": {
        "keywords": ["bitcoin", "btc", "ethereum", "eth", "crypto", "solana", "sol", "xrp", "microstrategy", "coinbase", "binance", "defi", "nft", "stablecoin"],
        "markets": []
    },
    "📊 株式・企業 (Stocks & Companies)": {
        "keywords": ["stock", "s&p", "sp500", "nasdaq", "apple", "tesla", "nvidia", "ipo", "earnings", "market cap", "dow"],
        "markets": []
    },
}

# --- データ取得: Events API ---
@st.cache_data(ttl=600)
def fetch_polymarket_events():
    url = "https://gamma-api.polymarket.com/events"
    all_markets = []
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    
    for offset in [0, 20, 40]:
        params = {
            "limit": 20,
            "active": "true",
            "closed": "false",
            "offset": offset
        }
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            events = response.json()
            if not isinstance(events, list):
                continue
            for event in events:
                markets = event.get("markets", [])
                for m in markets:
                    # Parse outcomePrices
                    op = m.get("outcomePrices", "")
                    if isinstance(op, str):
                        try:
                            op = json.loads(op)
                        except:
                            continue
                    if not op:
                        continue
                    
                    # Parse outcomes
                    outcomes = m.get("outcomes", [])
                    if isinstance(outcomes, str):
                        try:
                            outcomes = json.loads(outcomes)
                        except:
                            continue
                    
                    # Skip resolved (0/1)
                    try:
                        floats = [float(p) for p in op]
                    except:
                        continue
                    if max(floats) >= 0.99 or max(floats) <= 0.01:
                        continue
                    
                    all_markets.append({
                        "question": m.get("question", ""),
                        "outcomes": outcomes,
                        "prices": floats,
                        "volume": float(m.get("volume", 0) or 0),
                        "image": m.get("image", ""),
                        "slug": m.get("slug", ""),
                        "event_title": event.get("title", ""),
                    })
        except Exception as e:
            st.warning(f"API Error (offset={offset}): {e}")
            continue
    
    return all_markets

# --- 表示関数 ---
def display_category(markets, title):
    st.subheader(title)
    
    if not markets:
        st.markdown(f"<span style='color:gray'>※ 現在、関連するトップ市場はありません。</span>", unsafe_allow_html=True)
        return
    
    # ボリューム順にソート
    sorted_markets = sorted(markets, key=lambda x: x["volume"], reverse=True)
    
    for m in sorted_markets[:5]:
        question = m["question"]
        outcomes = m["outcomes"]
        prices = m["prices"]
        volume = m["volume"]
        
        # 一番確率が高い結果
        max_idx = prices.index(max(prices))
        top_outcome = outcomes[max_idx] if max_idx < len(outcomes) else "?"
        probability = prices[max_idx] * 100
        
        with st.container():
            st.markdown(f"**{question}**")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                # 確率バー
                st.progress(min(int(probability), 100))
                
                # 全outcomes表示
                outcome_text = " | ".join([
                    f"{'👉 ' if i == max_idx else ''}{outcomes[i]}: **{prices[i]*100:.1f}%**"
                    for i in range(min(len(outcomes), len(prices)))
                ])
                st.markdown(outcome_text, unsafe_allow_html=True)
                
            with col2:
                st.metric("Top", f"{top_outcome}", f"{probability:.1f}%")
                if volume > 0:
                    st.caption(f"Volume: ${volume:,.0f}")
            
            st.divider()

# --- メイン処理 ---

# 1. データ取得
with st.spinner("Polymarketからデータを取得中..."):
    all_markets = fetch_polymarket_events()

st.info(f"📊 {len(all_markets)} 件のアクティブな予測市場を取得しました")

# 2. フィルタリング
for m in all_markets:
    q = m["question"].lower()
    is_categorized = False
    
    for cat_name, cat_data in CATEGORIES.items():
        if any(k in q for k in cat_data["keywords"]):
            cat_data["markets"].append(m)
            is_categorized = True
            break
    
    if not is_categorized:
        # "その他トレンド" に追加
        if "other" not in CATEGORIES:
            CATEGORIES["🔥 その他トレンド (Trending)"] = {"keywords": [], "markets": []}
        # Find the "その他" key
        for k in CATEGORIES:
            if "その他" in k:
                CATEGORIES[k]["markets"].append(m)
                break

# 3. 表示
for cat_name, cat_data in CATEGORIES.items():
    display_category(cat_data["markets"], cat_name)

# 4. サマリーチャート
st.markdown("---")
st.subheader("📊 カテゴリ別 市場数")

chart_data = []
for cat_name, cat_data in CATEGORIES.items():
    chart_data.append({
        "カテゴリ": cat_name.split("(")[0].strip(),
        "市場数": len(cat_data["markets"]),
        "平均Volume": sum(m["volume"] for m in cat_data["markets"]) / max(len(cat_data["markets"]), 1)
    })

if chart_data:
    df = pd.DataFrame(chart_data)
    fig = px.bar(df, x="カテゴリ", y="市場数", color="カテゴリ", title="カテゴリ別アクティブ市場数")
    st.plotly_chart(fig, use_container_width=True)

# 5. デバッグ
with st.expander("🔧 取得した生データ確認（Debug）"):
    if all_markets:
        st.write(f"Total: {len(all_markets)} markets")
        st.json(all_markets[:3])
    else:
        st.warning("No data fetched.")
