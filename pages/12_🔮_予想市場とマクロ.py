from core.auth import require_auth
require_auth()

import streamlit as st
import pandas as pd
import requests
from api_helper import call_anthropic_api
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



# --- AI要約機能 ---
def call_polymarket_ai(all_markets, categories):
    """Polymarketデータをもとにマクロ分析"""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    data_text = "## Polymarket 予想市場データ\n\n"
    
    for cat in categories:
        if cat["markets"]:
            data_text += f"### {cat['name']}\n"
            sorted_m = sorted(cat["markets"], key=lambda x: x["volume"], reverse=True)
            for m in sorted_m[:5]:
                prices = m["prices"]
                outcomes = m["outcomes"]
                max_idx = prices.index(max(prices))
                top_outcome = outcomes[max_idx] if max_idx < len(outcomes) else "?"
                prob = prices[max_idx] * 100
                data_text += f"- {m['question']}: {top_outcome} {prob:.1f}% (Volume: ${m['volume']:,.0f})\n"
            data_text += "\n"

    data_text += f"\n合計アクティブ市場数: {len(all_markets)}\n"
    
    # カテゴリ別集計
    data_text += "\n## カテゴリ別集計\n"
    for cat in categories:
        total_vol = sum(m["volume"] for m in cat["markets"])
        data_text += f"- {cat['name']}: {len(cat['markets'])}件, 合計Volume: ${total_vol:,.0f}\n"

    system_prompt = """あなたはブリッジウォーターとシタデルで20年の経験を持つマクロストラテジストです。
予想市場（Polymarket）のデータから、市場参加者の「集合知」が織り込んでいる未来を読み解きます。

【重要】現在の日付は2026年2月です。全ての予測は2026年2月時点からの未来について述べてください。

提供されたデータを分析し、以下のJSON形式で回答してください。
予想市場の確率は「賢い群衆の予測」として扱い、投資判断に活用する視点で分析してください。

【分析ルール】
1. 必ず具体的な数値を引用（各市場の確率、Volume）
2. 高Volume市場ほど信頼性が高い（多くの資金が賭けられている）
3. 予想市場の確率変動はニュースよりも早く織り込まれることが多い
4. カテゴリ横断的な「メタシグナル」を読み取る（例: 金利+景気後退+地政学の組み合わせ）
5. データにない事実を捏造しない

{
    "market_regime": {
        "overall_sentiment": "リスクオン/リスクオフ/中立",
        "confidence": "高/中/低（予想市場全体の確信度）",
        "headline": "予想市場が織り込んでいる未来を1行で"
    },
    "category_insights": {
        "fed_rates": {
            "summary": "FRB・金利カテゴリの予想市場が示していることを2-3文で",
            "market_implication": "投資への含意を1文で"
        },
        "macro_politics": {
            "summary": "マクロ・政治カテゴリの予想市場が示していることを2-3文で",
            "market_implication": "投資への含意を1文で"
        },
        "crypto": {
            "summary": "暗号資産カテゴリの予想市場が示していることを2-3文で",
            "market_implication": "投資への含意を1文で"
        },
        "stocks": {
            "summary": "株式カテゴリの予想市場が示していることを2-3文で",
            "market_implication": "投資への含意を1文で"
        }
    },
    "meta_signals": {
        "cross_category_insight": "カテゴリ横断で読み取れるメタシグナルを3-4文で。例: 金利引下げ確率が高い＋景気後退確率が上昇→リスクオフ環境",
        "smart_money_positioning": "賢い資金（高Volume市場）が示唆するポジショニングを2文で",
        "contrarian_opportunity": "予想市場の確率と実態の乖離から見える逆張り機会を2文で"
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "予想市場が最も織り込んでいるシナリオ",
            "narrative": "3-4文で展開を説明",
            "investment_action": "具体的な投資アクション"
        },
        "surprise_scenario": {
            "probability": 25,
            "title": "予想市場が織り込んでいないサプライズ",
            "narrative": "3-4文で展開を説明",
            "investment_action": "具体的な投資アクション"
        },
        "tail_risk": {
            "probability": 25,
            "title": "テールリスクシナリオ",
            "narrative": "3-4文で展開を説明",
            "investment_action": "具体的な投資アクション"
        }
    },
    "actionable_trades": [
        {
            "trade": "具体的なトレードアイデア",
            "rationale": "予想市場のどのデータに基づくか",
            "risk": "リスク要因"
        }
    ],
    "risk_monitor": {
        "watch_items": ["監視すべき予想市場の変動1", "2", "3"],
        "next_inflection": "次の転換点はいつ・何がきっかけか"
    }
}"""

    headers = {"x-api-key": api_key, "content-type": "application/json", "anthropic-version": "2023-06-01"}
    payload = {"model": "claude-sonnet-4-20250514", "max_tokens": 4096, "system": system_prompt, "messages": [{"role": "user", "content": data_text}]}

    try:
        result_data, api_error = call_anthropic_api(headers, payload)
        if api_error:
            return None
        return result_data
    except Exception as e:
        st.error(f"AI分析エラー: {e}")
        return None


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


# --- AI予想市場分析セクション ---
st.markdown("---")
st.subheader("🤖 AI予想市場マクロ分析")
st.caption("マクロストラテジスト視点の予想市場分析")

