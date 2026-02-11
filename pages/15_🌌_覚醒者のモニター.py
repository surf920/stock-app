import streamlit as st
import ephem
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import ssl

# --- 🚨 Avoid SSL Errors ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ----------------------

# -----------------------------------------------------------------------------
# Page Config
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="覚醒者のモニター",
    page_icon="🌌",
    layout="wide"
)

st.title("🌌 覚醒者のモニター (Self-Remembering Dashboard)")

# -----------------------------------------------------------------------------
# 1. Moon Phase (Ephem)
# -----------------------------------------------------------------------------
def get_moon_status():
    """
    Returns (phase_pct, age_days, alert_message, alert_level)
    alert_level: 'normal', 'warning'
    """
    today = datetime.now()
    observer = ephem.Observer()
    observer.date = today
    
    # Calculate Moon
    moon = ephem.Moon(observer)
    phase_pct = moon.phase # 0.0 to 100.0 illuminated
    
    # Calculate Age (days since previous New Moon)
    # previous_new_moon returns an ephem.Date (float)
    prev_new = ephem.previous_new_moon(today)
    # Convert ephem date to datetime for difference calculation
    # Or just use the float difference (1 day = 1.0)
    # ephem dates are floats
    age_days = float(ephem.Date(today)) - float(prev_new)
    
    # Alert Logic
    alert_msg = "通常運転 (Normal)"
    alert_lvl = "normal"
    
    if phase_pct > 90:
        alert_msg = "🌕 満月接近 (Full Moon) - 機械的な高揚に注意"
        alert_lvl = "warning"
    elif phase_pct < 10:
        alert_msg = "🌑 新月接近 (New Moon) - 機械的な悲観に注意"
        alert_lvl = "warning"
        
    return phase_pct, age_days, alert_msg, alert_lvl

try:
    phase_pct, age, moon_msg, moon_lvl = get_moon_status()
    
    # Display Moon Alert
    if moon_lvl == "warning":
        st.error(f"⚠️ **Moon Alert**: {moon_msg}")
    else:
        st.success(f"✅ **Moon Status**: {moon_msg}")
        
except Exception as e:
    st.error(f"Error calculating moon data: {e}")
    phase_pct, age = 0, 0


# -----------------------------------------------------------------------------
# 2. Market Data (VIX, Gold)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=300)
def fetch_market_data():
    tickers = {"VIX": "^VIX", "Gold": "GC=F"}
    data = {}
    
    for key, t in tickers.items():
        # Fetch 5 days history to calculate change safely
        try:
            hist = yf.Ticker(t).history(period="5d")
            if not hist.empty:
                data[key] = hist
        except Exception as e:
            st.warning(f"Failed to fetch {key}: {e}")
            
    return data

market_data = fetch_market_data()

vix_val = 0.0
vix_change = 0.0
gold_val = 0.0
gold_change = 0.0
gurdjieff_alarm = False

# VIX Logic
if "VIX" in market_data:
    vix_df = market_data["VIX"]
    if len(vix_df) >= 2:
        vix_val = vix_df["Close"].iloc[-1]
        vix_prev = vix_df["Close"].iloc[-2]
        vix_change = ((vix_val - vix_prev) / vix_prev) * 100
        
        # Alarm Condition: VIX > 20 OR Change > 5%
        if vix_val > 20 or vix_change > 5:
            gurdjieff_alarm = True

# Gold Logic
if "Gold" in market_data:
    gold_df = market_data["Gold"]
    if len(gold_df) >= 2:
        gold_val = gold_df["Close"].iloc[-1]
        gold_prev = gold_df["Close"].iloc[-2]
        gold_change = ((gold_val - gold_prev) / gold_prev) * 100

# Gurdjieff Alarm UI (Top Priority)
if gurdjieff_alarm:
    st.warning(f"""
    ### 🔔 Self-Remembering Check
    **市場はパニック（機械的な反応）に陥っています。**
    
    *   **VIX**: {vix_val:.2f} (前日比 +{vix_change:.1f}%)
    *   あなたは今、冷静ですか？
    *   呼吸をして、同一化しないように。
    """)

# Metrics Row
col1, col2, col3 = st.columns(3)
col1.metric("🌙 Moon Phase", f"{phase_pct:.1f}%", f"Age: {age:.1f} days")
col2.metric("😰 VIX (Fear)", f"{vix_val:.2f}", f"{vix_change:.2f}%", delta_color="inverse")
col3.metric("🥇 Gold (Truth)", f"{gold_val:.1f}", f"{gold_change:.2f}%")


# -----------------------------------------------------------------------------
# 3. Fractal Cycles (Text)
# -----------------------------------------------------------------------------
now = datetime.now()
year_12_ago = now.year - 12
year_36_ago = now.year - 36
year_60_ago = now.year - 60

st.markdown("---")
st.subheader("🕰️ フラクタル・タイム (Fractal Time)")
st.caption("「歴史は繰り返さないが、韻を踏む」 - 12年/36年/60年サイクルの比較")

