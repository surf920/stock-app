from core.auth import require_auth
require_auth()

"""
決算ガイダンス分析エンジン v4
PDF自動抽出 + テキストエリア表示修正版
"""

import streamlit as st
from datetime import datetime
from api_helper import call_anthropic_api

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4000
TODAY = datetime.now().strftime("%Y年%m月%d日")

ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
HEADERS = {
    "x-api-key": ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

st.set_page_config(page_title="ガイダンス分析", page_icon="🎙️", layout="wide")
st.title("🎙️ 決算ガイダンス分析エンジン")
st.caption("経営者の言葉を分析する。数字より「何を言ったか」「何を言わなかったか」で差がつく。")

if "guidance_result" not in st.session_state:
    st.session_state.guidance_result = None
if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""
if "extracted_prev_text" not in st.session_state:
    st.session_state.extracted_prev_text = ""
if "last_pdf_name" not in st.session_state:
    st.session_state.last_pdf_name = ""
if "last_prev_pdf_name" not in st.session_state:
    st.session_state.last_prev_pdf_name = ""


def extract_guidance_from_pdf(uploaded_file) -> str:
    """PDFから全テキストを抽出。ガイダンスセクションの特定はClaudeに任せる。"""
    if not PDF_AVAILABLE:
        return ""
    full_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n"
    return full_text.strip()


ANALYSIS_PROMPT = """【今日の日付: {today}】

あなたは、ヘッジファンドのアナリストとして、決算ガイダンスの言語分析を行う専門家です。
数字そのものではなく、経営者の「言葉の選び方」「トーンの変化」「言及したこと/しなかったこと」から、
他の投資家がまだ気づいていないシグナルを抽出してください。

## 分析対象
銘柄: {company}
決算期: {period}

## 決算短信テキスト（全文または抜粋）
以下は決算短信の全文または一部です。この中から「今後の見通し」「業績予想」「経営方針」に関するセクションを特定し、
そのセクションの言語・トーンを分析してください。目次や財務諸表の数字部分は無視してください。

{guidance_text}

{prev_section}

## 分析指示

以下の7つの観点から分析し、必ずJSON形式で返してください（他のテキストは一切含めない）:

{{
  "overall_signal": "BULLISH / BEARISH / NEUTRAL のいずれか",
  "confidence": "HIGH / MEDIUM / LOW（判定の確信度）",
  "signal_summary": "判定の根拠を2-3文で簡潔に。投資判断に直結する核心だけ書く。",

  "tone_analysis": {{
    "aggressive_phrases": ["経営者が使った強気な表現をリストアップ"],
    "defensive_phrases": ["経営者が使った弱気・慎重な表現をリストアップ"],
    "tone_verdict": "全体的なトーンの評価を1文で"
  }},

  "what_they_emphasized": [
    "経営者が意図的に強調していたテーマ・事業・数字を列挙"
  ],

  "what_they_avoided": [
    "経営者が言及を避けた、または軽く流したテーマ・事業・数字を列挙"
  ],

  "guidance_vs_reality": {{
    "conservative_signs": ["ガイダンスが意図的に保守的に見える根拠"],
    "aggressive_signs": ["ガイダンスが楽観的すぎる可能性がある根拠"],
    "verdict": "保守的 / 楽観的 / 妥当 のいずれか、根拠1文添え"
  }},

  "hidden_catalysts": [
    "テキストから読み取れる、まだ市場が織り込んでいない可能性のあるカタリスト"
  ],

  "action_items": [
    "この分析を踏まえて、投資家として次に確認すべきこと3つ"
  ]
}}

【重要な文体ルール】
- 高校生にも理解できる日本語
- 専門用語は括弧で説明
- 率直な口調。ヘッジせず断言する
- ただし確信度が低い場合は confidence を LOW にして理由を書く
"""

COMPARISON_SECTION = """
## 前回のガイダンステキスト（比較用）
{prev_text}

【追加分析指示】
前回と今回のガイダンスを比較し、以下も分析に含めてください:
- トーンの変化（前回より強気/弱気になったか）
- 新しく登場したキーワード
- 消えたキーワード
上記を tone_analysis の中に "tone_change" というキーで追加してください。
"""

# ============================================================
# UI
# ============================================================
st.markdown("### 📝 銘柄情報")

col_info1, col_info2 = st.columns(2)
with col_info1:
    company = st.text_input("銘柄名 / コード", placeholder="例: テラスカイ (3915)")
with col_info2:
    period = st.text_input("決算期", placeholder="例: 2026年2月期 通期")

# TDnet便利リンク
code_only = "".join(c for c in company if c.isdigit())
if code_only and len(code_only) == 4:
    st.markdown(f"📎 [Google で {code_only} の決算短信を検索](https://www.google.com/search?q={code_only}+決算短信)")

st.divider()

# --- データ入力 ---
st.markdown("### 📄 ガイダンスデータの入力")
input_method = st.radio(
    "入力方法を選択",
    ["PDFアップロード（推奨）", "テキスト直接入力"],
    horizontal=True,
)

guidance_text = ""
prev_guidance = ""

if input_method == "PDFアップロード（推奨）":
    if not PDF_AVAILABLE:
        st.error("pdfplumber がインストールされていません。requirements.txt に pdfplumber を追加してください。")
    else:
        uploaded_pdf = st.file_uploader(
            "決算短信PDFをアップロード",
            type=["pdf"],
            help="決算短信PDFをドラッグ&ドロップ。「今後の見通し」セクションを自動で抽出します。",
        )

        if uploaded_pdf is not None:
            if st.session_state.last_pdf_name != uploaded_pdf.name:
                with st.spinner("PDFからテキストを抽出中..."):
                    extracted = extract_guidance_from_pdf(uploaded_pdf)
                    if extracted:
                        st.session_state.extracted_text = extracted
                        st.session_state.last_pdf_name = uploaded_pdf.name
                    else:
                        st.session_state.extracted_text = ""
                        st.warning("テキストを抽出できませんでした。手動入力に切り替えてください。")

        if st.session_state.extracted_text:
            st.success(f"✅ テキスト抽出完了 ({len(st.session_state.extracted_text)}文字)")

        guidance_text = st.text_area(
            "抽出されたガイダンステキスト（編集可能）",
            value=st.session_state.extracted_text,
            height=250,
        )

        with st.expander("📊 前回の決算短信と比較する（任意）"):
            st.caption("前回の決算短信PDFをアップロードすると、トーンの変化を自動検出します")
            prev_pdf = st.file_uploader("前回の決算短信PDF", type=["pdf"])
            if prev_pdf is not None:
                if st.session_state.last_prev_pdf_name != prev_pdf.name:
                    with st.spinner("前回PDFからテキスト抽出中..."):
                        prev_extracted = extract_guidance_from_pdf(prev_pdf)
                        if prev_extracted:
                            st.session_state.extracted_prev_text = prev_extracted
                            st.session_state.last_prev_pdf_name = prev_pdf.name
            prev_guidance = st.text_area(
                "前回のガイダンステキスト（編集可能）",
                value=st.session_state.extracted_prev_text,
                height=150,
            )

else:
    guidance_text = st.text_area(
        "ガイダンス本文",
        placeholder="決算説明資料のガイダンス部分、決算短信の「今後の見通し」セクションを貼り付け",
        height=250,
    )
    with st.expander("📊 前回のガイダンスと比較する（任意）"):
        prev_guidance = st.text_area(
            "前回のガイダンス本文",
            placeholder="前四半期のガイダンステキストを貼り付け",
            height=150,
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

    signal = g.get("overall_signal", "NEUTRAL")
    confidence = g.get("confidence", "MEDIUM")
    summary = g.get("signal_summary", "")

    signal_color = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(signal, "⚪")
    conf_label = {"HIGH": "高確信", "MEDIUM": "中確信", "LOW": "低確信"}.get(confidence, "")

    st.markdown(f"## {signal_color} {signal}  （{conf_label}）")
    st.markdown(f"*{summary}*")

    st.divider()

    tone = g.get("tone_analysis", {})
    col_t1, col_t2 = st.columns(2)

    with col_t1:
        st.markdown("### 🟢 強気な表現")
        for phrase in tone.get("aggressive_phrases", []):
            st.markdown(f"- 「{phrase}」")
        if not tone.get("aggressive_phrases"):
            st.caption("検出なし")

    with col_t2:
        st.markdown("### 🔴 弱気・慎重な表現")
        for phrase in tone.get("defensive_phrases", []):
            st.markdown(f"- 「{phrase}」")
        if not tone.get("defensive_phrases"):
            st.caption("検出なし")

    tone_verdict = tone.get("tone_verdict", "")
    if tone_verdict:
        st.info(f"**トーン判定:** {tone_verdict}")

    tone_change = tone.get("tone_change")
    if tone_change:
        st.warning(f"**前回からのトーン変化:** {tone_change}")

    st.divider()

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.markdown("### 🔦 経営者が強調したこと")
        st.caption("「これを見てほしい」という意図")
        for item in g.get("what_they_emphasized", []):
            st.markdown(f"- {item}")

    with col_e2:
        st.markdown("### 🕳️ 経営者が避けたこと")
        st.caption("ここに本当の弱点がある可能性")
        for item in g.get("what_they_avoided", []):
            st.markdown(f"- {item}")

    st.divider()

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

    catalysts = g.get("hidden_catalysts", [])
    if catalysts:
        st.markdown("### 💡 隠れたカタリスト（市場未織り込みの可能性）")
        for cat in catalysts:
            st.markdown(f"- {cat}")
        st.divider()

    actions = g.get("action_items", [])
    if actions:
        st.markdown("### ✅ 次に確認すべきこと")
        for i, action in enumerate(actions, 1):
            st.markdown(f"{i}. {action}")

else:
    if not can_analyze:
        st.info("銘柄名・決算期を入力し、PDFをアップロードまたはテキストを入力してください。")
        st.markdown("### 💡 3ステップで分析")
        st.markdown("""
        1. **銘柄コードと決算期を入力**
        2. **決算短信PDFをアップロード**（「今後の見通し」を自動抽出）
        3. **「ガイダンスを分析する」をクリック**
        """)