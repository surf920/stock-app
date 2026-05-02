from core.auth import require_auth
require_auth()

import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
from typing import Optional
from api_helper import call_anthropic_api

# === J-Quants V2 API 設定 ===
JQUANTS_BASE = "https://api.jquants.com/v2"

# === Claude API 設定 ===
MODEL = "claude-opus-4-6"
MAX_TOKENS = 2000
TODAY = datetime.now().strftime("%Y年%m月%d日")
ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
HEADERS = {
    "x-api-key": ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}
WEB_SEARCH_TOOL = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]

# === ページ設定 ===
st.set_page_config(page_title="個別株分析", page_icon="📊", layout="wide")
st.title("📊 個別株分析")
st.caption("証券コードを入力 → 判断に必要な情報を一画面で")

# === セッション状態 ===
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "analysis_code" not in st.session_state:
    st.session_state.analysis_code = None
if "rumor_result" not in st.session_state:
    st.session_state.rumor_result = None


# ============================================================
# J-Quants V2 認証 & 安全なリクエスト
# ============================================================
def _headers() -> dict:
    api_key = st.secrets.get("JQUANTS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "JQUANTS_API_KEY が Streamlit Secrets に設定されていません。"
            "J-QuantsダッシュボードのAPI KeysページでAPI Keyを発行し、"
            "Streamlit CloudのSettings > Secrets に JQUANTS_API_KEY として設定してください。"
        )
    return {"x-api-key": api_key}


def _safe_get(url: str, params: dict = None) -> dict:
    try:
        r = requests.get(url, params=params, headers=_headers(), timeout=30)
    except requests.RequestException:
        raise RuntimeError("ネットワークエラー: J-Quants APIに接続できませんでした")
    if r.status_code == 200:
        return r.json()
    if r.status_code == 400:
        raise RuntimeError("リクエストエラー (400): パラメータに問題があります。証券コードを確認してください。")
    elif r.status_code == 401:
        raise RuntimeError("認証エラー (401): API Keyが無効です。再発行してSecretsを更新してください。")
    elif r.status_code == 403:
        raise RuntimeError("権限エラー (403): このプランではアクセスできないデータです。")
    elif r.status_code == 404:
        raise RuntimeError("データなし (404): 指定された証券コードのデータが見つかりません。")
    elif r.status_code == 429:
        raise RuntimeError("レート制限 (429): しばらく待ってから再実行してください。")
    else:
        raise RuntimeError(f"J-Quants APIエラー (HTTP {r.status_code})")


# ============================================================
# データ取得
# ============================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_daily_prices(code: str, years: int = 5) -> pd.DataFrame:
    end = datetime.now()
    start = end - timedelta(days=years * 365 + 30)
    all_rows = []
    pagination_key = None
    while True:
        params = {"code": code, "from": start.strftime("%Y%m%d"), "to": end.strftime("%Y%m%d")}
        if pagination_key:
            params["pagination_key"] = pagination_key
        data = _safe_get(f"{JQUANTS_BASE}/equities/bars/daily", params=params)
        all_rows.extend(data.get("data", []))
        pagination_key = data.get("pagination_key")
        if not pagination_key:
            break
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_financial_summary(code: str) -> pd.DataFrame:
    data = _safe_get(f"{JQUANTS_BASE}/fins/summary", params={"code": code})
    df = pd.DataFrame(data.get("data", []))
    if not df.empty:
        df["DiscDate"] = pd.to_datetime(df["DiscDate"])
        df = df.sort_values("DiscDate").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_margin(code: str) -> pd.DataFrame:
    data = _safe_get(f"{JQUANTS_BASE}/markets/margin-interest", params={"code": code})
    df = pd.DataFrame(data.get("data", []))
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
    return df


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_listed_info(code: str) -> dict:
    data = _safe_get(f"{JQUANTS_BASE}/equities/master", params={"code": code})
    items = data.get("data", [])
    return items[0] if items else {}


# ============================================================
# 汎用ユーティリティ
# ============================================================
def _f(x) -> Optional[float]:
    try:
        return float(x) if x not in (None, "", "-") else None
    except (ValueError, TypeError):
        return None


# ============================================================
# Phase 1 計算: バリュエーション、成長性、健全性、需給
# ============================================================
def calc_price_metrics(prices: pd.DataFrame) -> dict:
    if prices.empty:
        return {}
    close_col = "C" if "C" in prices.columns else "Close"
    high_col = "H" if "H" in prices.columns else "High"
    if close_col not in prices.columns:
        return {}
    current = prices[close_col].iloc[-1]
    high_52w = prices.tail(52 * 5)[high_col].max() if high_col in prices.columns else None
    return {
        "current_price": round(current, 2),
        "high_52w": round(high_52w, 2) if high_52w else None,
        "high_52w_deviation": round((current / high_52w - 1) * 100, 2) if high_52w else None,
    }


