import streamlit as st
import pandas as pd
import yfinance as yf
import ssl

# --- 🚨 通信エラー回避 ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ----------------------

# ページ設定
st.set_page_config(page_title="AI投資コックピット", page_icon="🚀", layout="wide")

# --- 💰 収益化コンポーネント (サイドバー広告) ---
def show_sidebar_ads():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📢 おすすめツール")
    
    # アフィリエイトリンクの例 (実際はASPのリンクに差し替えます)
    st.sidebar.info("""
    **📈 TradingView**
    
    プロも使う最強チャートツール。
    [👉 無料で試す](https://jp.tradingview.com/)
    """)
    
    st.sidebar.success("""
    **🐮 MooMoo証券**
    
    機関投資家の手口が見れるアプリ。
    [👉 口座開設はこちら](https://www.moomoo.com/jp)
    """)
    
    st.sidebar.warning("""
    **🔒 Ledger Nano**
    
    暗号資産をハッキングから守る。
    [👉 公式ストアへ](https://shop.ledger.com/)
    """)
    
    st.sidebar.caption("※当サイトはアフィリエイトプログラムを利用しています。")

# サイドバー広告を表示
show_sidebar_ads()

# --- メインコンテンツ開始 ---
st.title("🚀 AI投資コックピット 2026 (司令室)")
st.markdown("全9ページの市場データを統合し、現在の**「投資チャンス」**と**「リスク」**を一元管理します。")

# --- データ一括取得関数 (変更なし) ---
@st.cache_data(ttl=600)
def get_dashboard_data():
    tickers = {
        "NVIDIA": "NVDA", "BDRY": "BDRY", "USD/JPY": "JPY=X", "US10Y": "^TNX",
        "Copper": "HG=F", "Gold": "GC=F", "Oil": "CL=F", "Bitcoin": "BTC-USD",
        "Tech": "XLK", "Energy": "XLE", "REIT": "XLRE", "VIX": "^VIX", "SKEW": "^SKEW"
    }
    data = {}
    try:
        for name, ticker in tickers.items():
            t = yf.Ticker(ticker)
            hist = t.history(period="3mo")
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change = price - prev
                pct = (change / prev) * 100
                ma50 = hist['Close'].rolling(50).mean().iloc[-1]
                data[name] = {
                    "Price": price, "Change": change, "Pct": pct, "MA50": ma50,
                    "Trend": "UP" if price > ma50 else "DOWN"
                }
            else:
                data[name] = None
    except:
        pass
    return data

# --- データ取得 ---
d = get_dashboard_data()

# --- AIスコア計算ロジック (変更なし) ---
score = 50
reasons = []

