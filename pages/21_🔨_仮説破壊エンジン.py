"""
機能1-A: 仮説破壊エンジン
Hiさんが「次は◯◯が来る」と仮説を持ったとき、
AIが最強の反証者として6つの問いで仮説を攻撃する。
Hiさん自身が反論に答えることで、仮説の強度を確認する。
"""

import streamlit as st
import json
from api_helper import call_anthropic_api
from datetime import datetime

# === モデル設定(将来 api_helper.py に集中管理する) ===
MODEL = "claude-opus-4-6"
MAX_TOKENS = 4000
TODAY = datetime.now().strftime("%Y年%m月%d日")

# === Streamlit secrets から API キーを取得 ===
ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
HEADERS = {
    "x-api-key": ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

# === ページ設定 ===
st.set_page_config(page_title="仮説破壊エンジン", page_icon="🔨", layout="wide")
st.title("🔨 仮説破壊エンジン")
st.caption("「次は◯◯が来る」という仮説を、AIが最強の反証者として攻撃します")

# === セッション状態の初期化 ===
if "challenges" not in st.session_state:
    st.session_state.challenges = None
if "user_responses" not in st.session_state:
    st.session_state.user_responses = {}
if "verdict" not in st.session_state:
    st.session_state.verdict = None

# === セクション1: 仮説の入力 ===
st.header("1. 検証したい仮説を入力")
hypothesis = st.text_area(
    "仮説",
    placeholder="例: イラン戦争が今後3ヶ月以内に停戦合意に至る\n例: 量子コンピューティング関連株が今後2年で大きく上昇する",
    height=100,
    key="hypothesis_input"
)

if st.button("🔨 仮説を破壊する", type="primary", disabled=not hypothesis.strip()):
    with st.spinner("Claude Opus が反証を生成中..."):
        prompt = f"""【今日の日付: {TODAY}】

あなたは、優秀な投資家の壁打ち相手として、ユーザーの投資仮説を徹底的に攻撃する役割です。
甘やかさず、最強の反証者として振る舞ってください。
反証を生成する際は、必ず今日の日付を起点にして時系列を考えてください。
ユーザーの仮説:

「{hypothesis}」

以下の6つの観点から、この仮説を攻撃する材料を生成してください。
必ず以下のJSON形式で返してください(他のテキストは一切含めない):

{{
  "logical_counters": "この仮説を論理的に否定する最強の反論3つ。具体的に、データや事実を含めて記述。",
  "historical_failures": "過去に同じ仮説を唱えた著名投資家・アナリストと、その結末。具体的な名前と結果を含める。",
  "opposing_view": "この仮説の反対立場の最強の論者は誰か。その主張の核心は何か。",
  "smart_money_silence": "なぜバフェット級の投資家はこの仮説に基づいて動いていないか。あるいは既に動いているか。",
  "falsification_criteria": "この仮説が外れた場合、何を観測したら『外れた』と判定できるか。具体的な指標、数値、イベント。",
  "emotional_appeal": "ユーザーがこの仮説に惹かれている可能性のある感情的理由。ナラティブの魅力、最近のニュース、希望的観測など。"
}}

各項目は、ユーザーが思考を深めるのに十分な具体性と深さを持たせてください。
"""
        payload = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
        result, error = call_anthropic_api(HEADERS, payload)
        if error:
            st.error(f"エラー: {error}")
        else:
            st.session_state.challenges = result
            st.session_state.user_responses = {}
            st.session_state.verdict = None
            st.rerun()

# === セクション2: 6つの反証質問 ===
if st.session_state.challenges:
    st.header("2. AIからの反証 ― 自分の言葉で答えてください")
    st.warning("⚠️ AIの反証を読むだけでは意味がありません。各項目の下に、自分の言葉で必ず回答してください。")

    sections = [
        ("logical_counters", "🔴 論理的な反論"),
        ("historical_failures", "📜 過去の失敗例"),
        ("opposing_view", "🎯 反対立場の論者"),
        ("smart_money_silence", "🧠 賢明な投資家の沈黙"),
        ("falsification_criteria", "📉 仮説が外れる判定基準"),
        ("emotional_appeal", "❤️ 感情的に惹かれる理由"),
    ]

    for key, title in sections:
        with st.expander(title, expanded=True):
            st.markdown(f"**AIの反証:**")
            st.write(st.session_state.challenges.get(key, "(取得失敗)"))
            st.markdown("---")
            st.markdown("**あなたの回答:**")
            response = st.text_area(
                f"この反証に対する、あなたの答え",
                key=f"response_{key}",
                height=120,
                label_visibility="collapsed",
            )
            st.session_state.user_responses[key] = response

    # === セクション3: 判定 ===
    all_filled = all(
        st.session_state.user_responses.get(key, "").strip()
        for key, _ in sections
    )

    st.header("3. 判定")
    if not all_filled:
        st.info("全ての反証への回答を埋めると、判定ボタンが押せます。")
    else:
        if st.button("⚖️ 仮説の強度を判定する", type="primary"):
            with st.spinner("Claude Opus が判定中..."):
                user_answers_text = "\n\n".join(
                    f"【{title}】\nAIの反証: {st.session_state.challenges.get(key, '')}\nユーザーの回答: {st.session_state.user_responses.get(key, '')}"
                    for key, title in sections
                )
                judge_prompt = f"""【今日の日付: {TODAY}】

あなたは、優秀な投資家の壁打ち相手です。
以下は、ユーザーが立てた投資仮説と、それに対するAIの反証、そしてユーザー自身の回答です。
判定する際は、必ず今日の日付を起点にして時系列を考えてください。

仮説:
「{hypothesis}」

反証とユーザーの回答:
{user_answers_text}

以下の観点で判定してください。必ず以下のJSON形式で返してください(他のテキストは一切含めない):

{{
  "strength_score": 1-10の整数。仮説の強度。10が最高(あらゆる反証に説得力ある回答)。1が最低(回答が空虚、論理破綻)。,
  "strongest_response": "ユーザーの回答の中で最も説得力があった部分とその理由。",
  "weakest_response": "ユーザーの回答の中で最も弱かった部分とその理由。具体的に何が足りないか。",
  "overall_verdict": "総合判定。この仮説は次のフェーズ(具体化・ポジション検討)に進むべきか、保留すべきか、棄却すべきか。理由とともに。",
  "next_action": "ユーザーが次に取るべき具体的なアクション。リサーチすべきこと、待つべき情報、考え直すべき前提など。"
}}
"""
                payload = {
                    "model": MODEL,
                    "max_tokens": MAX_TOKENS,
                    "messages": [{"role": "user", "content": judge_prompt}],
                }
                result, error = call_anthropic_api(HEADERS, payload)
                if error:
                    st.error(f"判定エラー: {error}")
                else:
                    st.session_state.verdict = result
                    st.rerun()

    # === セクション4: 判定結果の表示 ===
    if st.session_state.verdict:
        v = st.session_state.verdict
        st.header("4. 判定結果")

        score = v.get("strength_score", 0)
        if score >= 8:
            st.success(f"**仮説強度: {score}/10** — 強い仮説です")
        elif score >= 5:
            st.warning(f"**仮説強度: {score}/10** — 中程度。再検討の余地あり")
        else:
            st.error(f"**仮説強度: {score}/10** — 弱い仮説。ポジションを取る前に再考を強く推奨")

        st.markdown("### 🌟 最も強かった回答")
        st.write(v.get("strongest_response", ""))

        st.markdown("### 🪨 最も弱かった回答")
        st.write(v.get("weakest_response", ""))

        st.markdown("### ⚖️ 総合判定")
        st.write(v.get("overall_verdict", ""))

        st.markdown("### 🎯 次に取るべきアクション")
        st.write(v.get("next_action", ""))

        st.info("💡 このセッションは保存されません。重要な内容は別途記録してください。次回のアップデートで保存機能を追加予定です。")

# === リセット ===
st.divider()
if st.button("🔄 新しい仮説で最初からやり直す"):
    st.session_state.challenges = None
    st.session_state.user_responses = {}
    st.session_state.verdict = None
    st.rerun()