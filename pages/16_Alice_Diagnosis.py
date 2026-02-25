import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import datetime

st.set_page_config(page_title="Alice Diagnosis", page_icon="🐇", layout="wide")

st.title("🐇 Alice Diagnosis: 信用収縮と流動性ドミノ")
st.markdown("市場の表面（株価）ではなく、裏側の「信用」と「流動性」の詰まりを監視するアリス・ロジックに基づく診断パネルです。")

# --- 関数: データ取得と整形 ---
@st.cache_data(ttl=3600)
def get_alice_data():
    # 取得リスト
    tickers = ['BIZD', 'HYG', 'DX-Y.NYB', 'IGV', '^GSPC', 'BTC-USD', 'INTU', 'CRM', 'ADBE']
    
    try:
        data = yf.download(tickers, period="1y", interval="1d")
        
        # yfinanceの仕様変更対応（MultiIndexのカラムをフラットにする）
        if isinstance(data.columns, pd.MultiIndex):
            try:
                data = data['Close'] # Closeのみ取得
            except KeyError:
                # Closeがない場合の保険
                data = data.xs('Close', level=0, axis=1, drop_level=True)
        
        # 欠損値の前方埋め
        data = data.ffill()
        return data
    except Exception as e:
        return pd.DataFrame()

try:
    df = get_alice_data()
    
    # データが空、または必要な列が足りない場合のチェック
    required_cols = ['^GSPC', 'BTC-USD']
    if df.empty or not all(col in df.columns for col in required_cols):
        st.warning("⚠️ 現在、一部のデータが取得できません（API接続エラー）。しばらく待ってからリロードしてください。")
        st.stop() # ここで安全に止める

    latest = df.iloc[-1]
    
    # --- 指標計算 (安全第一) ---
    # 移動平均
    ma_50 = df.rolling(window=50).mean().iloc[-1]
    ma_200 = df.rolling(window=200).mean().iloc[-1]
    
    # DXY (存在確認)
    if 'DX-Y.NYB' in df.columns:
        dxy_val = latest['DX-Y.NYB']
        dxy_mean = df['DX-Y.NYB'].rolling(window=20).mean().iloc[-1]
        dxy_std = df['DX-Y.NYB'].rolling(window=20).std().iloc[-1]
        dxy_spike = dxy_val > (dxy_mean + 2 * dxy_std)
    else:
        dxy_val = 0
        dxy_spike = False

    # SaaS相対強度 (存在確認)
    if 'IGV' in df.columns and '^GSPC' in df.columns:
        df['SaaS_Rel'] = df['IGV'] / df['^GSPC']
        latest_saas_rel = df['SaaS_Rel'].iloc[-1]
    else:
        df['SaaS_Rel'] = 0
        latest_saas_rel = 0

    # --- 機能1: 流動性ドミノ・ゲージ ---
    st.subheader("1. 🌊 流動性ドミノ・ゲージ (Liquidity Domino)")
    col1, col2, col3, col4 = st.columns(4)
    
    # Step 1: DXY Spike
    with col1:
        st.metric("Step 1: DXY Spike", f"{dxy_val:.2f}", delta="Risk On" if not dxy_spike else "ALERT", delta_color="inverse")

    # Step 2: Canary (BTC)
    btc_down = latest['BTC-USD'] < ma_50['BTC-USD']
    with col2:
        st.metric("Step 2: Canary Breath", "BTC Trend", delta="Alive" if not btc_down else "Suffocating", delta_color="inverse")

    # Step 3: Credit Crack (BIZD)
    if 'BIZD' in df.columns:
        bizd_crack = latest['BIZD'] < ma_200['BIZD']
        bizd_val = latest['BIZD']
    else:
        bizd_crack = False
        bizd_val = 0

    with col3:
        st.metric("Step 3: Credit Crack", f"{bizd_val:.2f}", delta="Safe" if not bizd_crack else "CRITICAL", delta_color="inverse")
        if bizd_crack:
            st.error("🔥 信用収縮 (Exit Signal)")

    # Step 4: Meltdown (S&P500)
    sp500_crack = latest['^GSPC'] < ma_200['^GSPC']
    with col4:
        st.metric("Step 4: Meltdown", f"{latest['^GSPC']:.0f}", delta="Bull" if not sp500_crack else "COLLAPSE", delta_color="inverse")

    st.divider()

    # --- 機能2: SaaSモデル崩壊トラッカー ---
    st.subheader("2. 📉 SaaS Erosion Tracker (IGV vs S&P500)")
    if 'SaaS_Rel' in df.columns and not df['SaaS_Rel'].empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df['SaaS_Rel'], mode='lines', name='IGV / SPX Ratio', line=dict(color='cyan')))
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("SaaSデータなし")

except Exception as e:
    st.error(f"⚠️ エラーが発生しました: {e}")