def calc_valuation(prices: pd.DataFrame, summary: pd.DataFrame) -> dict:
    if prices.empty or summary.empty:
        return {}
    latest = summary.iloc[-1]
    eps = _f(latest.get("EPS"))
    bps = _f(latest.get("BPS"))
    sales = _f(latest.get("Sales"))
    shares = _f(latest.get("AvgSh"))
    sps = (sales / shares) if (sales and shares) else None

    close_col = "C" if "C" in prices.columns else "Close"
    if close_col not in prices.columns:
        return {}

    p = prices.copy()
    if eps and eps > 0:
        p["PER"] = p[close_col] / eps
    if bps and bps > 0:
        p["PBR"] = p[close_col] / bps
    if sps and sps > 0:
        p["PSR"] = p[close_col] / sps

    def _pct(col):
        if col not in p.columns:
            return None, None
        s = p[col].dropna()
        if s.empty:
            return None, None
        cur = s.iloc[-1]
        rank = (s <= cur).sum() / len(s) * 100
        return round(cur, 2), round(rank, 1)

    per, per_pct = _pct("PER")
    pbr, pbr_pct = _pct("PBR")
    psr, psr_pct = _pct("PSR")

    return {
        "per": per, "per_percentile": per_pct,
        "pbr": pbr, "pbr_percentile": pbr_pct,
        "psr": psr, "psr_percentile": psr_pct,
        "per_min": round(p["PER"].min(), 2) if "PER" in p.columns else None,
        "per_max": round(p["PER"].max(), 2) if "PER" in p.columns else None,
        "pbr_min": round(p["PBR"].min(), 2) if "PBR" in p.columns else None,
        "pbr_max": round(p["PBR"].max(), 2) if "PBR" in p.columns else None,
        "psr_min": round(p["PSR"].min(), 2) if "PSR" in p.columns else None,
        "psr_max": round(p["PSR"].max(), 2) if "PSR" in p.columns else None,
    }


def calc_growth(summary: pd.DataFrame) -> dict:
    if summary.empty:
        return {}
    annual = summary[summary["CurPerType"] == "FY"].copy() if "CurPerType" in summary.columns else summary.copy()
    if len(annual) < 2:
        annual = summary.copy()

    def _tail(field, n=5):
        if field not in annual.columns:
            return []
        vals = [_f(v) for v in annual[field].tail(n).tolist()]
        return [v for v in vals if v is not None]

    sales = _tail("Sales")
    op_profit = _tail("OP")
    net_income = _tail("NP")
    equity = _tail("Eq")
    total_assets = _tail("TA")
    op_cf = _tail("CFO")
    inv_cf = _tail("CFI")

    sales_cagr = None
    if len(sales) >= 2 and sales[0] > 0:
        n = len(sales) - 1
        sales_cagr = ((sales[-1] / sales[0]) ** (1 / n) - 1) * 100

    op_margins = [op / s * 100 for op, s in zip(op_profit, sales) if s > 0]
    roe = [ni / eq * 100 for ni, eq in zip(net_income, equity) if eq > 0]

    latest_eq_ar = _f(annual.iloc[-1].get("EqAR")) if "EqAR" in annual.columns else None
    if latest_eq_ar and latest_eq_ar < 2:
        equity_ratio = latest_eq_ar * 100
    elif equity and total_assets and total_assets[-1] > 0:
        equity_ratio = equity[-1] / total_assets[-1] * 100
    else:
        equity_ratio = None

    fcf = [o + i for o, i in zip(op_cf, inv_cf)]

    return {
        "sales_cagr_5y": round(sales_cagr, 2) if sales_cagr else None,
        "op_margin_first": round(op_margins[0], 2) if op_margins else None,
        "op_margin_last": round(op_margins[-1], 2) if op_margins else None,
        "roe_first": round(roe[0], 2) if roe else None,
        "roe_last": round(roe[-1], 2) if roe else None,
        "equity_ratio": round(equity_ratio, 2) if equity_ratio else None,
        "fcf_latest_oku": round(fcf[-1] / 1e8, 1) if fcf else None,
        "fcf_positive_streak": all(f > 0 for f in fcf) if fcf else False,
    }


def calc_margin_signal(margin: pd.DataFrame) -> dict:
    if margin.empty:
        return {}
    latest = margin.iloc[-1]
    long_bal = _f(latest.get("LongVol"))
    short_bal = _f(latest.get("ShrtVol"))

    year_ago = margin.tail(52)
    long_pct = None
    if long_bal and not year_ago.empty and "LongVol" in year_ago.columns:
        vals = [_f(v) for v in year_ago["LongVol"].tolist()]
        vals = [v for v in vals if v is not None]
        if vals:
            long_pct = sum(1 for v in vals if v <= long_bal) / len(vals) * 100

    return {
        "long_margin": int(long_bal) if long_bal else None,
        "short_margin": int(short_bal) if short_bal else None,
        "long_margin_percentile": round(long_pct, 1) if long_pct else None,
    }


