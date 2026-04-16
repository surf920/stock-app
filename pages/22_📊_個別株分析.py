from core.auth import require_auth
require_auth()

"""
機能: 個別株分析 (Phase 1)
証券コードを入力すると、J-Quants APIから財務・株価データを取得し、
投資判断に必要な10項目を1画面に表示する。

Hi の投資手法に準拠した設計:
- 構造的需要成長 × 逆張りタイミング × 1-3年保有
- 「何合目か」を視覚化 (PER/PBR/PSRの5年レンジ内位置)
- 自動化不可能な判断 (テーマ、ボトルネック、エグジット) はメモ欄で人間が入力
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional

# === J-Quants API 設定 ===
JQUANTS_BASE = "https://api.jquants.com/v1"

# === ページ設定 ===
st.set_page_config(page_title="個別株分析", page_icon="📊", layout="wide")
st.title("📊 個別株分析")
st.caption("証券コードを入力 → J-Quantsから財務・株価を取得 → 判断に必要な10項目を一画面で")

# === セッション状態 ===
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "analysis_code" not in st.session_state:
    st.session_state.analysis_code = None


# ============================================================
# J-Quants 認証
# ============================================================
@st.cache_data(ttl=20 * 3600, show_spinner=False)
def get_id_token() -> str:
    """IDトークン取得 (20時間キャッシュ)
    J-QuantsのAPI Keysページで発行したリフレッシュトークンを使用。
    リフレッシュトークンは7日間有効。切れたら再発行してSecretsを更新。
    """
    refresh_token = st.secrets.get("JQUANTS_REFRESH_TOKEN", "")
    if not refresh_token:
        raise RuntimeError("JQUANTS_REFRESH_TOKEN を Streamlit Secrets に設定してください")

    r = requests.post(
        f"{JQUANTS_BASE}/token/auth_refresh?refreshtoken={refresh_token}",
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["idToken"]


def _headers() -> dict:
    return {"Authorization": f"Bearer {get_id_token()}"}


# ============================================================
# データ取得 (銘柄ごとに1時間キャッシュ)
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
        r = requests.get(f"{JQUANTS_BASE}/prices/daily_quotes", params=params, headers=_headers(), timeout=30)
        r.raise_for_status()
        data = r.json()
        all_rows.extend(data.get("daily_quotes", []))
        pagination_key = data.get("pagination_key")
        if not pagination_key:
            break
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_statements(code: str) -> pd.DataFrame:
    r = requests.get(f"{JQUANTS_BASE}/fins/statements", params={"code": code}, headers=_headers(), timeout=30)
    r.raise_for_status()
    df = pd.DataFrame(r.json().get("statements", []))
    if not df.empty:
        df["DisclosedDate"] = pd.to_datetime(df["DisclosedDate"])
        df = df.sort_values("DisclosedDate").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_margin(code: str) -> pd.DataFrame:
    r = requests.get(
        f"{JQUANTS_BASE}/markets/weekly_margin_interest",
        params={"code": code},
        headers=_headers(),
        timeout=30,
    )
    r.raise_for_status()
    df = pd.DataFrame(r.json().get("weekly_margin_interest", []))
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
    return df


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_listed_info(code: str) -> dict:
    r = requests.get(f"{JQUANTS_BASE}/listed/info", params={"code": code}, headers=_headers(), timeout=30)
    r.raise_for_status()
    info = r.json().get("info", [])
    return info[0] if info else {}


# ============================================================
# 計算 (10項目)
# ============================================================
def _f(x) -> Optional[float]:
    try:
        return float(x) if x not in (None, "", "-") else None
    except (ValueError, TypeError):
        return None


def calc_price_metrics(prices: pd.DataFrame) -> dict:
    if prices.empty:
        return {}
    current = prices["Close"].iloc[-1]
    high_52w = prices.tail(52 * 5)["High"].max()
    return {
        "current_price": round(current, 2),
        "high_52w": round(high_52w, 2),
        "high_52w_deviation": round((current / high_52w - 1) * 100, 2),
    }


def calc_valuation(prices: pd.DataFrame, statements: pd.DataFrame) -> dict:
    """PER/PBR/PSRの5年レンジ内位置 (簡易版: 直近決算のEPS/BPS/SPSで近似)"""
    if prices.empty or statements.empty:
        return {}

    latest = statements.iloc[-1]
    eps = _f(latest.get("EarningsPerShare"))
    bps = _f(latest.get("BookValuePerShare"))
    net_sales = _f(latest.get("NetSales"))
    shares = _f(latest.get("AverageNumberOfShares"))
    sps = (net_sales / shares) if (net_sales and shares) else None

    p = prices.copy()
    if eps and eps > 0:
        p["PER"] = p["Close"] / eps
    if bps and bps > 0:
        p["PBR"] = p["Close"] / bps
    if sps and sps > 0:
        p["PSR"] = p["Close"] / sps

    def _pct(col: str):
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


def calc_growth(statements: pd.DataFrame) -> dict:
    if statements.empty:
        return {}

    annual = statements[statements["TypeOfCurrentPeriod"] == "FY"].copy() if "TypeOfCurrentPeriod" in statements.columns else statements.copy()
    if len(annual) < 2:
        annual = statements.copy()

    def _tail(field: str, n: int = 5):
        if field not in annual.columns:
            return []
        vals = [_f(v) for v in annual[field].tail(n).tolist()]
        return [v for v in vals if v is not None]

    sales = _tail("NetSales")
    op_profit = _tail("OperatingProfit")
    net_income = _tail("Profit")
    equity = _tail("Equity")
    total_assets = _tail("TotalAssets")
    op_cf = _tail("CashFlowsFromOperatingActivities")
    inv_cf = _tail("CashFlowsFromInvestingActivities")

    sales_cagr = None
    if len(sales) >= 2 and sales[0] > 0:
        n = len(sales) - 1
        sales_cagr = ((sales[-1] / sales[0]) ** (1 / n) - 1) * 100

    op_margins = [op / s * 100 for op, s in zip(op_profit, sales) if s > 0]
    roe = [ni / eq * 100 for ni, eq in zip(net_income, equity) if eq > 0]

    equity_ratio = None
    if equity and total_assets and total_assets[-1] > 0:
        equity_ratio = equity[-1] / total_assets[-1] * 100

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
    long_bal = _f(latest.get("LongMarginTradeVolume"))
    short_bal = _f(latest.get("ShortMarginTradeVolume"))

    year_ago = margin.tail(52)
    long_pct = None
    if long_bal and not year_ago.empty:
        vals = [_f(v) for v in year_ago["LongMarginTradeVolume"].tolist()]
        vals = [v for v in vals if v is not None]
        if vals:
            long_pct = sum(1 for v in vals if v <= long_bal) / len(vals) * 100

    return {
        "long_margin": int(long_bal) if long_bal else None,
        "short_margin": int(short_bal) if short_bal else None,
        "long_margin_percentile": round(long_pct, 1) if long_pct else None,
    }


def analyze(code: str) -> dict:
    info = fetch_listed_info(code)
    prices = fetch_daily_prices(code)
    statements = fetch_statements(code)
    margin = fetch_margin(code)

    return {
        "code": code,
        "company_name": info.get("CompanyName", "-"),
        "sector": info.get("Sector17CodeName", "-"),
        "market": info.get("MarketCodeName", "-"),
        **calc_price_metrics(prices),
        **calc_valuation(prices, statements),
        **calc_growth(statements),
        **calc_margin_signal(margin),
    }


# ============================================================
# UI
# ============================================================
def percentile_label(pct: Optional[float]) -> str:
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


def render_bar(pct: Optional[float]):
    """パーセンタイル表示用の色付きバー"""
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
        f"""
        <div style="position: relative; height: 10px; background: #2a2a3e; border-radius: 5px; margin: 4px 0;">
            <div style="position: absolute; left: 0; top: 0; width: {pct}%; height: 100%; background: {color}; border-radius: 5px;"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --- 入力 ---
