from core.auth import require_auth
require_auth()

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import requests

st.set_page_config(page_title="織り込み度分析", page_icon="🔍", layout="wide")

st.title("🔍 織り込み度分析（決算イベント）")
st.caption("Implied Move vs Actual Move — 市場の織り込み度を定量化する")

# =====================================================
# yfinance session with User-Agent (rate limit対策)
# =====================================================
def make_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    return session


def yf_with_retry(func, max_retries=4, base_delay=2):
    """yfinance呼び出しを指数バックオフでリトライ"""
    last_err = None
    for attempt in range(max_retries):
        try:
            result = func()
            return result, None
        except Exception as e:
            last_err = e
            err_msg = str(e).lower()
            if 'rate' in err_msg or 'too many' in err_msg or '429' in err_msg:
                wait = base_delay * (2 ** attempt)
                time.sleep(wait)
                continue
            else:
                if attempt == 0:
                    time.sleep(1)
                    continue
                return None, str(e)
    return None, f"Rate limit (最終): {last_err}"


# =====================================================
# Helper functions
# =====================================================

@st.cache_data(ttl=3600)
def get_stock_data(ticker_symbol, period="2y"):
    """株価データ取得"""
    def _fetch():
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period=period)
        if hist.empty:
            return None, None
        try:
            info = ticker.info
        except Exception:
            info = {}
        return hist, info

    result, err = yf_with_retry(_fetch)
    if err:
        return None, None, err
    if result is None:
        return None, None, "データなし"
    hist, info = result
    return hist, info, None


@st.cache_data(ttl=3600)
def get_earnings_dates(ticker_symbol):
    """決算日取得"""
    def _fetch():
        ticker = yf.Ticker(ticker_symbol)
        return ticker.earnings_dates

    result, err = yf_with_retry(_fetch)
    if err or result is None or (hasattr(result, 'empty') and result.empty):
        return None
    return result


@st.cache_data(ttl=900)
def get_options_expirations(ticker_symbol):
    """オプション満期リスト取得"""
    def _fetch():
        ticker = yf.Ticker(ticker_symbol)
        return ticker.options

    result, err = yf_with_retry(_fetch)
    if err or not result:
        return None
    return result


def get_options_chain_data(ticker_symbol, expiration):
    """オプションチェーン取得"""
    def _fetch():
        ticker = yf.Ticker(ticker_symbol)
        return ticker.option_chain(expiration)

    result, err = yf_with_retry(_fetch)
    if err:
        return None
    return result


def calc_implied_move(ticker_symbol, expiration, current_price):
    """ATMストラドル価格からインプライドムーブを計算"""
    chain = get_options_chain_data(ticker_symbol, expiration)
    if chain is None:
        return None, None, None
    try:
        calls = chain.calls
        puts = chain.puts
        if calls.empty or puts.empty:
            return None, None, None

        calls_sorted = calls.copy()
        calls_sorted['dist'] = abs(calls_sorted['strike'] - current_price)
        atm_call = calls_sorted.loc[calls_sorted['dist'].idxmin()]

        puts_sorted = puts.copy()
        puts_sorted['dist'] = abs(puts_sorted['strike'] - current_price)
        atm_put = puts_sorted.loc[puts_sorted['dist'].idxmin()]

        call_mid = (atm_call['bid'] + atm_call['ask']) / 2 if atm_call['bid'] > 0 else atm_call['lastPrice']
        put_mid = (atm_put['bid'] + atm_put['ask']) / 2 if atm_put['bid'] > 0 else atm_put['lastPrice']

        straddle_price = call_mid + put_mid
        implied_move_pct = (straddle_price / current_price) * 100
        avg_iv = (atm_call.get('impliedVolatility', 0) + atm_put.get('impliedVolatility', 0)) / 2

        return implied_move_pct, straddle_price, avg_iv
    except Exception:
        return None, None, None


