import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
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
st.set_page_config(page_title="海運サイクル", page_icon="🚢", layout="wide")
st.title("海運サイクル & バルチック指数 🚢")
st.markdown("鉄鉱石や穀物を運ぶ「バラ積み船」の運賃指数（BDI）と、日本の海運株の連動性をチェックします。")

# キャッシュ設定
@st.cache_data(ttl=3600)
def get_shipping_data():
    # BDRY: バルチック指数に連動するETF（指数の代用として優秀）
    tickers = {
        "BDRY (バルチックETF)": "BDRY",
        "日本郵船 (9101)": "9101.T",
        "商船三井 (9104)": "9104.T",
        "川崎汽船 (9107)": "9107.T"
    }
    
    data_list = []
    hist_data = {}
    
    progress_text = "海運データを取得中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(tickers)

    for name, ticker in tickers.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} のデータを取得中...")
            
            t = yf.Ticker(ticker)
            
            # 1年分のデータ取得
            hist = t.history(period="1y")
            
            if not hist.empty:
                # 最新価格
                price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else price
                
                # トレンド判定 (50日移動平均線)
                ma50 = hist['Close'].rolling(window=50).mean().iloc[-1]
                if price > ma50:
                    trend = "上昇 📈"
                    trend_color = "normal" # 緑
                else:
                    trend = "下落 📉"
                    trend_color = "inverse" # 赤
                
                # チャート用データ（正規化：1年前を100とする）
                # 最初の有効な値で正規化する
                first_valid_price = hist['Close'].dropna().iloc[0]
                norm_price = (hist['Close'] / first_valid_price) * 100
                hist_data[name] = norm_price

                data_list.append({
                    "Name": name,
                    "Price": price,
                    "PrevPrice": prev_price,
                    "Trend": trend,
                    "TrendColor": trend_color,
                    "MA50": ma50
                })
        except:
            pass
            
    my_bar.empty()
    
    # チャート用DataFrame作成と整形
    if hist_data:
        df_chart = pd.DataFrame(hist_data)
        # 【重要】データの隙間を埋める（前日データを引き継ぐ）ことで線を繋げる
        df_chart = df_chart.ffill()
        # 全銘柄のデータが揃う最初の時点までカットして、スタートラインを合わせる
        df_chart = df_chart.dropna()
    else:
        df_chart = pd.DataFrame()
        
    return pd.DataFrame(data_list), df_chart

# --- メイン処理 ---
df, df_chart = get_shipping_data()

if df.empty:
    st.error("データの取得に失敗しました。")
else:
    # 1. 重要指標カード (BDRY)
    st.subheader("🌊 バルチック海運指数のトレンド (BDRY ETF)")
    
    # BDRYの行を取得
    try:
        bdry_row = df[df["Name"].str.contains("BDRY")].iloc[0]
        diff = bdry_row["Price"] - bdry_row["PrevPrice"]
        trend_color = bdry_row["TrendColor"]
        trend_text = bdry_row["Trend"]
    except:
        # BDRYが取れなかった場合のダミー
        bdry_row = None
        diff = 0
        trend_color = "off"
        trend_text = "不明"

    col1, col2 = st.columns([1, 3])
    with col1:
        if bdry_row is not None:
            st.metric(
                label="BDRY (バルチック指数連動)",
                value=f"${bdry_row['Price']:.2f}",
                delta=f"{diff:+.2f}",
                delta_color=trend_color
            )
            st.caption(f"トレンド判定: **{trend_text}**")
            
            if trend_color == "normal":
                st.success("✅ 運賃上昇中：海運株に追い風")
            elif trend_color == "inverse":
                st.error("⚠️ 運賃下落中：海運株に逆風")
        else:
             st.warning("BDRYデータの取得に失敗しました")

    with col2:
        st.info("💡 **バルチック指数 (BDI)** とは？\n\n鉄鉱石・石炭・穀物などを運ぶ船の運賃価格。**「世界経済の体温計」** とも呼ばれ、これが上がると世界中の物流が活発（好景気）であることを示します。海運株の利益に直結します。")

    st.markdown("---")

    # 2. 日本の海運株カード
    st.subheader("🇯🇵 日本の大手海運 3社")
    cols = st.columns(3)
    
    # BDRY以外のデータ（日本株）を表示
    jp_stocks = df[~df["Name"].str.contains("BDRY")]
    
    for i, (index, row) in enumerate(jp_stocks.iterrows()):
        with cols[i % 3]:
            diff = row["Price"] - row["PrevPrice"]
            st.metric(
                label=row["Name"],
                value=f"¥{row['Price']:,.0f}",
                delta=f"{diff:+,.0f}",
                delta_color=row["TrendColor"]
            )
            st.caption(f"トレンド: {row['Trend']}")

    # 3. 比較チャート（綺麗バージョン）
    st.subheader("📈 株価連動チャート (過去1年・比較)")
    st.markdown("「バルチック指数（青線）」が上がるとき、日本の海運株も遅れて上がることが多いです。")
    
    if not df_chart.empty:
        # Plotlyで描画 (デザイン調整)
        fig = px.line(
            df_chart, 
            x=df_chart.index, 
            y=df_chart.columns,
            title="相対パフォーマンス比較 (1年前 = 100)"
        )
        # レイアウトをスタイリッシュに
        fig.update_layout(
            hovermode="x unified", 
            yaxis_title="騰落率 (スタート=100)",
            xaxis_title="日付",
            legend_title="銘柄",
            plot_bgcolor="rgba(0,0,0,0)", # 背景透明化
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False), # X軸グリッドなし
            yaxis=dict(showgrid=True, gridcolor="#444") # Y軸グリッド薄く
        )
        # 線を少し太くする
        fig.update_traces(line=dict(width=2))
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("チャート表示用のデータが不足しています。")
    
    # 4. 凡例
    st.markdown("""
    <div style="background-color: #262730; padding: 15px; border-radius: 5px; border: 1px solid #41444C;">
        <b>💡 投資のヒント</b>
        <ul>
            <li><b>BDRY（青）が底打ちして上昇</b> ➡ 海運株の買いシグナル</li>
            <li><b>BDRYが急落</b> ➡ 海運株の売りシグナル（利益確定の目安）</li>
            <li>日本の海運株は配当利回りが高いため、権利落ち日（3月・9月）前後に大きく動くことがあります。</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)