col_in1, col_in2, _ = st.columns([1, 1, 4])
with col_in1:
    code = st.text_input("証券コード", value="7011", placeholder="例: 7011", max_chars=5)
with col_in2:
    st.write("")
    analyze_btn = st.button("🔍 分析する", type="primary", use_container_width=True)

if analyze_btn and code.strip():
    with st.spinner(f"[{code}] J-Quantsからデータ取得中..."):
        try:
            st.session_state.analysis_result = analyze(code.strip())
            st.session_state.analysis_code = code.strip()
        except requests.HTTPError as e:
            st.error(f"J-Quants APIエラー: {e}. コードが正しいか、プランが対応しているか確認してください。")
        except RuntimeError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"予期せぬエラー: {e}")

# --- 結果表示 ---
r = st.session_state.analysis_result
if r:
    st.divider()

    # 企業情報ヘッダー
    st.subheader(f"{r.get('company_name')} ({r.get('code')})")
    st.caption(f"{r.get('sector')} / {r.get('market')}")

    # 主要指標 4カラム
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("株価", f"¥{r.get('current_price', '-'):,}" if r.get('current_price') else "-")
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

    # ⑤ 逆張りシグナル
    st.markdown("### ⑤ 逆張りタイミング")
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

    # 未取得項目の注記
    with st.expander("📝 未取得項目 (手動入力が必要)"):
        st.markdown("""
        以下の2項目は J-Quants では取得できないため、自分で確認:
        - **④ セグメント別売上構成**: 有価証券報告書 or 決算説明資料を参照
        - **⑩ アナリスト予想変化**: 代替として、会社予想の修正履歴を決算短信で確認
        """)

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

    # アクション
    st.write("")
    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b1:
        if st.button("✅ 買い判断", use_container_width=True):
            st.success("買い判断を記録 (将来: 判断ログに保存)")
    with col_b2:
        if st.button("⏸ 見送り", use_container_width=True):
            st.info("見送りを記録")
    with col_b3:
        if st.button("👁 監視リスト追加", use_container_width=True):
            st.info("監視リストに追加 (将来: ウォッチリスト機能)")

else:
    st.info("証券コードを入力して「分析する」を押してください。")
    st.caption("例: 7011 (三菱重工), 8001 (伊藤忠商事), 6758 (ソニーグループ)")
