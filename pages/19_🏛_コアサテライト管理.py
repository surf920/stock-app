from core.auth import require_auth
require_auth()

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from scipy.optimize import minimize
import json
import io
import base64
import requests

st.set_page_config(page_title="コア・サテライト管理", page_icon="🏛", layout="wide")

# ===== 定数定義 =====
CORE_ETFS = {
    "VTI": {"name": "米国株式", "class": "equity", "target_rp": 0.20},
    "VEA": {"name": "先進国株式", "class": "equity", "target_rp": 0.10},
    "VWO": {"name": "新興国株式", "class": "equity", "target_rp": 0.05},
    "AGG": {"name": "米国債券", "class": "bond", "target_rp": 0.25},
    "TIP": {"name": "インフレ連動債", "class": "bond_tips", "target_rp": 0.15},
    "IAU": {"name": "金", "class": "commodity", "target_rp": 0.25},
}

EQUAL_WEIGHT = 1.0 / len(CORE_ETFS)  # ~16.7%

CORE_RATIO = 0.80  # コア比率
SATELLITE_A_RATIO = 0.15  # サテライトA比率
SATELLITE_B_RATIO = 0.05  # サテライトB比率

REBALANCE_BAND = 0.05  # 5%乖離でリバランス

DATE_CONTEXT = f"現在の日付は{datetime.now().strftime('%Y年%m月')}です。"


# ===== ヘルパー関数 =====
@st.cache_data(ttl=3600)
def fetch_prices(tickers, period="1y"):
    """yfinanceから価格データを取得"""
    data = yf.download(tickers, period=period, auto_adjust=True, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        prices = data["Close"]
    else:
        prices = data
    return prices


@st.cache_data(ttl=3600)
def fetch_current_prices(tickers):
    """現在価格を取得"""
    result = {}
    for t in tickers:
        try:
            info = yf.Ticker(t)
            hist = info.history(period="1d")
            if not hist.empty:
                result[t] = hist["Close"].iloc[-1]
            else:
                result[t] = None
        except Exception:
            result[t] = None
    return result


def calculate_risk_parity_weights(returns_df):
    """リスクパリティウェイトを計算"""
    cov_matrix = returns_df.cov() * 252  # 年率化
    n = len(returns_df.columns)

    def risk_contribution(w, cov):
        port_var = w @ cov @ w
        port_std = np.sqrt(port_var)
        mrc = (cov @ w) / port_std
        trc = w * mrc
        return trc

    def objective(w, cov):
        trc = risk_contribution(w, cov)
        target_rc = np.ones(n) / n
        return np.sum((trc / trc.sum() - target_rc) ** 2)

    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1}
    bounds = [(0.02, 0.50) for _ in range(n)]  # Asset constraints: 2%-50%
    x0 = np.ones(n) / n

    result = minimize(
        objective,
        x0,
        args=(cov_matrix.values,),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000},
    )

    if result.success:
        weights = result.x
        weights = weights / weights.sum()  # 正規化
        return dict(zip(returns_df.columns, weights))
    else:
        # フォールバック: 逆ボラティリティ加重
        vols = returns_df.std() * np.sqrt(252)
        inv_vol = 1 / vols
        weights = inv_vol / inv_vol.sum()
        return dict(zip(returns_df.columns, weights))


def calculate_risk_contributions(weights_dict, returns_df):
    """各資産のリスク寄与度を計算"""
    tickers = list(weights_dict.keys())
    w = np.array([weights_dict[t] for t in tickers])
    cov = returns_df[tickers].cov().values * 252

    port_var = w @ cov @ w
    port_std = np.sqrt(port_var)
    mrc = (cov @ w) / port_std
    trc = w * mrc
    trc_pct = trc / trc.sum()

    return dict(zip(tickers, trc_pct)), port_std


