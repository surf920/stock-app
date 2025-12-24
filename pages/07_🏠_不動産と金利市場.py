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
st.set_page_config(page_title="不動産と金利市場", page_icon="🏠", layout="wide")
st.title("不動産市況 & 金利サイクル 🏠")
st.markdown("不動産は「金利」に支配されています。**住宅ローン金利（長期金利）**と**不動産株（REIT・建設）**のシーソー関係を分析します。")

# キャッシュ設定
@st.cache_data(ttl=3600)
def get_real_estate_data():
    tickers = {
        "XLRE (不動産セクター)": "XLRE",     # 大型REIT
        "VNQ (全米不動産ETF)": "VNQ",       # より広い範囲の不動産
        "XHB (住宅建設業者)": "XHB",        # 家を建てる会社（景気に敏感）
        "US 10Y (長期金利)": "^TNX"        # 住宅ローン金利の目安
    }
    
    data_list = []
    hist_data = {}
    
    progress_text = "不動産データを取得中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(tickers)

    for name, ticker in tickers.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} のデータを取得中...")
            
            t = yf.Ticker(ticker)
            hist = t.history(period="1y")
            
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                
                # チャート用データ（金利以外は正規化）
                if "10Y" in name:
                    # 金利はそのままの値を使う（％表示のため）
                    hist_data[name] = hist['Close']
                else:
                    # 株価は1年前を100として正規化
                    start_val = hist['Close'].iloc[0]
                    hist_data[name] = (hist['Close'] / start_val) * 100
                
                data_list.append({
                    "Name": name,
                    "Price": price,
                    "Prev": prev
                })
        except:
            pass
            
    my_bar.empty()
    
    # データ整形（結合と欠損値埋め）
    if hist_data:
        df_chart = pd.concat(hist_data.values(), axis=1, keys=hist_data.keys())
        df_chart = df_chart.ffill().dropna()
    else:
        df_chart = pd.DataFrame()
        
    return pd.DataFrame(data_list), df_chart

# --- メイン処理 ---
df, df_chart = get_real_estate_data()

if df.empty:
    st.error("データ取得失敗")
else:
    # 1. 価格ボード
    st.subheader("📊 現在の不動産価格と金利")
    cols = st.columns(4)
    
    for i, row in df.iterrows():
        with cols[i % 4]:
            diff = row["Price"] - row["Prev"]
            
            # 金利の場合のフォーマット
            if "10Y" in row["Name"]:
                fmt = "{:.2f}%"
                val_str = fmt.format(row["Price"])
                delta_color = "inverse" # 金利上昇は赤（悪い）
            else:
                fmt = "${:.2f}"
                val_str = fmt.format(row["Price"])
                delta_color = "normal" # 株価上昇は緑（良い）
                
            st.metric(
                label=row["Name"],
                value=val_str,
                delta=f"{diff:+.2f}",
                delta_color=delta_color
            )
            
    st.markdown("---")

    # 2. 逆相関チャート
    st.subheader("📉 「金利」vs「不動産」の逆相関チャート")
    st.markdown("赤線（金利）が上がると、緑線（不動産）が下がる傾向にあります。**「赤線が天井を打って下がり始めた時」**が不動産の買い場です。")
    
    if not df_chart.empty:
        fig = go.Figure()
        
        # 左軸: 不動産株 (正規化)
        reit_col = "XLRE (不動産セクター)"
        home_col = "XHB (住宅建設業者)"
        
        if reit_col in df_chart.columns:
            fig.add_trace(go.Scatter(
                x=df_chart.index, y=df_chart[reit_col],
                name="XLRE (REIT)",
                line=dict(color="#00CC96", width=2.5)
            ))
        
        if home_col in df_chart.columns:
            fig.add_trace(go.Scatter(
                x=df_chart.index, y=df_chart[home_col],
                name="XHB (住宅建設)",
                line=dict(color="#FFA15A", width=2)
            ))

        # 右軸: 長期金利
        rate_col = "US 10Y (長期金利)"
        if rate_col in df_chart.columns:
            fig.add_trace(go.Scatter(
                x=df_chart.index, y=df_chart[rate_col],
                name="米国10年債金利 (逆風)",
                line=dict(color="#EF553B", width=2, dash="dot"),
                yaxis="y2"
            ))

        # レイアウト
        fig.update_layout(
            title="不動産株 vs 金利 (過去1年)",
            yaxis=dict(title="株価騰落率 (スタート=100)"),
            yaxis2=dict(
                title="金利 (%)",
                overlaying="y",
                side="right",
                showgrid=False
            ),
            hovermode="x unified",
            legend=dict(orientation="h", y=1.1, x=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False),
            yaxis1=dict(showgrid=True, gridcolor="#444")
        )
        
        st.plotly_chart(fig, use_container_width=True)

    # 3. 診断コメント
    st.subheader("🤖 AI不動産市況診断")
    
    # 最新の金利と不動産トレンド
    latest_rate = df[df["Name"].str.contains("10Y")].iloc[0]["Price"]
    latest_reit_diff = df[df["Name"].str.contains("XLRE")].iloc[0]["Price"] - df[df["Name"].str.contains("XLRE")].iloc[0]["Prev"]
    
    c1, c2 = st.columns([2, 1])
    with c1:
        if latest_rate > 4.5:
            st.error("🥶 **冬の時代 (High Rates)**\n\n金利が4.5%を超えており、不動産には非常に厳しい環境です。住宅ローンが高すぎて家が売れにくい状態です。無理に買わず、金利低下を待つのが賢明です。")
        elif latest_rate < 3.5:
            st.success("🌞 **春の到来 (Low Rates)**\n\n金利が落ち着いています。資金調達コストが安いため、不動産価格は上昇しやすいボーナスタイムです。")
        else:
            st.warning("☁️ **曇り (Neutral)**\n\n金利は歴史的平均レベルです。物件ごとの選別が必要です。")
            
    with c2:
        st.info("""
        **💡 注目ポイント: XHB (建設株)**
        実はREITよりも先に動くのが「住宅建設株(XHB)」です。
        「金利はまだ高いけど、建設株が上がり始めた」場合、市場は**将来の利下げ**を織り込み始めています。
        """)