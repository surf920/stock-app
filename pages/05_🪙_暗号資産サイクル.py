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
st.set_page_config(page_title="暗号資産サイクル", page_icon="🪙", layout="wide")
st.title("暗号資産(クリプト) & リスクセンチメント 🪙")
st.markdown("「炭鉱のカナリア」であるビットコイン(BTC)の動きから、市場全体のリスク許容度を測ります。")

# キャッシュ設定
@st.cache_data(ttl=300) # クリプトは動きが速いのでキャッシュ短め
def get_crypto_data():
    tickers = {
        "Bitcoin": "BTC-USD",
        "Ethereum": "ETH-USD",
        "Solana": "SOL-USD",
        "Nasdaq100": "QQQ",    # 比較用（ハイテク株）
        "Gold": "GLD"          # 比較用（安全資産）
    }
    
    data_list = []
    hist_data = {} # チャート用データを一時保存
    
    progress_text = "暗号資産データを取得中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(tickers)

    for name, ticker in tickers.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} のデータを取得中...")
            
            t = yf.Ticker(ticker)
            
            # 過去1年分
            hist = t.history(period="1y")
            
            if not hist.empty:
                # 最新価格
                price = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2] if len(hist) > 1 else price
                
                # RSIの計算 (14日)
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                # ゼロ除算対策
                if not rs.empty and rs.iloc[-1] is not None:
                     rsi = 100 - (100 / (1 + rs)).iloc[-1]
                else:
                     rsi = 50 # 計算不能時は中立
                
                # チャート用データ（Seriesとして保存）
                # ここではまだ正規化せず、結合してから処理する
                hist_data[name] = hist['Close']

                data_list.append({
                    "Name": name,
                    "Price": price,
                    "Prev": prev,
                    "RSI": rsi
                })
        except:
            pass
            
    my_bar.empty()
    
    # --- チャートデータの整形処理 (ここを修正) ---
    if hist_data:
        # 1. 全てのSeriesを1つのDataFrameに結合（外部結合で日付を網羅）
        df_merged = pd.concat(hist_data.values(), axis=1, keys=hist_data.keys())
        
        # 2. データの隙間（土日など）を前日の値で埋める
        df_merged = df_merged.ffill()
        
        # 3. 欠損が残っている行（開始時点など）を削除
        df_merged = df_merged.dropna()
        
        # 4. 正規化（スタート地点を100にする）
        # 各列の最初の値で割って100を掛ける
        df_chart = df_merged.apply(lambda x: (x / x.iloc[0]) * 100)
    else:
        df_chart = pd.DataFrame()
        
    return pd.DataFrame(data_list), df_chart

# --- メイン処理 ---
df, df_chart = get_crypto_data()

if df.empty:
    st.error("データ取得失敗")
else:
    # 1. 価格 & RSIボード
    st.subheader("📊 現在の価格と過熱感 (RSI)")
    st.caption("RSIが **70以上** なら「買われすぎ（過熱）」、**30以下** なら「売られすぎ（底値圏）」です。")
    
    cols = st.columns(3)
    # 主要クリプト3種のみ表示
    crypto_list = ["Bitcoin", "Ethereum", "Solana"]
    
    for i, target_name in enumerate(crypto_list):
        # 該当する行を探す
        rows = df[df["Name"] == target_name]
        if not rows.empty:
            row = rows.iloc[0]
            with cols[i]:
                # 価格表示
                diff = row["Price"] - row["Prev"]
                st.metric(
                    label=row["Name"],
                    value=f"${row['Price']:,.2f}",
                    delta=f"{diff:+,.2f}"
                )
                
                # RSIメーター
                rsi_val = row["RSI"]
                rsi_color = "off"
                if rsi_val >= 70: rsi_color = "inverse" # 赤（危険）
                elif rsi_val <= 30: rsi_color = "normal" # 緑（チャンス）
                
                # プログレスバー（範囲外エラー防止）
                bar_val = max(0.0, min(rsi_val / 100, 1.0))
                st.progress(bar_val)
                st.caption(f"RSI: **{rsi_val:.1f}** ({'🔥 過熱' if rsi_val>=70 else ('🥶 底値' if rsi_val<=30 else '中立')})")
                st.markdown("---")

    # 2. 相関チャート (BTC vs Nasdaq vs Gold)
    st.subheader("📈 ビットコインは何と連動しているか？")
    st.markdown("BTC（青）が **Nasdaq（赤）** と一緒に動くなら「リスク資産」、**Gold（黄）** と動くなら「安全資産」としての性質が強まっています。")
    
    if not df_chart.empty:
        # 表示したい列だけを抽出（存在確認してから）
        target_cols = [c for c in ["Bitcoin", "Nasdaq100", "Gold"] if c in df_chart.columns]
        
        if target_cols:
            fig = px.line(
                df_chart, 
                x=df_chart.index, 
                y=target_cols,
                title="相対パフォーマンス比較 (1年前=100)",
                color_discrete_map={
                    "Bitcoin": "#00CC96",  # 青緑
                    "Nasdaq100": "#EF553B", # 赤
                    "Gold": "#FFD700"      # 金色
                }
            )
            # デザイン調整
            fig.update_layout(
                hovermode="x unified", 
                yaxis_title="騰落率 (スタート=100)",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#444")
            )
            # 線を少し太く
            fig.update_traces(line=dict(width=2))
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("比較用のデータ（BTC, Nasdaq, Gold）が揃っていません。")
    else:
        st.warning("チャートデータを作成できませんでした。")

    # 3. 投資判断のヒント
    st.info("""
    **💡 分析のポイント**
    * **BTCとNasdaqの乖離（デカップリング）**: 
        * 株が下がっているのにBTCだけ強い場合 ➡ 資金が「次世代の逃避先」として暗号資産に流れている可能性があります（強い買いシグナル）。
    * **RSIの逆張り**: 
        * 強い上昇トレンドでも、RSIが80を超えたら一旦調整（下落）することが多いです。
    """)