# ============================================================
# Phase 2 計算: D. 決算の質
# ============================================================
def calc_earnings_quality(summary: pd.DataFrame) -> dict:
    if summary.empty or "CurPerType" not in summary.columns:
        return {}

    result = {}

    latest = summary.iloc[-1]
    cur_per_type = latest.get("CurPerType", "")
    f_sales = _f(latest.get("FSales"))
    f_op = _f(latest.get("FOP"))
    f_np = _f(latest.get("FNP"))
    f_eps = _f(latest.get("FEPS"))
    actual_sales = _f(latest.get("Sales"))
    actual_op = _f(latest.get("OP"))
    actual_np = _f(latest.get("NP"))
    actual_eps = _f(latest.get("EPS"))

    expected_progress = {"1Q": 25, "2Q": 50, "3Q": 75, "FY": 100, "4Q": 100}
    expected = expected_progress.get(cur_per_type, None)

    if actual_sales and f_sales and f_sales > 0:
        result["progress_sales"] = round(actual_sales / f_sales * 100, 1)
    if actual_op and f_op and f_op > 0:
        result["progress_op"] = round(actual_op / f_op * 100, 1)
    if actual_np and f_np and f_np > 0:
        result["progress_np"] = round(actual_np / f_np * 100, 1)

    result["current_quarter"] = cur_per_type
    result["expected_progress"] = expected
    result["forecast_sales"] = f_sales
    result["forecast_op"] = f_op
    result["forecast_np"] = f_np
    result["forecast_eps"] = f_eps

    prog_np = result.get("progress_np")
    if prog_np and expected:
        overachieve = prog_np - expected
        if overachieve >= 10:
            result["progress_verdict"] = "🟢 大幅超過 (上方修正期待)"
        elif overachieve >= 3:
            result["progress_verdict"] = "🟢 順調 (予想通りかやや上)"
        elif overachieve >= -3:
            result["progress_verdict"] = "🟡 概ね計画線上"
        elif overachieve >= -10:
            result["progress_verdict"] = "🟠 やや遅れ (下方修正リスク)"
        else:
            result["progress_verdict"] = "🔴 大幅未達 (下方修正懸念)"
        result["progress_overachieve"] = round(overachieve, 1)

    eps_yoy_list = []
    for qt in ["1Q", "2Q", "3Q", "FY"]:
        qt_rows = summary[summary["CurPerType"] == qt].copy()
        if len(qt_rows) >= 2:
            prev_eps = _f(qt_rows.iloc[-2].get("EPS"))
            curr_eps = _f(qt_rows.iloc[-1].get("EPS"))
            if prev_eps and prev_eps != 0 and curr_eps is not None:
                yoy = (curr_eps / prev_eps - 1) * 100
                eps_yoy_list.append({
                    "quarter": qt,
                    "prev_eps": round(prev_eps, 2),
                    "curr_eps": round(curr_eps, 2),
                    "yoy_pct": round(yoy, 1),
                })

    result["eps_yoy"] = eps_yoy_list

    if len(eps_yoy_list) >= 2:
        recent_yoys = [e["yoy_pct"] for e in eps_yoy_list[-3:]]
        if all(y > 0 for y in recent_yoys):
            if recent_yoys[-1] > recent_yoys[0]:
                result["eps_trend"] = "🟢 EPS成長加速"
            else:
                result["eps_trend"] = "🟡 EPS成長だが減速傾向"
        elif recent_yoys[-1] > 0:
            result["eps_trend"] = "🟢 EPS前年同期比プラス"
        elif recent_yoys[-1] > -10:
            result["eps_trend"] = "🟠 EPS微減"
        else:
            result["eps_trend"] = "🔴 EPS大幅減"

    if "CurFYEn" in summary.columns:
        latest_fy_end = latest.get("CurFYEn")
        if latest_fy_end:
            same_fy = summary[summary["CurFYEn"] == latest_fy_end].copy()
            if len(same_fy) >= 2:
                first_fnp = _f(same_fy.iloc[0].get("FNP"))
                last_fnp = _f(same_fy.iloc[-1].get("FNP"))
                first_fsales = _f(same_fy.iloc[0].get("FSales"))
                last_fsales = _f(same_fy.iloc[-1].get("FSales"))

                revisions = []
                if first_fnp and last_fnp and first_fnp > 0:
                    rev_pct = (last_fnp / first_fnp - 1) * 100
                    revisions.append({"item": "純利益予想", "change_pct": round(rev_pct, 1)})
                if first_fsales and last_fsales and first_fsales > 0:
                    rev_pct = (last_fsales / first_fsales - 1) * 100
                    revisions.append({"item": "売上予想", "change_pct": round(rev_pct, 1)})

                result["revisions"] = revisions

                if revisions:
                    np_rev = next((r for r in revisions if r["item"] == "純利益予想"), None)
                    if np_rev:
                        if np_rev["change_pct"] >= 5:
                            result["revision_verdict"] = "🟢 上方修正済み"
                        elif np_rev["change_pct"] >= 0:
                            result["revision_verdict"] = "🟡 予想据え置き"
                        elif np_rev["change_pct"] >= -10:
                            result["revision_verdict"] = "🟠 小幅下方修正"
                        else:
                            result["revision_verdict"] = "🔴 大幅下方修正"

    return result


