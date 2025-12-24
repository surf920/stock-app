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
st.set_page_config(
    page_title="AI 投資コックピット",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🚀 AI Global Macro Cockpit (司令室)")
st.markdown("全9ページの市場データを統合し、現在の**「勝算」**と各セクターの**「異常」**を一元管理します。")

# キャッシュ設定
@st.cache_data(ttl=600)
def get_global_data():
    tickers = {
        # --- 01. 半導体 & 08. AI ---
        "SOX": "^SOX",       # 半導体指数
        "NVDA": "NVDA",      # AIバブルの主役
        
        # --- 02. 海運 ---
        "BDRY": "BDRY",      # バルチック海運ETF
        
        # --- 03. 為替 & 金利 ---
        "USDJPY": "JPY=X",   # ドル円
        "TNX": "^TNX",       # 米国10年債金利
        
        # --- 04. 商品 (インフレ) ---
        "GLD": "GLD",        # ゴールド (安全資産)
        
        # --- 05. 暗号資産 ---
        "BTC": "BTC-USD",    # ビットコイン
        
        # --- 06. クレジット (銀行不信感) & 07. 不動産 ---
        "IYR": "IYR",        # 米国不動産
        "HYG": "HYG",        # ジャンク債 (不信感用)
        "LQD": "LQD",        # 優良社債 (不信感用)
        
        # --- 09. オプション (リスク) ---
        "VIX": "^VIX",       # 恐怖指数
        "SKEW": "^SKEW"      # ブラックスワン指数
    }
    
    data_list = []
    
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="6mo")
            
            if not hist.empty:
                s = hist["Close"]
                s.name = name
                s.index = s.index.tz_localize(None)
                data_list.append(s)
        except:
            pass
            
    if data_list:
        df = pd.concat(data_list, axis=1)
        df = df.ffill().dropna()
        
        # クレジットストレス比率を計算 (LQD/HYG)
        if "LQD" in df.columns and "HYG" in df.columns:
            df["CREDIT"] = df["LQD"] / df["HYG"]
            
        return df
    return pd.DataFrame()

df = get_global_data()

# --- ロジック計算 ---

def calculate_trend_score(series):
    """ トレンド判定 (0-100) """
    if series is None or series.empty: return 50
    current = series.iloc[-1]
    ma50 = series.rolling(window=50).mean().iloc[-1]
    if pd.isna(ma50): return 50
    diff = (current - ma50) / ma50
    score = 50 + (diff * 500) 
    return min(max(score, 0), 100)

if df.empty:
    st.error("⏳ データ取得中... リロードしてください")
