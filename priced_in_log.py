"""
priced_in_log.py
織り込み度スコアの「前向き検証」ログ（GitHub API 永続化）

────────────────────────────────────────────────────────────
【検証する仮説 — 仮説A（記録を始める前にここで固定する）】

  織り込み度スコアが高い銘柄ほど、決算後の実際の値動きは
  インプライドムーブ（市場の予想）より小さくなりやすい。
  → 高スコア = プレミアム売り（カバードコール等）が有利、という読み。

このファイルにスコアを記録し、決算が過ぎたら actual_move_pct を
埋めて、仮説A が現実に成り立つかを後で検証する。
仮説を先に文字で固定しておくこと自体が、「データを見てから
都合よく解釈する」のを防ぐための歯止め。後から変えないこと。
────────────────────────────────────────────────────────────
"""

import json
import base64
from datetime import datetime

import requests
import streamlit as st

# 記録ファイル（リポジトリ直下に作られる）
LOG_FILE = "priced_in_log.json"

# 検証する仮説（事前固定。変更しない）
HYPOTHESIS = "A"

# 固定銘柄ユニバース（S&P100 中心の大型・高流動性 30 銘柄）
# このリストは固定する。気分で足し引きしないこと（選択バイアス防止）。
UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO",
    "AMD", "NFLX", "ORCL", "ADBE", "CRM", "JPM", "BAC", "GS",
    "V", "MA", "UNH", "JNJ", "LLY", "ABBV", "MRK", "WMT",
    "HD", "MCD", "COST", "NKE", "PG", "XOM",
]


# =====================================================
# GitHub API ヘルパー（Home.py と同じ方式）
# =====================================================
def _get_github_config():
    """GitHub 設定を取得 → (token, repo)"""
    try:
        token = st.secrets["github"]["token"]
        repo = st.secrets["github"]["repo"]
        return token, repo
    except Exception:
        return None, None


def _github_get_file(token, repo, path):
    """GitHub からファイルを取得 → (内容, sha)。無ければ (None, None)"""
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]
    return None, None


def _github_put_file(token, repo, path, content_str, sha=None):
    """GitHub にファイルを書き込み（create or update）→ (ok: bool, detail: str)"""
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    encoded = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
    body = {
        "message": f"Update priced_in_log {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "content": encoded,
    }
    if sha:
        body["sha"] = sha
    try:
        r = requests.put(url, headers=headers, json=body, timeout=15)
    except Exception as e:
        return False, f"request error: {e}"
    if r.status_code in (200, 201):
        return True, ""
    # 失敗時：GitHubが返した理由をそのまま見せる
    try:
        msg = r.json().get("message", "")
    except Exception:
        msg = (r.text or "")[:200]
    return False, f"HTTP {r.status_code} — {msg}"


# =====================================================
# ログの読み書き
# =====================================================
def load_log():
    """記録ログを読み込む → (records: list, sha: str or None)"""
    token, repo = _get_github_config()
    if not token or not repo:
        return [], None
    content, sha = _github_get_file(token, repo, LOG_FILE)
    if content is None:
        # ファイルがまだ存在しない（初回）
        return [], None
    try:
        records = json.loads(content)
        if not isinstance(records, list):
            return [], sha
        return records, sha
    except Exception:
        # 壊れている場合は上書きせず空で返す（sha は保持）
        return [], sha


def save_log(records, sha):
    """記録ログを書き込む → (ok: bool, detail: str)"""
    token, repo = _get_github_config()
    if not token or not repo:
        return False, "Secrets が読めません（st.secrets['github']['token'] / ['repo']）"
    try:
        content_str = json.dumps(records, ensure_ascii=False, indent=2)
    except Exception as e:
        return False, f"JSON 変換エラー: {e}"
    return _github_put_file(token, repo, LOG_FILE, content_str, sha)


def make_entry_id(ticker, earnings_date):
    """重複判定用 ID: ティッカー + 決算日"""
    return f"{ticker}_{earnings_date}"


def is_recorded(records, ticker, earnings_date):
    """同じ銘柄・同じ決算日が既に記録済みか"""
    target = make_entry_id(ticker, earnings_date)
    return any(r.get("id") == target for r in records)


def append_entry(entry):
    """
    1 件記録する。同じ銘柄・同じ決算日が既にあれば追記しない。
    → (ok: bool, message: str)
    """
    records, sha = load_log()
    if is_recorded(records, entry["ticker"], entry["earnings_date"]):
        return False, "この銘柄の今回の決算は既に記録済みです"
    records.append(entry)
    ok, detail = save_log(records, sha)
    if ok:
        return True, f"記録しました（現在 {len(records)} 件）"
    return False, f"GitHub への保存に失敗: {detail}"