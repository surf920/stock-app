import streamlit as st
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
st.set_page_config(page_title="AIバブル崩壊シナリオ", page_icon="🧠", layout="wide")
st.title("🧠 ソロスのAIバブル崩壊モデル (Boom/Bust)")
st.markdown("伝説の投資家ジョージ・ソロスの「再帰性理論」に基づき、**市場の歪み（バブル度）**を計測します。")

# --- データ取得 ---
@st.cache_data(ttl=3600)
def get_bubble_indicators():
    try:
        # NVIDIAのデータ（AIバブルの主役）
        nvda = yf.Ticker("NVDA")
        hist = nvda.history(period="1d")
        price = hist['Close'].iloc[-1]
        
        # PSR (株価売上高倍率) の簡易計算: 時価総額 / 売上
        info = nvda.info
        market_cap = info.get('marketCap', 0)
        revenue = info.get('totalRevenue', 0)
        
        if revenue > 0:
            psr = market_cap / revenue
        else:
            psr = 35.0 # データ取得失敗時の暫定値（高め）

        # 米国10年債利回り（バブルを刺す針）
        tnx = yf.Ticker("^TNX")
        tnx_hist = tnx.history(period="1d")
        rate = tnx_hist['Close'].iloc[-1]
        
        return price, psr, rate
    except:
        return 0, 0, 0

# データ表示
price, psr, rate = get_bubble_indicators()

# --- 1. 現実世界のデータ (Reality) ---
st.subheader("📊 現実のマーケット環境 (Reality)")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("NVIDIA 株価", f"${price:.2f}")
with c2:
    st.metric("NVIDIA PSR (割高感)", f"{psr:.1f}倍", help="通常、10倍を超えると割高、20倍を超えるとバブルと言われます。AIバブル期は30-40倍になることも。")
with c3:
    st.metric("米10年債利回り (重力)", f"{rate:.2f}%", help="金利が上がると、バブル（高PER株）は弾けやすくなります。")

st.markdown("---")

# --- 2. ソロスのパラメーター設定 (Psychology) ---
st.subheader("🎛️ バブル崩壊シミュレーター")
st.caption("市場の「心理状態」をスライダーで入力してください。")

col1, col2 = st.columns([1, 1])

with col1:
    # E(t): 期待の乖離
    e = st.slider(
        "1. 熱狂度 (Expectation Bias)", 
        min_value=1.0, max_value=10.0, value=7.5, step=0.5,
        help="現実よりもどれだけ期待が膨らんでいるか。10は「完全に熱狂状態」。"
    )
    
    # L(t): レバレッジ
    l = st.slider(
        "2. 信用取引・借金 (Leverage)", 
        min_value=1.0, max_value=5.0, value=3.0, step=0.1,
        help="市場参加者がどれだけ借金（信用買い・オプション）をして買っているか。"
    )

with col2:
    # T(t): 技術の未知性
    t = st.slider(
        "3. 技術の革新性 (New Tech Mystery)", 
        min_value=1.0, max_value=5.0, value=4.5, step=0.1,
        help="その技術が「よく分からないけど凄そう」なほどバブルは大きくなります。"
    )
    
    # R(t): 現実の収益化 (分母)
    r = st.slider(
        "4. 収益化のスピード (Revenue Reality)", 
        min_value=0.5, max_value=2.0, value=0.8, step=0.1,
        help="実際に企業が稼ぐスピード。これが遅い（低い）ほど、夢とのギャップでバブルスコアは高くなります。"
    )

# --- 計算ロジック: B(t) = E * L * T / R ---
# ※ これは概念的な数式です
bubble_score = (e * l * t) / r
max_score = 500 # ゲージの最大値

# --- 3. 危険度メーター (Gauge Chart) ---
st.subheader("🚨 バブル崩壊リスクスコア")

fig = go.Figure(go.Indicator(
    mode = "gauge+number+delta",
    value = bubble_score,
    title = {'text': "Bubble Burst Score B(t)"},
    delta = {'reference': 200}, # 基準値
    gauge = {
        'axis': {'range': [None, max_score]},
        'bar': {'color': "black"},
        'steps' : [
            {'range': [0, 150], 'color': "#00CC96"},  # Safe (Green)
            {'range': [150, 300], 'color': "#FFA15A"}, # Warning (Orange)
            {'range': [300, max_score], 'color': "#EF553B"} # Danger (Red)
        ],
        'threshold' : {
            'line': {'color': "red", 'width': 4},
            'thickness': 0.75,
            'value': 350
        }
    }
))

fig.update_layout(height=400)
st.plotly_chart(fig, use_container_width=True)

# --- 4. 診断結果 ---
st.markdown("### 📝 AI診断レポート")

if bubble_score > 300:
    st.error(f"🛑 **DANGER (スコア: {bubble_score:.1f})**\n\n**「崩壊寸前」です。**\n熱狂とレバレッジが限界を超えています。小さなきっかけ（金利上昇や決算ミス）で暴落が始まる可能性があります。キャッシュポジションを高めてください。")
elif bubble_score > 150:
    st.warning(f"⚠️ **CAUTION (スコア: {bubble_score:.1f})**\n\n**「過熱感」があります。**\n株価は上昇していますが、実態（収益）よりも期待が先行しています。急落に備えてストップロス（逆指値）を設定する時期です。")
else:
    st.success(f"✅ **SAFE (スコア: {bubble_score:.1f})**\n\n**「健全な成長」です。**\n期待と実績のバランスが取れています。まだバブルというほどではありません。押し目買いのチャンスかもしれません。")

st.info("""
**💡 ソロスの教え:**
「市場は常に間違っている（バイアスがかかっている）。」
バブルは**「誤った期待」**が**「株価を押し上げ」**、それがさらに**「誤った期待を強化する」**という自己強化プロセス（再帰性）で発生します。
このプロセスが逆回転し始めた時（期待が剥落した時）、暴落は起こります。
""")