# ============================================================
# Rumor Stage 自動判定(AI + Web Search)
# ============================================================
def calc_rumor_stage(company_name: str, code: str, theme: str) -> dict:
    prompt = f"""【今日の日付: {TODAY}】

あなたは投資リサーチャーです。以下の銘柄と投資テーマについて、
「噂の成熟度(Rumor Stage)」を判定してください。

銘柄: {company_name}（証券コード: {code}）
投資テーマ: {theme}

必ずウェブ検索を使って、以下の5つを調査してください:

1. この銘柄+テーマに関する大手メディア(日経、Bloomberg、Reuters)の記事数と内容
2. 証券会社アナリストの推奨状況(目標株価の引き上げはあるか)
3. 直近3ヶ月〜1年の株価上昇率
4. SNS・掲示板(Twitter/X、Yahoo掲示板)での言及量と温度感
5. 機関投資家・大株主の動き(大量保有報告等)

これらを総合して、以下のJSON形式で返してください(他のテキストは含めない):

{{
  "rumor_stage": 1から5の整数,
  "stage_label": "ステージの名前",
  "evidence": "判定の根拠を3〜5文で。具体的な記事名、数字、日付を含める",
  "media_count": "大手メディアの記事数の概算(例: 約3本、約20本以上)",
  "market_sentiment": "市場の温度感を一言で(例: ほぼ無関心、一部で注目、広く認知、過熱気味)",
  "risk_note": "この Rumor Stage で注意すべきこと"
}}

Rumor Stage の定義:
1 = 微かな予兆(ほぼ誰も知らない。大手メディア記事ゼロ。専門家だけが注目)
2 = 芽吹き(専門メディアに1〜3本。株価はほぼ未反応。早期参入のチャンス)
3 = 噂の拡散(日経・Bloombergに記事。株価が3ヶ月で+20%以上。買いの最適ゾーン)
4 = コンセンサス形成(テレビ報道。アナリスト大多数が買い推奨。もう遅い)
5 = 事実確認(決算サプライズや公式発表で確定。売りを検討すべき)

【文体ルール】
- 高校生にも理解できる日本語
- 専門用語は括弧で説明
- 率直な口調
"""

    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "tools": WEB_SEARCH_TOOL,
        "messages": [{"role": "user", "content": prompt}],
    }

    result, error = call_anthropic_api(HEADERS, payload)
    if error:
        return {"error": error}
    return result


# ============================================================
# KPI スコアリング(6カテゴリ + Rumor補正 → 100点満点)
# ============================================================
def calc_kpi_score(result: dict, rumor_stage: int = None) -> dict:
    scores = {}
    details = {}

    # ① バリュエーション
    per_pct = result.get("per_percentile")
    if per_pct is not None:
        if per_pct <= 20:
            scores["valuation"] = 2
            details["valuation"] = f"PER {per_pct}%タイル → 底値圏 💎"
        elif per_pct <= 40:
            scores["valuation"] = 1
            details["valuation"] = f"PER {per_pct}%タイル → 割安 🔵"
        elif per_pct <= 60:
            scores["valuation"] = 0
            details["valuation"] = f"PER {per_pct}%タイル → 中立 🟢"
        elif per_pct <= 80:
            scores["valuation"] = -1
            details["valuation"] = f"PER {per_pct}%タイル → 割高 🟡"
        else:
            scores["valuation"] = -2
            details["valuation"] = f"PER {per_pct}%タイル → 過熱圏 🔴"
    else:
        scores["valuation"] = 0
        details["valuation"] = "データなし"

    # ② 成長性
    cagr = result.get("sales_cagr_5y")
    op_first = result.get("op_margin_first")
    op_last = result.get("op_margin_last")
    margin_improving = (op_last is not None and op_first is not None and op_last > op_first)

    if cagr is not None:
        if cagr >= 15 and margin_improving:
            scores["growth"] = 2
            details["growth"] = f"売上CAGR {cagr}% + 利益率改善 🟢🟢"
        elif cagr >= 5:
            scores["growth"] = 1
            details["growth"] = f"売上CAGR {cagr}% → 堅調 🟢"
        elif cagr >= 0:
            scores["growth"] = 0
            details["growth"] = f"売上CAGR {cagr}% → 横ばい"
        elif not margin_improving and cagr < 0:
            scores["growth"] = -2
            details["growth"] = f"売上CAGR {cagr}% + 利益率悪化 🔴🔴"
        else:
            scores["growth"] = -1
            details["growth"] = f"売上CAGR {cagr}% → 減収 🔴"
    else:
        scores["growth"] = 0
        details["growth"] = "データなし"

    # ③ 健全性
    eq_ratio = result.get("equity_ratio")
    fcf_streak = result.get("fcf_positive_streak", False)

    if eq_ratio is not None:
        if eq_ratio >= 50 and fcf_streak:
            scores["health"] = 2
            details["health"] = f"自己資本比率 {eq_ratio}% + FCF5年連続◯ 🟢🟢"
        elif eq_ratio >= 30:
            scores["health"] = 1
            details["health"] = f"自己資本比率 {eq_ratio}% 🟢"
        elif eq_ratio >= 20:
            scores["health"] = 0
            details["health"] = f"自己資本比率 {eq_ratio}% → 普通"
        else:
            scores["health"] = -1
            details["health"] = f"自己資本比率 {eq_ratio}% → 低い 🟠"
    else:
        scores["health"] = 0
        details["health"] = "データなし"

    # ④ 決算の質
    eq = result.get("earnings_quality", {})
    progress_verdict = eq.get("progress_verdict", "")

    if "大幅超過" in progress_verdict:
        scores["earnings"] = 2
        details["earnings"] = progress_verdict
    elif "順調" in progress_verdict:
        scores["earnings"] = 1
        details["earnings"] = progress_verdict
    elif "計画線上" in progress_verdict:
        scores["earnings"] = 0
        details["earnings"] = progress_verdict
    elif "やや遅れ" in progress_verdict:
        scores["earnings"] = -1
        details["earnings"] = progress_verdict
    elif "大幅未達" in progress_verdict:
        scores["earnings"] = -2
        details["earnings"] = progress_verdict
    else:
        scores["earnings"] = 0
        details["earnings"] = "判定なし"

    # ⑤ EPSトレンド
    eps_trend = eq.get("eps_trend", "")

    if "成長加速" in eps_trend:
        scores["eps"] = 2
        details["eps"] = eps_trend
    elif "前年同期比プラス" in eps_trend or "成長だが" in eps_trend:
        scores["eps"] = 1
        details["eps"] = eps_trend
    elif "微減" in eps_trend:
        scores["eps"] = -1
        details["eps"] = eps_trend
    elif "大幅減" in eps_trend:
        scores["eps"] = -2
        details["eps"] = eps_trend
    else:
        scores["eps"] = 0
        details["eps"] = "判定なし"

    # ⑥ 需給
    long_pct = result.get("long_margin_percentile")

    if long_pct is not None:
        if long_pct <= 20:
            scores["demand"] = 2
            details["demand"] = f"買残 {long_pct}%タイル → 需給好転 💎"
        elif long_pct <= 40:
            scores["demand"] = 1
            details["demand"] = f"買残 {long_pct}%タイル → 軽い 🔵"
        elif long_pct <= 60:
            scores["demand"] = 0
            details["demand"] = f"買残 {long_pct}%タイル → 中立"
        elif long_pct <= 80:
            scores["demand"] = -1
            details["demand"] = f"買残 {long_pct}%タイル → 重い 🟡"
        else:
            scores["demand"] = -2
            details["demand"] = f"買残 {long_pct}%タイル → 過剰 🔴"
    else:
        scores["demand"] = 0
        details["demand"] = "データなし"

    # KPI合計(-12 〜 +12)
    kpi_total = sum(scores.values())

    # 100点満点に変換(KPI -12〜+12 → 0〜100)
    base_score = round((kpi_total + 12) / 24 * 100)

    # Rumor 補正
    rumor_multiplier = 1.0
    rumor_label = ""
    if rumor_stage is not None:
        if rumor_stage == 1:
            rumor_multiplier = 1.3
            rumor_label = "💤 微かな予兆 → 大幅加点"
        elif rumor_stage == 2:
            rumor_multiplier = 1.15
            rumor_label = "🌱 芽吹き → 加点"
        elif rumor_stage == 3:
            rumor_multiplier = 1.0
            rumor_label = "📢 噂の拡散 → 補正なし"
        elif rumor_stage == 4:
            rumor_multiplier = 0.7
            rumor_label = "📰 コンセンサス形成 → 大幅減点"
        elif rumor_stage == 5:
            rumor_multiplier = 0.5
            rumor_label = "✅ 事実確認 → 半減"

    final_score = min(100, max(0, round(base_score * rumor_multiplier)))

    # 5段階判定
    if final_score >= 80:
        verdict = "🟢 買い"
        verdict_color = "success"
    elif final_score >= 60:
        verdict = "🔵 興味あり"
        verdict_color = "info"
    elif final_score >= 40:
        verdict = "⚪ 様子見"
        verdict_color = "warning"
    elif final_score >= 20:
        verdict = "🟠 注意"
        verdict_color = "warning"
    else:
        verdict = "🔴 危険"
        verdict_color = "error"

    return {
        "scores": scores,
        "details": details,
        "kpi_total": kpi_total,
        "base_score": base_score,
        "rumor_stage": rumor_stage,
        "rumor_multiplier": rumor_multiplier,
        "rumor_label": rumor_label,
        "final_score": final_score,
        "verdict": verdict,
        "verdict_color": verdict_color,
    }


