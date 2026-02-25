import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import ssl
import json
import requests
import pandas as pd

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


# --- AI要約機能 ---
def call_bubble_ai(price, psr, rate, bubble_score, e, l, t, r):
    """AIバブル崩壊シナリオをClaude APIで分析"""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    data_text = f"""## AIバブル指標データ

### NVIDIA（AIバブルの主役）
- 株価: ${price:.2f}
- PSR（株価売上高倍率）: {psr:.1f}倍（通常10倍以下が適正、20倍超はバブル）
- 米国10年債利回り: {rate:.2f}%

### バブルスコア計算
- 熱狂度 (E): {e}/10
- レバレッジ (L): {l}/5
- 技術の革新性 (T): {t}/5
- 収益化スピード (R): {r}/2
- バブルスコア B(t) = E×L×T/R = {bubble_score:.1f}
- 判定: {"DANGER（崩壊寸前）" if bubble_score > 300 else "CAUTION（過熱）" if bubble_score > 150 else "SAFE（健全）"}

### 参考: 過去のバブル
- ドットコムバブル(2000): Cisco PSR=30倍 → 崩壊後80%下落
- 仮想通貨バブル(2017): BTC 20倍上昇 → 崩壊後85%下落
- NVIDIA現在: PSR={psr:.1f}倍"""

    system_prompt = """あなたはジョージ・ソロスのクォンタムファンドで15年、その後レイ・ダリオのブリッジウォーターで10年の経験を持つバブル分析の世界的権威です。
ソロスの再帰性理論とダリオのデットサイクル理論を組み合わせてAIバブルを分析します。

【重要】現在の日付は2026年2月です。全ての予測・見通しは2026年2月時点からの未来について述べてください。

提供されたデータを分析し、以下のJSON形式で回答してください。
ファンドのリスク委員会に提出する警告レポートのように、具体的な数値と歴史的比較を明確にしてください。

【分析ルール】
1. 必ず具体的な数値を引用（NVIDIA株価、PSR、金利、バブルスコア）
2. 過去のバブル（ドットコム、仮想通貨、日本バブル等）との定量的比較
3. ソロスの再帰性理論の枠組みで分析（自己強化→転換点→自己崩壊）
4. 感情的にならず、確率論的に冷静に分析
5. データにない事実を捏造しない

{
    "cycle_position": {
        "total_stages": 6,
        "current_stage": 3,
        "stage_name": "現在のステージ名",
        "stages_map": [
            {"stage": 1, "name": "イノベーション誕生", "description": "新技術登場、一部の先見者が投資"},
            {"stage": 2, "name": "認知拡大・初期上昇", "description": "メディア注目、機関投資家参入開始"},
            {"stage": 3, "name": "自己強化フェーズ", "description": "株価上昇→業績改善→さらに上昇の好循環"},
            {"stage": 4, "name": "ユーフォリア（熱狂）", "description": "一般投資家殺到、バリュエーション無視"},
            {"stage": 5, "name": "転換テスト", "description": "最初の亀裂、否定→回復→再度下落"},
            {"stage": 6, "name": "自己崩壊・暴落", "description": "パニック売り、レバレッジ崩壊、長期低迷"}
        ],
        "evidence": "現在のステージだと判断した根拠を2-3文で。NVIDIAのPSR等具体数値必須"
    },
    "current_diagnosis": {
        "headline": "1行の見出し（例: 自己強化フェーズ後期、転換テストに接近中）",
        "summary": "現在のAIバブルの状態を4-5文で詳細に説明。具体数値を引用",
        "reflexivity_status": "ソロスの再帰性理論で見た現在の状態。自己強化/均衡/自己崩壊のどの段階か。2文で",
        "historical_comparison": "過去のバブルとの比較。ドットコムバブルの同時期と比べてどうか。2文で"
    },
    "bubble_anatomy": {
        "narrative_strength": "現在のAIナラティブ（物語）の強さと脆弱性を2文で",
        "earnings_reality": "実際の企業収益はバリュエーションを正当化できるか。2文で",
        "leverage_risk": "市場のレバレッジ状況とリスク。2文で",
        "catalyst_for_burst": "バブル崩壊のきっかけになりうるもの。2-3個"
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "メインシナリオのタイトル",
            "next_3months": "今後3ヶ月に起きること",
            "next_6months": "3-6ヶ月後に起きること",
            "next_12months": "6-12ヶ月後の状態",
            "nvidia_path": "NVIDIAの予想価格パス",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "soft_landing": {
            "probability": 25,
            "title": "ソフトランディング（バブル回避）シナリオ",
            "narrative": "何が起きて、バブルが回避されるか。3-4文",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "hard_crash": {
            "probability": 25,
            "title": "ハードクラッシュ（暴落）シナリオ",
            "narrative": "何がきっかけで、どう崩壊して、どこまで下がるか。3-4文",
            "triggers": ["実現条件1", "条件2"],
            "downside_target": "暴落時の下値目安",
            "investment_action": "具体的な投資アクション"
        }
    },
    "protection_playbook": {
        "hedging_strategies": ["ヘッジ手段1", "ヘッジ手段2", "ヘッジ手段3"],
        "warning_signals": ["崩壊が近いことを示すシグナル1", "2", "3"],
        "safe_havens": "バブル崩壊時の逃避先"
    },
    "risk_monitor": {
        "watch_items": ["監視すべき指標やイベント1", "2", "3"],
        "next_inflection": "次の転換点はいつ・何がきっかけか"
    }
}"""

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": data_text}]
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=90
        )
        response.raise_for_status()
        result = response.json()
        text = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                text += block["text"]
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
    except Exception as e:
        st.error(f"AI分析エラー: {e}")
        return None


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