# Data Fetching for 12 years ago
@st.cache_data(ttl=86400)
def fetch_past_price(ticker, years_ago):
    try:
        target_date = datetime.now() - timedelta(days=365*years_ago)
        start_date = target_date - timedelta(days=5) # Look back a few days to find trading day
        end_date = target_date + timedelta(days=5)
        
        df = yf.Ticker(ticker).history(start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
        
        if not df.empty:
            # Get the price closest to the target date (which is roughly the middle of the range)
            # Actually, just taking the last available price in that window before "today 12 years ago" is fine.
            # But let's take the row closest to target_date.
            df['diff'] = abs(df.index - target_date.astimezone(df.index.tz))
            closest_row = df.sort_values('diff').iloc[0]
            price = closest_row['Close']
            date = closest_row.name.strftime("%Y-%m-%d")
            return price, date
    except Exception as e:
        return None, None
    return None, None

past_gold, past_gold_date = fetch_past_price("GC=F", 12)
past_sp500, past_sp500_date = fetch_past_price("^GSPC", 12)

# Calculate Multipliers
gold_mult_str = f"x{(gold_val / past_gold):.2f}" if (past_gold and gold_val) else "-"
sp500_val = yf.Ticker("^GSPC").history(period="1d")['Close'].iloc[-1] if True else 0 # simple fetch for current S&P
sp500_mult_str = f"x{(sp500_val / past_sp500):.2f}" if (past_sp500 and sp500_val) else "-"

# 3 Columns Layout
c_text0, c_text1, c_text2 = st.columns(3)

# --- 12 Years Ago (Jupiter Cycle) ---
with c_text0:
    st.info(f"### 12年前 ({year_12_ago}年)")
    st.caption("🪐 **木星サイクル (拡大と原点)**")
    
    st.markdown("#### 🌍 当時のテーマ")
    if year_12_ago == 2014:
        st.markdown("""
        *   🏰 **クリミア危機** (地政学リスクの再燃)
        *   🛢️ **原油価格の大暴落** (資源国ショック)
        *   🪙 **マウントゴックス事件** (暗号資産の淘汰)
        """)
        st.markdown("**現在とのリンク:**")
        st.markdown("地政学リスクの再燃と暗号資産の淘汰・再編。")
    else:
        st.markdown("*(木星サイクルの転換点)*")

    if past_gold and past_sp500:
        st.markdown("#### 💰 価格比較 (Then vs Now)")
        st.write(f"**Gold**: ${past_gold:.0f} → **{gold_mult_str}**")
        st.write(f"**S&P500**: ${past_sp500:.0f} → **{sp500_mult_str}**")
        st.caption(f"Ref Date: {past_gold_date}")

# --- 36 Years Ago (Saturn/Pluto) ---
with c_text1:
    st.warning(f"### 36年前 ({year_36_ago}年)")
    st.caption("☠️ **土星・冥王星 (バブル崩壊)**")
    
    st.markdown("#### 🌍 当時のテーマ")
    if year_36_ago == 1990:
        st.markdown("""
        *   🇯🇵 **日本のバブル崩壊** (株価暴落の始まり)
        *   🇮🇶 **湾岸危機の勃発** (原油高騰)
        *   💀 **「行き過ぎた熱狂」の強制終了**
        """)
    elif year_36_ago == 1989:
        st.markdown("""
        *   🇯🇵 **日経平均 史上最高値 (38,915円)**
        *   💸 消費税導入 (3%)
        *   「ジャパン・ア・ズ・ナンバーワン」の絶頂期。
        """)
    elif year_36_ago == 1991:
        st.markdown("""
        *   🌏 ソビエト連邦崩壊
        *   📉 日本の地価下落が本格化
        """)
    else:
        st.markdown("*(特記すべきバブル/崩壊の転換点を確認してください)*")

# --- 60 Years Ago (Sexagenary Cycle) ---
with c_text2:
    st.error(f"### 60年前 ({year_60_ago}年)")
    st.caption("🔄 **還暦 (構造転換)**")
    
    st.markdown("#### 🌍 当時のテーマ")
    if year_60_ago == 1966:
        st.markdown("""
        *   🇺🇸 **信用収縮 (Credit Crunch)**
        *   🧨 ベトナム戦争の泥沼化
        *   🇨🇳 文化大革命の開始
        *   💀 **「インフレと社会不安」の同時進行**
        """)
    elif year_60_ago == 1965:
        st.markdown("""
        *   🇯🇵 昭和40年不況 (証券恐慌)
        *   🇺🇸 ベトナム戦争への本格介入
        """)
    else:
        st.markdown("*(特記すべき信用収縮/インフレの転換点を確認してください)*")

# -----------------------------------------------------------------------------
# 4. Optional: Gold Helper Chart
# -----------------------------------------------------------------------------
if "Gold" in market_data:
    st.markdown("### 🥇 Gold Trend (直近1年)")
    try:
        gold_1y = yf.Ticker("GC=F").history(period="1y")
        if not gold_1y.empty:
            st.line_chart(gold_1y["Close"])
    except:
        pass