def calc_actual_earnings_moves(hist, earnings_dates_df):
    """過去の決算日前後の実際の値動きを計算"""
    results = []

    hist_naive = hist.copy()
    if hist_naive.index.tz is not None:
        hist_naive.index = hist_naive.index.tz_localize(None)

    earn_idx = earnings_dates_df.index
    if earn_idx.tz is not None:
        earn_idx_naive = earn_idx.tz_localize(None)
    else:
        earn_idx_naive = earn_idx

    now = pd.Timestamp.now()
    past_mask = earn_idx_naive <= now
    past_dates_naive = earn_idx_naive[past_mask]
    past_dates_orig = earn_idx[past_mask]

    for i, earn_date_naive in enumerate(past_dates_naive[:16]):
        try:
            before_mask = hist_naive.index <= earn_date_naive
            if not before_mask.any():
                continue
            pre_date = hist_naive.index[before_mask][-1]
            pre_close = hist_naive.loc[pre_date, 'Close']

            after_mask = hist_naive.index > earn_date_naive
            if not after_mask.any():
                continue
            post_date = hist_naive.index[after_mask][0]
            post_close = hist_naive.loc[post_date, 'Close']

            actual_move_pct = ((post_close - pre_close) / pre_close) * 100
            abs_move_pct = abs(actual_move_pct)

            eps_actual = None
            eps_estimate = None
            surprise_pct = None
            orig_date = past_dates_orig[i]
            if 'Reported EPS' in earnings_dates_df.columns:
                eps_actual = earnings_dates_df.loc[orig_date, 'Reported EPS']
            if 'EPS Estimate' in earnings_dates_df.columns:
                eps_estimate = earnings_dates_df.loc[orig_date, 'EPS Estimate']
            if eps_actual is not None and eps_estimate is not None and eps_estimate != 0:
                if not (pd.isna(eps_actual) or pd.isna(eps_estimate)):
                    surprise_pct = ((eps_actual - eps_estimate) / abs(eps_estimate)) * 100

            results.append({
                '決算日': earn_date_naive.strftime('%Y-%m-%d'),
                '決算前終値': round(pre_close, 2),
                '決算後終値': round(post_close, 2),
                '変動率(%)': round(actual_move_pct, 2),
                '絶対変動率(%)': round(abs_move_pct, 2),
                '方向': '↑' if actual_move_pct > 0 else '↓',
                'EPS実績': round(eps_actual, 2) if eps_actual is not None and not pd.isna(eps_actual) else None,
                'EPS予想': round(eps_estimate, 2) if eps_estimate is not None and not pd.isna(eps_estimate) else None,
                'EPSサプライズ(%)': round(surprise_pct, 1) if surprise_pct is not None else None,
            })
        except Exception:
            continue

    return pd.DataFrame(results) if results else None


# =====================================================
# Main UI
# =====================================================

col_input1, col_input2 = st.columns([2, 3])
with col_input1:
    ticker_symbol = st.text_input(
        "ティッカーシンボル",
        value="AAPL",
        help="米国株のティッカーを入力（例: AAPL, TSLA, NVDA, META）"
    ).upper().strip()

with col_input2:
    watchlist = st.text_input(
        "ウォッチリスト（カンマ区切り）",
        value="AAPL, NVDA, TSLA, META, GOOGL, AMZN, MSFT",
        help="複数銘柄を比較する場合"
    )

col_btn1, col_btn2 = st.columns([1, 5])
with col_btn1:
    if st.button("🔄 キャッシュクリア"):
        st.cache_data.clear()
        st.rerun()

if not ticker_symbol:
    st.info("ティッカーシンボルを入力してください")
    st.stop()

with st.spinner(f"{ticker_symbol} のデータを取得中..."):
    hist, info, fetch_err = get_stock_data(ticker_symbol)

if fetch_err:
    st.error(f"❌ {fetch_err}")
    st.warning("""
    **Yahoo Financeのレート制限の可能性があります。**
    - 1〜2分待ってから再試行してください
    - キャッシュが効くので、一度成功すれば1時間は再リクエストしません
    - Streamlit Cloudの共有IPが原因の場合、時間帯を変えると改善することがあります
    """)
    st.stop()

