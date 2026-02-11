import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import ssl

# --- 🚨 SSL Error Handling ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ----------------------

st.set_page_config(page_title="世界の通貨強弱", page_icon="💴", layout="wide")

st.title("💴 世界の通貨強弱ランキング (対円)")
st.caption("主要通貨が「円」に対して買われているか（強い）、売られているか（弱い）をランキング表示します。")

# --- 1. Data Fetching ---

@st.cache_data(ttl=3600)
def fetch_forex_data():
    """Fetch 8 major currency pairs against JPY."""
    # Yahoo Finance Tickers for JPY pairs
    tickers = {
        "USD (米ドル)": "USDJPY=X",
        "EUR (ユーロ)": "EURJPY=X",
        "GBP (ポンド)": "GBPJPY=X",
        "AUD (豪ドル)": "AUDJPY=X",
        "CAD (カナダドル)": "CADJPY=X",
        "CHF (スイスフラン)": "CHFJPY=X",
        "NZD (NZドル)": "NZDJPY=X",
        "THB (タイバーツ)": "THBJPY=X"
    }
    
    data = []
    
    for label, symbol in tickers.items():
        try:
            t = yf.Ticker(symbol)
            # Fetch 5 days to calculate daily and weekly change roughly
            hist = t.history(period="5d")
            
            if len(hist) >= 2:
                curr = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2]
                
                # Daily Change
                change_pct = (curr - prev) / prev * 100
                
                # Weekly Change (approx, 5 days ago if avail)
                if len(hist) >= 5:
                    week_prev = hist["Close"].iloc[0]
                    week_change_pct = (curr - week_prev) / week_prev * 100
                else:
                    week_change_pct = 0.0
                
                data.append({
                    "Currency": label,
                    "Price": curr,
                    "Daily Change (%)": change_pct,
                    "Weekly Change (%)": week_change_pct
                })
        except Exception as e:
            # Error handling: continue even if one fails
            pass
            
    return pd.DataFrame(data)

# --- 2. Main Logic ---

df = fetch_forex_data()

if df.empty:
    st.error("データ取得に失敗しました。時間をおいて再読み込みしてください。")
else:
    # Sort by Daily Change
    df_sorted = df.sort_values(by="Daily Change (%)", ascending=True) # Ascending for bar chart (bottom to top)
    
    # Identify Strongest/Weakest
    strongest = df_sorted.iloc[-1]
    weakest = df_sorted.iloc[0]
    
    # --- Top Metrics ---
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.metric(
            label="🏆 本日の最強通貨 (vs JPY)",
            value=f"{strongest['Currency']}",
            delta=f"{strongest['Daily Change (%)']:+.2f}%"
        )
    with c2:
        st.metric(
            label="📉 本日の最弱通貨 (vs JPY)",
            value=f"{weakest['Currency']}",
            delta=f"{weakest['Daily Change (%)']:+.2f}%",
            delta_color="inverse"
        )
    st.divider()

    # --- Chart Area ---
    st.subheader("📊 通貨騰落率ランキング (前日比)")
    
    # Set colors: Green for positive, Red for negative
    df_sorted["Color"] = df_sorted["Daily Change (%)"].apply(lambda x: "Up" if x >= 0 else "Down")
    
    fig = px.bar(
        df_sorted,
        x="Daily Change (%)",
        y="Currency",
        orientation="h",
        text_auto=".2f",
        color="Daily Change (%)",
        color_continuous_scale=["red", "gray", "green"],
        range_color=[-1.5, 1.5] # Fix range to make colors comparable roughly
    )
    
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    # --- Detailed Table ---
    with st.expander("📋 詳細データ一覧を見る", expanded=False):
        st.dataframe(
            df.sort_values(by="Daily Change (%)", ascending=False).set_index("Currency").style.format({
                "Price": "{:.2f}",
                "Daily Change (%)": "{:+.2f}%",
                "Weekly Change (%)": "{:+.2f}%"
            })
        )

    # --- AI Analysis Comment ---
    st.subheader("🦁 市場環境分析")
    
    strong_currency = strongest['Currency']
    
    comment = ""
    
    # Logic based analysis
    if "USD" in strong_currency:
        comment = """
        **【ドル高・円安トレンド】**
        米ドルが最も強く推移しています。米国の金利先高観や、根強いインフレ懸念が背景にある可能性があります。
        市場全体として「ドル1強」になりやすい地合いです。
        """
    elif "AUD" in strong_currency or "NZD" in strong_currency or "CAD" in strong_currency:
        comment = """
        **【資源国通貨買い = リスクオン】**
        豪ドルやカナダドルなどの資源国通貨が選好されています。
        原油や金属価格の上昇、あるいは中国経済への期待感が支援材料になっている可能性があります。
        株式市場にとってもポジティブなサイン（リスクオン）と言えます。
        """
    elif "CHF" in strong_currency:
        comment = """
        **【スイスフラン高 = リスク回避】**
        安全資産の代表格であるスイスフランが買われています。
        地政学リスクの高まりや、金融不安など、投資家がリスク回避姿勢（リスクオフ）を強めている可能性があります。
        """
    elif strongest['Daily Change (%)'] < 0:
        comment = """
        **【全面的円高】**
        全ての通貨が前日比でマイナス、つまり「円」が最強の状態です。
        日銀の政策修正観測や、急速な円の買い戻し（巻き戻し）が起きています。
        クロス円のショートポジションがワークしやすい局面です。
        """
    else:
        comment = f"""
        **【選別色の強い展開】**
        本日は {strong_currency} が相対的に強い動きを見せています。
        通貨ごとの個別の材料（経済指標や要人発言）に反応している可能性があります。
        """
        
    st.info(comment)
