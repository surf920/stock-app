from core.auth import require_auth
require_auth()

"""
機能: 決算ガイダンス分析エンジン
決算説明資料・決算短信・IRコメントのテキストを入力すると、
AIが経営者の言葉を分析し、ブル/ベア/ニュートラルを判定する。

数字ではなく「何を言っているか」「何を言っていないか」「トーンの変化」に注目。
これは四季報にもBloombergにも存在しない、Hi独自の分析ツール。
"""

import streamlit as st
from datetime import datetime
from api_helper import call_anthropic_api

# === モデル設定 ===
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4000
TODAY = datetime.now().strftime("%Y年%m月%d日")

# === API設定 ===
ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
HEADERS = {
    "x-api-key": ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

# === ページ設定 ===
st.set_page_config(page_title="ガイダンス分析", page_icon="🎙️", layout="wide")
st.title("🎙️ 決算ガイダンス分析エンジン")
st.caption("経営者の言葉を分析する。数字より「何を言ったか」「何を言わなかったか」で差がつく。")

# === セッション状態 ===
if "guidance_result" not in st.session_state:
    st.session_state.guidance_result = None
if "prev_guidance_result" not in st.session_state:
    st.session_state.prev_guidance_result = None

# === 分析プロンプト ===
ANALYSIS_PROMPT = """【今日の日付: {today}】

あなたは、ヘッジファンドのアナリストとして、決算ガイダンスの言語分析を行う専門家です。
数字そのものではなく、経営者の「言葉の選び方」「トーンの変化」「言及したこと/しなかったこと」から、
他の投資家がまだ気づいていないシグナルを抽出してください。

## 分析対象
銘柄: {company}
決算期: {period}

## ガイダンステキスト
{guidance_text}

{prev_section}

## 分析指示

以下の7つの観点から分析し、必ずJSON形式で返してください（他のテキストは一切含めない）:

{{
  "overall_signal": "BULLISH / BEARISH / NEUTRAL のいずれか",
  "confidence": "HIGH / MEDIUM / LOW（判定の確信度）",
  "signal_summary": "判定の根拠を2-3文で簡潔に。投資判断に直結する核心だけ書く。",

  "tone_analysis": {{
    "aggressive_phrases": ["経営者が使った強気な表現をリストアップ（例: '力強い成長', '大幅に上回る', '積極的に投資'）"],
    "defensive_phrases": ["経営者が使った弱気・慎重な表現をリストアップ（例: '不透明', '慎重に見極め', '下振れリスク'）"],
    "tone_verdict": "全体的なトーンの評価を1文で"
  }},

  "what_they_emphasized": [
    "経営者が意図的に強調していたテーマ・事業・数字を列挙。これは『見てほしいもの』"
  ],

  "what_they_avoided": [
    "経営者が言及を避けた、または軽く流したテーマ・事業・数字を列挙。これが本当の弱点の可能性。",
    "例: 特定セグメントの見通しに触れない、前回言及していた施策に触れない、競合について一切触れない"
  ],

  "guidance_vs_reality": {{
    "conservative_signs": ["ガイダンスが意図的に保守的に見える根拠。保守的なら上方修正余地あり"],
    "aggressive_signs": ["ガイダンスが楽観的すぎる可能性がある根拠。楽観的なら下方修正リスク"],
    "verdict": "保守的 / 楽観的 / 妥当 のいずれか、根拠1文添え"
  }},

  "hidden_catalysts": [
    "テキストから読み取れる、まだ市場が織り込んでいない可能性のあるカタリスト（触媒）。",
    "例: 新規事業の進捗を示唆する表現、M&Aを匂わせる表現、規制変更への言及"
  ],

  "action_items": [
    "この分析を踏まえて、投資家として次に確認すべきこと3つ。",
    "例: '次の四半期でセグメントXの利益率が改善しているか確認', '競合Yの決算と比較'"
  ]
}}

【重要な文体ルール】
- 高校生にも理解できる日本語
- 専門用語は括弧で説明
- 率直な口調。ヘッジせず断言する。「〜かもしれません」ではなく「〜です」
- ただし確信度が低い場合は confidence を LOW にして、その理由を signal_summary に書く
"""

COMPARISON_SECTION = """
## 前回のガイダンステキスト（比較用）
{prev_text}

【追加分析指示】
前回と今回のガイダンスを比較し、以下も分析に含めてください:
- トーンの変化（前回より強気/弱気になったか）
- 新しく登場したキーワード（前回にはなかった表現）
- 消えたキーワード（前回はあったが今回なくなった表現）
上記を tone_analysis の中に "tone_change" というキーで追加してください。
"""


def parse_result(text: str) -> dict:
    """Claude の返答からJSONを抽出"""
    import json
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ============================================================
# UI
# ============================================================

# --- 入力セクション ---
st.markdown("### 📝 ガイダンステキストを入力")

col_info1, col_info2 = st.columns(2)
with col_info1:
    company = st.text_input("銘柄名 / コード", placeholder="例: 三菱重工 (7011)")
with col_info2:
    period = st.text_input("決算期", placeholder="例: 2026年3月期 3Q")

guidance_text = st.text_area(
    "ガイダンス本文",
    placeholder="決算説明資料のガイダンス部分、決算短信の定性的情報、"
                "IR説明会のコメント、社長メッセージなどを貼り付けてください。\n\n"
                "TIP: 決算説明資料PDFの「今期見通し」「業績予想」「中期経営計画の進捗」"
                "のセクションが最も有用です。",
    height=250,
    key="guidance_input",
)

# --- 前回ガイダンス（比較用、任意） ---
with st.expander("📊 前回のガイダンスと比較する（任意）"):
    st.caption("前回の決算ガイダンスを貼り付けると、トーンの変化を検出します")
    prev_guidance = st.text_area(
        "前回のガイダンス本文",
        placeholder="前四半期または前年同期のガイダンステキストを貼り付け",
        height=150,
        key="prev_guidance_input",
    )

# --- 分析実行 ---
can_analyze = company.strip() and period.strip() and guidance_text.strip()

if st.button("🎙️ ガイダンスを分析する", type="primary", disabled=not can_analyze):
    with st.spinner("Claude がガイダンスの言葉を読み解いています..."):
        prev_section = ""
        if prev_guidance and prev_guidance.strip():
            prev_section = COMPARISON_SECTION.format(prev_text=prev_guidance.strip())

        prompt = ANALYSIS_PROMPT.format(
            today=TODAY,
            company=company.strip(),
            period=period.strip(),
            guidance_text=guidance_text.strip(),
            prev_section=prev_section,
        )

        payload = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }

       result, error = call_anthropic_api(HEADERS, payload)
        if error:
            st.error(f"エラー: {error}")
        elif result and isinstance(result, dict):
            st.session_state.guidance_result = result
        else:
            st.error("分析結果の解析に失敗しました。もう一度試してください。")

