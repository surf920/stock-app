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
st.set_page_config(page_title="オプション市場", page_icon="🦁", layout="wide")
st.title("オプション市場 & スマートマネー手口 🦁")
st.markdown("機関投資家の「本音」はオプション市場に現れます。**VIX（恐怖）** と **SKEW（ブラックスワン）** を監視して、暴落の予兆を捉えます。")

# キャッシュ設定
@st.cache_data(ttl=300)
def get_option_data():
    tickers = {
        "VIX": "^VIX",
        "VIX3M": "^VIX3M", 
        "VVIX": "^VVIX",   
        "SKEW": "^SKEW" 
    }
    
    data_list = []
    hist_data = {}
    
    progress_text = "オプションデータを解析中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(tickers)

    for name, ticker in tickers.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} を取得中...")
            
            t = yf.Ticker(ticker)
            hist = t.history(period="1y")
            
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                
                # チャート用に保存
                hist_data[name] = hist['Close']
                
                data_list.append({
                    "Name": name,
                    "Price": price,
                    "Prev": prev
                })
        except:
            pass
            
    my_bar.empty()
    
    # データ結合と整形
    if hist_data:
        df_chart = pd.concat(hist_data.values(), axis=1, keys=hist_data.keys())
        df_chart = df_chart.ffill().dropna()
    else:
        df_chart = pd.DataFrame()
        
    return pd.DataFrame(data_list), df_chart

# --- メイン処理 ---
df, df_chart = get_option_data()

if df.empty:
    st.error("データ取得失敗")
else:
    # データ抽出（安全に）
    def get_val(name):
        row = df[df["Name"] == name]
        return row.iloc[0]["Price"] if not row.empty else 0
    
    def get_prev(name):
        row = df[df["Name"] == name]
        return row.iloc[0]["Prev"] if not row.empty else 0

    vix_val = get_val("VIX")
    vix3m_val = get_val("VIX3M")
    skew_val = get_val("SKEW")
    vvix_val = get_val("VVIX")
    
    vix_diff = vix_val - get_prev("VIX")
    skew_diff = skew_val - get_prev("SKEW")

    # 1. 重要指標ダッシュボード
    st.subheader("📊 Volatility Dashboard")
    
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        # VIX
        color = "inverse" if vix_diff > 0 else "normal"
        st.metric("VIX (恐怖指数)", f"{vix_val:.2f}", f"{vix_diff:+.2f}", delta_color=color)
        
    with c2:
        # Term Structure Spread
        spread = vix3m_val - vix_val
        st.metric("VIX期間構造 (3M - Spot)", f"{spread:.2f}", help="マイナス（逆鞘）になるとパニック状態")
        
    with c3:
        # SKEW
        color_skew = "inverse" if skew_val > 140 else "off"
        st.metric("SKEW (ブラックスワン)", f"{skew_val:.2f}", f"{skew_diff:+.2f}", delta_color=color_skew)
        
    with c4:
        # VVIX
        st.metric("VVIX (VIXの予兆)", f"{vvix_val:.2f}")

    st.markdown("---")

    # 2. 警戒レベル判定
    st.subheader("🦁 機関投資家の警戒レベル判定")
    
    status = ""
    if spread < 0:
        status = "🛑 PANIC (パニック)"
        msg = "現在のVIXが3ヶ月先より高い「逆鞘」状態です。市場はクラッシュを恐れています。"
        bg_color = "#EF553B"
    elif spread < 2.0:
        status = "⚠️ CAUTION (警戒)"
        msg = "VIXスプレッドが縮小しています。警戒感が高まっています。"
        bg_color = "#FFA15A"
    else:
        status = "✅ NORMAL (正常)"
        msg = "期間構造は正常（順鞘）です。今のところ過度なパニックは見られません。"
        bg_color = "#00CC96"

    st.markdown(f"""
    <div style="padding: 15px; border-radius: 5px; background-color: {bg_color}; color: white; margin-bottom: 20px;">
        <h3 style="margin:0;">判定: {status}</h3>
        <p style="margin:0;">{msg}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # --- チャート描画セクション ---
    
    if not df_chart.empty:
        # Chart 1: VIX Term Structure
        st.markdown("### 📉 1. VIX期間構造チャート (恐怖の逆転監視)")
        st.caption("通常は「緑線(3ヶ月後)」が上にあります。**「赤線(今)」が上に来たらパニック**です。")
        
        fig_vix = go.Figure()
        # VIX (Spot) -> Red
        fig_vix.add_trace(go.Scatter(
            x=df_chart.index, y=df_chart["VIX"], 
            name="Spot VIX (現在)", 
            line=dict(color="#EF553B", width=2)
        ))
        # VIX3M -> Green
        fig_vix.add_trace(go.Scatter(
            x=df_chart.index, y=df_chart["VIX3M"], 
            name="VIX 3M (3ヶ月後)", 
            line=dict(color="#00CC96", width=2)
        ))
        
        fig_vix.update_layout(
            height=400,
            hovermode="x unified",
            yaxis_title="VIXポイント",
            legend=dict(orientation="h", y=1.02, x=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#444")
        )
        st.plotly_chart(fig_vix, use_container_width=True)

        # Chart 2: SKEW Index
        st.markdown("### 🦢 2. SKEW指数チャート (ブラックスワン監視)")
        st.caption("暴落への保険料（プットオプション需要）。**140の赤い点線を超えると、暴落警戒警報**です。")
        
        fig_skew = go.Figure()
        
        # SKEW Line
        fig_skew.add_trace(go.Scatter(
            x=df_chart.index, y=df_chart["SKEW"], 
            name="SKEW Index", 
            line=dict(color="#FFA15A", width=1.5),
            fill='tozeroy', # 下を塗りつぶし
            fillcolor='rgba(255, 161, 90, 0.1)'
        ))
        
        # Danger Line (140)
        fig_skew.add_hline(
            y=140, 
            line_dash="dash", 
            line_color="red", 
            annotation_text="⚠️ 警戒ライン (140)", 
            annotation_position="bottom right"
        )
        
        fig_skew.update_layout(
            height=350,
            hovermode="x unified",
            yaxis_title="SKEWポイント",
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#444")
        )
        st.plotly_chart(fig_skew, use_container_width=True)

    else:
        st.warning("チャート用のデータが取得できませんでした。")

    # 4. ヒント
    with st.expander("📚 オプション指標の読み方"):
        st.markdown("""
        * **VIX (Volatility Index):**
            * **< 15:** 楽観（株は上がりやすいが、油断禁物）
            * **20 - 30:** 警戒（相場が荒れている）
            * **> 30:** パニック（セリングクライマックスの可能性、買い場が近い）
        * **SKEW (Skew Index):**
            * 通常は100〜120。
            * **140以上** になると、市場参加者が「まさかの暴落」に備えてヘッジコストを払っている状態。**暴落の先行指標**になりやすい。
        * **VIX期間構造 (Spread):**
            * **VIX3M > VIX (順鞘):** 正常。将来の方が不確実性が高いのは当たり前。
            * **VIX > VIX3M (逆鞘):** 異常事態。今すぐ現金化したいパニック売りが起きている状態。
        """)