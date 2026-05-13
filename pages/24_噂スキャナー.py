from core.auth import require_auth
require_auth()

import streamlit as st
import json
from datetime import datetime
from api_helper import call_anthropic_api

# === Claude API 設定 ===
MODEL = "claude-opus-4-6"
MAX_TOKENS = 8000
TODAY = datetime.now().strftime("%Y年%m月%d日")
ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
HEADERS = {
    "x-api-key": ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}
WEB_SEARCH_TOOL = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}]

# === ページ設定 ===
st.set_page_config(page_title="噂スキャナー", page_icon="📡", layout="wide")
st.title("📡 噂スキャナー")
st.caption("まだ市場が織り込んでいない変化の兆候を、AIがウェブ検索で発見します")

# === セッション状態 ===
if "scan_results" not in st.session_state:
    st.session_state.scan_results = None
if "scan_theme" not in st.session_state:
    st.session_state.scan_theme = None


# ============================================================
# スキャン実行
# ============================================================
def run_scan(theme: str) -> dict:
    prompt = f"""【今日の日付: {TODAY}】

あなたは、まだ市場が織り込んでいない投資機会を探す「噂スキャナー」です。

ユーザーが興味を持っているテーマ:
「{theme}」

以下の手順で、ウェブ検索を徹底的に行ってください:

【検索すべき情報源】
- 最新のニュース記事(過去1〜2週間)
- 特許出願・技術発表
- 政府の審議会・パブリックコメント・政策文書
- 業界団体の発表・レポート
- 企業の決算説明資料・IR資料での経営者発言
- サプライチェーンの変化(部品メーカーの受注動向等)
- 海外の先行事例(米国・欧州・中国で既に起きていること)

【あなたの任務】
このテーマに関連する「まだほとんどの投資家が気づいていない変化の兆候」を見つけてください。
大手メディアで大きく報道されている情報は価値が低い(Rumor Stage 4-5)。
専門メディアや政府文書にしか出ていない情報ほど価値が高い(Rumor Stage 1-2)。

必ず以下のJSON形式で返してください(他のテキストは含めない):

{{
  "theme": "{theme}",
  "scan_date": "{TODAY}",
  "signals": [
    {{
      "title": "シグナルのタイトル(何が変わったか、一言で)",
      "description": "何が起きているかの詳細説明(3〜5文。具体的な数字、日付、情報源を含める)",
      "source_type": "情報源の種類(例: 専門メディア、政府審議会、特許出願、IR資料、海外事例)",
      "beneficiary_companies": "恩恵を受ける可能性のある企業名と証券コード(わかれば)。3社以内",
      "rumor_stage": 1から5の整数,
      "stage_reason": "なぜこのRumor Stageと判定したか(1文で)",
      "puzzle_hint": "二次・三次の推論ヒント。公開情報からどんなパズルが組めるか(例: AがBになると、Cの需要が爆発する → D社が恩恵)",
      "risk": "この噂が外れるリスクシナリオ(1文で)"
    }},
    {{
      "title": "2つ目のシグナル",
      "description": "...",
      "source_type": "...",
      "beneficiary_companies": "...",
      "rumor_stage": 1から5の整数,
      "stage_reason": "...",
      "puzzle_hint": "...",
      "risk": "..."
    }},
    {{
      "title": "3つ目のシグナル",
      "description": "...",
      "source_type": "...",
      "beneficiary_companies": "...",
      "rumor_stage": 1から5の整数,
      "stage_reason": "...",
      "puzzle_hint": "...",
      "risk": "..."
    }}
  ],
  "meta_observation": "このテーマ全体について、今の市場がどう見ているかの俯瞰コメント(2〜3文)"
}}

【重要なルール】
- シグナルは必ず3つ以上5つ以内で返す
- Rumor Stage が低い(1〜2)シグナルを優先的に探す。Stage 4〜5 の「みんな知っている」情報は最小限に
- 各シグナルには必ず具体的な情報源(記事名、日付、発表元)を含める
- puzzle_hint は Hi さん(投資家)が「なるほど、そこからそう繋がるのか」と思えるような二次推論を提供する
- 検索できなかった場合や情報が不足している場合は、正直に「情報が限定的」と書く

【出力フォーマット厳守事項】
- JSON の値の中で、マークダウンの表（| で区切る形式）は絶対に使わないでください
- 改行は \\n で表現し、JSON として正しくパースできる形式を保ってください

【文体ルール】
- 高校生にも理解できる日本語で書いてください
- 専門用語を使う場合は必ず括弧で簡単な説明を添える
- 率直な口調で、ただし内容の鋭さは削らない
"""

    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "tools": WEB_SEARCH_TOOL,
        "system": "あなたはJSON生成マシンです。ウェブ検索を行い、結果を必ずJSON形式のみで返してください。JSON以外のテキスト(説明、前置き、思考過程)は一切出力しないでください。",
            "messages": [{"role": "user", "content": prompt}],
    }

    result, error = call_anthropic_api(HEADERS, payload)
    if error:
        return {"error": error}
    return result


