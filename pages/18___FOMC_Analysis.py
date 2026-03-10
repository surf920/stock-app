"""
FOMC自動分析ページ
1. FOMC声明文を自動取得（FRB公式サイト）
2. 前回との差分をClaude APIで分析
3. タカ派/ハト派スコアリング
4. CME FedWatch情報の手動入力 + 分析
5. パウエル記者会見のキーフレーズ抽出
"""

from api_helper import call_anthropic_api
import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import re

st.set_page_config(page_title="FOMC分析", page_icon="🏦", layout="wide")
st.title("🏦 FOMC自動分析")
st.markdown("声明文の自動取得 → 前回との差分 → タカ派/ハト派スコアリング")

# --- API Key ---
ANTHROPIC_API_KEY = ""
try:
    ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

if not ANTHROPIC_API_KEY:
    st.error("⚠️ ANTHROPIC_API_KEY が設定されていません。")
    st.stop()


# ============================================================
# FOMC声明文の取得
# ============================================================

# 最近のFOMC声明文URL（手動で更新 or RSSで自動取得）
FOMC_CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FOMC_RSS_URL = "https://www.federalreserve.gov/feeds/press_monetary.xml"


@st.cache_data(ttl=3600)
def fetch_fomc_statement_links():
    """FRB公式サイトからFOMC声明文のリンクを取得"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

        # RSS フィードから取得を試みる
        r = requests.get(FOMC_RSS_URL, headers=headers, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "xml")
            items = soup.find_all("item")
            statements = []
            for item in items:
                title = item.find("title")
                link = item.find("link")
                pub_date = item.find("pubDate")
                if title and link:
                    title_text = title.get_text()
                    if "statement" in title_text.lower() or "press release" in title_text.lower():
                        statements.append({
                            "title": title_text,
                            "url": link.get_text().strip(),
                            "date": pub_date.get_text() if pub_date else "",
                        })
            if statements:
                return statements[:10]  # 最新10件

        # フォールバック: カレンダーページからスクレイピング
        r2 = requests.get(FOMC_CALENDAR_URL, headers=headers, timeout=15)
        if r2.status_code == 200:
            soup2 = BeautifulSoup(r2.text, "html.parser")
            links = soup2.find_all("a", href=True)
            statements = []
            for link in links:
                href = link.get("href", "")
                text = link.get_text()
                if "monetary" in href and "htm" in href:
                    full_url = f"https://www.federalreserve.gov{href}" if href.startswith("/") else href
                    statements.append({
                        "title": text.strip(),
                        "url": full_url,
                        "date": "",
                    })
            if statements:
                return statements[:10]

        return []
    except Exception as e:
        return [{"error": str(e)}]


@st.cache_data(ttl=3600)
def fetch_statement_text(url):
    """声明文のテキストを取得"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"

        soup = BeautifulSoup(r.text, "html.parser")

        # FRBのページ構造に合わせてテキスト抽出
        # メインコンテンツエリアを探す
        content = soup.find("div", {"id": "article"})
        if not content:
            content = soup.find("div", class_="col-xs-12")
        if not content:
            content = soup.find("main")
        if not content:
            content = soup.body

        if content:
            # 不要な要素を除去
            for tag in content.find_all(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = content.get_text(separator="\n", strip=True)
            # 空行を整理
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            return "\n".join(lines), None
        return None, "コンテンツが見つかりません"
    except Exception as e:
        return None, str(e)


def analyze_fomc_with_claude(current_statement, previous_statement=None, press_conference=None, fedwatch_data=None):
    """Claude APIでFOMC声明文を分析"""

    system_prompt = """あなたはFRBの金融政策を専門に分析するシニアエコノミストです。
FOMC声明文を詳細に分析し、以下のJSON形式で回答してください。
日本語で回答してください。

{
    "hawk_dove_score": {
        "score": -5から+5の数値（-5=極めてハト派, 0=中立, +5=極めてタカ派）,
        "previous_score": 前回のスコア（前回声明文がある場合）,
        "direction": "タカ派シフト/ハト派シフト/変化なし",
        "reasoning": "スコアの根拠"
    },
    "key_changes": [
        {
            "category": "変更カテゴリ（金利、QT、経済認識、インフレ、雇用等）",
            "previous_wording": "前回の文言（ない場合はN/A）",
            "current_wording": "今回の文言",
            "significance": "この変更の意味",
            "direction": "タカ派/ハト派/中立"
        }
    ],
    "economic_assessment": {
        "growth": "FRBの成長認識（改善/悪化/変化なし）",
        "inflation": "FRBのインフレ認識",
        "labor": "FRBの雇用認識",
        "risks": "FRBが認識しているリスク"
    },
    "forward_guidance": {
        "next_move": "次回の予想されるアクション（利上げ/利下げ/据え置き）",
        "timing_hint": "タイミングに関するヒント",
        "conditions": "アクションの条件"
    },
    "market_implications": {
        "stocks": "株式市場への影響",
        "bonds": "債券市場への影響",
        "dollar": "ドルへの影響",
        "gold": "金への影響",
        "crypto": "暗号資産への影響"
    },
    "press_conference_analysis": {
        "key_phrases": ["重要フレーズ1", "重要フレーズ2"],
        "tone": "全体的なトーン",
        "surprises": "市場が予想していなかった発言",
        "implications": "記者会見から読み取れる追加情報"
    },
    "fedwatch_analysis": {
        "market_alignment": "市場の織り込みとFRBの示唆は一致しているか",
        "mispricing": "市場が誤って織り込んでいる可能性があるもの",
        "trading_implication": "この乖離から生じるトレード機会"
    },
    "action_items": [
        "投資家として取るべきアクション1",
        "投資家として取るべきアクション2",
        "投資家として取るべきアクション3"
    ],
    "summary": "200文字以内の総合サマリー"
}

重要ルール:
1. 声明文の文言を正確に引用すること
2. 前回との差分がある場合、変更箇所を全て特定すること
3. 表面的な分析ではなく、FRBが意図的に選んだ言い回しの意味を読み取ること
4. 投資判断に直結する具体的な示唆を提供すること"""

    user_parts = []
    user_parts.append("以下のFOMC関連データを分析してください。\n")

    user_parts.append("=== 今回のFOMC声明文 ===")
    user_parts.append(current_statement)

    if previous_statement:
        user_parts.append("\n=== 前回のFOMC声明文 ===")
        user_parts.append(previous_statement)
        user_parts.append("\n【指示】前回と今回の声明文の差分を全て特定し、各変更の意味を分析してください。")
    else:
        user_parts.append("\n【注意】前回の声明文がないため、差分分析は行わず、今回の声明文のみを分析してください。")

    if press_conference:
        user_parts.append("\n=== パウエル議長 記者会見テキスト ===")
        user_parts.append(press_conference)

    if fedwatch_data:
        user_parts.append("\n=== CME FedWatch データ ===")
        user_parts.append(fedwatch_data)

    user_parts.append("\n上記データに基づいて、JSON形式で分析結果を返してください。")

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 8192,
        "system": system_prompt,
        "messages": [{"role": "user", "content": "\n".join(user_parts)}]
    }

    result_data, api_error = call_anthropic_api(headers, payload)
    if api_error:
        return None
    return result_data


