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

# ページ設定
st.set_page_config(page_title="DAI: 市場異常度指数", page_icon="🦁", layout="wide")
st.title("🦁 DAI: Derivative Anomaly Index")
st.markdown("市場の「不信感・金利・恐怖・歪み」を統合監視するプロ仕様ダッシュボード")

# キャッシュ設定
@st.cache_data(ttl=60)
def get_dai_data():
    tickers = {
        "HYG": "HYG", "LQD": "LQD",
        "TNX": "^TNX", "VIX": "^VIX", "SKEW": "^SKEW"
    }
    
    data_list = []
    
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1y")
            
            if not hist.empty:
                s = hist["Close"]
                s.name = name
                # ⚠️重要: タイムゾーンを削除して日付を強制的に合わせる
                s.index = s.index.tz_localize(None)
                data_list.append(s)
        except:
            pass
            
    if data_list:
        # データを結合し、欠損を前日の値で埋める
        df = pd.concat(data_list, axis=1)
        df = df.ffill().dropna()
        return df
    return pd.DataFrame()

df = get_dai_data()

# 安全な計算用関数
def safe_z(series):
    if series is None or len(series) < 5: return 0
    std = series.std()
    if std == 0: return 0
    return (series.iloc[-1] - series.mean()) / std

def safe_val(series):
    return series.iloc[-1] if series is not None and not series.empty else 0

if df.empty:
    st.error("⏳ データ取得中... 少し待ってからリロードしてください")
else:
    # --- 1. Credit Score (不信感) ---
    # 行を短く分割してエラーを防止
    has_lqd = "LQD" in df.columns
    has_hyg = "HYG" in df.columns
    
    if has_lqd and has_hyg:
        credit_ratio = df["LQD"] / df["HYG"]
        score_c = min(max(30 + safe_z(credit_ratio) * 25, 0), 100)
        val_c = safe_val(credit_ratio)
    else:
        credit_ratio = pd.Series(dtype=float)
        score_c, val_c = 0, 0

    # --- 2. Rate Score (金利) ---
    if "TNX" in df.columns:
        score_r = min(max(30 + safe_z(df["TNX"]) * 20, 0), 100)
        val_r = safe_val(df["TNX"])
    else:
        score_r, val_r = 0, 0

    # --- 3. Volatility Score (恐怖) ---
    if "VIX" in df.columns:
        vix = safe_val(df["VIX"])
        score_v = min((vix / 50) * 100, 100)
    else:
        vix, score_v = 0, 0
    
    # --- 4. Skew Score (歪み) ---
    if "SKEW" in df.columns:
        skew = safe_val(df["SKEW"])
        score_s = min(max((skew - 100) * 2, 0), 100)
    else:
        skew, score_s = 0, 0

    # 🏆 DAI 総合指数
    dai = (score_c * 0.3) + (score_r * 0.25) + (score_v * 0.25) + (score_s * 0.2)

    # --- 表示エリア ---
    c_main, c_detail = st.columns([1, 2])
    
    with c_main:
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=dai,
            title={'text': "<b>DAI 総合異常度</b>"},
            gauge={
                'axis': {'range': [None, 100]},
                'steps': [
                    {'range': [0, 40], 'color': "#00CC96"},
                    {'range': [40, 60], 'color': "#FFA15A"},
                    {'range': [60, 80], 'color': "#FF6692"},
                    {'range': [80, 100], 'color': "#EF553B"}
                ],
                'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': dai}
            }
        ))
        fig.update_layout(height=300, margin=dict(l=20,r=20,t=50,b=20))
        st.plotly_chart(fig, use_container_width=True)
        
        if dai < 40: st.success("✅ 市場は正常です")
        elif dai < 60: st.warning("⚠️ 緊張感が出ています")
        else: st.error("🔥 警戒・危険レベルです")

    with c_detail:
        st.subheader("🔍 詳細スコア (0-100)")
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        
        def show_gauge(title, val, raw_text):
            st.markdown(f"**{title}**")
            st.progress(int(min(max(val, 0), 100)) / 100)
            st.caption(f"{raw_text}")

        with c1: show_gauge("🏦 Credit (信用)", score_c, f"LQD/HYG Ratio: {val_c:.2f}")
        with c2: show_gauge("📈 Rate (金利)", score_r, f"US 10Y: {val_r:.2f}%")
        with c3: show_gauge("📉 Volatility (恐怖)", score_v, f"VIX: {vix:.2f}")
        with c4: show_gauge("🦢 Skew (歪み)", score_s, f"SKEW: {skew:.2f}")

    st.markdown("---")
    st.subheader("📊 時系列チャート")
    
    t1, t2 = st.tabs(["信用リスク (LQD/HYG)", "金利 & 恐怖 (TNX/VIX)"])
    with t1:
        if not credit_ratio.empty:
            st.caption("上昇すると「信用リスク（不信感）」が高まっています")
            st.line_chart(credit_ratio)
        else:
            st.info("データ待機中...")
            
    with t2:
        if "TNX" in df.columns and "VIX" in df.columns:
            st.caption("金利(TNX)と恐怖指数(VIX)の推移")
            st.line_chart(pd.DataFrame({"US 10Y": df["TNX"], "VIX/10": df["VIX"]/10}))