def parse_ib_csv(uploaded_file):
    """IB Flex CSVを解析してポジションデータを取得"""
    try:
        content = uploaded_file.read().decode("utf-8")
        lines = content.strip().split("\n")

        header_idx = None
        for i, line in enumerate(lines):
            if "ClientAccountID" in line and "Symbol" in line:
                header_idx = i
                break

        if header_idx is None:
            st.error("IB Flex CSVのヘッダーが見つかりません")
            return None

        csv_data = "\n".join(lines[header_idx:])
        df = pd.read_csv(io.StringIO(csv_data))

        required = ["Symbol", "Quantity", "MarkPrice", "PositionValue"]
        if not all(col in df.columns for col in required):
            missing = [c for c in required if c not in df.columns]
            st.error(f"必要なカラムが不足: {missing}")
            return None

        df = df[df["Quantity"] != 0].copy()
        df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
        df["MarkPrice"] = pd.to_numeric(df["MarkPrice"], errors="coerce")
        df["PositionValue"] = pd.to_numeric(df["PositionValue"], errors="coerce")

        # 通貨変換（JPY→USD）
        if "CurrencyPrimary" in df.columns:
            jpy_mask = df["CurrencyPrimary"] == "JPY"
            if jpy_mask.any():
                try:
                    fx = yf.Ticker("JPY=X")
                    fx_hist = fx.history(period="1d")
                    if not fx_hist.empty:
                        usd_jpy = fx_hist["Close"].iloc[-1]
                    else:
                        usd_jpy = 150.0
                except Exception:
                    usd_jpy = 150.0
                df.loc[jpy_mask, "PositionValue"] = (
                    df.loc[jpy_mask, "PositionValue"] / usd_jpy
                )

        return df[["Symbol", "Quantity", "MarkPrice", "PositionValue"]].dropna()

    except Exception as e:
        st.error(f"CSV解析エラー: {e}")
        return None


def call_claude_api(prompt, system_prompt=None):
    """Claude APIを呼び出し"""
    try:
        from api_helper import call_api
        return call_api(prompt, system_prompt=system_prompt)
    except ImportError:
        # api_helper がない場合のフォールバック
        try:
            import requests
            api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                return "API キーが設定されていません。"

            headers = {
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            body = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                body["system"] = system_prompt

            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]
            return text.strip("```json").strip("```").strip()
        except Exception as e:
            return f"API呼び出しエラー: {e}"


# ===== リバランス提案 & 履歴 =====
def get_next_rebalance_date(today=None):
    """次の四半期リバランス日（1/4/7/10月の第1営業日）を返す"""
    if today is None:
        today = datetime.now().date()
    year = today.year
    quarter_months = [1, 4, 7, 10]
    for m in quarter_months:
        candidate = datetime(year, m, 1).date()
        if candidate > today:
            return candidate
    return datetime(year + 1, 1, 1).date()


def generate_order_list(rebalance_data, current_prices):
    """リバランスデータから発注リストをテキスト形式で生成"""
    sell_orders = []
    buy_orders = []

    for row in rebalance_data:
        ticker = row["ticker"]
        shares = row["trade_shares"]
        if shares == 0:
            continue
        px = current_prices.get(ticker, 0)
        total = abs(shares * px)
        if shares < 0:
            sell_orders.append(
                f"SELL  {ticker:5s}  {abs(shares):5d} shares  @ ~${px:.2f}  (≈${total:,.0f})"
            )
        else:
            buy_orders.append(
                f"BUY   {ticker:5s}  {shares:5d} shares  @ ~${px:.2f}  (≈${total:,.0f})"
            )

    lines = [f"# リバランス発注リスト  {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    lines.append("")
    if sell_orders:
        lines.append("## 売却注文")
        lines.extend(sell_orders)
        lines.append("")
    if buy_orders:
        lines.append("## 購入注文")
        lines.extend(buy_orders)
        lines.append("")
    if not sell_orders and not buy_orders:
        lines.append("# 取引不要（全資産が目標±5%以内）")

    return "\n".join(lines)


def get_github_config():
    """GitHub設定を取得"""
    try:
        token = st.secrets.get("GITHUB_TOKEN", "")
        repo = st.secrets.get("GITHUB_REPO", "surf920/stock-app")
        return token, repo
    except Exception:
        return "", "surf920/stock-app"


def load_rebalance_history():
    """GitHubからリバランス履歴を取得"""
    token, repo = get_github_config()
    if not token:
        return []

    url = f"https://api.github.com/repos/{repo}/contents/data/rebalance_history.json"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content)
    except Exception as e:
        st.warning(f"履歴の読み込みに失敗: {e}")
        return []