if hist is None or hist.empty:
    st.error(f"{ticker_symbol} の株価データが取得できませんでした")
    st.stop()

current_price = hist['Close'].iloc[-1]
company_name = info.get('shortName', ticker_symbol) if info else ticker_symbol

st.markdown(f"### {company_name} ({ticker_symbol})　現在値: **${current_price:.2f}**")

earnings_df = get_earnings_dates(ticker_symbol)

# =====================================================
# Section 1: 現在のインプライドムーブ
# =====================================================
st.markdown("---")
st.subheader("⚡ 現在のインプライドムーブ（次回決算向け）")

im_pct = None
expirations = get_options_expirations(ticker_symbol)

if expirations:
    next_earnings = None
    if earnings_df is not None:
        earn_idx = earnings_df.index
        if earn_idx.tz is not None:
            earn_idx_naive = earn_idx.tz_localize(None)
        else:
            earn_idx_naive = earn_idx
        now = pd.Timestamp.now()
        future_mask = earn_idx_naive > now
        if future_mask.any():
            next_earnings = earn_idx_naive[future_mask].min()

    if next_earnings is not None:
        next_earn_str = next_earnings.strftime('%Y-%m-%d')
        st.info(f"📅 次回決算予定日: **{next_earn_str}**")

        best_exp = None
        min_diff = float('inf')
        for exp_str in expirations:
            try:
                exp_date = pd.Timestamp(exp_str)
                diff = (exp_date - next_earnings).days
                if diff >= 0 and diff < min_diff:
                    min_diff = diff
                    best_exp = exp_str
            except Exception:
                continue

        if best_exp:
            with st.spinner("オプションデータ取得中..."):
                im_pct, straddle, avg_iv = calc_implied_move(ticker_symbol, best_exp, current_price)
            if im_pct is not None:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("インプライドムーブ", f"±{im_pct:.1f}%")
                col2.metric("ストラドル価格", f"${straddle:.2f}")
                col3.metric("ATM平均IV", f"{avg_iv*100:.0f}%" if avg_iv else "N/A")
                col4.metric("オプション満期", best_exp)

                upper = current_price * (1 + im_pct / 100)
                lower = current_price * (1 - im_pct / 100)
                st.markdown(f"**想定レンジ**: ${lower:.2f} 〜 ${upper:.2f}")
            else:
                st.warning("ATMストラドル価格を計算できませんでした")
        else:
            st.warning("決算日を跨ぐオプション満期が見つかりません")
    else:
        st.warning("次回決算日が取得できませんでした（参考: 最短満期のIVを使用）")
        if expirations:
            with st.spinner("オプションデータ取得中..."):
                im_pct, straddle, avg_iv = calc_implied_move(ticker_symbol, expirations[0], current_price)
            if im_pct is not None:
                col1, col2, col3 = st.columns(3)
                col1.metric("インプライドムーブ", f"±{im_pct:.1f}%")
                col2.metric("ストラドル価格", f"${straddle:.2f}")
                col3.metric("オプション満期", expirations[0])
else:
    st.warning("オプションデータが取得できませんでした")


# =====================================================
# Section 2: 過去の決算分析
# =====================================================
st.markdown("---")
st.subheader("📊 過去の決算 — Actual Move 分析")