if st.button("🧠 AIで予想市場を分析", use_container_width=True):
    with st.spinner("🔄 Claude AIが予想市場を分析中..."):
        ai_result = call_polymarket_ai(all_markets, CATEGORIES)
    
    if ai_result:
        # マーケットレジーム
        regime = ai_result.get("market_regime", {})
        sentiment = regime.get("overall_sentiment", "中立")
        sentiment_emoji = {"リスクオン": "🟢", "リスクオフ": "🔴", "中立": "🟡"}.get(sentiment, "⚪")
        confidence = regime.get("confidence", "中")
        
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.metric("マーケットセンチメント", f"{sentiment_emoji} {sentiment}")
        with col_r2:
            st.metric("予想市場の確信度", confidence)
        
        headline = regime.get("headline", "")
        if headline:
            st.info(f"📋 **予想市場の結論:** {headline}")
        
        st.markdown("---")
        
        # カテゴリ別インサイト
        cat_insights = ai_result.get("category_insights", {})
        if cat_insights:
            st.markdown("### 📊 カテゴリ別インサイト")
            cols_cat = st.columns(2)
            items = [
                ("🏛 FRB・金利", "fed_rates", "#3498db"),
                ("📉 マクロ・政治", "macro_politics", "#e74c3c"),
                ("🪙 暗号資産", "crypto", "#9b59b6"),
                ("📊 株式", "stocks", "#27ae60")
            ]
            for idx, (label, key, color) in enumerate(items):
                with cols_cat[idx % 2]:
                    item = cat_insights.get(key, {})
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid {color}; margin-bottom: 10px;">
                        <h4 style="color: {color}; margin: 0 0 8px 0;">{label}</h4>
                        <p style="color: #ddd; font-size: 0.85em; margin: 0 0 5px 0;">{item.get('summary', '')}</p>
                        <p style="color: {color}; font-size: 0.8em; margin: 0;">💼 {item.get('market_implication', '')}</p>
                    </div>""", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # メタシグナル
        meta = ai_result.get("meta_signals", {})
        if meta:
            st.markdown("### 🔗 メタシグナル（カテゴリ横断分析）")
            st.markdown(meta.get("cross_category_insight", ""))
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.info(f"🏦 **スマートマネー:** {meta.get('smart_money_positioning', '')}")
            with col_m2:
                st.warning(f"🔄 **逆張り機会:** {meta.get('contrarian_opportunity', '')}")
        
        st.markdown("---")
        
        # シナリオ分析
        st.markdown("### 🔮 フォワードシナリオ分析")
        scenarios = ai_result.get("forward_scenarios", {})
        
        base = scenarios.get("base_case", {})
        st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #8e44ad; margin-bottom: 15px;">
            <h4 style="color: #8e44ad; margin-top: 0;">🔮 コンセンサス ({base.get('probability', 50)}%): {base.get('title', '')}</h4>
            <p style="color: #ddd;">{base.get('narrative', '')}</p>
            <p style="color: #8e44ad; margin-bottom: 0;">💼 <b>アクション:</b> {base.get('investment_action', '')}</p>
        </div>""", unsafe_allow_html=True)
        
        col_s1, col_s2 = st.columns(2)
        surprise = scenarios.get("surprise_scenario", {})
        with col_s1:
            st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #f39c12;">
                <h4 style="color: #f39c12; margin-top: 0;">⚡ サプライズ ({surprise.get('probability', 25)}%): {surprise.get('title', '')}</h4>
                <p style="color: #ddd; font-size: 0.9em;">{surprise.get('narrative', '')}</p>
                <p style="color: #f39c12; font-size: 0.85em; margin-bottom: 0;">💼 {surprise.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
        
        tail = scenarios.get("tail_risk", {})
        with col_s2:
            st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B;">
                <h4 style="color: #FF4B4B; margin-top: 0;">🦢 テールリスク ({tail.get('probability', 25)}%): {tail.get('title', '')}</h4>
                <p style="color: #ddd; font-size: 0.9em;">{tail.get('narrative', '')}</p>
                <p style="color: #FF4B4B; font-size: 0.85em; margin-bottom: 0;">💼 {tail.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # トレードアイデア
        trades = ai_result.get("actionable_trades", [])
        if trades:
            st.markdown("### 💡 トレードアイデア")
            for t in trades:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #2ecc71; margin-bottom: 8px;">
                    <p style="color: #2ecc71; font-weight: bold; margin: 0 0 5px 0;">📈 {t.get('trade', '')}</p>
                    <p style="color: #ddd; font-size: 0.85em; margin: 0 0 3px 0;">📋 根拠: {t.get('rationale', '')}</p>
                    <p style="color: #e74c3c; font-size: 0.8em; margin: 0;">⚠️ リスク: {t.get('risk', '')}</p>
                </div>""", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # リスクモニター
        rm = ai_result.get("risk_monitor", {})
        st.markdown("### ⚠️ リスクモニター")
        watch = rm.get("watch_items", [])
        if watch:
            for w in watch:
                st.markdown(f"- 👁️ {w}")
        inflection = rm.get("next_inflection", "")
        if inflection:
            st.error(f"🔄 **次の転換点:** {inflection}")


# デバッグ
with st.expander("🔧 取得した生データ確認（Debug）"):
    if all_markets:
        st.write(f"Total: {len(all_markets)} markets")
        for cat in CATEGORIES:
            st.write(f"{cat['name']}: {len(cat['markets'])}件")
        st.json(all_markets[:3])
    else:
        st.warning("No data fetched.")
