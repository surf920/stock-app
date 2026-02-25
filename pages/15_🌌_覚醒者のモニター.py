import streamlit as st
import ephem
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import ssl
import requests
import json

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


# -----------------------------------------------------------------------------
# 4. AI覚醒者分析
# -----------------------------------------------------------------------------
def call_awakener_ai(phase_pct, age, moon_msg, vix_val, vix_change, gold_val, gold_change, gurdjieff_alarm, year_12_ago, year_36_ago, year_60_ago):
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    data_text = f"""## 覚醒者モニター データ

### 月齢
- 月相: {phase_pct:.1f}% (月齢: {age:.1f}日)
- 状態: {moon_msg}

### 恐怖指標
- VIX: {vix_val:.2f} (前日比: {vix_change:+.1f}%)
- グルジェフアラーム: {"発動中（パニック状態）" if gurdjieff_alarm else "通常"}

### 安全資産
- Gold: ${gold_val:.1f} (前日比: {gold_change:+.1f}%)

### フラクタルサイクル
- 12年前 ({year_12_ago}年): 木星サイクル
- 36年前 ({year_36_ago}年): 土星・冥王星サイクル
- 60年前 ({year_60_ago}年): 還暦サイクル"""

    system_prompt = """あなたはジョージ・ソロス、レイ・ダリオ、そしてグルジェフの思想を統合した「覚醒した投資家」です。
市場の機械的反応（パニック・陶酔）を見抜き、「Self-Remembering（自己想起）」の視点から市場を分析します。

【重要】現在の日付は2026年2月です。全ての予測は2026年2月時点からの未来について述べてください。

提供されたデータを分析し、以下のJSON形式で回答してください。

【分析の哲学】
1. 市場参加者の大半は「機械的」に反応している（恐怖で売り、陶酔で買う）
2. 覚醒した投資家は群衆の機械的反応を「観察」し、逆を行く
3. 月齢サイクル、フラクタルサイクルは「集合無意識」のリズムを示す
4. VIXは市場の「機械的恐怖」、Goldは「本質的価値への回帰」を示す
5. 具体的な数値を必ず引用すること

{
    "awakening_status": {
        "consciousness_level": "覚醒/半覚醒/機械的/パニック のいずれか",
        "headline": "市場の意識状態を1行で",
        "crowd_behavior": "群衆が今どんな機械的反応をしているか。2文で",
        "contrarian_insight": "覚醒者が見ている真実。群衆が見逃していること。2文で"
    },
    "moon_analysis": {
        "current_phase_meaning": "現在の月相が市場心理に与える影響。2文で",
        "historical_pattern": "満月/新月付近の市場パターンの傾向。1文で",
        "action_guidance": "月齢に基づく行動指針。1文で"
    },
    "fractal_cycles": {
        "year_12": {
            "theme": "12年前のテーマと現在の類似性。2文で",
            "lesson": "12年前から学ぶべき教訓。1文で"
        },
        "year_36": {
            "theme": "36年前のテーマと現在の類似性。2文で",
            "lesson": "36年前から学ぶべき教訓。1文で"
        },
        "year_60": {
            "theme": "60年前のテーマと現在の類似性。2文で",
            "lesson": "60年前から学ぶべき教訓。1文で"
        },
        "convergence": "3つのサイクルが同時に示唆していること。2-3文で"
    },
    "fear_greed_diagnosis": {
        "vix_reading": "VIXの数値が示す市場の機械的状態。2文で",
        "gold_reading": "Goldの動きが示す本質的な動き。2文で",
        "mechanical_trap": "今、投資家が陥りやすい機械的な罠は何か。2文で"
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "メインシナリオ",
            "narrative": "覚醒者の視点から見た今後3-6ヶ月の展開。3-4文",
            "investment_action": "具体的な投資アクション"
        },
        "awakened_opportunity": {
            "probability": 25,
            "title": "覚醒者だけが見えるチャンス",
            "narrative": "群衆が恐怖/陶酔で見逃しているチャンス。3-4文",
            "investment_action": "具体的アクション"
        },
        "mechanical_danger": {
            "probability": 25,
            "title": "機械的反応が招く危険",
            "narrative": "群衆の機械的行動が引き起こすリスク。3-4文",
            "investment_action": "具体的アクション"
        }
    },
    "self_remembering_practice": {
        "todays_meditation": "今日の市場を前にした瞑想的考察。2-3文。詩的に。",
        "do_not": "今日、機械的にやってはいけないこと",
        "do_instead": "代わりに覚醒者として取るべき行動"
    },
    "risk_monitor": {
        "watch_items": ["監視項目1", "監視項目2", "監視項目3"],
        "next_inflection": "次の転換点の予測"
    }
}"""

    headers = {"x-api-key": api_key, "content-type": "application/json", "anthropic-version": "2023-06-01"}
    payload = {"model": "claude-3-5-sonnet-20241022", "max_tokens": 4096, "system": system_prompt, "messages": [{"role": "user", "content": data_text}]}
    try:
        resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        result = resp.json()
        text = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                text += block["text"]
        text = text.strip()
        if text.startswith("```json"): text = text[7:]
        if text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        return json.loads(text.strip())
    except Exception as e:
        st.error(f"AI分析エラー: {e}")
        return None

