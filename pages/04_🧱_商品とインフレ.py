import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
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
st.set_page_config(page_title="商品とインフレ", page_icon="🧱", layout="wide")
st.title("商品(コモディティ) & インフレ観測 🧱")
st.markdown("「ドクター・カッパー（銅）」による景気診断と、インフレの主役「原油・金」の動きを分析します。")

# キャッシュ設定
@st.cache_data(ttl=3600)
def get_commodity_data():
    tickers = {
        "Gold (金)": "GLD",       # 安全資産
        "Copper (銅)": "CPER",    # 実体経済（景気）
        "Oil (原油)": "USO",      # インフレ・エネルギー
        "Silver (銀)": "SLV",     # 工業需要 & 貴金属
        "SP500": "^GSPC"          # 比較用
    }
    
    data_list = []
    hist_data = {}
    
    progress_text = "コモディティデータを取得中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(tickers)

    for name, ticker in tickers.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} のデータを取得中...")
            
            t = yf.Ticker(ticker)
            hist = t.history(period="2y")
            
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                
                # チャート用（正規化なしの実数データも保持）
                hist_data[name] = hist['Close']
                
                data_list.append({
                    "Name": name,
                    "Price": price,
                    "Prev": prev
                })
        except:
            pass
            
    my_bar.empty()
    return pd.DataFrame(data_list), pd.DataFrame(hist_data)

# --- メイン処理 ---
df, df_hist = get_commodity_data()

if df.empty:
    st.error("データ取得失敗")
else:
    # 1. 価格ボード
    st.subheader("📊 現在の価格")
    cols = st.columns(4)
    for i, row in df.iterrows():
        if row["Name"] != "SP500": # SP500はカード表示しない
            with cols[i % 4]:
                diff = row["Price"] - row["Prev"]
                st.metric(row["Name"], f"${row['Price']:.2f}", f"{diff:+.2f}")

    st.markdown("---")

    # 2. 銅金レシオ (Copper/Gold Ratio)
    st.subheader("👨‍⚕️ ドクター・カッパーの景気診断 (銅金レシオ)")
    
    if "Copper (銅)" in df_hist.columns and "Gold (金)" in df_hist.columns:
        # レシオ計算: 銅価格 ÷ 金価格
        # (ETF価格ベースなので絶対値より「トレンド」が重要)
        ratio = df_hist["Copper (銅)"] / df_hist["Gold (金)"]
        
        # SP500との比較のため、正規化
        sp500 = df_hist["SP500"]
        
        fig_ratio = go.Figure()
        
        # 左軸: 銅金レシオ
        fig_ratio.add_trace(go.Scatter(
            x=ratio.index, y=ratio,
            name="銅金レシオ (景気強度)",
            line=dict(color="#FF8C00", width=2),
            fill='tozeroy', # 下を塗りつぶす
            fillcolor='rgba(255, 140, 0, 0.1)'
        ))
        
        # 右軸: S&P500
        fig_ratio.add_trace(go.Scatter(
            x=sp500.index, y=sp500,
            name="S&P500 (株価)",
            line=dict(color="#00CC96", width=2, dash="dot"),
            yaxis="y2"
        ))
        
        fig_ratio.update_layout(
            title="銅金レシオ vs 株価 (連動性チェック)",
            yaxis=dict(title="銅金レシオ (Copper/Gold)"),
            yaxis2=dict(title="S&P500", overlaying="y", side="right", showgrid=False),
            hovermode="x unified",
            legend=dict(orientation="h", y=1.1, x=0)
        )
        
        st.plotly_chart(fig_ratio, use_container_width=True)
        
        # 診断コメント
        current_ratio = ratio.iloc[-1]
        ma50_ratio = ratio.rolling(50).mean().iloc[-1]
        
        c1, c2 = st.columns([2, 1])
        with c1:
            if current_ratio > ma50_ratio:
                st.success("✅ **リスクオン信号**\n\nレシオが上昇中。「不安（金）」より「実需（銅）」が買われています。景気回復への期待が強く、株価にはプラス要因です。")
            else:
                st.warning("⚠️ **リスクオフ信号**\n\nレシオが下落中。「実需（銅）」より「不安（金）」が買われています。景気後退への警戒が必要です。")
        with c2:
            st.info("💡 **銅金レシオとは？**\n\n「銅」は好景気で買われ、「金」は不景気（不安）で買われます。この比率が上がれば景気良し、下がれば景気悪しと判断します。")
            
    else:
        st.warning("銅または金のデータ不足でレシオ計算ができません。")

    st.markdown("---")

    # 3. 原油トレンド
    st.subheader("🛢️ 原油価格 (インフレの源)")
    if "Oil (原油)" in df_hist.columns:
        oil = df_hist["Oil (原油)"]
        ma200 = oil.rolling(200).mean()
        
        fig_oil = go.Figure()
        fig_oil.add_trace(go.Scatter(x=oil.index, y=oil, name="原油価格 (USO)", line=dict(color="#EF553B")))
        fig_oil.add_trace(go.Scatter(x=ma200.index, y=ma200, name="200日平均", line=dict(color="white", dash="dash")))
        
        fig_oil.update_layout(hovermode="x unified", yaxis_title="価格 ($)")
        st.plotly_chart(fig_oil, use_container_width=True)
        
        if oil.iloc[-1] > ma200.iloc[-1]:
            st.error("🔥 **インフレ警戒**：原油が長期トレンド(200日線)を超えています。物価上昇→金利高のリスクあり。")
        else:
            st.success("💧 **インフレ沈静化**：原油は落ち着いています。株価にはプラス材料です。")