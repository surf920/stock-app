import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import ssl

# --- 🚨 SSL Error Handling ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ----------------------

st.set_page_config(page_title="Weekly Report", page_icon="📅", layout="wide")

st.title("📅 Weekly Market Report")
st.markdown("9つの主要セクターを網羅的に分析し、今週の市場テーマとリスクを特定します。")

# --- 1. Data Fetching ---

@st.cache_data(ttl=3600)
def fetch_comprehensive_data():
    """Fetch data for 9 key sectors."""
    tickers = {
        # 1. Semi
        "SOX (Semi)": "^SOX",
        "NVDA (AI)": "NVDA",
        # 2. Shipping
        "BDRY (Shipping)": "BDRY",
        # 3. Rates & FX
        "USD/JPY": "JPY=X",
        "US 10Y Yield": "^TNX",
        # 4. Commodities
        "Gold": "GLD",
        "Oil": "CL=F",
        # 5. Crypto
        "Bitcoin": "BTC-USD",
        "Ethereum": "ETH-USD",
        # 6. Sector Rotation
        "Energy (XLE)": "XLE",
        "Finance (XLF)": "XLF",
        "Tech (XLK)": "XLK",
        # 7. Real Estate
        "Real Estate (VNQ)": "VNQ",
        # 8. Market & AI Bubble Proxy
        "S&P 500": "SPY",     # SPY is safer than ^GSPC for data availability
        "Nasdaq 100": "QQQ",
        # 9. Options/Risk
        "VIX": "^VIX",
        "SKEW": "^SKEW"  
    }
    
    data = {}
    for name, symbol in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            # Fetch a bit more data to ensure we have enough valid days
            hist = ticker.history(period="6mo")
            
            if not hist.empty and "Close" in hist.columns:
                # Forward fill to handle missing days (holidays etc)
                s = hist["Close"].ffill()
                if not s.empty:
                    data[name] = s
            else:
                # Fallback or just skip
                pass
        except Exception:
            pass 
            
    return pd.DataFrame(data)

# --- 2. Helper Functions ---

def get_stats(series):
    """Return latest val, daily changes %, and trend score."""
    if series is None or len(series) < 2:
        return 0.0, 0.0, 50.0
    
    # Drop NaNs just in case
    series = series.dropna()
    if series.empty:
        return 0.0, 0.0, 50.0

    curr = series.iloc[-1]
    prev = series.iloc[-2]
    
    # Safety Check for zero division or NaNs
    if pd.isna(curr) or pd.isna(prev) or prev == 0:
        return 0.0, 0.0, 50.0
        
    change_pct = (curr - prev) / prev * 100
    
    ma50 = series.rolling(50).mean().iloc[-1]
    if pd.isna(ma50) or ma50 == 0: 
        ma50 = curr
    
    # Simple Trend Score (0-100)
    diff = (curr - ma50) / ma50
    score = 50 + (diff * 500)
    score = max(0, min(100, score))
    
    return curr, change_pct, score

def get_trend_icon(score, change_pct):
    # Risk check first
    if change_pct < -2.0: return "⚠️ Crash", "red"
    if score >= 60: return "Bull ↗️", "green"
    if score <= 40: return "Bear ↘️", "red"
    return "Neutral ➡️", "gray"

# --- 3. Analysis Logic ---