if earnings_df is not None:
    moves_df = calc_actual_earnings_moves(hist, earnings_df)

    if moves_df is not None and not moves_df.empty:
        avg_abs_move = moves_df['絶対変動率(%)'].mean()
        median_abs_move = moves_df['絶対変動率(%)'].median()
        max_move = moves_df.loc[moves_df['絶対変動率(%)'].idxmax()]
        up_count = (moves_df['変動率(%)'] > 0).sum()
        down_count = (moves_df['変動率(%)'] < 0).sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("平均絶対変動率", f"±{avg_abs_move:.1f}%")
        col2.metric("中央値", f"±{median_abs_move:.1f}%")
        col3.metric("最大変動", f"{max_move['変動率(%)']}%")
        col4.metric("上昇/下落", f"{up_count}↑ / {down_count}↓")

        if im_pct is not None:
            st.markdown("---")
            st.subheader("🎯 織り込み度スコア")

            ratio = im_pct / avg_abs_move if avg_abs_move > 0 else 1.0
            raw_score = (ratio - 0.5) / 1.5 * 100
            score = max(0, min(100, raw_score))

            if score >= 80:
                verdict = "🔴 過剰織り込み（IV売り有利 — ボラティリティ売りに優位性）"
            elif score >= 60:
                verdict = "🟡 やや過剰（慎重に — 過去よりIVが高め）"
            elif score >= 40:
                verdict = "⚪ 適正水準（過去実績と概ね整合）"
            elif score >= 20:
                verdict = "🟡 やや過小（IVが過去実績より低め）"
            else:
                verdict = "🔵 過小織り込み（IV買い有利 — サプライズ余地あり）"

            score_col1, score_col2 = st.columns([1, 2])
            with score_col1:
                st.metric("織り込み度スコア", f"{score:.0f} / 100")
                st.markdown(f"**IV/実績比率**: {ratio:.2f}x")

            with score_col2:
                st.markdown(f"### {verdict}")
                st.markdown(f"""
                | 指標 | 値 |
                |---|---|
                | 現在のインプライドムーブ | ±{im_pct:.1f}% |
                | 過去平均絶対変動率 | ±{avg_abs_move:.1f}% |
                | 比率 (IV ÷ 実績) | {ratio:.2f}x |
                """)

            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=score,
                title={'text': "織り込み度"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 20], 'color': '#3498db'},
                        {'range': [20, 40], 'color': '#85c1e9'},
                        {'range': [40, 60], 'color': '#d5d8dc'},
                        {'range': [60, 80], 'color': '#f5b041'},
                        {'range': [80, 100], 'color': '#e74c3c'},
                    ],
                }
            ))
            fig_gauge.update_layout(height=300)
            st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown("#### 決算ごとの価格変動")
        fig = go.Figure()
        colors = ['#2ecc71' if x > 0 else '#e74c3c' for x in moves_df['変動率(%)']]

        fig.add_trace(go.Bar(
            x=moves_df['決算日'],
            y=moves_df['変動率(%)'],
            marker_color=colors,
            text=[f"{v:+.1f}%" for v in moves_df['変動率(%)']],
            textposition='outside',
        ))

        fig.add_hline(y=avg_abs_move, line_dash="dash", line_color="blue",
                      annotation_text=f"平均 +{avg_abs_move:.1f}%")
        fig.add_hline(y=-avg_abs_move, line_dash="dash", line_color="blue",
                      annotation_text=f"平均 -{avg_abs_move:.1f}%")

        if im_pct is not None:
            fig.add_hline(y=im_pct, line_dash="dot", line_color="red",
                          annotation_text=f"現在IV ±{im_pct:.1f}%")
            fig.add_hline(y=-im_pct, line_dash="dot", line_color="red")

        fig.update_layout(
            title=f"{ticker_symbol} 決算日の価格変動",
            xaxis_title="決算日",
            yaxis_title="変動率 (%)",
            height=450,
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📋 決算データ詳細"):
            st.dataframe(moves_df, use_container_width=True, hide_index=True)
    else:
        st.warning("過去の決算データが不十分です")
else:
    st.warning("決算日データが取得できませんでした")


# =====================================================
# Section 3: ウォッチリスト比較
# =====================================================
st.markdown("---")
st.subheader("📋 ウォッチリスト — 織り込み度比較")

st.caption("⚠️ レート制限対策のため、銘柄ごとに2秒間隔で取得します")

if watchlist:
    tickers_list = [t.strip().upper() for t in watchlist.split(',') if t.strip()]

    if st.button("ウォッチリスト分析実行", type="primary"):
        comparison_data = []
        progress = st.progress(0)
        status = st.empty()

        for i, sym in enumerate(tickers_list):
            progress.progress((i + 1) / len(tickers_list))
            status.text(f"分析中: {sym} ({i+1}/{len(tickers_list)})")

            try:
                h, inf, err = get_stock_data(sym, period="2y")
                if err or h is None:
                    continue

                e = get_earnings_dates(sym)
                if e is None:
                    continue

                cp = h['Close'].iloc[-1]
                mv = calc_actual_earnings_moves(h, e)
                if mv is None or mv.empty:
                    continue

                avg_mv = mv['絶対変動率(%)'].mean()

                exps = get_options_expirations(sym)
                iv_move = None
                score_val = None
                if exps:
                    im, _, _ = calc_implied_move(sym, exps[0], cp)
                    if im is not None:
                        iv_move = im
                        r = im / avg_mv if avg_mv > 0 else 1.0
                        score_val = max(0, min(100, (r - 0.5) / 1.5 * 100))

                name = inf.get('shortName', sym) if inf else sym

                comparison_data.append({
                    'ティッカー': sym,
                    '銘柄名': name[:25],
                    '現在値': round(cp, 2),
                    '過去平均変動(%)': round(avg_mv, 1),
                    'IV想定(%)': round(iv_move, 1) if iv_move else None,
                    '織り込み度': round(score_val, 0) if score_val is not None else None,
                })

                time.sleep(2)

            except Exception:
                continue

        progress.empty()
        status.empty()

        if comparison_data:
            comp_df = pd.DataFrame(comparison_data)
            comp_df = comp_df.sort_values('織り込み度', ascending=True, na_position='last')

            st.dataframe(
                comp_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    '織り込み度': st.column_config.ProgressColumn(
                        "織り込み度", min_value=0, max_value=100, format="%.0f",
                    ),
                }
            )

            chart_df = comp_df.dropna(subset=['織り込み度'])
            if not chart_df.empty:
                fig_comp = go.Figure()
                colors_comp = []
                for s in chart_df['織り込み度']:
                    if s >= 80: colors_comp.append('#e74c3c')
                    elif s >= 60: colors_comp.append('#f5b041')
                    elif s >= 40: colors_comp.append('#d5d8dc')
                    elif s >= 20: colors_comp.append('#85c1e9')
                    else: colors_comp.append('#3498db')

                fig_comp.add_trace(go.Bar(
                    x=chart_df['ティッカー'],
                    y=chart_df['織り込み度'],
                    marker_color=colors_comp,
                    text=[f"{s:.0f}" for s in chart_df['織り込み度']],
                    textposition='outside'
                ))
                fig_comp.add_hline(y=80, line_dash="dash", line_color="red",
                                  annotation_text="空売りゾーン(80)")
                fig_comp.add_hline(y=20, line_dash="dash", line_color="blue",
                                  annotation_text="買いゾーン(20)")
                fig_comp.update_layout(
                    title="ウォッチリスト 織り込み度スコア",
                    yaxis_title="織り込み度 (0=過小, 100=過剰)",
                    height=400,
                )
                st.plotly_chart(fig_comp, use_container_width=True)

            st.caption("⚠️ スコアは参考指標です。投資判断の唯一の根拠にしないでください。")
        else:
            st.warning("有効なデータが取得できませんでした（レート制限の可能性）")


# =====================================================
# Section 4: メソドロジー
# =====================================================
st.markdown("---")
with st.expander("📖 メソドロジー（計算方法）"):
    st.markdown("""
    ### 織り込み度スコアの算出方法

    **ステップ1**: 決算日を跨ぐ最短満期のATMストラドル価格 ÷ 株価 = インプライドムーブ
    **ステップ2**: 過去16四半期の決算前後の絶対変動率の平均
    **ステップ3**: 比率 = IV ÷ 実績平均 → 0.5x→0点、1.0x→50点、2.0x→100点

    **解釈**
    - 80-100: 過剰織り込み — ボラティリティ売りに優位性
    - 60-80: やや過剰
    - 40-60: 適正
    - 20-40: やや過小
    - 0-20: 過小織り込み — サプライズ余地大

    **限界**: 決算イベント限定。FOMCや地政学リスクは対象外。これだけで売買判断しないこと。
    """)