def save_rebalance_snapshot(snapshot):
    """GitHubにリバランススナップショットを保存"""
    token, repo = get_github_config()
    if not token:
        return False, "GITHUB_TOKENが設定されていません"

    url = f"https://api.github.com/repos/{repo}/contents/data/rebalance_history.json"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # 既存履歴を取得
    history = []
    sha = None
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            sha = data["sha"]
            content = base64.b64decode(data["content"]).decode("utf-8")
            history = json.loads(content)
    except Exception:
        pass

    # 新スナップショットを追加
    history.append(snapshot)

    # 最新50件のみ保持
    history = history[-50:]

    new_content = json.dumps(history, indent=2, ensure_ascii=False)
    encoded = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")

    payload = {
        "message": f"Rebalance snapshot {snapshot.get('date', '')}",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    try:
        resp = requests.put(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        return True, "保存成功"
    except Exception as e:
        return False, f"保存失敗: {e}"


# ===== メイン UI =====
st.title("🏛 コア・サテライト ポートフォリオ管理")
st.caption("リスクパリティ・コア + アクティブ・サテライト")

# タブ構成
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 コア配分分析", "⚖️ リバランス計算", "🎯 サテライト状況", "🤖 AI診断"]
)

# ===== Tab 1: コア配分分析 =====
with tab1:
    st.subheader("リスクパリティ目標 vs 現在配分")

    col_mode, col_period = st.columns(2)
    with col_mode:
        mode = st.radio(
            "配分方式",
            ["リスクパリティ（推奨）", "均等配分（シンプル）"],
            horizontal=True,
        )
    with col_period:
        lookback = st.selectbox(
            "ボラティリティ計算期間",
            ["6ヶ月", "1年", "2年"],
            index=1,
        )

    period_map = {"6ヶ月": "6mo", "1年": "1y", "2年": "2y"}

    with st.spinner("市場データを取得中..."):
        tickers = list(CORE_ETFS.keys())
        prices = fetch_prices(tickers, period=period_map[lookback])
        current_px = fetch_current_prices(tickers)

    if prices is not None and not prices.empty:
        returns = prices.pct_change().dropna()

        if mode == "リスクパリティ（推奨）":
            computed_weights = calculate_risk_parity_weights(returns)
            target_label = "リスクパリティ（算出）"
        else:
            computed_weights = {t: EQUAL_WEIGHT for t in tickers}
            target_label = "均等配分"

        # 固定目標との比較も表示
        manual_weights = {t: info["target_rp"] for t, info in CORE_ETFS.items()}

        # リスク寄与度計算
        rc_computed, port_std_computed = calculate_risk_contributions(
            computed_weights, returns
        )
        rc_manual, port_std_manual = calculate_risk_contributions(
            manual_weights, returns
        )

        # 比較テーブル
        comparison_data = []
        for t in tickers:
            comparison_data.append(
                {
                    "ティッカー": t,
                    "資産クラス": CORE_ETFS[t]["name"],
                    "現在価格": f"${current_px.get(t, 0):.2f}" if current_px.get(t) else "N/A",
                    f"{target_label}": f"{computed_weights[t]:.1%}",
                    "手動目標": f"{manual_weights[t]:.1%}",
                    "リスク寄与度": f"{rc_computed[t]:.1%}",
                    "年率ボラ": f"{returns[t].std() * np.sqrt(252):.1%}",
                }
            )

        df_comp = pd.DataFrame(comparison_data)
        st.dataframe(df_comp, use_container_width=True, hide_index=True)

        # ポートフォリオ指標
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("ポートフォリオ年率σ", f"{port_std_computed:.1%}")
        with col2:
            # リスク寄与度の均等度（Herfindahl指数の逆数）
            rc_arr = np.array(list(rc_computed.values()))
            hhi = np.sum(rc_arr**2)
            effective_n = 1 / hhi if hhi > 0 else 0
            st.metric("有効資産数", f"{effective_n:.1f} / {len(tickers)}")
        with col3:
            max_rc = max(rc_computed.values())
            max_rc_ticker = max(rc_computed, key=rc_computed.get)
            st.metric("最大リスク寄与", f"{max_rc_ticker}: {max_rc:.1%}")

        # チャート: ウェイト vs リスク寄与度
        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=["資本配分（ウェイト）", "リスク寄与度"],
            specs=[[{"type": "pie"}, {"type": "pie"}]],
        )

        colors = ["#378ADD", "#1D9E75", "#D85A30", "#639922", "#BA7517", "#7F77DD"]

        fig.add_trace(
            go.Pie(
                labels=[CORE_ETFS[t]["name"] for t in tickers],
                values=[computed_weights[t] for t in tickers],
                marker=dict(colors=colors),
                textinfo="label+percent",
                hole=0.35,
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Pie(
                labels=[CORE_ETFS[t]["name"] for t in tickers],
                values=[rc_computed[t] for t in tickers],
                marker=dict(colors=colors),
                textinfo="label+percent",
                hole=0.35,
            ),
            row=1,
            col=2,
        )

        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        # 相関行列ヒートマップ
        with st.expander("📈 相関行列・共分散データ"):
            corr = returns.corr()
            fig_corr = go.Figure(
                data=go.Heatmap(
                    z=corr.values,
                    x=corr.columns,
                    y=corr.columns,
                    colorscale="RdBu_r",
                    zmin=-1,
                    zmax=1,
                    text=corr.values.round(2),
                    texttemplate="%{text}",
                )
            )
            fig_corr.update_layout(
                title="資産間相関行列",
                height=400,
            )
            st.plotly_chart(fig_corr, use_container_width=True)

            st.caption(
                f"計算期間: {lookback} | データソース: yfinance | "
                f"年率ボラティリティ = 日次σ × √252"
            )


# ===== Tab 2: リバランス計算 =====
with tab2:
    st.subheader("⚖️ リバランス計算機")

    # 次回リバランス日の表示
    next_date = get_next_rebalance_date()
    today = datetime.now().date()
    days_until = (next_date - today).days

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        st.metric("今日", today.strftime("%Y-%m-%d"))
    with col_d2:
        st.metric("次回リバランス予定", next_date.strftime("%Y-%m-%d"))
    with col_d3:
        if days_until <= 7:
            st.metric("残り日数", f"{days_until}日", delta="まもなく実施", delta_color="normal")
        else:
            st.metric("残り日数", f"{days_until}日")

    st.markdown("---")

    input_method = st.radio(
        "ポジション入力方法",
        ["手動入力", "IB Flex CSVアップロード"],
        horizontal=True,
    )

    positions = {}

    if input_method == "手動入力":
        st.markdown("コアETFの現在保有数量を入力してください:")
        cols = st.columns(3)
        for i, (ticker, info) in enumerate(CORE_ETFS.items()):
            with cols[i % 3]:
                qty = st.number_input(
                    f"{ticker} ({info['name']})",
                    min_value=0,
                    value=0,
                    step=1,
                    key=f"qty_{ticker}",
                )
                if qty > 0:
                    positions[ticker] = qty

        satellite_value = st.number_input(
            "サテライト保有額（USD）", min_value=0.0, value=0.0, step=100.0
        )

    else:
        uploaded = st.file_uploader("IB Flex CSVをアップロード", type=["csv"])
        satellite_value = 0.0

        if uploaded:
            df_ib = parse_ib_csv(uploaded)
            if df_ib is not None:
                st.dataframe(df_ib, use_container_width=True, hide_index=True)

                for _, row in df_ib.iterrows():
                    symbol = row["Symbol"]
                    if symbol in CORE_ETFS:
                        positions[symbol] = row["Quantity"]
                    else:
                        satellite_value += abs(row["PositionValue"])

    if positions:
        # 現在価格取得
        current_px = fetch_current_prices(list(positions.keys()))

        # 現在のポジション価値計算
        position_values = {}
        for ticker, qty in positions.items():
            px = current_px.get(ticker)
            if px:
                position_values[ticker] = qty * px

        core_total = sum(position_values.values())
        total_portfolio = core_total + satellite_value

        if total_portfolio > 0:
            st.markdown("---")

            # 現在の配分 vs 目標
            col_summary1, col_summary2, col_summary3 = st.columns(3)
            with col_summary1:
                st.metric(
                    "コア合計",
                    f"${core_total:,.0f}",
                    f"{core_total/total_portfolio:.0%} of total",
                )
            with col_summary2:
                st.metric(
                    "サテライト合計",
                    f"${satellite_value:,.0f}",
                    f"{satellite_value/total_portfolio:.0%} of total",
                )
            with col_summary3:
                st.metric("総資産", f"${total_portfolio:,.0f}")

            # 目標配分計算
            target_core_total = total_portfolio * CORE_RATIO

            # リスクパリティ目標でリバランス計算
            rebalance_data = []
            raw_trades = []
            needs_rebalance = False

            for ticker, info in CORE_ETFS.items():
                current_val = position_values.get(ticker, 0)
                current_pct = current_val / core_total if core_total > 0 else 0
                target_pct = info["target_rp"]
                target_val = target_core_total * target_pct

                deviation = current_pct - target_pct
                trade_val = target_val - current_val
                px = current_px.get(ticker, 0)
                trade_shares = int(trade_val / px) if px and px > 0 else 0

                if abs(deviation) > REBALANCE_BAND:
                    needs_rebalance = True

                raw_trades.append(
                    {
                        "ticker": ticker,
                        "current_val": current_val,
                        "current_pct": current_pct,
                        "target_pct": target_pct,
                        "deviation": deviation,
                        "trade_val": trade_val,
                        "trade_shares": trade_shares,
                    }
                )

                rebalance_data.append(
                    {
                        "ティッカー": ticker,
                        "資産クラス": info["name"],
                        "現在額": f"${current_val:,.0f}",
                        "現在比率": f"{current_pct:.1%}",
                        "目標比率": f"{target_pct:.1%}",
                        "乖離": f"{deviation:+.1%}",
                        "要取引額": f"${trade_val:+,.0f}",
                        "要取引株数": f"{trade_shares:+d}" if trade_shares != 0 else "—",
                    }
                )

            df_rebal = pd.DataFrame(rebalance_data)
            st.dataframe(df_rebal, use_container_width=True, hide_index=True)

            if needs_rebalance:
                st.warning(
                    f"⚠️ 5%以上の乖離があります。リバランスを検討してください。"
                )
            else:
                st.success("✅ 全資産が目標±5%以内です。リバランス不要。")

            # 乖離バーチャート
            deviations = []
            for ticker in CORE_ETFS:
                current_val = position_values.get(ticker, 0)
                current_pct = current_val / core_total if core_total > 0 else 0
                target_pct = CORE_ETFS[ticker]["target_rp"]
                deviations.append(current_pct - target_pct)

            fig_dev = go.Figure()
            fig_dev.add_trace(
                go.Bar(
                    x=list(CORE_ETFS.keys()),
                    y=[d * 100 for d in deviations],
                    marker_color=[
                        "#E24B4A" if abs(d) > REBALANCE_BAND else "#1D9E75"
                        for d in deviations
                    ],
                    text=[f"{d:+.1%}" for d in deviations],
                    textposition="outside",
                )
            )
            fig_dev.add_hline(
                y=REBALANCE_BAND * 100,
                line_dash="dash",
                line_color="gray",
                annotation_text="+5% band",
            )
            fig_dev.add_hline(
                y=-REBALANCE_BAND * 100,
                line_dash="dash",
                line_color="gray",
                annotation_text="-5% band",
            )
            fig_dev.update_layout(
                title="目標配分からの乖離（%）",
                yaxis_title="乖離（%pt）",
                height=350,
                showlegend=False,
            )
            st.plotly_chart(fig_dev, use_container_width=True)

            # ===== 発注リスト出力 =====
            st.markdown("---")
            st.subheader("📋 発注リスト（コピー用）")

            order_text = generate_order_list(raw_trades, current_px)
            st.code(order_text, language="text")

            col_save1, col_save2 = st.columns([1, 3])
            with col_save1:
                save_clicked = st.button(
                    "💾 履歴に保存",
                    type="primary",
                    disabled=not needs_rebalance,
                )
            with col_save2:
                if not needs_rebalance:
                    st.caption("リバランス不要のため保存は不要です")

            if save_clicked:
                snapshot = {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "total_portfolio": total_portfolio,
                    "core_total": core_total,
                    "satellite_value": satellite_value,
                    "trades": raw_trades,
                    "order_text": order_text,
                    "needs_rebalance": needs_rebalance,
                }
                with st.spinner("GitHubに保存中..."):
                    success, msg = save_rebalance_snapshot(snapshot)
                if success:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

    # ===== リバランス履歴 =====
    st.markdown("---")
    with st.expander("📜 過去のリバランス履歴", expanded=False):
        with st.spinner("履歴を取得中..."):
            history = load_rebalance_history()

        if not history:
            st.info("まだ履歴がありません。リバランス実施時に保存してください。")
        else:
            st.caption(f"直近{len(history)}件を表示")

            history_rows = []
            for h in reversed(history):
                sells = sum(
                    1 for t in h.get("trades", []) if t.get("trade_shares", 0) < 0
                )
                buys = sum(
                    1 for t in h.get("trades", []) if t.get("trade_shares", 0) > 0
                )
                history_rows.append(
                    {
                        "日付": h.get("date", "—"),
                        "総資産": f"${h.get('total_portfolio', 0):,.0f}",
                        "コア": f"${h.get('core_total', 0):,.0f}",
                        "売却銘柄数": sells,
                        "購入銘柄数": buys,
                    }
                )

            st.dataframe(
                pd.DataFrame(history_rows),
                use_container_width=True,
                hide_index=True,
            )

            # 最新の履歴詳細
            if len(history) > 0:
                latest = history[-1]
                st.markdown("**最新リバランスの発注内容:**")
                st.code(latest.get("order_text", "—"), language="text")


# ===== Tab 3: サテライト状況 =====
with tab3:
    st.subheader("🎯 サテライト配分ルール")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### サテライトA: 戦術的配分（10-20%）")
        st.markdown(
            """
            **エントリー条件**
            - stockAppシグナル信頼度 > 70%
            - 3/5以上の指標が整合

            **ポジション管理**
            - 1アイデア最大5%
            - サテライトA合計20%上限
            - ストップロス: -10%（例外なし）

            **現在のシグナル源**
            - AIバブル分析（5シグナル）
            - マーケット参加者マインド
            - セクターローテーション

            **保有中の個別株**
            - 日本個別株（IB保有分）
            - stockAppシグナルに基づく米国株
            """
        )

        # Kill switch status
        st.markdown("---")
        st.markdown("**Kill Switch 状態**")
        kill_status = st.radio(
            "サテライトA運用状態",
            ["🟢 通常運用", "🟡 縮小中（5%以下）", "🔴 凍結"],
            index=0,
            key="kill_a",
        )

    with col_b:
        st.markdown("#### サテライトB: オプション収益（5-10%）")
        st.markdown(
            """
            **対象戦略**
            - IYR（不動産ETF）のカバードコール
            - コア保有分のカバードコール
            - ウォッチリストのCSP

            **フィルター条件**
            - IV Rank > 30
            - DTE: 30-45日
            - Delta: 0.20-0.30

            **管理ルール**
            - 50%利益で利確 or 21DTE
            - 想定元本: ポートフォリオの30%以下

            **ツール連携**
            - オプション戦略AI（ページ17）
            - カバードコールシミュレーター（ページ18）
            """
        )

        st.markdown("---")
        st.markdown("**Kill Switch 状態**")
        kill_status_b = st.radio(
            "サテライトB運用状態",
            ["🟢 通常運用", "🟡 縮小中", "🔴 凍結"],
            index=0,
            key="kill_b",
        )

    # ポートフォリオ全体のKill switch
    st.markdown("---")
    st.markdown("### 🚨 全体 Kill Switch")
    st.markdown(
        "> 総ポートフォリオのドローダウンが **25%** を超えた場合、"
        "全サテライト活動を凍結し、コアのみに戻す。"
    )
    st.markdown(
        "> サテライトAがコアを **5%以上** 6ヶ月間アンダーパフォームした場合、"
        "サテライトAを5%以下に縮小してレビュー。"
    )
    st.markdown(
        "> サテライトBの勝率が3ヶ月間 **50%未満** の場合、"
        "一時停止してストライク選定とサイジングを見直す。"
    )


# ===== Tab 4: AI診断 =====
with tab4:
    st.subheader("🤖 AI ポートフォリオ診断")

    if st.button("AIにポートフォリオ診断を依頼", type="primary"):
        with st.spinner("分析中..."):
            # 現在のデータを収集
            tickers = list(CORE_ETFS.keys())
            prices = fetch_prices(tickers, period="1y")
            returns = prices.pct_change().dropna()
            computed_weights = calculate_risk_parity_weights(returns)
            rc, port_std = calculate_risk_contributions(computed_weights, returns)
            corr = returns.corr()

            # VIXを取得
            try:
                vix = yf.Ticker("^VIX")
                vix_hist = vix.history(period="5d")
                vix_val = vix_hist["Close"].iloc[-1] if not vix_hist.empty else "N/A"
            except Exception:
                vix_val = "N/A"

            prompt = f"""
{DATE_CONTEXT}

以下のリスクパリティ・コアポートフォリオの診断をしてください。

【算出されたリスクパリティ配分】
{json.dumps({t: f"{w:.1%}" for t, w in computed_weights.items()}, indent=2)}

【リスク寄与度】
{json.dumps({t: f"{r:.1%}" for t, r in rc.items()}, indent=2)}

【ポートフォリオ年率ボラティリティ】{port_std:.1%}

【相関行列】
{corr.round(2).to_string()}

【現在のVIX】{vix_val}

【コア・サテライト構造】
- コア: 80%（リスクパリティ、上記配分）
- サテライトA: 15%（AIバブル分析・マーケット参加者マインドに基づく戦術的配分）
- サテライトB: 5%（カバードコール・CSPのオプション収益）

以下の観点で診断してください：
1. リスクパリティ配分の妥当性（現在の市場環境を踏まえて）
2. 相関構造の変化リスク（株債券の相関転換など）
3. 地政学リスク（中東情勢）がポートフォリオに与える影響
4. コア・サテライト比率の適切性
5. 今後3ヶ月で注視すべきリスクシナリオ

率直に、本質的な助言を日本語で回答してください。お世辞は不要です。
"""
            system = (
                "あなたはポートフォリオ分析の専門家です。"
                "率直で本質的な助言を提供してください。"
                "リスクを過小評価せず、盲点を指摘してください。"
            )

            result = call_claude_api(prompt, system_prompt=system)
            st.markdown(result)

    st.markdown("---")
    st.caption(
        "⚠️ このツールは教育・分析目的です。投資判断はご自身の責任で行ってください。"
    )


# ===== サイドバー: 設定 =====
with st.sidebar:
    st.markdown("### ⚙️ 設定")

    st.markdown("**コア・サテライト比率**")
    core_pct = st.slider("コア比率", 60, 90, 80, 5, key="core_slider")
    sat_a_pct = st.slider(
        "サテライトA比率", 5, 25, 15, 5, key="sat_a_slider"
    )
    remaining = 100 - core_pct - sat_a_pct
    st.markdown(f"サテライトB: **{remaining}%**")

    if core_pct + sat_a_pct > 100:
        st.error("合計が100%を超えています")

    st.markdown("---")
    st.markdown("**リバランスバンド**")
    band = st.slider("乖離許容幅（%）", 3, 10, 5, 1)

    st.markdown("---")
    st.markdown("**手動目標配分**")
    st.caption("リスクパリティ算出値を上書きする場合")

    manual_overrides = {}
    for ticker, info in CORE_ETFS.items():
        val = st.number_input(
            f"{ticker} 目標%",
            min_value=0,
            max_value=50,
            value=int(info["target_rp"] * 100),
            step=1,
            key=f"manual_{ticker}",
        )
        manual_overrides[ticker] = val

    total_manual = sum(manual_overrides.values())
    if total_manual != 100:
        st.warning(f"合計: {total_manual}% (100%にしてください)")
    else:
        st.success("合計: 100% ✓")