# ============================================================
# メイン UI
# ============================================================

# ============================================================
# 分析結果の表示関数（タブより先に定義）
# ============================================================
def display_analysis(analysis):
    """分析結果を表示"""
    st.markdown("---")

    # タカ派/ハト派スコア
    st.subheader("🦅🕊 タカ派/ハト派 スコア")
    hd = analysis.get("hawk_dove_score", {})

    col_hd1, col_hd2, col_hd3 = st.columns(3)
    with col_hd1:
        score = hd.get("score", 0)
        if isinstance(score, str):
            try:
                score = int(score)
            except:
                score = 0
        score_color = "🔴" if score > 2 else "🟡" if score > 0 else "🟢" if score > -2 else "🔵"
        if score >= 4:
            label = "極めてタカ派"
        elif score >= 2:
            label = "タカ派"
        elif score >= 1:
            label = "ややタカ派"
        elif score == 0:
            label = "中立"
        elif score >= -1:
            label = "ややハト派"
        elif score >= -3:
            label = "ハト派"
        else:
            label = "極めてハト派"
        st.metric("今回スコア", f"{score_color} {score:+d} ({label})")
    with col_hd2:
        prev_score = hd.get("previous_score", "N/A")
        if isinstance(prev_score, (int, float)):
            st.metric("前回スコア", f"{prev_score:+.0f}")
        else:
            st.metric("前回スコア", "N/A")
    with col_hd3:
        direction = hd.get("direction", "N/A")
        dir_icon = {"タカ派シフト": "🦅↑", "ハト派シフト": "🕊↑", "変化なし": "→"}.get(direction, "")
        st.metric("方向", f"{dir_icon} {direction}")

    if hd.get("reasoning"):
        st.info(f"📝 {hd['reasoning']}")

    # スコアバー（視覚化）
    bar_position = (score + 5) / 10  # 0-1に正規化
    st.markdown(f"""
    <div style="background: linear-gradient(to right, #3b82f6, #94a3b8, #ef4444); 
                height: 20px; border-radius: 10px; position: relative; margin: 10px 0;">
        <div style="position: absolute; left: {bar_position*100}%; top: -5px; 
                    width: 30px; height: 30px; background: white; border-radius: 50%; 
                    border: 3px solid #333; transform: translateX(-15px);"></div>
    </div>
    <div style="display: flex; justify-content: space-between; font-size: 12px; color: #888;">
        <span>🕊 ハト派 (-5)</span>
        <span>中立 (0)</span>
        <span>🦅 タカ派 (+5)</span>
    </div>
    """, unsafe_allow_html=True)

    # 主要変更点
    key_changes = analysis.get("key_changes", [])
    if key_changes:
        st.markdown("---")
        st.subheader("🔍 前回からの主要変更点")
        for change in key_changes:
            dir_icon = {"タカ派": "🦅", "ハト派": "🕊", "中立": "➡️"}.get(change.get("direction", ""), "")
            with st.expander(f"{dir_icon} {change.get('category', '')} — {change.get('direction', '')}"):
                if change.get("previous_wording") and change["previous_wording"] != "N/A":
                    st.markdown(f"**前回:** {change['previous_wording']}")
                st.markdown(f"**今回:** {change.get('current_wording', '')}")
                st.info(f"💡 意味: {change.get('significance', '')}")

    # 経済評価
    st.markdown("---")
    st.subheader("📊 FRBの経済認識")
    ea = analysis.get("economic_assessment", {})
    col_e1, col_e2, col_e3, col_e4 = st.columns(4)
    with col_e1:
        st.markdown(f"**成長:** {ea.get('growth', 'N/A')}")
    with col_e2:
        st.markdown(f"**インフレ:** {ea.get('inflation', 'N/A')}")
    with col_e3:
        st.markdown(f"**雇用:** {ea.get('labor', 'N/A')}")
    with col_e4:
        st.markdown(f"**リスク:** {ea.get('risks', 'N/A')}")

    # フォワードガイダンス
    st.markdown("---")
    st.subheader("🔮 フォワードガイダンス")
    fg = analysis.get("forward_guidance", {})
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        next_move = fg.get("next_move", "N/A")
        move_icon = {"利上げ": "🔴", "利下げ": "🟢", "据え置き": "🟡"}.get(next_move, "⚪")
        st.metric("次の動き", f"{move_icon} {next_move}")
    with col_f2:
        st.markdown(f"**タイミング:** {fg.get('timing_hint', 'N/A')}")
    with col_f3:
        st.markdown(f"**条件:** {fg.get('conditions', 'N/A')}")

    # 市場への影響
    st.markdown("---")
    st.subheader("💹 市場への影響")
    mi = analysis.get("market_implications", {})
    col_mi1, col_mi2, col_mi3, col_mi4, col_mi5 = st.columns(5)
    with col_mi1:
        st.markdown(f"**📈 株式**\n\n{mi.get('stocks', 'N/A')}")
    with col_mi2:
        st.markdown(f"**📊 債券**\n\n{mi.get('bonds', 'N/A')}")
    with col_mi3:
        st.markdown(f"**💵 ドル**\n\n{mi.get('dollar', 'N/A')}")
    with col_mi4:
        st.markdown(f"**🥇 金**\n\n{mi.get('gold', 'N/A')}")
    with col_mi5:
        st.markdown(f"**🪙 暗号資産**\n\n{mi.get('crypto', 'N/A')}")

    # 記者会見分析
    pca = analysis.get("press_conference_analysis", {})
    if pca and pca.get("key_phrases"):
        st.markdown("---")
        st.subheader("🎤 パウエル記者会見 分析")
        for phrase in pca.get("key_phrases", []):
            st.warning(f"💬 {phrase}")
        if pca.get("tone"):
            st.markdown(f"**全体トーン:** {pca['tone']}")
        if pca.get("surprises"):
            st.error(f"⚡ サプライズ: {pca['surprises']}")
        if pca.get("implications"):
            st.info(f"💡 示唆: {pca['implications']}")

    # FedWatch分析
    fwa = analysis.get("fedwatch_analysis", {})
    if fwa and fwa.get("market_alignment"):
        st.markdown("---")
        st.subheader("📊 FedWatch分析")
        st.markdown(f"**市場との一致度:** {fwa.get('market_alignment', 'N/A')}")
        if fwa.get("mispricing"):
            st.warning(f"⚠️ 誤った織り込み: {fwa['mispricing']}")
        if fwa.get("trading_implication"):
            st.success(f"💡 トレード機会: {fwa['trading_implication']}")

    # アクションアイテム
    st.markdown("---")
    st.subheader("⚡ アクションアイテム")
    for action in analysis.get("action_items", []):
        st.success(f"✅ {action}")

    # 総合サマリー
    st.markdown("---")
    st.subheader("📝 総合サマリー")
    st.info(analysis.get("summary", "N/A"))

    st.caption(f"分析時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# ============================================================
# タブ構成
# ============================================================
tab_auto, tab_manual, tab_history = st.tabs(["🤖 自動分析", "📝 手動入力", "📚 分析履歴"])

# --- タブ1: 自動分析 ---
with tab_auto:
    st.subheader("🤖 FOMC声明文 自動取得 & 分析")

    # 声明文リンクを取得
    with st.spinner("FRBサイトから声明文リストを取得中..."):
        links = fetch_fomc_statement_links()

    if links and not any("error" in l for l in links):
        st.success(f"✅ {len(links)}件の声明文を検出")

        # 最新と前回を選択
        options = [f"{l.get('date', '')} - {l.get('title', '')}" for l in links]

        col_sel1, col_sel2 = st.columns(2)
        with col_sel1:
            current_idx = st.selectbox("📄 今回の声明文", range(len(options)), format_func=lambda x: options[x], key="current")
        with col_sel2:
            prev_idx = st.selectbox("📄 前回の声明文（比較用）", range(len(options)), index=min(1, len(options)-1), format_func=lambda x: options[x], key="prev")

        # 追加データ入力
        st.markdown("---")
        col_extra1, col_extra2 = st.columns(2)
        with col_extra1:
            press_conf = st.text_area(
                "🎤 パウエル記者会見テキスト（任意）",
                height=150,
                placeholder="記者会見のトランスクリプトを貼り付け（なくてもOK）",
                key="press_auto"
            )
        with col_extra2:
            fedwatch = st.text_area(
                "📊 CME FedWatch データ（任意）",
                height=150,
                placeholder="例:\n次回FOMC: 据え置き 72%, 利下げ25bp 28%\n6ヶ月後: 据え置き 30%, 利下げ25bp 45%, 利下げ50bp 25%",
                key="fedwatch_auto"
            )

        # 分析実行
        if st.button("🔍 自動分析を実行", type="primary", use_container_width=True, key="auto_btn"):

            # 声明文テキスト取得
            with st.spinner("声明文を取得中..."):
                current_text, err1 = fetch_statement_text(links[current_idx]["url"])
                previous_text, err2 = fetch_statement_text(links[prev_idx]["url"])

            if err1:
                st.error(f"今回の声明文取得エラー: {err1}")
                st.info("💡 取得に失敗した場合は「手動入力」タブからテキストを貼り付けてください。")
            else:
                st.success("✅ 声明文を取得完了")

                with st.expander("📄 今回の声明文（プレビュー）"):
                    st.text(current_text[:2000] + "..." if len(current_text) > 2000 else current_text)

                if previous_text:
                    with st.expander("📄 前回の声明文（プレビュー）"):
                        st.text(previous_text[:2000] + "..." if len(previous_text) > 2000 else previous_text)

                # Claude API分析
                with st.spinner("🤖 Claude APIで分析中... (15-30秒)"):
                    analysis = analyze_fomc_with_claude(
                        current_text,
                        previous_text if not err2 else None,
                        press_conf if press_conf.strip() else None,
                        fedwatch if fedwatch.strip() else None,
                    )

                if analysis:
                    display_analysis(analysis)
                else:
                    st.error("分析に失敗しました")

    else:
        st.warning("⚠️ FRBサイトから声明文を自動取得できませんでした。「手動入力」タブを使ってください。")
        if links:
            for l in links:
                if "error" in l:
                    st.caption(f"エラー: {l['error']}")


# --- タブ2: 手動入力 ---
with tab_manual:
    st.subheader("📝 手動入力で分析")
    st.caption("声明文のテキストを直接貼り付けて分析します。")

    current_manual = st.text_area(
        "📄 今回のFOMC声明文",
        height=300,
        placeholder="FOMCの声明文をここに貼り付け",
        key="current_manual"
    )

    previous_manual = st.text_area(
        "📄 前回のFOMC声明文（任意 — 差分分析用）",
        height=300,
        placeholder="前回の声明文を貼り付け（差分分析が不要ならスキップ）",
        key="prev_manual"
    )

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        press_manual = st.text_area(
            "🎤 パウエル記者会見テキスト（任意）",
            height=150,
            placeholder="記者会見のトランスクリプトを貼り付け",
            key="press_manual"
        )
    with col_m2:
        fedwatch_manual = st.text_area(
            "📊 CME FedWatch データ（任意）",
            height=150,
            placeholder="例:\n次回FOMC: 据え置き 72%, 利下げ25bp 28%",
            key="fedwatch_manual"
        )

    if st.button("🔍 分析を実行", type="primary", use_container_width=True, key="manual_btn"):
        if not current_manual.strip():
            st.error("声明文を入力してください")
        else:
            with st.spinner("🤖 Claude APIで分析中... (15-30秒)"):
                analysis = analyze_fomc_with_claude(
                    current_manual,
                    previous_manual if previous_manual.strip() else None,
                    press_manual if press_manual.strip() else None,
                    fedwatch_manual if fedwatch_manual.strip() else None,
                )

            if analysis:
                display_analysis(analysis)
            else:
                st.error("分析に失敗しました")


# --- タブ3: 分析履歴 ---
with tab_history:
    st.subheader("📚 FOMC分析履歴")
    st.info("今後のアップデートで、過去の分析結果を保存・比較できるようにします。")
    st.caption("現時点では、分析結果のスクリーンショットを日記に記録してください。")


# サイドバー
with st.sidebar:
    st.markdown("### 🏦 FOMC分析ツール")
    st.markdown("""
    **自動分析:**
    - FRB公式サイトから声明文を自動取得
    - 前回との文言差分を全て検出
    - タカ派/ハト派スコア(-5〜+5)
    
    **手動入力:**
    - 声明文のテキストを貼り付けて分析
    - 記者会見テキストも分析可能
    
    **追加データ:**
    - CME FedWatchの金利確率
    - パウエル記者会見トランスクリプト
    """)

    st.markdown("---")
    st.markdown("### 📅 2026年 FOMCスケジュール")
    st.markdown("""
    - ~~1月28-29日~~
    - ~~3月18-19日~~
    - 5月6-7日
    - 6月17-18日
    - 7月29-30日
    - 9月16-17日
    - 10月28-29日
    - 12月9-10日
    """)
    st.caption("※ スケジュールはFRB公式サイトで確認")
