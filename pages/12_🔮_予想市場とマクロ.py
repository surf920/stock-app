import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
import json
import re

st.set_page_config(page_title="予想市場とマクロ", page_icon="🔮", layout="wide")

st.title("🔮 予想市場（Polymarket）とマクロ分析")
st.markdown("分散型予想市場 Polymarket のデータを活用し、市場が織り込んでいる「金利」「景気後退」「地政学リスク」の確率を可視化します。")

# --- カテゴリ定義（優先順位順: 上から順にマッチ） ---
CATEGORIES = [
    {
        "name": "🪙 暗号資産 (Crypto)",
        "keywords": ["bitcoin", "btc", "ethereum", "eth", "crypto", "solana", "sol", "xrp",
                      "microstrategy", "coinbase", "binance", "defi", "nft", "stablecoin",
                      "altcoin", "memecoin", "dogecoin", "cardano"],
        "markets": []
    },
    {
        "name": "🏛 FRB 金利・金融政策 (Fed)",
        "keywords": ["federal reserve", "fed funds", "rate cut", "rate hike", "fomc",
                      "interest rate", "powell", "inflation", "cpi", "pce", "monetary policy",
                      "basis points", "quantitative"],
        "markets": []
    },
    {
        "name": "📊 株式・企業 (Stocks & Companies)",
        "keywords": ["stock", "s&p", "sp500", "nasdaq", "apple", "tesla", "nvidia",
                      "ipo", "earnings", "market cap", "dow jones", "kraken ipo"],
        "markets": []
    },
    {
        "name": "📉 マクロ・政治・地政学 (Macro & Politics)",
        "keywords": ["recession", "war", "trump", "gdp", "tariff", "china", "russia",
                      "ukraine", "israel", "iran", "election", "congress", "senate",
                      "macron", "eu ", "nato", "deport", "immigration", "trade war",
                      "president", "governor", "ceasefire", "sanctions"],
        "markets": []
    },
    {
        "name": "🔥 その他トレンド (Trending)",
        "keywords": [],
        "markets": []
    },
]


def match_category(question):
    """単語マッチでカテゴリを判定（複合キーワード対応）"""
    q = question.lower()
    for i, cat in enumerate(CATEGORIES):
        for kw in cat["keywords"]:
            # 複合キーワード（スペース含む）はそのまま部分一致
            if " " in kw:
                if kw in q:
                    return i
            else:
                # 単語境界でマッチ（"rate" が "microstrategy" にマッチしない）
                pattern = r'\b' + re.escape(kw) + r'\b'
                if re.search(pattern, q):
                    return i
    return len(CATEGORIES) - 1  # その他


# --- データ取得: Events API ---
@st.cache_data(ttl=600)
def fetch_polymarket_events():
    url = "https://gamma-api.polymarket.com/events"
    all_markets = []
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

    for offset in [0, 20, 40, 60]:
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
                    op = m.get("outcomePrices", "")
                    if isinstance(op, str):
                        try:
                            op = json.loads(op)
                        except Exception:
                            continue
                    if not op:
                        continue

                    outcomes = m.get("outcomes", [])
                    if isinstance(outcomes, str):
                        try:
                            outcomes = json.loads(outcomes)
                        except Exception:
                            continue

                    try:
                        floats = [float(p) for p in op]
                    except Exception:
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
        except Exception:
            continue

    return all_markets


# --- 表示関数 ---
def display_category(markets, title):
    st.subheader(title)

    if not markets:
        st.markdown('<span style="color:gray">※ 現在、関連するトップ市場はありません。</span>', unsafe_allow_html=True)
        return

    sorted_markets = sorted(markets, key=lambda x: x["volume"], reverse=True)

    for m in sorted_markets[:5]:
        question = m["question"]
        outcomes = m["outcomes"]
        prices = m["prices"]
        volume = m["volume"]

        max_idx = prices.index(max(prices))
        top_outcome = outcomes[max_idx] if max_idx < len(outcomes) else "?"
        probability = prices[max_idx] * 100

        with st.container():
            st.markdown(f"**{question}**")

            col1, col2 = st.columns([3, 1])
            with col1:
                st.progress(min(int(probability), 100))
                parts = []
                for i in range(min(len(outcomes), len(prices))):
                    prefix = "👉 " if i == max_idx else ""
                    parts.append(f"{prefix}{outcomes[i]}: **{prices[i]*100:.1f}%**")
                outcome_text = " | ".join(parts)
                st.markdown(outcome_text, unsafe_allow_html=True)

            with col2:
                st.metric("Top", f"{top_outcome}", f"{probability:.1f}%")
                if volume > 0:
                    st.caption(f"Volume: ${volume:,.0f}")

            st.divider()


# --- メイン処理 ---

with st.spinner("Polymarketからデータを取得中..."):
    all_markets = fetch_polymarket_events()

st.info(f"📊 {len(all_markets)} 件のアクティブな予測市場を取得しました")

# フィルタリング
for m in all_markets:
    cat_idx = match_category(m["question"])
    CATEGORIES[cat_idx]["markets"].append(m)

# 表示
for cat in CATEGORIES:
    display_category(cat["markets"], cat["name"])

# サマリーチャート
st.markdown("---")
st.subheader("📊 カテゴリ別 市場数")

chart_data = []
for cat in CATEGORIES:
    chart_data.append({
        "カテゴリ": cat["name"].split("(")[0].strip(),
        "市場数": len(cat["markets"]),
        "合計Volume": sum(m["volume"] for m in cat["markets"])
    })

if chart_data:
    df = pd.DataFrame(chart_data)
    fig = px.bar(df, x="カテゴリ", y="市場数", color="カテゴリ",
                 title="カテゴリ別アクティブ市場数")
    st.plotly_chart(fig, use_container_width=True)

# デバッグ
with st.expander("🔧 取得した生データ確認（Debug）"):
    if all_markets:
        st.write(f"Total: {len(all_markets)} markets")
        for cat in CATEGORIES:
            st.write(f"{cat['name']}: {len(cat['markets'])}件")
        st.json(all_markets[:3])
    else:
        st.warning("No data fetched.")