# --- 結果表示 ---
g = st.session_state.guidance_result
if g:
    st.divider()

    # シグナルヘッダー
    signal = g.get("overall_signal", "NEUTRAL")
    confidence = g.get("confidence", "MEDIUM")
    summary = g.get("signal_summary", "")

    signal_color = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(signal, "⚪")
    conf_label = {"HIGH": "高確信", "MEDIUM": "中確信", "LOW": "低確信"}.get(confidence, "")

    st.markdown(f"## {signal_color} {signal} （{conf_label}）")
    st.markdown(f"*{summary}*")

    st.divider()

    # トーン分析
    tone = g.get("tone_analysis", {})
    col_t1, col_t2 = st.columns(2)

    with col_t1:
        st.markdown("### 🟢 強気な表現")
        aggressive = tone.get("aggressive_phrases", [])
        if aggressive:
            for phrase in aggressive:
                st.markdown(f"- 「{phrase}」")
        else:
            st.caption("検出なし")

    with col_t2:
        st.markdown("### 🔴 弱気・慎重な表現")
        defensive = tone.get("defensive_phrases", [])
        if defensive:
            for phrase in defensive:
                st.markdown(f"- 「{phrase}」")
        else:
            st.caption("検出なし")

    tone_verdict = tone.get("tone_verdict", "")
    if tone_verdict:
        st.info(f"**トーン判定:** {tone_verdict}")

    # トーン変化（前回比較がある場合）
    tone_change = tone.get("tone_change")
    if tone_change:
        st.warning(f"**前回からのトーン変化:** {tone_change}")

    st.divider()

    # 強調していたこと vs 避けていたこと
    col_e1, col_e2 = st.columns(2)

    with col_e1:
        st.markdown("### 🔦 経営者が強調したこと")
        st.caption("「これを見てほしい」という意図")
        emphasized = g.get("what_they_emphasized", [])
        for item in emphasized:
            st.markdown(f"- {item}")

    with col_e2:
        st.markdown("### 🕳️ 経営者が避けたこと")
        st.caption("ここに本当の弱点がある可能性")
        avoided = g.get("what_they_avoided", [])
        for item in avoided:
            st.markdown(f"- {item}")

    st.divider()

    # ガイダンスの保守度
    gvr = g.get("guidance_vs_reality", {})
    st.markdown("### 📐 ガイダンスは保守的か？楽観的か？")

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("**保守的サイン（上方修正余地）**")
        for sign in gvr.get("conservative_signs", []):
            st.markdown(f"- {sign}")
    with col_g2:
        st.markdown("**楽観的サイン（下方修正リスク）**")
        for sign in gvr.get("aggressive_signs", []):
            st.markdown(f"- {sign}")

    gvr_verdict = gvr.get("verdict", "")
    if gvr_verdict:
        st.info(f"**判定:** {gvr_verdict}")

    st.divider()

    # 隠れたカタリスト
    catalysts = g.get("hidden_catalysts", [])
    if catalysts:
        st.markdown("### 💡 隠れたカタリスト（市場未織り込みの可能性）")
        for cat in catalysts:
            st.markdown(f"- {cat}")
        st.divider()

    # 次のアクション
    actions = g.get("action_items", [])
    if actions:
        st.markdown("### ✅ 次に確認すべきこと")
        for i, action in enumerate(actions, 1):
            st.markdown(f"{i}. {action}")

    st.divider()

    # 仮説破壊エンジンへの連携
    st.caption("この分析結果をもとに仮説を立て、仮説破壊エンジンで検証するのが最強の使い方です。")

else:
    if not can_analyze:
        st.info("銘柄名、決算期、ガイダンステキストを入力してください。")

        st.markdown("### 💡 使い方のヒント")
        st.markdown("""
        **何を貼り付けるか:**
        - 決算説明資料の「今期見通し」「業績予想の前提」セクション
        - 決算短信の「今後の見通し」セクション
        - IR説明会での社長/CFOのコメント（書き起こしがあれば）
        - 中期経営計画の進捗報告

        **どこで見つけるか:**
        - 各社IRページ（「IR」「投資家情報」で検索）
        - TDnet (https://www.release.tdnet.info/)
        - 決算プロ (https://kessan.labelmake.jp/)
        - ログミーファイナンス（IR説明会の書き起こし）

        **最も効果が高いのは:**
        前回と今回のガイダンスを両方入力して、**トーンの変化**を検出すること。
        数字は同じでも、言葉が変わっていれば、経営者の本音が変わっている証拠。
        """)
