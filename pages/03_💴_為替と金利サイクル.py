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
st.set_page_config(page_title="為替と金利", page_icon="💴", layout="wide")
st.title("ドル円 & 日米金利差トラッカー 💴")
st.markdown("「お金は金利の高い国に流れる」。日米の**金利差（ギャップ）**とドル円レートの連動性を分析します。")

# サイドバー設定（日本の金利は手動調整も可能に）
with st.sidebar:
    st.header("⚙️ パラメータ設定")
    # 日本の10年債利回りはデータ取得が難しいため、デフォルト値を設定しつつ調整可能にする
    jp_yield = st.slider("🇯🇵 日本国債10年利回り (%)", 0.0, 3.0, 1.05, 0.01, help="日本の長期金利。現状は約1.0%前後で推移しています。")
    st.caption("※ 日本の金利データはリアルタイム取得が難しいため、固定値または手動入力を使用します。")

# キャッシュ設定
@st.cache_data(ttl=3600)
def get_forex_data(jp_yield_val):
    tickers = {
        "USD/JPY": "JPY=X",   # ドル円レート
        "US 10Y": "^TNX"      # 米国10年債利回り
    }
    
    data_frames = []
    
    # データの取得
    try:
        # まとめて取得するとエラーになりやすいので個別に取得
        for name, ticker in tickers.items():
            t = yf.Ticker(ticker)
            hist = t.history(period="2y")
            
            if not hist.empty:
                df = hist[['Close']].rename(columns={'Close': name})
                data_frames.append(df)
        
        if data_frames:
            # データを結合
            df_merged = pd.concat(data_frames, axis=1)
            # 欠損値を埋める（休日のズレなどを補正）
            df_merged = df_merged.ffill().dropna()
            
            # 金利差の計算 (米金利 - 日本金利)
            df_merged["Spread"] = df_merged["US 10Y"] - jp_yield_val
            
            return df_merged
        else:
            return pd.DataFrame()

    except Exception as e:
        return pd.DataFrame()

# --- メイン処理 ---
df = get_forex_data(jp_yield)

if df.empty:
    st.error("データの取得に失敗しました。")
else:
    # 最新データの取得
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. メトリクス表示
    st.subheader("📊 現在のマーケット環境")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        diff = latest["USD/JPY"] - prev["USD/JPY"]
        st.metric("💴 ドル円レート", f"¥{latest['USD/JPY']:.2f}", f"{diff:+.2f}")
    
    with c2:
        diff = latest["US 10Y"] - prev["US 10Y"]
        st.metric("🇺🇸 米国10年債利回り", f"{latest['US 10Y']:.2f}%", f"{diff:+.2f}%")
    
    with c3:
        st.metric("🇯🇵 日本国債10年利回り", f"{jp_yield:.2f}%", "固定 (設定可)", help="サイドバーで変更可能です")
        
    with c4:
        # 金利差
        spread = latest["Spread"]
        prev_spread = prev["Spread"]
        diff = spread - prev_spread
        
        # 金利差が開くとドル高要因
        color = "normal" if diff > 0 else "inverse"
        st.metric("⚖️ 日米金利差", f"{spread:.2f}%", f"{diff:+.2f}%", delta_color=color, help="これが開く（プラス）と円安、縮まる（マイナス）と円高になりやすい")

    st.markdown("---")

    # 2. 2軸チャート
    st.subheader("📈 ドル円 vs 金利差 連動チャート")
    st.markdown("緑の線（ドル円）は、赤の点線（金利差）の後を追いかける傾向があります。")
    
    fig = go.Figure()

    # 左軸: ドル円
    fig.add_trace(go.Scatter(
        x=df.index, y=df["USD/JPY"],
        name="ドル円 (左軸)",
        line=dict(color="#00CC96", width=2.5)
    ))

    # 右軸: 金利差
    fig.add_trace(go.Scatter(
        x=df.index, y=df["Spread"],
        name="日米金利差 (右軸)",
        line=dict(color="#EF553B", width=2, dash="dot"),
        yaxis="y2"
    ))

    # レイアウト
    fig.update_layout(
        title="過去2年間の推移",
        yaxis=dict(title="ドル円 (JPY)", showgrid=False),
        yaxis2=dict(
            title="金利差 (%)",
            overlaying="y",
            side="right",
            showgrid=True,
            gridcolor="#444"
        ),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, use_container_width=True)

    # 3. 相関分析と解説
    st.subheader("🧠 AI分析: 今のレートは適正？")
    
    # 直近3ヶ月の相関係数を計算
    recent_df = df.tail(60) # 約3ヶ月
    correlation = recent_df["USD/JPY"].corr(recent_df["Spread"])
    
    c_col1, c_col2 = st.columns([1, 2])
    
    with c_col1:
        st.metric("直近3ヶ月の相関係数", f"{correlation:.2f}")
        if correlation > 0.7:
            st.success("✅ **非常に強い連動**\n\n現在は「金利差」に素直に反応しています。米金利が上がれば円安になります。")
        elif correlation > 0.3:
            st.info("ℹ️ **緩やかな連動**\n\n金利以外の要因（株価や地政学リスク）も影響しています。")
        else:
            st.warning("⚠️ **連動崩れ (乖離)**\n\n金利差とは無関係に動いています。投機的な動きや介入警戒の可能性があります。")

    with c_col2:
        st.info("""
        **💡 見方のポイント**
        * **赤の点線（金利差）が下がっているのに、緑（ドル円）が高いまま**
            * ➡ 「円安行き過ぎ」のサイン。いずれ修正（円高）が入る可能性が高いです。
        * **赤の点線が上がっているのに、緑がついてこない**
            * ➡ 「円安余地あり」。まだドル高になるエネルギーが残っています。
        """)