# --- AIバブル分析セクション ---
st.markdown("---")
st.subheader("🤖 AIバブル崩壊リスク分析")
st.caption("ソロス×ダリオ流バブル分析の世界的権威による診断")

if st.button("🧠 AIでバブル崩壊リスクを分析", use_container_width=True):
    with st.spinner("🔄 Claude AIがバブルリスクを分析中..."):
        ai_result = call_bubble_ai(price, psr, rate, bubble_score, e, l, t, r)
    
    if ai_result:
        # --- サイクルポジション ---
        cp = ai_result.get("cycle_position", {})
        current = cp.get("current_stage", 1)
        total = cp.get("total_stages", 6)
        stage_name = cp.get("stage_name", "")
        stages = cp.get("stages_map", [])
        
        st.markdown("### 📍 バブルサイクル 現在地")
        
        cols_cycle = st.columns(total)
        for i, stage in enumerate(stages):
            with cols_cycle[i]:
                is_current = (i + 1 == current)
                if is_current:
                    st.markdown(f"""<div style="background: linear-gradient(135deg, #5c0a0a, #8b1a1a); padding: 10px; border-radius: 8px; text-align: center; border: 2px solid #e74c3c;">
                        <div style="font-size: 1.4em; font-weight: bold;">🧠</div>
                        <div style="font-size: 0.75em; font-weight: bold; color: #fff;">Stage {i+1}</div>
                        <div style="font-size: 0.65em; color: #ddd;">{stage.get('name', '')}</div>
                    </div>""", unsafe_allow_html=True)
                else:
                    opacity = "0.4" if abs(i + 1 - current) > 1 else "0.7"
                    st.markdown(f"""<div style="background: #262730; padding: 10px; border-radius: 8px; text-align: center; opacity: {opacity}; border: 1px solid #41444C;">
                        <div style="font-size: 1.2em;">{"✅" if i + 1 < current else "⬜"}</div>
                        <div style="font-size: 0.7em; color: #888;">Stage {i+1}</div>
                        <div style="font-size: 0.6em; color: #888;">{stage.get('name', '')}</div>
                    </div>""", unsafe_allow_html=True)
        
        progress_pct = current / total
        st.progress(progress_pct, text=f"バブル進行度: Stage {current}/{total} - {stage_name}")
        
        evidence = cp.get("evidence", "")
        if evidence:
            st.info(f"📋 **判断根拠:** {evidence}")
        
        st.markdown("---")
        
        # --- 現状診断 ---
        diag = ai_result.get("current_diagnosis", {})
        st.markdown(f"### 🔍 現状診断: {diag.get('headline', '')}")
        st.markdown(diag.get("summary", ""))
        
        col_ref, col_hist = st.columns(2)
        with col_ref:
            st.markdown("**🔄 再帰性理論の現在地:**")
            st.markdown(diag.get("reflexivity_status", ""))
        with col_hist:
            st.markdown("**📜 歴史的比較:**")
            st.markdown(diag.get("historical_comparison", ""))
        
        st.markdown("---")
        
        # --- バブルの解剖 ---
        anatomy = ai_result.get("bubble_anatomy", {})
        if anatomy:
            st.markdown("### 🔬 バブルの解剖")
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #9b59b6; margin-bottom: 10px;">
                    <p style="color: #9b59b6; font-weight: bold; margin: 0 0 5px 0;">📖 ナラティブの強度</p>
                    <p style="color: #ddd; font-size: 0.85em; margin: 0;">{anatomy.get('narrative_strength', '')}</p>
                </div>""", unsafe_allow_html=True)
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #3498db;">
                    <p style="color: #3498db; font-weight: bold; margin: 0 0 5px 0;">💰 収益の現実</p>
                    <p style="color: #ddd; font-size: 0.85em; margin: 0;">{anatomy.get('earnings_reality', '')}</p>
                </div>""", unsafe_allow_html=True)
            with col_a2:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #e74c3c; margin-bottom: 10px;">
                    <p style="color: #e74c3c; font-weight: bold; margin: 0 0 5px 0;">⚡ レバレッジリスク</p>
                    <p style="color: #ddd; font-size: 0.85em; margin: 0;">{anatomy.get('leverage_risk', '')}</p>
                </div>""", unsafe_allow_html=True)
                catalysts = anatomy.get("catalyst_for_burst", [])
                if isinstance(catalysts, list):
                    cat_text = "<br>".join([f"💥 {c}" for c in catalysts])
                else:
                    cat_text = f"💥 {catalysts}"
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #f39c12;">
                    <p style="color: #f39c12; font-weight: bold; margin: 0 0 5px 0;">🔥 崩壊のきっかけ</p>
                    <p style="color: #ddd; font-size: 0.85em; margin: 0;">{cat_text}</p>
                </div>""", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # --- シナリオ分析 ---
        st.markdown("### 🔮 フォワードシナリオ分析")
        
        scenarios = ai_result.get("forward_scenarios", {})
        
        base = scenarios.get("base_case", {})
        st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #9b59b6; margin-bottom: 15px;">
            <h4 style="color: #9b59b6; margin-top: 0;">🧠 メインシナリオ ({base.get('probability', 50)}%): {base.get('title', '')}</h4>
            <p style="color: #F7C948; font-size: 1.1em;">📊 NVIDIA予想パス: <b>{base.get('nvidia_path', '')}</b></p>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; color: #888; width: 120px;">3ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_3months', '')}</td></tr>
                <tr><td style="padding: 8px; color: #888;">6ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_6months', '')}</td></tr>
                <tr><td style="padding: 8px; color: #888;">12ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_12months', '')}</td></tr>
            </table>
            <p style="color: #9b59b6; margin-bottom: 0;">💼 <b>アクション:</b> {base.get('investment_action', '')}</p>
        </div>""", unsafe_allow_html=True)
        
        col_soft, col_hard = st.columns(2)
        
        soft = scenarios.get("soft_landing", {})
        with col_soft:
            st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B; height: 100%;">
                <h4 style="color: #09AB3B; margin-top: 0;">🟢 ソフトランディング ({soft.get('probability', 25)}%): {soft.get('title', '')}</h4>
                <p style="color: #ddd; font-size: 0.9em;">{soft.get('narrative', '')}</p>
                <p style="color: #09AB3B; font-size: 0.85em; margin-bottom: 0;">💼 {soft.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
        
        hard = scenarios.get("hard_crash", {})
        with col_hard:
            st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B; height: 100%;">
                <h4 style="color: #FF4B4B; margin-top: 0;">🔴 ハードクラッシュ ({hard.get('probability', 25)}%): {hard.get('title', '')}</h4>
                <p style="color: #ddd; font-size: 0.9em;">{hard.get('narrative', '')}</p>
                <p style="color: #F7C948; font-size: 0.9em;">📉 下値目安: <b>{hard.get('downside_target', '')}</b></p>
                <p style="color: #FF4B4B; font-size: 0.85em; margin-bottom: 0;">💼 {hard.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # --- プロテクション・プレイブック ---
        playbook = ai_result.get("protection_playbook", {})
        if playbook:
            st.markdown("### 🛡️ プロテクション・プレイブック")
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                hedges = playbook.get("hedging_strategies", [])
                hedge_text = "<br>".join([f"🔒 {h}" for h in hedges])
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #3498db;">
                    <p style="color: #3498db; font-weight: bold; margin: 0 0 5px 0;">ヘッジ手段</p>
                    <p style="color: #ddd; font-size: 0.85em; margin: 0;">{hedge_text}</p>
                </div>""", unsafe_allow_html=True)
            with col_p2:
                warnings = playbook.get("warning_signals", [])
                warn_text = "<br>".join([f"⚡ {w}" for w in warnings])
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #e74c3c;">
                    <p style="color: #e74c3c; font-weight: bold; margin: 0 0 5px 0;">崩壊の前兆シグナル</p>
                    <p style="color: #ddd; font-size: 0.85em; margin: 0;">{warn_text}</p>
                </div>""", unsafe_allow_html=True)
            with col_p3:
                st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #09AB3B;">
                    <p style="color: #09AB3B; font-weight: bold; margin: 0 0 5px 0;">🏕️ 逃避先</p>
                    <p style="color: #ddd; font-size: 0.85em; margin: 0;">{playbook.get('safe_havens', '')}</p>
                </div>""", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # --- リスクモニター ---
        rm = ai_result.get("risk_monitor", {})
        st.markdown("### ⚠️ リスクモニター")
        watch = rm.get("watch_items", [])
        if watch:
            for w in watch:
                st.markdown(f"- 👁️ {w}")
        inflection = rm.get("next_inflection", "")
        if inflection:
            st.error(f"🔄 **次の転換点:** {inflection}")