st.markdown("---")
st.subheader("🤖 AI覚醒者分析")
st.caption("グルジェフ×ソロス×ダリオ - 覚醒した投資家の視点")

if st.button("🔮 覚醒者の分析を実行", type="primary", use_container_width=True):
    with st.spinner("🧘 覚醒者が市場を観照中..."):
        ai_result = call_awakener_ai(phase_pct, age, moon_msg, vix_val, vix_change, gold_val, gold_change, gurdjieff_alarm, year_12_ago, year_36_ago, year_60_ago)

    if ai_result:
        # 覚醒ステータス
        awaken = ai_result.get("awakening_status", {})
        level = awaken.get("consciousness_level", "")
        level_emoji = {"覚醒": "🟢", "半覚醒": "🟡", "機械的": "🟠", "パニック": "🔴"}.get(level, "⚪")

        st.metric("市場の意識レベル", f"{level_emoji} {level}")
        st.info(f"🌌 **{awaken.get('headline', '')}**")

        col_cr, col_ci = st.columns(2)
        with col_cr:
            st.markdown("**🤖 群衆の機械的反応:**")
            st.markdown(awaken.get("crowd_behavior", ""))
        with col_ci:
            st.markdown("**👁️ 覚醒者の洞察:**")
            st.markdown(awaken.get("contrarian_insight", ""))
        st.markdown("---")

        # 月齢分析
        moon_a = ai_result.get("moon_analysis", {})
        if moon_a:
            st.markdown("### 🌙 月齢サイクル分析")
            st.markdown(moon_a.get("current_phase_meaning", ""))
            st.caption(f"📊 {moon_a.get('historical_pattern', '')}")
            st.success(f"🎯 **行動指針:** {moon_a.get('action_guidance', '')}")
        st.markdown("---")

        # フラクタルサイクル
        fractal = ai_result.get("fractal_cycles", {})
        if fractal:
            st.markdown("### 🕰️ フラクタルサイクル AI分析")
            col_f1, col_f2, col_f3 = st.columns(3)
            y12 = fractal.get("year_12", {})
            with col_f1:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #3498db;">
                    <h4 style="color: #3498db; margin: 0 0 8px 0;">🪐 12年前 ({year_12_ago})</h4>
                    <p style="color: #ddd; font-size: 0.85em;">{y12.get('theme', '')}</p>
                    <p style="color: #3498db; font-size: 0.8em;">💡 {y12.get('lesson', '')}</p>
                </div>""", unsafe_allow_html=True)
            y36 = fractal.get("year_36", {})
            with col_f2:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #f39c12;">
                    <h4 style="color: #f39c12; margin: 0 0 8px 0;">☠️ 36年前 ({year_36_ago})</h4>
                    <p style="color: #ddd; font-size: 0.85em;">{y36.get('theme', '')}</p>
                    <p style="color: #f39c12; font-size: 0.8em;">💡 {y36.get('lesson', '')}</p>
                </div>""", unsafe_allow_html=True)
            y60 = fractal.get("year_60", {})
            with col_f3:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #e74c3c;">
                    <h4 style="color: #e74c3c; margin: 0 0 8px 0;">🔄 60年前 ({year_60_ago})</h4>
                    <p style="color: #ddd; font-size: 0.85em;">{y60.get('theme', '')}</p>
                    <p style="color: #e74c3c; font-size: 0.8em;">💡 {y60.get('lesson', '')}</p>
                </div>""", unsafe_allow_html=True)
            convergence = fractal.get("convergence", "")
            if convergence:
                st.warning(f"🔮 **3サイクルの収束:** {convergence}")
        st.markdown("---")

        # 恐怖・貪欲診断
        fg = ai_result.get("fear_greed_diagnosis", {})
        if fg:
            st.markdown("### 😰 恐怖と貪欲の診断")
            col_fg1, col_fg2 = st.columns(2)
            with col_fg1:
                st.markdown(f"**😰 VIX（機械的恐怖）:** {fg.get('vix_reading', '')}")
            with col_fg2:
                st.markdown(f"**🥇 Gold（本質的価値）:** {fg.get('gold_reading', '')}")
            st.error(f"⚡ **機械的な罠:** {fg.get('mechanical_trap', '')}")
        st.markdown("---")

        # シナリオ分析
        st.markdown("### 🔮 フォワードシナリオ分析")
        scenarios = ai_result.get("forward_scenarios", {})
        base = scenarios.get("base_case", {})
        st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #8e44ad; margin-bottom: 15px;">
            <h4 style="color: #8e44ad; margin-top: 0;">🌌 メイン ({base.get('probability', 50)}%): {base.get('title', '')}</h4>
            <p style="color: #ddd;">{base.get('narrative', '')}</p>
            <p style="color: #8e44ad; margin-bottom: 0;">💼 {base.get('investment_action', '')}</p>
        </div>""", unsafe_allow_html=True)

        col_aw, col_md = st.columns(2)
        awake_opp = scenarios.get("awakened_opportunity", {})
        with col_aw:
            st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B;">
                <h4 style="color: #09AB3B; margin-top: 0;">👁️ 覚醒者のチャンス ({awake_opp.get('probability', 25)}%)</h4>
                <p style="color: #2ecc71; font-weight: bold;">{awake_opp.get('title', '')}</p>
                <p style="color: #ddd; font-size: 0.9em;">{awake_opp.get('narrative', '')}</p>
                <p style="color: #09AB3B; font-size: 0.85em;">💼 {awake_opp.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
        mech_danger = scenarios.get("mechanical_danger", {})
        with col_md:
            st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B;">
                <h4 style="color: #FF4B4B; margin-top: 0;">🤖 機械的な危険 ({mech_danger.get('probability', 25)}%)</h4>
                <p style="color: #e74c3c; font-weight: bold;">{mech_danger.get('title', '')}</p>
                <p style="color: #ddd; font-size: 0.9em;">{mech_danger.get('narrative', '')}</p>
                <p style="color: #FF4B4B; font-size: 0.85em;">💼 {mech_danger.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
        st.markdown("---")

        # Self-Remembering Practice
        practice = ai_result.get("self_remembering_practice", {})
        if practice:
            st.markdown("### 🧘 今日のSelf-Remembering")
            st.markdown(f"""<div style="background: linear-gradient(135deg, #0a0a2e, #1a1a3e); padding: 20px; border-radius: 10px; border: 1px solid #8e44ad;">
                <p style="color: #bb8fce; font-style: italic; font-size: 1.1em;">{practice.get('todays_meditation', '')}</p>
                <p style="color: #e74c3c; margin-top: 10px;">🚫 <b>やってはいけないこと:</b> {practice.get('do_not', '')}</p>
                <p style="color: #2ecc71;">✅ <b>覚醒者として:</b> {practice.get('do_instead', '')}</p>
            </div>""", unsafe_allow_html=True)
        st.markdown("---")

        rm = ai_result.get("risk_monitor", {})
        st.markdown("### ⚠️ リスクモニター")
        watch = rm.get("watch_items", [])
        if watch:
            for w in watch:
                st.markdown(f"- 👁️ {w}")
        inflection = rm.get("next_inflection", "")
        if inflection:
            st.error(f"🔄 **次の転換点:** {inflection}")
# -----------------------------------------------------------------------------