def analyze_market_theme(df):
    """
    Determine Risk On/Off and Main Theme.
    Returns: (Title, Color, Description)
    """
    # Extract key stats
    vix_curr, vix_chg, _ = get_stats(df.get("VIX"))
    spy_curr, spy_chg, spy_score = get_stats(df.get("S&P 500"))
    tnx_curr, tnx_chg, _ = get_stats(df.get("US 10Y Yield"))
    sox_curr, sox_chg, _ = get_stats(df.get("SOX (Semi)"))
    
    # --- Logic 1: RISK OFF CHECK (Priority) ---
    if vix_curr > 20 or vix_chg > 5.0 or spy_chg < -1.0:
        reason = []
        if vix_curr > 20: reason.append(f"VIXが高水準 ({vix_curr:.2f})")
        if vix_chg > 5.0: reason.append(f"VIXが急騰 (前日比 {vix_chg:+.2f}%)")
        if spy_chg < -1.0: reason.append(f"株価が急落 (S&P500 {spy_chg:.2f}%)")
        
        reason_str = "、".join(reason)
        return "⚠️ RISK OFF (警戒モード)", "red", f"""
        **市場は現在、強い警戒感を抱いています。**
        主な要因は **{reason_str}** です。
        投資家の心理が悪化しており、キャッシュポジションを高めて守りを固めるべき局面です。
        無理な押し目買いは避け、ボラティリティが落ち着くのを待ちましょう。
        """

    # --- Logic 2: INFLATION / RATES FEAR ---
    if tnx_curr > 4.5 or (tnx_chg > 2.0 and spy_chg < 0):
        return "💸 Yield Spike (金利警戒)", "orange", f"""
        **金利上昇が株式市場の重しになっています。**
        米国10年債利回りが {tnx_curr:.2f}% (前日比 {tnx_chg:+.2f}%) に上昇しました。
        これにより、特にハイテク株などの高PER銘柄でバリュエーション調整（売り）圧力が働いています。
        金利動向が落ち着くまで、上値は重くなるでしょう。
        """
        
    # --- Logic 3: RISK ON (AI / TECH DRIVEN) ---
    if sox_chg > 0.5 and spy_score > 55:
        return "🚀 RISK ON (AI主導)", "green", f"""
        **AI・半導体セクターが市場を牽引しています。**
        SOX指数が堅調 ({sox_chg:+.2f}%) で、S&P500も上昇トレンドを維持しています。
        投資家のリスク許容度は高く、成長株への資金流入が続いています。
        トレンドに乗って利益を伸ばすべき局面ですが、過熱感がないか定期的に確認してください。
        """
        
    # --- Logic 4: NEUTRAL / ROTATION ---
    return "⚖️ NEUTRAL (様子見・循環)", "gray", f"""
    **明確な方向感が欠けており、セクター間での資金循環（ローテーション）が起きています。**
    S&P500は {spy_chg:+.2f}% と小幅な動きに留まっています。
    特定のセクターに資金が集中していないか、あるいは全体的に薄商いなのか見極める必要があります。
    大きなポジションは取らず、次のトレンド発生を待つのが賢明です。
    """

# --- 4. Main App ---

if st.button("📝 レポートを作成する (Generate Report)", type="primary"):
    with st.spinner("Collecting data from 9 sectors..."):
        df = fetch_comprehensive_data()
        
        if df.empty:
            st.error("データの取得に失敗しました。")
        else:
            # --- PART 1: MAIN THEME ---
            title, color, desc = analyze_market_theme(df)
            
            st.markdown(f"## Part 1: Current Market Focus")
            st.markdown(f"### :{color}[{title}]")
            st.info(desc)
            
            st.divider()
            
            # --- PART 2: SECTOR DEEP DIVE ---
            st.markdown(f"## Part 2: Sector Deep Dive (9 Sectors)")
            
            # Helper to display expander content
            def render_sector(label, *tickers):
                # Calculate aggregated stats for the expander header
                main_ticker = tickers[0]
                if main_ticker not in df:
                    return
                
                curr, chg, score = get_stats(df[main_ticker])
                icon, color_name = get_trend_icon(score, chg)
                
                with st.expander(f"{icon} {label} (Main: {chg:+.2f}%)"):
                    cols = st.columns(len(tickers))
                    for i, ticker_name in enumerate(tickers):
                        if ticker_name in df:
                            c_val, c_chg, c_score = get_stats(df[ticker_name])
                            with cols[i]:
                                st.metric(ticker_name, f"{c_val:,.2f}", f"{c_chg:+.2f}%")
                                st.caption(f"Trend Score: {c_score:.0f}")
                                st.line_chart(df[ticker_name].tail(50))
                    
                    # Automated Context Comment
                    if chg < -1.0:
                        st.write(f"📉 **分析**: {main_ticker} が下落しており、このセクターに調整圧力がかかっています。")
                    elif chg > 1.0:
                        st.write(f"📈 **分析**: {main_ticker} が強く、セクター全体に資金が流入しています。")
                    else:
                        st.write(f"➡️ **分析**: {main_ticker} は横ばいです。方向感を探る展開です。")

            render_sector("1. 半導体・AI", "SOX (Semi)", "NVDA (AI)")
            render_sector("2. 海運 (物流)", "BDRY (Shipping)")
            render_sector("3. 為替・金利", "USD/JPY", "US 10Y Yield")
            render_sector("4. 商品・インフレ", "Gold", "Oil")
            render_sector("5. 暗号資産", "Bitcoin", "Ethereum")
            render_sector("6. セクターローテーション", "Tech (XLK)", "Finance (XLF)", "Energy (XLE)")
            render_sector("7. 不動産", "Real Estate (VNQ)")
            render_sector("8. AIバブル指標 (市場全体)", "S&P 500", "Nasdaq 100")
            render_sector("9. オプション・VIX (恐怖指数)", "VIX", "SKEW")

else:
    st.info("上のボタンを押して最新の週間レポートを作成してください。")