# ============================================================
# 統合分析
# ============================================================
def analyze(code: str) -> dict:
    info = fetch_listed_info(code)
    prices = fetch_daily_prices(code)
    summary = fetch_financial_summary(code)
    margin = fetch_margin(code)

    company_name = info.get("CompanyName") or info.get("CompanyNameFull") or info.get("Name") or "-"
    sector = info.get("Sector17CodeName") or info.get("Sector33CodeName") or info.get("SectorName") or "-"
    market = info.get("MarketCodeName") or info.get("Market") or "-"

    result = {
        "code": code,
        "company_name": company_name,
        "sector": sector,
        "market": market,
        **calc_price_metrics(prices),
        **calc_valuation(prices, summary),
        **calc_growth(summary),
        **calc_margin_signal(margin),
        "earnings_quality": calc_earnings_quality(summary),
    }

    return result


# ============================================================
# UI
# ============================================================
def percentile_label(pct):
    if pct is None:
        return "-"
    floor = round(pct / 10, 1)
    if pct >= 80:
        return f"{floor}合目 🔴 過熱圏"
    elif pct >= 60:
        return f"{floor}合目 🟡 割高"
    elif pct >= 40:
        return f"{floor}合目 🟢 中立"
    elif pct >= 20:
        return f"{floor}合目 🔵 割安"
    else:
        return f"{floor}合目 💎 底値圏"


