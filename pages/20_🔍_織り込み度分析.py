import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import math
import time

st.set_page_config(page_title="織り込み度分析", page_icon="🔍", layout="wide")

st.title("🔍 織り込み度分析（決算イベント）")
st.caption("Implied Move vs Actual Move — 市場の織り込み度を定量化する")

# =====================================================
# Helper functions
# =====================================================

@st.cache_data(ttl=300)
def get_stock_data(ticker_symbol, period="2y"):
    """株価データ取得"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period=period)
        if hist.empty:
            return None, None
        info = ticker.info
        return hist, info
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return None, None


@st.cache_data(ttl=300)
def get_earnings_dates(ticker_symbol):
    """決算日取得"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        earnings = ticker.earnings_dates
        if earnings is None or earnings.empty:
            return None
        return earnings
    except Exception:
        return None


@st.cache_data(ttl=60)
def get_options_chain(ticker_symbol):
    """オプションチェーン取得"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        expirations = ticker.options
        if not expirations:
            return None, None
        return ticker, expirations
    except Exception:
        return None, None


def calc_implied_move(ticker, expiration, current_price):
    """
    ATMストラドル価格からインプライドムーブを計算
    Implied Move ≈ Straddle Price / Stock Price
    """
    try:
        chain = ticker.option_chain(expiration)
        calls = chain.calls
        puts = chain.puts

        if calls.empty or puts.empty:
            return None, None, None

        # ATMに最も近いストライクを探す
        calls_sorted = calls.copy()
        calls_sorted['dist'] = abs(calls_sorted['strike'] - current_price)
        atm_call = calls_sorted.loc[calls_sorted['dist'].idxmin()]

        puts_sorted = puts.copy()
        puts_sorted['dist'] = abs(puts_sorted['strike'] - current_price)
        atm_put = puts_sorted.loc[puts_sorted['dist'].idxmin()]

        # ストラドル価格（mid price使用）
        call_mid = (atm_call['bid'] + atm_call['ask']) / 2 if atm_call['bid'] > 0 else atm_call['lastPrice']
        put_mid = (atm_put['bid'] + atm_put['ask']) / 2 if atm_put['bid'] > 0 else atm_put['lastPrice']

        straddle_price = call_mid + put_mid
        implied_move_pct = (straddle_price / current_price) * 100

        # IV情報
        avg_iv = (atm_call.get('impliedVolatility', 0) + atm_put.get('impliedVolatility', 0)) / 2

        return implied_move_pct, straddle_price, avg_iv

    except Exception as e:
        return None, None, None


def calc_actual_earnings_moves(hist, earnings_dates_df):
    """過去の決算日前後の実際の値動きを計算"""
    results = []

    now = pd.Timestamp.now()
    if earnings_dates_df.index.tz is not None:
        now = pd.Timestamp.now(tz=earnings_dates_df.index.tz)

    past_dates = earnings_dates_df[earnings_dates_df.index <= now].index

    # histのインデックスをtz-naive or tz-awareに揃える
    hist_idx = hist.index
    if hist_idx.tz is not None and earnings_dates_df.index.tz is None:
        hist_idx = hist_idx.tz_localize(None)
    elif hist_idx.tz is None and earnings_dates_df.index.tz is not None:
        hist_idx = hist_idx.tz_localize('UTC')

    hist_copy = hist.copy()
    hist_copy.index = hist_idx

    for earn_date in past_dates[:16]:  # 直近16四半期
        try:
            earn_date_naive = earn_date.tz_localize(None) if earn_date.tz else earn_date
            hist_naive = hist_copy.copy()
            if hist_naive.index.tz is not None:
                hist_naive.index = hist_naive.index.tz_localize(None)

            # 決算日以前の最後の取引日を探す
            before_mask = hist_naive.index <= earn_date_naive
            if not before_mask.any():
                continue
            pre_date = hist_naive.index[before_mask][-1]
            pre_close = hist_naive.loc[pre_date, 'Close']

            # 決算日以降の最初の取引日を探す（翌日）
            after_mask = hist_naive.index > earn_date_naive
            if not after_mask.any():
                continue
            post_date = hist_naive.index[after_mask][0]
            post_close = hist_naive.loc[post_date, 'Close']

            # 変動率
            actual_move_pct = ((post_close - pre_close) / pre_close) * 100
            abs_move_pct = abs(actual_move_pct)

            # EPS情報（あれば）
            eps_actual = None
            eps_estimate = None
            surprise_pct = None
            if 'Reported EPS' in earnings_dates_df.columns:
                eps_actual = earnings_dates_df.loc[earn_date, 'Reported EPS']
            if 'EPS Estimate' in earnings_dates_df.columns:
                eps_estimate = earnings_dates_df.loc[earn_date, 'EPS Estimate']
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
                'EPS実績': eps_actual if eps_actual is not None and not pd.isna(eps_actual) else None,
                'EPS予想': eps_estimate if eps_estimate is not None and not pd.isna(eps_estimate) else None,
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

if not ticker_symbol:
    st.info("ティッカーシンボルを入力してください")
    st.stop()

# --- データ取得 ---
with st.spinner(f"{ticker_symbol} のデータを取得中..."):
    hist, info = get_stock_data(ticker_symbol)
    earnings_df = get_earnings_dates(ticker_symbol)

if hist is None or hist.empty:
    st.error(f"{ticker_symbol} の株価データが取得できませんでした")
    st.stop()

current_price = hist['Close'].iloc[-1]
company_name = info.get('shortName', ticker_symbol) if info else ticker_symbol

st.markdown(f"### {company_name} ({ticker_symbol})　現在値: **${current_price:.2f}**")

# =====================================================
# Section 1: 現在のインプライドムーブ（次回決算）
# =====================================================
st.markdown("---")
st.subheader("⚡ 現在のインプライドムーブ（次回決算向け）")

ticker_obj, expirations = get_options_chain(ticker_symbol)

if ticker_obj and expirations:
    # 次回決算日を取得
    next_earnings = None
    if earnings_df is not None:
        now_ts = pd.Timestamp.now()
        if earnings_df.index.tz is not None:
            now_ts = pd.Timestamp.now(tz=earnings_df.index.tz)
        future_mask = earnings_df.index > now_ts
        if future_mask.any():
            next_earnings = earnings_df.index[future_mask][-1]  # 最も近い未来の日付
            # earnings_datesは降順の場合があるので最小値を取る
            future_dates = earnings_df.index[future_mask]
            next_earnings = future_dates.min()

    if next_earnings:
        next_earn_str = next_earnings.strftime('%Y-%m-%d')
        st.info(f"📅 次回決算予定日: **{next_earn_str}**")

        # 決算日を跨ぐ最も近い満期を選択
        earn_naive = next_earnings.tz_localize(None) if next_earnings.tz else next_earnings
        best_exp = None
        min_diff = float('inf')
        for exp_str in expirations:
            exp_date = pd.Timestamp(exp_str)
            diff = (exp_date - earn_naive).days
            if diff >= 0 and diff < min_diff:
                min_diff = diff
                best_exp = exp_str

        if best_exp:
            im_pct, straddle, avg_iv = calc_implied_move(ticker_obj, best_exp, current_price)
            if im_pct is not None:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("インプライドムーブ", f"±{im_pct:.1f}%")
                col2.metric("ストラドル価格", f"${straddle:.2f}")
                col3.metric("ATM平均IV", f"{avg_iv*100:.0f}%" if avg_iv else "N/A")
                col4.metric("オプション満期", best_exp)

                # 想定レンジ
                upper = current_price * (1 + im_pct / 100)
                lower = current_price * (1 - im_pct / 100)
                st.markdown(f"**想定レンジ**: ${lower:.2f} 〜 ${upper:.2f}")
            else:
                st.warning("ATMストラドル価格を計算できませんでした")
        else:
            st.warning("決算日を跨ぐオプション満期が見つかりません")
    else:
        st.warning("次回決算日が取得できませんでした")

        # 決算日不明でも最も近い満期のIVを表示
        if expirations:
            im_pct, straddle, avg_iv = calc_implied_move(ticker_obj, expirations[0], current_price)
            if im_pct is not None:
                st.markdown(f"**参考**: 最短満期({expirations[0]})のインプライドムーブ: ±{im_pct:.1f}%")
else:
    st.warning("オプションデータが取得できませんでした（日本株はオプション未対応の場合があります）")


# =====================================================
# Section 2: 過去の決算イベント分析
# =====================================================
st.markdown("---")
st.subheader("📊 過去の決算 — Actual Move 分析")

if earnings_df is not None:
    moves_df = calc_actual_earnings_moves(hist, earnings_df)

    if moves_df is not None and not moves_df.empty:
        # サマリー統計
        avg_abs_move = moves_df['絶対変動率(%)'].mean()
        median_abs_move = moves_df['絶対変動率(%)'].median()
        max_move = moves_df.loc[moves_df['絶対変動率(%)'].idxmax()]
        up_count = (moves_df['変動率(%)'] > 0).sum()
        down_count = (moves_df['変動率(%)'] < 0).sum()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("平均絶対変動率", f"±{avg_abs_move:.1f}%")
        col2.metric("中央値", f"±{median_abs_move:.1f}%")
        col3.metric("最大変動", f"{max_move['変動率(%)']}% ({max_move['決算日']})")
        col4.metric("上昇/下落", f"{up_count}↑ / {down_count}↓")

        # --- 織り込み度の判定（現在のIV vs 過去の実績） ---
        if ticker_obj and expirations and im_pct is not None:
            st.markdown("---")
            st.subheader("🎯 織り込み度スコア")

            # 織り込み度 = IV想定 ÷ 過去平均実績の比率を正規化
            # ratio > 1: オプション市場が過大評価（IV高すぎ＝織り込みすぎ）
            # ratio < 1: オプション市場が過小評価（IV低すぎ＝織り込み不足）
            ratio = im_pct / avg_abs_move if avg_abs_move > 0 else 1.0

            # スコア化: ratio=1.0 → 50, ratio=2.0 → 100, ratio=0.5 → 0
            # 線形マッピング: score = (ratio - 0.5) / 1.5 * 100、0-100にクリップ
            raw_score = (ratio - 0.5) / 1.5 * 100
            score = max(0, min(100, raw_score))

            # 判定
            if score >= 80:
                verdict = "🔴 過剰織り込み（IV売り有利 — ボラティリティの売り手に優位性）"
                color = "red"
            elif score >= 60:
                verdict = "🟡 やや過剰（慎重に — 過去よりIVが高め）"
                color = "orange"
            elif score >= 40:
                verdict = "⚪ 適正水準（過去実績と概ね整合）"
                color = "gray"
            elif score >= 20:
                verdict = "🟡 やや過小（IVが過去実績より低め）"
                color = "orange"
            else:
                verdict = "🔵 過小織り込み（IV買い有利 — 大きなサプライズの可能性）"
                color = "blue"

            # スコア表示
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
                st.caption("スコア解釈: 0=過小織り込み（実績より大きく動く可能性）、50=適正、100=過剰織り込み（IVが高すぎ）")

            # ゲージチャート
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
                    'threshold': {
                        'line': {'color': "black", 'width': 4},
                        'thickness': 0.75,
                        'value': score
                    }
                }
            ))
            fig_gauge.update_layout(height=300)
            st.plotly_chart(fig_gauge, use_container_width=True)

        # --- 過去の決算チャート ---
        st.markdown("#### 決算ごとの価格変動")
        fig = go.Figure()

        colors = ['#2ecc71' if x > 0 else '#e74c3c' for x in moves_df['変動率(%)']]

        fig.add_trace(go.Bar(
            x=moves_df['決算日'],
            y=moves_df['変動率(%)'],
            marker_color=colors,
            text=[f"{v:+.1f}%" for v in moves_df['変動率(%)']],
            textposition='outside',
            name='実際の変動率'
        ))

        # 平均絶対変動率のライン
        fig.add_hline(y=avg_abs_move, line_dash="dash", line_color="blue",
                      annotation_text=f"平均 +{avg_abs_move:.1f}%")
        fig.add_hline(y=-avg_abs_move, line_dash="dash", line_color="blue",
                      annotation_text=f"平均 -{avg_abs_move:.1f}%")

        # 現在のIV想定ムーブ（あれば）
        if ticker_obj and expirations and im_pct is not None:
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

        # テーブル表示
        with st.expander("📋 決算データ詳細"):
            display_df = moves_df.copy()
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    else:
        st.warning("過去の決算データが不十分です")
else:
    st.warning("決算日データが取得できませんでした")


# =====================================================
# Section 3: ウォッチリスト比較
# =====================================================
st.markdown("---")
st.subheader("📋 ウォッチリスト — 織り込み度比較")

if watchlist:
    tickers_list = [t.strip().upper() for t in watchlist.split(',') if t.strip()]

    if st.button("ウォッチリスト分析実行", type="primary"):
        comparison_data = []
        progress = st.progress(0)

        for i, sym in enumerate(tickers_list):
            progress.progress((i + 1) / len(tickers_list))
            try:
                h, inf = get_stock_data(sym, period="2y")
                e = get_earnings_dates(sym)
                t_obj, t_exp = get_options_chain(sym)

                if h is None or e is None:
                    continue

                cp = h['Close'].iloc[-1]
                mv = calc_actual_earnings_moves(h, e)

                if mv is None or mv.empty:
                    continue

                avg_mv = mv['絶対変動率(%)'].mean()

                # 現在のIV
                iv_move = None
                score = None
                if t_obj and t_exp:
                    im, _, _ = calc_implied_move(t_obj, t_exp[0], cp)
                    if im is not None:
                        iv_move = im
                        r = im / avg_mv if avg_mv > 0 else 1.0
                        score = max(0, min(100, (r - 0.5) / 1.5 * 100))

                name = inf.get('shortName', sym) if inf else sym

                comparison_data.append({
                    'ティッカー': sym,
                    '銘柄名': name,
                    '現在値': round(cp, 2),
                    '過去平均変動(%)': round(avg_mv, 1),
                    'IV想定(%)': round(iv_move, 1) if iv_move else None,
                    '織り込み度': round(score, 0) if score is not None else None,
                })

                time.sleep(0.3)  # rate limit対策

            except Exception:
                continue

        progress.empty()

        if comparison_data:
            comp_df = pd.DataFrame(comparison_data)
            comp_df = comp_df.sort_values('織り込み度', ascending=True, na_position='last')

            st.dataframe(
                comp_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    '織り込み度': st.column_config.ProgressColumn(
                        "織り込み度",
                        min_value=0,
                        max_value=100,
                        format="%.0f",
                    ),
                }
            )

            # チャート
            chart_df = comp_df.dropna(subset=['織り込み度'])
            if not chart_df.empty:
                fig_comp = go.Figure()
                colors_comp = []
                for s in chart_df['織り込み度']:
                    if s >= 80:
                        colors_comp.append('#e74c3c')
                    elif s >= 60:
                        colors_comp.append('#f5b041')
                    elif s >= 40:
                        colors_comp.append('#d5d8dc')
                    elif s >= 20:
                        colors_comp.append('#85c1e9')
                    else:
                        colors_comp.append('#3498db')

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

            st.caption("⚠️ スコアは過去の決算変動率とオプションIVの比較に基づく参考指標です。投資判断の唯一の根拠にしないでください。")
        else:
            st.warning("有効なデータが取得できませんでした")


# =====================================================
# Section 4: メソドロジー説明
# =====================================================
st.markdown("---")
with st.expander("📖 メソドロジー（計算方法）"):
    st.markdown("""
    ### 織り込み度スコアの算出方法

    **ステップ1: インプライドムーブの計算**
    - 決算日を跨ぐ最短満期のオプションチェーンを取得
    - ATM（現在値に最も近い）ストライクのコール＋プットの中値を合計（ストラドル価格）
    - インプライドムーブ(%) = ストラドル価格 ÷ 株価 × 100

    **ステップ2: 過去の実績変動率の計算**
    - 過去の決算日前後（決算前終値 → 翌取引日終値）の変動率を計算
    - 絶対値の平均を「過去平均実績」とする

    **ステップ3: スコア化**
    - 比率 = インプライドムーブ ÷ 過去平均実績
    - 比率を0〜100にマッピング（0.5x → 0点、1.0x → 50点、2.0x → 100点）

    **解釈**
    - **80-100 (赤)**: 過剰織り込み — IVが過去実績の1.7倍以上。ボラティリティの売り手に有利。空売りシグナル。
    - **60-80 (黄)**: やや過剰 — IVが高め。慎重に。
    - **40-60 (灰)**: 適正 — 過去の実績と整合。
    - **20-40 (青)**: やや過小 — IVが低め。サプライズの可能性。
    - **0-20 (青)**: 過小織り込み — 市場が油断。大きなサプライズがあれば大きく動く。買いシグナル。

    **限界と注意点**
    - これは「決算イベント」限定の指標です。地政学リスクやFOMCは対象外。
    - 過去の変動パターンが未来を保証するわけではありません。
    - IVは満期までの「全期間」を反映するため、決算以外のイベントが重なると歪みます。
    - このスコアだけで売買判断をしないでください。
    """)
