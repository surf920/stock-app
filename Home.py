import streamlit as st
import json
import os
from datetime import datetime, timedelta
import pandas as pd

st.set_page_config(page_title="Macro Intelligence HQ", page_icon="🏠", layout="wide")

# --- スタイル ---
st.markdown("""
<style>
    .routine-box {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 20px;
        margin: 8px 0;
        border-left: 4px solid #00d4aa;
    }
    .routine-box-weekly {
        border-left-color: #3b82f6;
    }
    .routine-box-monthly {
        border-left-color: #f59e0b;
    }
    .domino-banner {
        text-align: center;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 日記データの読み書き
# ============================================================
DIARY_FILE = "diary_data.json"

def load_diary():
    """日記データを読み込み"""
    if os.path.exists(DIARY_FILE):
        try:
            with open(DIARY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_diary(data):
    """日記データを保存"""
    try:
        with open(DIARY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"保存エラー: {e}")

def export_diary_csv(diary_data):
    """日記データをCSVに変換"""
    rows = []
    for date_str, entry in sorted(diary_data.items(), reverse=True):
        rows.append({
            "日付": date_str,
            "マーケット目線": entry.get("outlook", ""),
            "今日の判断": entry.get("decision", ""),
            "根拠": entry.get("reasoning", ""),
            "感情メモ": entry.get("emotion", ""),
            "反省・学び": entry.get("reflection", ""),
            "ポジション変更": entry.get("position_change", ""),
        })
    return pd.DataFrame(rows)


# ============================================================
# メインヘッダー
# ============================================================
col_title, col_date = st.columns([3, 1])
with col_title:
    st.title("🏠 Macro Intelligence HQ")
with col_date:
    now = datetime.now()
    st.markdown(f"### 📅 {now.strftime('%Y年%m月%d日')}")
    weekdays_jp = ["月", "火", "水", "木", "金", "土", "日"]
    st.caption(f"{weekdays_jp[now.weekday()]}曜日 {now.strftime('%H:%M')}")

st.markdown("---")

# ============================================================
# タブ構成
# ============================================================
tab_routine, tab_diary, tab_history = st.tabs(["📋 ルーティン", "📝 トレード日記", "📚 日記履歴"])

# ============================================================
# タブ1: ルーティン
# ============================================================
with tab_routine:

    # --- 毎日やること ---
    st.subheader("⚡ 毎日やること（10分）")
    st.caption("市場が開く前に。判断するな、確認だけしろ。")

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.markdown("#### 🔍 3指標チェック（TradingView 30秒）")
        daily_check_1 = st.checkbox("米10年債利回り — 方向確認（上昇↑ or 下落↓）", key="d1")
        daily_check_2 = st.checkbox("DXY（ドル指数）— 方向確認", key="d2")
        daily_check_3 = st.checkbox("原油（WTI）— 方向確認", key="d3")

        if daily_check_1 and daily_check_2 and daily_check_3:
            st.success("✅ 3指標確認完了")
            st.info("💡 3つとも昨日と同じ方向なら → **何もしない**。これが最善の日が大半。")

    with col_d2:
        st.markdown("#### 🎯 Alice Diagnosis（10秒）")
        daily_check_4 = st.checkbox("ドミノ点灯数を確認（0/4 → 無視、2/4以上 → 行動検討）", key="d4")

        if daily_check_4:
            st.success("✅ ドミノ確認完了")

        st.markdown("#### ⚠️ 異常検知（該当時のみ）")
        st.caption("以下のいずれかが発生した日だけ、個別ページで深掘り：")
        st.markdown("""
        - 原油が **1日で±5%以上** 動いた
        - VIXが **25を超えた**
        - DXYが **1日で±1.5%以上** 動いた
        - ドミノが **2/4以上** 点灯した
        """)

    st.markdown("")
    st.warning("🚫 **やるな:** AI Agent Analysisを毎日回すこと。ノイズに振り回される。")

    st.markdown("---")

    # --- 毎週やること ---
    st.subheader("📊 毎週やること（日曜 30分）")
    st.caption("週に1回、腰を据えて分析する。ここが判断の中心。")

    col_w1, col_w2 = st.columns(2)

    with col_w1:
        st.markdown("#### Step 1: AI Agent Analysisを実行")
        weekly_check_1 = st.checkbox("AI Agent Analysisを回す（20カテゴリ全収集）", key="w1")
        weekly_check_2 = st.checkbox("ポートフォリオCSVもアップロードして分析", key="w2")

        st.markdown("#### Step 2: シナリオ検証")
        weekly_check_3 = st.checkbox("先週の3シナリオのうち、どれに現実が近づいたか確認", key="w3")
        weekly_check_4 = st.checkbox("各シナリオの発火条件に対して、今週の数字がどう動いたか確認", key="w4")

    with col_w2:
        st.markdown("#### Step 3: 来週の行動ルール設定")
        weekly_check_5 = st.checkbox("「この条件になったらこう動く」を事前に決めて書き出す", key="w5")
        weekly_check_6 = st.checkbox("AIの推奨と自分の直観が食い違う点を確認", key="w6")

        st.markdown("#### Step 4: トレード日記を書く")
        weekly_check_7 = st.checkbox("今週の判断とその結果を記録（日記タブへ）", key="w7")

    weekly_done = sum([weekly_check_1, weekly_check_2, weekly_check_3, weekly_check_4, weekly_check_5, weekly_check_6, weekly_check_7])
    if weekly_done == 7:
        st.success("✅ 週次レビュー完了。来週の行動ルールは明確か？")
    elif weekly_done > 0:
        st.info(f"📊 週次レビュー進捗: {weekly_done}/7")

    st.markdown("")
    st.info("""
    💡 **週次の行動ルール例（紙に書いておく）:**
    - 「原油がWTI $70以下に落ちたら → 日本株を20%買い戻す」
    - 「VIXが30超え + ドミノ2/4以上 → 残りの米株も半分落とす」
    - 「停戦が正式発表されたら → エネルギー以外のセクターを買い増す」
    """)

    st.markdown("---")

    # --- 毎月やること ---
    st.subheader("🏦 毎月やること（FOMC後 1時間）")
    st.caption("月に1回の最重要判断。ここで「目線」を決める。")

    col_m1, col_m2 = st.columns(2)

    with col_m1:
        st.markdown("#### FOMC分析")
        monthly_check_1 = st.checkbox("FOMC声明文の全文をClaudeに分析させる（前回との差分）", key="m1")
        monthly_check_2 = st.checkbox("パウエル記者会見のキーフレーズを抽出", key="m2")
        monthly_check_3 = st.checkbox("CME FedWatchで金利織り込みの変化を確認", key="m3")

    with col_m2:
        st.markdown("#### 月次判断")
        monthly_check_4 = st.checkbox("来月の「目線」を決める（リスクオン / リスクオフ / 中立）", key="m4")
        monthly_check_5 = st.checkbox("ポートフォリオ全体のリバランスを検討", key="m5")
        monthly_check_6 = st.checkbox("トレード日記に月次サマリーを記録", key="m6")

    monthly_done = sum([monthly_check_1, monthly_check_2, monthly_check_3, monthly_check_4, monthly_check_5, monthly_check_6])
    if monthly_done == 6:
        st.success("✅ 月次レビュー完了。来月の目線は明確か？")
    elif monthly_done > 0:
        st.info(f"🏦 月次レビュー進捗: {monthly_done}/6")

    st.markdown("")
    st.error("""
    🚫 **絶対にやるな:**
    - AI分析を見るたびにポジションを動かすこと → 取引コストで資産が削られる
    - AIが「確度：高」と言ったからといって大きなポジションを取ること → 1回の判断にポートフォリオの10%以上を賭けるな
    - 底を拾おうとすること → 反転が明確になってから動いても十分間に合う
    """)

    # --- ドミノ別行動ルール ---
    st.markdown("---")
    st.subheader("🎯 ドミノ別 ポジション管理ルール")

    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    with col_r1:
        st.markdown("### 🟢 0/4")
        st.metric("株式", "60-80%")
        st.metric("現金", "20-40%")
        st.caption("通常運転")
    with col_r2:
        st.markdown("### 🟡 1/4")
        st.metric("株式", "40-60%")
        st.metric("現金", "40-60%")
        st.caption("やや縮小")
    with col_r3:
        st.markdown("### 🟠 2/4")
        st.metric("株式", "20-40%")
        st.metric("現金", "60-80%")
        st.caption("大幅縮小")
    with col_r4:
        st.markdown("### 🔴 3-4/4")
        st.metric("株式", "0-20%")
        st.metric("現金", "80-100%")
        st.caption("退避モード")

    st.caption("※ ドミノは機械的判定。地政学リスク等は自分の直観が先行することがある。直観がドミノより保守的な場合、直観を優先してよい。")


# ============================================================
# タブ2: トレード日記
# ============================================================
with tab_diary:
    st.subheader("📝 トレード日記")
    st.caption("判断の記録が、将来のエッジになる。")

    diary_data = load_diary()

    # 日付選択
    diary_date = st.date_input("📅 日付", value=datetime.now().date(), key="diary_date")
    date_key = diary_date.strftime("%Y-%m-%d")

    # 既存データがあればロード
    existing = diary_data.get(date_key, {})

    st.markdown("---")

    col_j1, col_j2 = st.columns(2)

    with col_j1:
        outlook = st.selectbox(
            "🧭 今日のマーケット目線",
            ["", "強気（リスクオン）", "やや強気", "中立・様子見", "やや弱気", "弱気（リスクオフ）"],
            index=["", "強気（リスクオン）", "やや強気", "中立・様子見", "やや弱気", "弱気（リスクオフ）"].index(existing.get("outlook", "")),
            key="outlook"
        )

        decision = st.text_area(
            "⚡ 今日の判断（何をした／何をしなかった）",
            value=existing.get("decision", ""),
            height=100,
            placeholder="例: 日本株のポジションを20%落とした / 何もせず現金維持",
            key="decision"
        )

        reasoning = st.text_area(
            "📊 判断の根拠（何を見てそう判断した）",
            value=existing.get("reasoning", ""),
            height=100,
            placeholder="例: 原油が$90超え、VIXが22に上昇、ドミノ1/4点灯",
            key="reasoning"
        )

    with col_j2:
        emotion = st.text_area(
            "🧠 感情メモ（その時どう感じたか）",
            value=existing.get("emotion", ""),
            height=100,
            placeholder="例: 焦りがあった / 冷静に判断できた / 迷いがあった",
            key="emotion"
        )

        reflection = st.text_area(
            "💡 反省・学び",
            value=existing.get("reflection", ""),
            height=100,
            placeholder="例: 噂で買って事実で売れ、を忘れて早まった",
            key="reflection"
        )

        position_change = st.text_area(
            "📂 ポジション変更の詳細",
            value=existing.get("position_change", ""),
            height=100,
            placeholder="例: MSFT 25株売却 / XLE 100株追加 / 変更なし",
            key="position_change"
        )

    st.markdown("---")

    # 週次サマリー用
    is_weekly = st.checkbox("📊 これは週次レビューの記録", value=existing.get("is_weekly", False), key="is_weekly")
    is_monthly = st.checkbox("🏦 これは月次レビューの記録", value=existing.get("is_monthly", False), key="is_monthly")

    weekly_summary = ""
    monthly_summary = ""
    if is_weekly:
        weekly_summary = st.text_area(
            "📊 週次サマリー",
            value=existing.get("weekly_summary", ""),
            height=100,
            placeholder="今週のシナリオ検証結果、来週の行動ルール",
            key="weekly_summary"
        )
    if is_monthly:
        monthly_summary = st.text_area(
            "🏦 月次サマリー（来月の目線）",
            value=existing.get("monthly_summary", ""),
            height=100,
            placeholder="FOMC分析結果、来月の目線（リスクオン/オフ/中立）、重点監視項目",
            key="monthly_summary"
        )

    # 保存ボタン
    col_save, col_clear = st.columns([1, 1])
    with col_save:
        if st.button("💾 保存する", type="primary", use_container_width=True):
            entry = {
                "outlook": outlook,
                "decision": decision,
                "reasoning": reasoning,
                "emotion": emotion,
                "reflection": reflection,
                "position_change": position_change,
                "is_weekly": is_weekly,
                "is_monthly": is_monthly,
                "weekly_summary": weekly_summary,
                "monthly_summary": monthly_summary,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            diary_data[date_key] = entry
            save_diary(diary_data)
            st.success(f"✅ {date_key} の日記を保存しました")
            st.rerun()

    with col_clear:
        if st.button("🗑 この日の記録を削除", use_container_width=True):
            if date_key in diary_data:
                del diary_data[date_key]
                save_diary(diary_data)
                st.success(f"🗑 {date_key} の記録を削除しました")
                st.rerun()


# ============================================================
# タブ3: 日記履歴
# ============================================================
with tab_history:
    st.subheader("📚 トレード日記 履歴")

    diary_data = load_diary()

    if not diary_data:
        st.info("まだ日記がありません。「トレード日記」タブから記録を始めましょう。")
    else:
        # フィルター
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filter_type = st.selectbox("フィルター", ["すべて", "週次レビューのみ", "月次レビューのみ", "ポジション変更ありのみ"], key="filter")
        with col_f2:
            sort_order = st.selectbox("並び順", ["新しい順", "古い順"], key="sort")
        with col_f3:
            # CSVエクスポート
            if st.button("📥 CSV出力", use_container_width=True):
                df_export = export_diary_csv(diary_data)
                csv = df_export.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="ダウンロード",
                    data=csv,
                    file_name=f"trade_diary_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        # フィルター適用
        filtered = {}
        for date_key, entry in diary_data.items():
            if filter_type == "週次レビューのみ" and not entry.get("is_weekly"):
                continue
            if filter_type == "月次レビューのみ" and not entry.get("is_monthly"):
                continue
            if filter_type == "ポジション変更ありのみ" and not entry.get("position_change", "").strip():
                continue
            filtered[date_key] = entry

        # ソート
        sorted_dates = sorted(filtered.keys(), reverse=(sort_order == "新しい順"))

        st.caption(f"📝 {len(sorted_dates)} 件の記録")

        # 表示
        for date_key in sorted_dates:
            entry = filtered[date_key]
            outlook = entry.get("outlook", "")
            outlook_icon = {
                "強気（リスクオン）": "🟢",
                "やや強気": "🟢",
                "中立・様子見": "🟡",
                "やや弱気": "🟠",
                "弱気（リスクオフ）": "🔴",
            }.get(outlook, "⚪")

            # タグ
            tags = []
            if entry.get("is_weekly"):
                tags.append("📊週次")
            if entry.get("is_monthly"):
                tags.append("🏦月次")
            if entry.get("position_change", "").strip():
                tags.append("📂変更あり")
            tag_str = " ".join(tags)

            with st.expander(f"{outlook_icon} **{date_key}** — {outlook}　{tag_str}"):
                col_h1, col_h2 = st.columns(2)
                with col_h1:
                    if entry.get("decision"):
                        st.markdown(f"**⚡ 判断:** {entry['decision']}")
                    if entry.get("reasoning"):
                        st.markdown(f"**📊 根拠:** {entry['reasoning']}")
                    if entry.get("position_change"):
                        st.info(f"📂 ポジション変更: {entry['position_change']}")
                with col_h2:
                    if entry.get("emotion"):
                        st.markdown(f"**🧠 感情:** {entry['emotion']}")
                    if entry.get("reflection"):
                        st.markdown(f"**💡 反省:** {entry['reflection']}")

                if entry.get("weekly_summary"):
                    st.warning(f"📊 週次サマリー: {entry['weekly_summary']}")
                if entry.get("monthly_summary"):
                    st.error(f"🏦 月次サマリー: {entry['monthly_summary']}")

                st.caption(f"保存: {entry.get('saved_at', '')}")

        # 統計
        if len(diary_data) >= 5:
            st.markdown("---")
            st.subheader("📈 日記の統計")

            outlooks = [e.get("outlook", "") for e in diary_data.values() if e.get("outlook")]
            if outlooks:
                outlook_counts = pd.Series(outlooks).value_counts()
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    st.metric("記録日数", f"{len(diary_data)}日")
                with col_s2:
                    bullish = sum(1 for o in outlooks if "強気" in o)
                    bearish = sum(1 for o in outlooks if "弱気" in o)
                    st.metric("強気/弱気比率", f"{bullish} / {bearish}")
                with col_s3:
                    pos_changes = sum(1 for e in diary_data.values() if e.get("position_change", "").strip())
                    st.metric("ポジション変更回数", f"{pos_changes}回")

                st.caption("💡 ポジション変更が多すぎないか定期的に確認。月2-3回が目安。")


# ============================================================
# サイドバー: クイックリファレンス
# ============================================================
with st.sidebar:
    st.markdown("### ⚡ クイックリファレンス")

    st.markdown("#### 毎日（10分）")
    st.caption("米10年債 + DXY + 原油 + ドミノ確認")

    st.markdown("#### 毎週日曜（30分）")
    st.caption("AI Agent Analysis → シナリオ検証 → 行動ルール設定")

    st.markdown("#### 毎月FOMC後（1時間）")
    st.caption("声明文分析 → 来月の目線決定 → リバランス")

    st.markdown("---")

    st.markdown("#### 🎯 ドミノルール")
    st.markdown("""
    - **0/4** → 通常（株60-80%）
    - **1/4** → 縮小（株40-60%）
    - **2/4** → 大幅縮小（株20-40%）
    - **3/4+** → 退避（株0-20%）
    """)

    st.markdown("---")

    st.markdown("#### 📏 鉄のルール")
    st.markdown("""
    - 1回の判断に10%以上賭けるな
    - 損切り: 個別-20%, ETF-15%
    - 行動は月2-3回が上限
    - AIと直観が食い違ったら直観優先
    - ただし根拠を言語化できること
    """)

    st.markdown("---")
    st.caption(f"📊 日記データ: {len(load_diary())}件保存中")
    st.caption("💡 定期的にCSV出力でバックアップ推奨")