def render_bar(pct):
    if pct is None:
        st.caption("データなし")
        return
    if pct >= 80:
        color = "#E24B4A"
    elif pct >= 60:
        color = "#EF9F27"
    elif pct >= 40:
        color = "#1D9E75"
    elif pct >= 20:
        color = "#378ADD"
    else:
        color = "#7F77DD"
    st.markdown(
        f'<div style="position:relative;height:10px;background:#2a2a3e;border-radius:5px;margin:4px 0;">'
        f'<div style="position:absolute;left:0;top:0;width:{pct}%;height:100%;background:{color};border-radius:5px;"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_score_bar(score, max_score=2):
    normalized = (score + max_score) / (max_score * 2) * 100
    if score >= 2:
        color = "#1D9E75"
    elif score >= 1:
        color = "#378ADD"
    elif score == 0:
        color = "#888888"
    elif score >= -1:
        color = "#EF9F27"
    else:
        color = "#E24B4A"
    st.markdown(
        f'<div style="position:relative;height:8px;background:#2a2a3e;border-radius:4px;margin:2px 0;">'
        f'<div style="position:absolute;left:0;top:0;width:{normalized}%;height:100%;background:{color};border-radius:4px;"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_big_score(score):
    if score >= 80:
        color = "#1D9E75"
    elif score >= 60:
        color = "#378ADD"
    elif score >= 40:
        color = "#888888"
    elif score >= 20:
        color = "#EF9F27"
    else:
        color = "#E24B4A"
    st.markdown(
        f'<div style="text-align:center;padding:20px;">'
        f'<div style="font-size:72px;font-weight:bold;color:{color};">{score}</div>'
        f'<div style="font-size:16px;color:#888;">/ 100点</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# --- 入力 ---
col_in1, col_in2, col_in3 = st.columns([1, 2, 1])
with col_in1:
    code = st.text_input("証券コード", value="7011", placeholder="例: 7011", max_chars=5)
with col_in2:
    theme = st.text_input("投資テーマ", value="", placeholder="例: AI向け半導体検査装置の需要拡大")
with col_in3:
    st.write("")
    analyze_btn = st.button("🔍 分析する", type="primary", use_container_width=True)

if analyze_btn and code.strip():
    with st.spinner(f"[{code}] J-Quantsからデータ取得中..."):
        try:
            st.session_state.analysis_result = analyze(code.strip())
            st.session_state.analysis_code = code.strip()
            st.session_state.rumor_result = None
        except RuntimeError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"予期せぬエラー: {type(e).__name__}")

# --- 結果表示 ---
r = st.session_state.analysis_result
if r:
    st.divider()

    st.subheader(f"{r.get('company_name')} ({r.get('code')})")
    st.caption(f"{r.get('sector')} / {r.get('market')}")

    # ============================================================
    # Rumor Stage 判定(テーマが入力されている場合)
    # ============================================================
    rumor_stage_value = None
    rumor_data = st.session_state.rumor_result

    if theme.strip() and not rumor_data:
        if st.button("🔍 Rumor Stage を判定する（AI + Web検索）", type="secondary"):
            with st.spinner("AIがウェブ検索でRumor Stageを判定中...（最大3分かかります）"):
                rumor_data = calc_rumor_stage(r.get("company_name", ""), code.strip(), theme.strip())
                st.session_state.rumor_result = rumor_data
                st.rerun()

    if rumor_data and "error" not in rumor_data:
        rumor_stage_value = rumor_data.get("rumor_stage")
        stage_label = rumor_data.get("stage_label", "")
        evidence = rumor_data.get("evidence", "")
        media_count = rumor_data.get("media_count", "")
        market_sentiment = rumor_data.get("market_sentiment", "")
        risk_note = rumor_data.get("risk_note", "")

        st.markdown("### 📡 Rumor Stage（噂の成熟度）")

        # ステージを大きく表示
        stage_colors = {1: "#7F77DD", 2: "#1D9E75", 3: "#378ADD", 4: "#EF9F27", 5: "#E24B4A"}
        stage_names = {1: "💤 微かな予兆", 2: "🌱 芽吹き", 3: "📢 噂の拡散", 4: "📰 コンセンサス形成", 5: "✅ 事実確認"}
        sc = stage_colors.get(rumor_stage_value, "#888")
        sn = stage_names.get(rumor_stage_value, "不明")

        st.markdown(
            f'<div style="text-align:center;padding:15px;background:{sc}22;border:2px solid {sc};border-radius:12px;margin:10px 0;">'
            f'<div style="font-size:36px;font-weight:bold;color:{sc};">Stage {rumor_stage_value}</div>'
            f'<div style="font-size:18px;color:{sc};">{sn}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # 5段階のプログレスバー
        bar_html = '<div style="display:flex;gap:4px;margin:10px 0;">'
        for i in range(1, 6):
            active = i <= rumor_stage_value
            c = sc if active else "#2a2a3e"
            bar_html += f'<div style="flex:1;height:8px;background:{c};border-radius:4px;"></div>'
        bar_html += '</div>'
        st.markdown(bar_html, unsafe_allow_html=True)

        with st.expander("📋 判定の詳細"):
            st.write(f"**根拠:** {evidence}")
            st.write(f"**メディア記事数:** {media_count}")
            st.write(f"**市場の温度感:** {market_sentiment}")
            st.write(f"**⚠️ 注意:** {risk_note}")

        st.divider()
    elif rumor_data and "error" in rumor_data:
        st.error(f"Rumor判定エラー: {rumor_data['error']}")

    # ============================================================
    # 🎯 総合判定(KPIスコア + Rumor補正 → 100点)
    # ============================================================
    kpi = calc_kpi_score(r, rumor_stage=rumor_stage_value)

    st.markdown("### 🎯 総合判定")

    # 大きなスコア表示
    col_score, col_verdict = st.columns([1, 2])
    with col_score:
        render_big_score(kpi["final_score"])
    with col_verdict:
        verdict = kpi["verdict"]
        if kpi["verdict_color"] == "success":
            st.success(f"**{verdict}**")
        elif kpi["verdict_color"] == "error":
            st.error(f"**{verdict}**")
        else:
            st.warning(f"**{verdict}**")

        st.caption(f"ファンダ基礎点: {kpi['base_score']}点")
        if kpi["rumor_stage"] is not None:
            st.caption(f"Rumor補正: ×{kpi['rumor_multiplier']} ({kpi['rumor_label']})")
        else:
            st.caption("Rumor補正: なし（投資テーマを入力してRumor判定を実行すると精度が上がります）")

    # 6カテゴリの内訳
    scores = kpi.get("scores", {})
    details = kpi.get("details", {})

    categories = [
        ("valuation", "① バリュエーション"),
        ("growth", "② 成長性"),
        ("health", "③ 健全性"),
        ("earnings", "④ 決算の質"),
        ("eps", "⑤ EPSトレンド"),
        ("demand", "⑥ 需給"),
    ]

    col_left, col_right = st.columns(2)
    for i, (key, label) in enumerate(categories):
        s = scores.get(key, 0)
        d = details.get(key, "")
        sign = "+" if s > 0 else ""
        with col_left if i < 3 else col_right:
            st.markdown(f"**{label}**: {sign}{s}")
            render_score_bar(s)
            st.caption(d)

    st.divider()

    # 主要指標 4カラム
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        cp = r.get("current_price")
        st.metric("株価", f"¥{cp:,}" if cp else "-")
    with c2:
        dev = r.get("high_52w_deviation")
        st.metric("52週高値からの乖離", f"{dev}%" if dev is not None else "-",
                  delta=f"高値 ¥{r.get('high_52w', '-'):,}" if r.get('high_52w') else None, delta_color="off")
    with c3:
        st.metric("PER", f"{r.get('per', '-')}倍" if r.get('per') else "-")
    with c4:
        st.metric("PBR", f"{r.get('pbr', '-')}倍" if r.get('pbr') else "-")

    st.divider()

    # ① 何合目か
    st.markdown("### ① 何合目か (5年レンジ内の位置)")
    for key, label in [("per", "PER"), ("pbr", "PBR"), ("psr", "PSR")]:
        cur = r.get(key)
        pct = r.get(f"{key}_percentile")
        vmin = r.get(f"{key}_min")
        vmax = r.get(f"{key}_max")
        col_l, col_m, col_r = st.columns([1, 4, 2])
        with col_l:
            st.write(f"**{label}**")
        with col_m:
            render_bar(pct)
            if vmin is not None and vmax is not None:
                st.caption(f"5年レンジ: {vmin} 〜 {vmax} / 現在: {cur}")
        with col_r:
            st.caption(percentile_label(pct))

    st.divider()

    # ② 構造的需要成長 | ③ 健全性
    col_g, col_h = st.columns(2)
    with col_g:
        st.markdown("### ② 構造的需要成長")
        st.metric("売上CAGR 5年", f"{r.get('sales_cagr_5y', '-')}%" if r.get('sales_cagr_5y') else "-")
        opf, opl = r.get("op_margin_first"), r.get("op_margin_last")
        if opf is not None and opl is not None:
            delta = round(opl - opf, 2)
            st.metric("営業利益率", f"{opl}%", delta=f"5年で{delta:+}pt")
        roe_f, roe_l = r.get("roe_first"), r.get("roe_last")
        if roe_f is not None and roe_l is not None:
            delta = round(roe_l - roe_f, 2)
            st.metric("ROE", f"{roe_l}%", delta=f"5年で{delta:+}pt")

    with col_h:
        st.markdown("### ③ 1-3年持てる健全性")
        st.metric("自己資本比率", f"{r.get('equity_ratio', '-')}%" if r.get('equity_ratio') else "-")
        fcf = r.get("fcf_latest_oku")
        if fcf is not None:
            st.metric("直近フリーCF", f"{fcf}億円",
                      delta="5年連続プラス ◯" if r.get("fcf_positive_streak") else "5年連続プラスではない ×",
                      delta_color="normal" if r.get("fcf_positive_streak") else "inverse")

    st.divider()

    # ④ セグメント情報
    st.markdown("### ④ セグメント別売上構成")
    st.caption("J-Quantsにセグメントデータはないため、決算説明資料を見ながら手入力。")

    seg_key = f"seg_{r.get('code')}"
    num_segments = st.number_input("セグメント数", min_value=1, max_value=8, value=3, key=f"{seg_key}_n")

    seg_data = []
    cols_seg = st.columns(min(num_segments, 4))
    for i in range(num_segments):
        with cols_seg[i % 4]:
            name = st.text_input(f"セグメント{i+1}名", key=f"{seg_key}_name_{i}", placeholder="例: エナジー")
            sales_pct = st.number_input(f"売上構成比 (%)", min_value=0, max_value=100, value=0, key=f"{seg_key}_pct_{i}")
            growth = st.text_input(f"前年比成長率", key=f"{seg_key}_growth_{i}", placeholder="例: +12%")
            if name:
                seg_data.append({"name": name, "pct": sales_pct, "growth": growth})

    if seg_data and any(s["pct"] > 0 for s in seg_data):
        colors = ["#378ADD", "#1D9E75", "#EF9F27", "#7F77DD", "#E24B4A", "#D4537E", "#5DCAA5", "#F0997B"]
        bar_html = '<div style="display:flex;width:100%;height:32px;border-radius:8px;overflow:hidden;margin:8px 0;">'
        for i, seg in enumerate(seg_data):
            if seg["pct"] > 0:
                c = colors[i % len(colors)]
                bar_html += (
                    f'<div style="width:{seg["pct"]}%;background:{c};display:flex;align-items:center;'
                    f'justify-content:center;font-size:12px;color:white;font-weight:500;">{seg["pct"]}%</div>'
                )
        bar_html += '</div>'
        st.markdown(bar_html, unsafe_allow_html=True)

    st.divider()

    # ⑤ 決算の質
    eq = r.get("earnings_quality", {})
    st.markdown("### ⑤ 決算の質")

    if eq:
        qt = eq.get("current_quarter", "-")
        st.markdown(f"**直近開示: {qt}**")

        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            prog_s = eq.get("progress_sales")
            exp = eq.get("expected_progress")
            if prog_s is not None:
                st.metric("売上進捗率", f"{prog_s}%",
                          delta=f"期待値 {exp}% との差: {round(prog_s - exp, 1):+}pt" if exp else None,
                          delta_color="normal" if prog_s and exp and prog_s >= exp else "inverse")
        with col_p2:
            prog_o = eq.get("progress_op")
            if prog_o is not None:
                st.metric("営業利益進捗率", f"{prog_o}%",
                          delta=f"期待値比: {round(prog_o - exp, 1):+}pt" if exp else None,
                          delta_color="normal" if prog_o and exp and prog_o >= exp else "inverse")
        with col_p3:
            prog_n = eq.get("progress_np")
            if prog_n is not None:
                st.metric("純利益進捗率", f"{prog_n}%",
                          delta=f"期待値比: {round(prog_n - exp, 1):+}pt" if exp else None,
                          delta_color="normal" if prog_n and exp and prog_n >= exp else "inverse")

        pv = eq.get("progress_verdict")
        if pv:
            st.markdown(f"**進捗判定: {pv}**")

        eps_yoy = eq.get("eps_yoy", [])
        if eps_yoy:
            st.markdown("**四半期EPS 前年同期比**")
            cols_eps = st.columns(len(eps_yoy))
            for i, e in enumerate(eps_yoy):
                with cols_eps[i]:
                    color = "normal" if e["yoy_pct"] > 0 else "inverse"
                    st.metric(f"{e['quarter']}", f"¥{e['curr_eps']}", delta=f"前年比 {e['yoy_pct']:+}%", delta_color=color)

        et = eq.get("eps_trend")
        if et:
            st.markdown(f"**EPSトレンド: {et}**")

        revisions = eq.get("revisions", [])
        if revisions:
            st.markdown("**今期の会社予想修正**")
            cols_rev = st.columns(len(revisions))
            for i, rev in enumerate(revisions):
                with cols_rev[i]:
                    color = "normal" if rev["change_pct"] >= 0 else "inverse"
                    st.metric(rev["item"], f"{rev['change_pct']:+}%", delta_color=color)

        rv = eq.get("revision_verdict")
        if rv:
            st.markdown(f"**修正判定: {rv}**")
    else:
        st.caption("決算データが不足しています")

    st.divider()

    # ⑥ 逆張りシグナル
    st.markdown("### ⑥ 逆張りタイミング")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        lm = r.get("long_margin")
        lmp = r.get("long_margin_percentile")
        if lm is not None:
            st.metric("信用買残", f"{lm:,}株", delta=f"過去1年の {lmp}%タイル" if lmp else None, delta_color="off")
            if lmp is not None:
                if lmp >= 80:
                    st.caption("🔴 買残過多: 戻り売り圧力が強い")
                elif lmp <= 20:
                    st.caption("💎 買残枯れ: 需給好転の可能性")
                else:
                    st.caption("🟢 中立水準")
    with col_s2:
        sm = r.get("short_margin")
        if sm is not None:
            st.metric("信用売残", f"{sm:,}株")

    st.divider()

    # 判断メモ
    st.markdown("### 🧠 あなたの判断メモ")
    st.caption("自動化すべきでない部分。ここを埋めることで銘柄への理解が深まる。")

    memo_key = f"memo_{r.get('code')}"
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.text_input("このテーマの何合目か", key=f"{memo_key}_theme",
                      placeholder="例: 防衛テーマは7-8合目、需要継続するが織り込み進行")
        st.text_input("次のボトルネック仮説", key=f"{memo_key}_bottleneck",
                      placeholder="例: 生産能力、熟練工不足、半導体")
    with col_m2:
        st.text_input("想定保有期間", key=f"{memo_key}_horizon", placeholder="例: 1-2年")
        st.text_input("エグジットシナリオ", key=f"{memo_key}_exit", placeholder="例: PER25倍超で段階利確")

else:
    st.info("証券コードを入力して「分析する」を押してください。")
    st.caption("例: 7011 (三菱重工), 8001 (伊藤忠商事), 6758 (ソニーグループ)")