if d:
    # (スコア計算ロジックは前回と同じ)
    if d["VIX"]["Price"] < 20: score += 10; reasons.append("✅ VIX安定 (+10)")
    else: score -= 20; reasons.append("🛑 VIX恐怖圏 (-20)")
    if d["SKEW"]["Price"] > 140: score -= 20; reasons.append("🦢 ブラックスワン警戒 (-20)")
    if d.get("Copper") and d.get("Gold"):
        ratio = d["Copper"]["Price"] / d["Gold"]["Price"]
        if ratio > 0.15: score += 10; reasons.append("✅ 景気(銅)強気 (+10)")
    if d["BDRY"]["Trend"] == "UP": score += 5; reasons.append("✅ 物流(海運)活発 (+5)")
    if d["NVIDIA"]["Trend"] == "UP": score += 10; reasons.append("✅ AI主導株堅調 (+10)")
    else: score -= 10
    if d["Bitcoin"]["Trend"] == "UP": score += 5; reasons.append("✅ リスク選好(BTC) (+5)")
    score = max(0, min(100, score))

    # --- アクションプラン ---
    if score >= 70:
        status = "積極投資 (Strong Buy)"; color = "#00CC96"
        action_msg = "今は「攻め」の時です。上昇トレンドに乗ってください。"
        portfolio = "株式 80% / 現金 10% / その他 10%"
        tactic = "押し目は積極的に拾う。レバレッジETFも検討可。"
    elif score >= 40:
        status = "様子見 (Neutral)"; color = "#FFA15A"
        action_msg = "方向感が乏しい、またはリスクとチャンスが混在しています。"
        portfolio = "株式 50% / 現金 40% / 金・債券 10%"
        tactic = "無理に動かない。「優良株の急落」だけを拾う。高値追いは禁止。"
    else:
        status = "警戒 (Defensive)"; color = "#EF553B"
        action_msg = "嵐が来ています。資産を守ることを最優先にしてください。"
        portfolio = "株式 20% / 現金 60% / ヘッジ 20%"
        tactic = "含み益は利確して現金化。落ちるナイフは掴まない。"

    # --- UI表示 ---
    col_score, col_advice = st.columns([1, 2])
    with col_score:
        st.markdown(f"""
        <div style="text-align: center; border: 4px solid {color}; border-radius: 10px; padding: 20px; background-color: rgba(0,0,0,0.3);">
            <h4 style="margin:0;">AI市場スコア</h4>
            <h1 style="font-size: 80px; margin: 0; color: {color};">{score}</h1>
            <h3 style="margin: 0; color: {color};">{status}</h3>
        </div>
        """, unsafe_allow_html=True)
    with col_advice:
        st.markdown(f"### 👮‍♂️ AI投資アドバイザーの助言")
        st.info(f"**現状の判断:** {action_msg}")
        c_a, c_b = st.columns(2)
        with c_a:
            st.markdown(f"**💰 推奨ポートフォリオ**")
            st.code(portfolio, language="text")
        with c_b:
            st.markdown(f"**⚔️ 今取るべき戦術**")
            st.warning(tactic)
        with st.expander("📝 スコアの算出根拠を見る"):
            for r in reasons: st.write(r)

    st.markdown("---")

    # --- 💰 収益化バナーエリア (記事中広告) ---
    # ここに「証券口座開設」などの横長バナーを置くとクリック率が高いです
    st.markdown("""
    <div style="background-color: #262730; border: 1px solid #FFD700; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
        <h3 style="margin:0; color: #FFD700;">🦁 米国株・オプション取引を始めるなら？</h3>
        <p>当アプリで分析したVIXやSKEWを活用するには、オプション取引対応の証券口座が必須です。</p>
        <a href="https://www.moomoo.com/jp" target="_blank" style="background-color: #FFD700; color: black; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
            👉 プロ愛用のツール「MooMoo」を無料で試す
        </a>
    </div>
    """, unsafe_allow_html=True)
    # ----------------------------------------

    # 2. 全マーケット要約
    st.subheader("📊 全マーケット要約 (Summary)")
    st.markdown("""<style>div[data-testid="stMetric"] { background-color: #262730; padding: 10px; border-radius: 5px; }</style>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### 🚀 成長・ハイテク")
        nvda = d["NVIDIA"]; btc = d["Bitcoin"]; xlk = d["Tech"]
        st.metric("01. 半導体 (NVDA)", f"${nvda['Price']:.2f}", f"{nvda['Pct']:.2f}%")
        st.metric("05. ビットコイン (BTC)", f"${btc['Price']:,.0f}", f"{btc['Pct']:.2f}%")
        st.caption(f"セクター動向: Techトレンドは {xlk['Trend']}")
    with c2:
        st.markdown("#### 🌏 実体経済・マクロ")
        bdry = d["BDRY"]; us10y = d["US10Y"]; jpy = d["USD/JPY"]
        st.metric("02. 海運 (BDRY)", f"{bdry['Price']:.2f}", f"{bdry['Pct']:.2f}%")
        st.metric("03. 米10年債金利", f"{us10y['Price']:.2f}%", f"{us10y['Pct']:.2f}%")
        st.caption(f"ドル円: ¥{jpy['Price']:.2f}")
    with c3:
        st.markdown("#### 🛡️ リスク管理")
        vix = d["VIX"]; skew = d["SKEW"]; reit = d["REIT"]
        v_col = "inverse" if vix['Price'] > 20 else "normal"
        st.metric("09. 恐怖指数 (VIX)", f"{vix['Price']:.2f}", f"{vix['Pct']:.2f}%", delta_color=v_col)
        s_col = "inverse" if skew['Price'] > 140 else "off"
        st.metric("09. SKEW (暴落警戒)", f"{skew['Price']:.2f}", f"{skew['Pct']:.2f}%", delta_color=s_col)
        st.caption(f"不動産(REIT)トレンド: {reit['Trend']}")

else:
    st.error("データ取得中...")

# --- ⚠️ 免責事項 (必須) ---
st.markdown("---")
st.caption("""
**免責事項:**
本アプリは情報提供のみを目的としており、投資勧誘を目的としたものではありません。
表示されるスコアやシグナルはAIによる自動計算であり、将来の運用成果を保証するものではありません。
投資判断はご自身の責任において行ってください。当サイトのリンクにはアフィリエイトが含まれる場合があります。
""")