# ============================================================
# UI ヘルパー
# ============================================================
def render_rumor_badge(stage: int):
    stage_config = {
        1: {"color": "#7F77DD", "name": "💤 微かな予兆", "bg": "#7F77DD22"},
        2: {"color": "#1D9E75", "name": "🌱 芽吹き", "bg": "#1D9E7522"},
        3: {"color": "#378ADD", "name": "📢 噂の拡散", "bg": "#378ADD22"},
        4: {"color": "#EF9F27", "name": "📰 コンセンサス形成", "bg": "#EF9F2722"},
        5: {"color": "#E24B4A", "name": "✅ 事実確認", "bg": "#E24B4A22"},
    }
    cfg = stage_config.get(stage, stage_config[3])
    st.markdown(
        f'<div style="display:inline-block;padding:4px 16px;background:{cfg["bg"]};'
        f'border:1px solid {cfg["color"]};border-radius:20px;'
        f'color:{cfg["color"]};font-weight:bold;font-size:14px;">'
        f'Stage {stage} : {cfg["name"]}</div>',
        unsafe_allow_html=True,
    )


def render_signal_card(signal: dict, index: int):
    title = signal.get("title", "不明")
    description = signal.get("description", "")
    source_type = signal.get("source_type", "")
    companies = signal.get("beneficiary_companies", "")
    rumor_stage = signal.get("rumor_stage", 3)
    stage_reason = signal.get("stage_reason", "")
    puzzle_hint = signal.get("puzzle_hint", "")
    risk = signal.get("risk", "")

    # カードの背景色をRumor Stageで変える
    stage_colors = {1: "#7F77DD", 2: "#1D9E75", 3: "#378ADD", 4: "#EF9F27", 5: "#E24B4A"}
    border_color = stage_colors.get(rumor_stage, "#888")

    st.markdown(
        f'<div style="border-left:4px solid {border_color};padding:12px 16px;'
        f'margin:8px 0;background:#1a1a2e;border-radius:0 8px 8px 0;">'
        f'<div style="font-size:18px;font-weight:bold;color:white;margin-bottom:8px;">'
        f'シグナル {index + 1}: {title}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    render_rumor_badge(rumor_stage)
    st.caption(stage_reason)

    st.markdown("**何が起きているか:**")
    st.write(description)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**情報源:** {source_type}")
        st.markdown(f"**恩恵企業:** {companies}")
    with col2:
        st.markdown(f"**⚠️ リスク:** {risk}")

    st.markdown("---")
    st.markdown("**🧩 パズルのヒント(二次推論):**")
    st.info(puzzle_hint)

    # 個別株分析へのリンク(将来的にはボタンで遷移)
    st.caption("💡 気になる企業があれば「個別株分析」ページで証券コードを入力して詳細を確認")


# ============================================================
# メイン UI
# ============================================================

# --- テーマ選択 ---
st.markdown("### スキャンしたいテーマを入力")

# クイック選択ボタン
st.caption("よく使うテーマ:")
quick_cols = st.columns(6)
quick_themes = ["AI・半導体", "防衛・安全保障", "再生エネルギー", "医療・バイオ", "宇宙・衛星", "暗号通貨・Web3"]

selected_quick = None
for i, qt in enumerate(quick_themes):
    with quick_cols[i]:
        if st.button(qt, key=f"quick_{i}", use_container_width=True):
            selected_quick = qt

# テキスト入力
theme_input = st.text_input(
    "テーマ",
    value=selected_quick if selected_quick else "",
    placeholder="例: AI半導体サプライチェーン、日本の防衛費拡大、量子コンピューティング",
    key="theme_input",
)

# オプション: スキャンの深さ
with st.expander("⚙️ スキャン設定"):
    scan_focus = st.radio(
        "重視する情報源",
        ["バランス(推奨)", "政策・規制系を重視", "技術・特許系を重視", "海外事例を重視"],
        index=0,
    )

# --- スキャン実行 ---
if st.button("📡 スキャン開始", type="primary", disabled=not theme_input.strip()):
    with st.spinner(f"AIが「{theme_input}」に関する噂をウェブ検索中...\n（最大3分かかります。Web検索を複数回実行しています）"):
        scan_result = run_scan(theme_input.strip())
        st.session_state.scan_results = scan_result
        st.session_state.scan_theme = theme_input.strip()
        st.rerun()

# --- 結果表示 ---
results = st.session_state.scan_results
if results:
    if "error" in results:
        st.error(f"スキャンエラー: {results['error']}")
    else:
        scan_theme = results.get("theme", st.session_state.scan_theme or "")
        scan_date = results.get("scan_date", TODAY)
        signals = results.get("signals", [])
        meta = results.get("meta_observation", "")

        st.divider()
        st.markdown(f"### 📡 スキャン結果: 「{scan_theme}」")
        st.caption(f"スキャン日: {scan_date}")

        # 俯瞰コメント
        if meta:
            st.markdown("**🌍 市場の俯瞰:**")
            st.write(meta)
            st.divider()

        # シグナル数とRumor Stage分布
        if signals:
            stage_counts = {}
            for sig in signals:
                s = sig.get("rumor_stage", 3)
                stage_counts[s] = stage_counts.get(s, 0) + 1

            st.markdown(f"**発見されたシグナル: {len(signals)}件**")

            # Rumor Stage分布を表示
            dist_cols = st.columns(5)
            stage_names = {1: "💤 予兆", 2: "🌱 芽吹き", 3: "📢 拡散", 4: "📰 形成", 5: "✅ 確認"}
            for i in range(1, 6):
                with dist_cols[i - 1]:
                    count = stage_counts.get(i, 0)
                    if count > 0:
                        st.metric(stage_names[i], f"{count}件")
                    else:
                        st.metric(stage_names[i], "-")

            st.divider()

            # シグナルをRumor Stageの低い順にソート(価値が高い順)
            sorted_signals = sorted(signals, key=lambda x: x.get("rumor_stage", 3))

            for i, signal in enumerate(sorted_signals):
                render_signal_card(signal, i)
                st.divider()

        else:
            st.warning("シグナルが検出されませんでした。テーマを変えて再スキャンしてみてください。")

        # --- アクションボタン ---
        st.markdown("### 次のステップ")
        col_a1, col_a2, col_a3 = st.columns(3)
        with col_a1:
            if st.button("🔨 仮説破壊エンジンで検証", use_container_width=True):
                st.info("気になるシグナルを仮説として「仮説破壊エンジン」ページに入力してください")
        with col_a2:
            if st.button("📊 個別株分析で銘柄を確認", use_container_width=True):
                st.info("恩恵企業の証券コードを「個別株分析」ページに入力してください")
        with col_a3:
            if st.button("📡 別のテーマでスキャン", use_container_width=True):
                st.session_state.scan_results = None
                st.session_state.scan_theme = None
                st.rerun()

# --- フッター ---
st.divider()
st.caption("💡 噂スキャナーは投資助言ではありません。AIが見つけた情報は必ず自分で検証してください。")
st.caption("🔍 Rumor Stage が低いシグナルほど「まだ誰も気づいていない」可能性が高く、投資機会として価値があります。")

if st.button("🔄 結果をクリアして最初からやり直す"):
    st.session_state.scan_results = None
    st.session_state.scan_theme = None
    st.rerun()