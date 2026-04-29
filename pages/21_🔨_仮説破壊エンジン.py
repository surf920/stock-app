from core.auth import require_auth
require_auth()


import streamlit as st
import json
from datetime import datetime
from api_helper import call_anthropic_api

# === モデル設定(将来 api_helper.py に集中管理する) ===
MODEL = "claude-opus-4-6"
MAX_TOKENS = 4000
WEB_SEARCH_TOOL = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
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
if "action_stages" not in st.session_state:
    st.session_state.action_stages = {}

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
仮説に関連する株価、為替、金利、経済指標などの数値は、必ずウェブ検索で最新のデータを確認してから使ってください。自分の記憶にあるデータは古い可能性があります。検索せずに市場データを断言しないでください。

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

【重要な文体ルール】
- 高校生にも理解できる日本語で書いてください
- 専門用語を使う場合は必ず括弧で簡単な説明を添える(例:「ナラティブバイアス(わかりやすい物語に惹かれる心理)」)
- 一文は長くしすぎない。主語と述語を近づける
- カタカナ語を多用しない。日本語で言い換えられるものは日本語で
- 学術的・論文調の表現を避け、友人に話すような率直な口調にする
- ただし内容の鋭さ・厳しさは一切削らない。優しい口調で厳しいことを言う
"""
        payload = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "tools": WEB_SEARCH_TOOL,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        result, error = call_anthropic_api(HEADERS, payload)
        if error:
            st.error(f"エラー: {error}")
        else:
            st.session_state.challenges = result
            st.session_state.user_responses = {}
            st.session_state.verdict = None
            st.session_state.action_stages = {}
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
  "strength_score": 1-10の整数。仮説の強度。10が最高。1が最低。,
  "strongest_response": "ユーザーの回答の中で最も説得力があった部分とその理由。",
  "weakest_response": "ユーザーの回答の中で最も弱かった部分とその理由。具体的に何が足りないか。",
  "overall_verdict": "総合判定。この仮説は次のフェーズに進むべきか、保留すべきか、棄却すべきか。理由とともに。",
  "next_actions": ["アクション1の具体的な説明", "アクション2の具体的な説明", "アクション3の具体的な説明", "アクション4の具体的な説明", "アクション5の具体的な説明"]
}}

next_actions は必ず配列形式で、5つの独立した具体的なアクションとして返してください。各アクションは1〜3文で、それぞれ独立して取り組めるものにしてください。

【重要な文体ルール】
- 高校生にも理解できる日本語で書いてください
- 専門用語を使う場合は必ず括弧で簡単な説明を添える
- 一文は長くしすぎない
- カタカナ語を多用しない
- 学術的・論文調の表現を避け、率直な口調で
- ただし内容の鋭さ・厳しさは一切削らない
"""
                payload = {
                    "model": MODEL,
                    "max_tokens": MAX_TOKENS,
                    "tools": WEB_SEARCH_TOOL,
                    "messages": [{"role": "user", "content": judge_prompt}],
                }
                result, error = call_anthropic_api(HEADERS, payload)
                if error:
                    st.error(f"判定エラー: {error}")
                else:
                    st.session_state.verdict = result
                    st.session_state.action_stages = {}
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

        # === セクション5: 次のアクション + 壁打ちブロック(機能1-A.5) ===
        st.markdown("### 🎯 次に取るべきアクション")

        next_actions = v.get("next_actions", [])
        if isinstance(next_actions, str):
            # フォールバック: 配列でなく文字列で返ってきた場合
            st.write(next_actions)
        elif isinstance(next_actions, list):
            for i, action in enumerate(next_actions):
                action_key = f"action_{i}"
                with st.container():
                    st.markdown(f"**アクション {i+1}**")
                    st.write(action)

                    # 壁打ちブロック
                    if action_key not in st.session_state.action_stages:
                        st.session_state.action_stages[action_key] = "idle"

                    stage = st.session_state.action_stages[action_key]

                    if stage == "idle":
                        if st.button(f"💭 このアクションを壁打ちする", key=f"btn_consult_{i}"):
                            with st.spinner("方法論を生成中..."):
                                consult_prompt = f"""【今日の日付: {TODAY}】

あなたは、本物のヘッジファンドマネージャーのリサーチチーム(Bridgewater、Soros、Buffett のようなトップファンドのリサーチプロセス)として、ユーザーに方法論を提案します。

ユーザーの投資仮説:
「{hypothesis}」

取り組むアクション:
「{action}」

以下のJSON形式で、このアクションに取り組むための方法論を提案してください(他のテキストは含めない):

{{
  "approach_name": "この方法論の名前(例: 『Bridgewater流のマクロ試算アプローチ』)",
  "data_sources": "参照すべき具体的なデータソース(レポート名、統計、URL等)",
  "framework": "計算式・分析フレームワークの具体的な構造",
  "pitfalls": "このアプローチで注意すべき落とし穴3つ"
}}

【重要な文体ルール】
- 高校生にも理解できる日本語で書いてください
- 専門用語を使う場合は必ず括弧で簡単な説明を添える
- 一文は長くしすぎない
- 率直な口調で、ただし内容の鋭さは削らない
"""
                                payload = {
                                    "model": MODEL,
                                    "max_tokens": MAX_TOKENS,
                                    "tools": WEB_SEARCH_TOOL,
                                    "messages": [{"role": "user", "content": consult_prompt}],
                                }
                                result, error = call_anthropic_api(HEADERS, payload)
                                if error:
                                    st.error(f"エラー: {error}")
                                else:
                                    st.session_state.action_stages[action_key] = "proposed"
                                    st.session_state[f"methodology_{i}"] = result
                                    st.rerun()

                    elif stage == "proposed":
                        methodology = st.session_state.get(f"methodology_{i}", {})
                        st.markdown("#### 📋 提案された方法論")
                        st.markdown(f"**アプローチ名:** {methodology.get('approach_name', '')}")
                        st.markdown(f"**参照すべきデータソース:**")
                        st.write(methodology.get('data_sources', ''))
                        st.markdown(f"**計算式・分析フレームワーク:**")
                        st.write(methodology.get('framework', ''))
                        st.markdown(f"**注意すべき落とし穴:**")
                        st.write(methodology.get('pitfalls', ''))

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ このアプローチで進める", key=f"btn_yes_{i}"):
                                with st.spinner("具体的な調査結果を生成中..."):
                                    execute_prompt = f"""【今日の日付: {TODAY}】

先ほど提案した以下の方法論に基づいて、具体的な調査結果と試算を出してください。

仮説: 「{hypothesis}」
アクション: 「{action}」
方法論: {json.dumps(methodology, ensure_ascii=False)}

以下のJSON形式で返してください(他のテキストは含めない):

{{
  "analysis": "方法論に基づいた具体的な分析結果。必要な数字や試算も含める。",
  "key_numbers": "重要な数字のリスト(具体的な値と、それが何を意味するか)",
  "verification_checklist": "これらの数字・分析を鵜呑みにする前に、必ず確認すべき項目のリスト。5つ以上。各項目は『なぜ確認が必要か』を含める。",
  "limitations": "この分析の限界。AIが知り得ない情報、仮定に依存している部分、信頼性の低い部分を率直に"
}}

【重要】数字は出してよい。ただし:
- 必ず verification_checklist で「鵜呑み禁止、確認すべきポイント」を強制的に併記する
- limitations で自分の限界を率直に認める
- ユーザーが最終判断者であることを前提とする

【文体ルール】
- 高校生にも理解できる日本語
- 専門用語は括弧で説明
- 率直な口調
"""
                                    payload = {
                                        "model": MODEL,
                                        "max_tokens": MAX_TOKENS,
                                        "tools": WEB_SEARCH_TOOL,
                                        "messages": [{"role": "user", "content": execute_prompt}],
                                    }
                                    result, error = call_anthropic_api(HEADERS, payload)
                                    if error:
                                        st.error(f"エラー: {error}")
                                    else:
                                        st.session_state.action_stages[action_key] = "executed"
                                        st.session_state[f"execution_{i}"] = result
                                        st.rerun()
                        with col2:
                            if st.button("✏️ 方法論を修正したい", key=f"btn_modify_{i}"):
                                st.session_state.action_stages[action_key] = "modifying"
                                st.rerun()

                    elif stage == "modifying":
                        methodology = st.session_state.get(f"methodology_{i}", {})
                        st.markdown("#### ✏️ 方法論の修正")
                        st.markdown("現在の方法論:")
                        st.write(methodology.get('approach_name', ''))
                        modification = st.text_area(
                            "どう修正したいか、具体的に記述してください",
                            key=f"mod_input_{i}",
                            height=100,
                        )
                        if st.button("再提案を生成", key=f"btn_regen_{i}", disabled=not modification.strip()):
                            with st.spinner("方法論を再提案中..."):
                                modify_prompt = f"""【今日の日付: {TODAY}】

以下の方法論を、ユーザーの修正要望に沿って再提案してください。

元の方法論: {json.dumps(methodology, ensure_ascii=False)}
ユーザーの修正要望: {modification}
仮説: 「{hypothesis}」
アクション: 「{action}」

以下のJSON形式で再提案してください(他のテキストは含めない):

{{
  "approach_name": "再提案された方法論の名前",
  "data_sources": "参照すべきデータソース",
  "framework": "計算式・分析フレームワーク",
  "pitfalls": "注意すべき落とし穴"
}}

【文体ルール】
- 高校生にも理解できる日本語
- 専門用語は括弧で説明
- 率直な口調
"""
                                payload = {
                                    "model": MODEL,
                                    "max_tokens": MAX_TOKENS,
                                    "tools": WEB_SEARCH_TOOL,
                                    "messages": [{"role": "user", "content": modify_prompt}],
                                }
                                result, error = call_anthropic_api(HEADERS, payload)
                                if error:
                                    st.error(f"エラー: {error}")
                                else:
                                    st.session_state[f"methodology_{i}"] = result
                                    st.session_state.action_stages[action_key] = "proposed"
                                    st.rerun()

                    elif stage == "executed":
                        execution = st.session_state.get(f"execution_{i}", {})
                        st.markdown("#### 📊 具体的な調査結果")
                        st.markdown("**分析:**")
                        st.write(execution.get('analysis', ''))
                        st.markdown("**重要な数字:**")
                        st.write(execution.get('key_numbers', ''))
                        st.error("**⚠️ 鵜呑み禁止。以下を必ず確認してから使ってください:**")
                        st.write(execution.get('verification_checklist', ''))
                        st.markdown("**分析の限界:**")
                        st.write(execution.get('limitations', ''))

                        if st.button("🔄 このアクションをやり直す", key=f"btn_reset_action_{i}"):
                            st.session_state.action_stages[action_key] = "idle"
                            st.rerun()

                    st.divider()

        st.info("💡 このセッションは保存されません。重要な内容は別途記録してください。次回のアップデートで保存機能を追加予定です。")

# === リセット ===
st.divider()
if st.button("🔄 新しい仮説で最初からやり直す"):
    st.session_state.challenges = None
    st.session_state.user_responses = {}
    st.session_state.verdict = None
    st.session_state.action_stages = {}
    st.rerun()