else:
    # 1. 攻めのスコア
    s_nvda = calculate_trend_score(df["NVDA"]) if "NVDA" in df.columns else 50
    s_sox = calculate_trend_score(df["SOX"]) if "SOX" in df.columns else 50
    s_btc = calculate_trend_score(df["BTC"]) if "BTC" in df.columns else 50
    growth_score = (s_nvda * 0.4) + (s_sox * 0.3) + (s_btc * 0.3)

    # 2. 守りのスコア
    risk_score = 0
    # VIX
    if "VIX" in df.columns:
        vix = df["VIX"].iloc[-1]
        risk_vix = max(100 - (vix - 12) * 5, 0)
        risk_score += risk_vix * 0.4
    else:
        risk_score += 40

    # Credit (LQD/HYG)
    if "CREDIT" in df.columns:
        ratio = df["CREDIT"]
        ma20 = ratio.rolling(window=20).mean().iloc[-1]
        curr = ratio.iloc[-1]
        # 比率上昇＝不信感＝リスク増
        risk_credit = 20 if curr > ma20 else 80
        risk_score += risk_credit * 0.3
    else:
        risk_score += 24
        
    # 金利
    if "TNX" in df.columns:
        tnx = df["TNX"].iloc[-1]
        risk_rate = max(100 - (tnx * 15), 0) 
        risk_score += risk_rate * 0.3
    else:
        risk_score += 15

    # 3. 総合判定
    final_score = (growth_score * 0.6) + (risk_score * 0.4)
    
    # --- 表示エリア ---

    col_gauge, col_advice = st.columns([1, 2])
    
    with col_gauge:
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = final_score,
            title = {'text': "<b>AI 市場判断スコア</b>", 'font': {'size': 20}}, # タイトルフォント調整
            number = {'font': {'size': 50}}, # 数字フォント調整
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "rgba(0,0,0,0)"},
                'steps': [
                    {'range': [0, 30], 'color': "#EF553B"},
                    {'range': [30, 60], 'color': "#FFA15A"},
                    {'range': [60, 100], 'color': "#00CC96"}
                ],
                'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': final_score}
            }
        ))
        # ⚠️ ここを修正！上下の余白(margin t, b)を広げて重なりを解消
        fig.update_layout(height=300, margin=dict(t=80, b=50, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)

    with col_advice:
        st.subheader("👮 AI 投資アドバイザーの助言")
        if final_score >= 70:
            st.info("🚀 **STRONG BUY (強気)**\n\nAI・半導体・仮想通貨が市場を牽引しています。リスク許容度を高め、トレンドに乗る局面です。")
        elif final_score >= 40:
            st.warning("⚖️ **NEUTRAL (様子見)**\n\n強弱材料が入り混じっています。金利や不信感(Credit)の動きを注視してください。")
        else:
            st.error("🛡️ **DEFENSE (退避推奨)**\n\nリスク指標が悪化しています。現金比率を最大化し、嵐が過ぎるのを待ちましょう。")

    st.markdown("---")

    # --- 全セクター状況確認パネル ---
    st.subheader("📡 全方位マーケット・モニタリング (9セクター)")
    st.caption("各メニューに対応する主要指標のリアルタイム状況です。")

    def metric_card(label, col_name, suffix="", inverse=False, sub_val=None, sub_label=""):
        if col_name in df.columns:
            val = df[col_name].iloc[-1]
            prev = df[col_name].iloc[-2]
            diff = val - prev
            pct = (diff / prev) * 100
            
            # inverse=Trueなら「下がった方が良い」(例:VIX, 金利, Credit比率)
            is_good = pct > 0 if not inverse else pct < 0
            delta_color = "normal" if not inverse else "inverse"
            
            st.metric(label, f"{val:,.2f}{suffix}", f"{pct:+.2f}%", delta_color=delta_color)
            
            if sub_val is not None:
                st.caption(f"{sub_label}: {sub_val:.2f}")
            elif is_good:
                st.caption("✅ 強気 / 安定")
            else:
                st.caption("⚠️ 弱気 / 警戒")
        else:
            st.metric(label, "N/A", "0.00%")

    # 1段目: 攻めの資産 (Growth)
    st.markdown("##### 🚀 成長テーマ (AI・半導体・仮想通貨)")
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1: metric_card("01. 半導体 (SOX)", "SOX")
    with r1c2: metric_card("08. AI主導株 (NVDA)", "NVDA")
    with r1c3: metric_card("05. ビットコイン (BTC)", "BTC", suffix=" $")

    st.divider()

    # 2段目: 実体経済・サイクル (海運・不動産・★不信感★)
    st.markdown("##### 🌍 実体経済・クレジット (不信感監視)")
    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1: metric_card("02. 海運 (BDRY)", "BDRY")
    with r2c2: metric_card("07. 不動産 (IYR)", "IYR")
    with r2c3: 
        # 上昇すると不信感増大なので inverse=True
        metric_card("06. 銀行不信感 (LQD/HYG)", "CREDIT", inverse=True)

    st.divider()

    # 3段目: リスク管理・ヘッジ (金利・商品・オプション)
    st.markdown("##### 🛡️ リスク管理・ヘッジ (金利・商品・オプション)")
    r3c1, r3c2, r3c3 = st.columns(3)
    with r3c1: metric_card("03. 米国金利 (TNX)", "TNX", suffix="%", inverse=True)
    with r3c2: metric_card("04. 商品/Gold (GLD)", "GLD")
    
    # オプション (VIX + SKEW)
    with r3c3: 
        skew_val = df["SKEW"].iloc[-1] if "SKEW" in df.columns else None
        metric_card("09. オプション市場 (VIX)", "VIX", inverse=True, sub_val=skew_val, sub_label="SKEW")

    st.divider()
    st.caption("💱 参考: ドル円 (USD/JPY)")
    if "USDJPY" in df.columns:
        st.text(f"1 ドル = {df['USDJPY'].iloc[-1]:.2f} 円")