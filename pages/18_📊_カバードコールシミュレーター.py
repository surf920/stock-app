import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import time
import os
import requests
import json

st.set_page_config(page_title="カバードコール シミュレーター", page_icon="📊", layout="wide")

st.title("📊 カバードコール シミュレーター")
st.markdown("保有銘柄に対するCC戦略のプレミアム収入をシミュレーション")

# --- Helper: API call with retry ---
try:
    from api_helper import call_anthropic_api
except ImportError:
    def call_anthropic_api(headers, payload, max_retries=3):
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers, json=payload, timeout=90
                )
                if response.status_code == 529:
                    if attempt < max_retries - 1:
                        time.sleep(5 * (attempt + 1))
                        continue
                    return None, "APIサーバーが混雑中。しばらく待って再試行してください。"
                if response.status_code != 200:
                    return None, f"API Error {response.status_code}: {response.text[:200]}"
                result = response.json()
                text = ""
                for block in result.get("content", []):
                    if block.get("type") == "text":
                        text += block["text"]
                text = text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                try:
                    return json.loads(text), None
                except:
                    import re
                    m = re.search(r"\{[\s\S]*\}", text)
                    if m:
                        return json.loads(m.group()), None
                    return {"text": text}, None
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return None, "APIタイムアウト"
            except Exception as e:
                return None, str(e)
        return None, "リトライ上限"


# --- IB Flex CSV Parser ---
def parse_ib_csv(uploaded_file):
    """Parse IB Flex Daily Positions CSV"""
    raw_lines = uploaded_file.getvalue().decode("utf-8").splitlines()

    header_idx = None
    for i, line in enumerate(raw_lines):
        if '"ClientAccountID"' in line or 'ClientAccountID' in line:
            header_idx = i
            break

    if header_idx is None:
        for i, line in enumerate(raw_lines):
            if '"Symbol"' in line or ',Symbol,' in line:
                header_idx = i
                break

    if header_idx is None:
        return None, "ヘッダー行が見つかりません"

    header = [h.strip().strip('"') for h in raw_lines[header_idx].split(",")]
    data_rows = []
    for line in raw_lines[header_idx + 1:]:
        if line.strip() == "":
            continue
        vals = [v.strip().strip('"') for v in line.split(",")]
        if len(vals) >= len(header):
            data_rows.append(vals[:len(header)])

    if not data_rows:
        return None, "データ行が見つかりません"

    df = pd.DataFrame(data_rows, columns=header)

    # Clean numeric columns
    for col in ['Quantity', 'MarkPrice', 'PositionValue']:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(',', '').str.replace('$', ''),
                errors='coerce'
            )

    # Find key columns
    symbol_col = next((c for c in ['Symbol', 'symbol'] if c in df.columns), None)
    qty_col = next((c for c in ['Quantity', 'Position'] if c in df.columns), None)
    price_col = next((c for c in ['MarkPrice', 'Market Price'] if c in df.columns), None)
    currency_col = next((c for c in ['CurrencyPrimary', 'Currency'] if c in df.columns), None)

    if symbol_col is None:
        return None, "Symbol列が見つかりません"

    # Filter valid rows
    df = df[df[symbol_col].notna() & (df[symbol_col] != '')]

    return {
        'df': df,
        'symbol_col': symbol_col,
        'qty_col': qty_col,
        'price_col': price_col,
        'currency_col': currency_col
    }, None


# --- Options Chain Fetcher ---
@st.cache_data(ttl=300)
def fetch_options_data(symbol, current_price):
    """Fetch options chain and calculate CC candidates"""
    try:
        ticker = yf.Ticker(symbol)
        expirations = ticker.options

        if not expirations:
            return None, "オプションチェーンなし"

        # Filter: 20-60 days out
        today = datetime.now()
        valid_exps = []
        for exp_str in expirations:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
            dte = (exp_date - today).days
            if 20 <= dte <= 60:
                valid_exps.append((exp_str, dte))

        if not valid_exps:
            # Fallback: nearest 2 expirations
            for exp_str in expirations[:2]:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
                dte = (exp_date - today).days
                if dte > 0:
                    valid_exps.append((exp_str, dte))

        if not valid_exps:
            return None, "有効な満期日なし"

        results = []
        for exp_str, dte in valid_exps[:3]:  # Max 3 expirations
            try:
                chain = ticker.option_chain(exp_str)
                calls = chain.calls

                if calls.empty:
                    continue

                # Filter OTM calls (strike > current price)
                otm_calls = calls[calls['strike'] > current_price].copy()
                if otm_calls.empty:
                    continue

                # Calculate key metrics
                otm_calls['otm_pct'] = ((otm_calls['strike'] - current_price) / current_price * 100).round(2)
                otm_calls['premium_pct'] = (otm_calls['lastPrice'] / current_price * 100).round(2)
                otm_calls['annualized_return'] = (otm_calls['premium_pct'] * 365 / max(dte, 1)).round(2)
                otm_calls['max_return_pct'] = (((otm_calls['strike'] - current_price + otm_calls['lastPrice']) / current_price) * 100).round(2)
                otm_calls['dte'] = dte
                otm_calls['expiration'] = exp_str

                # Select best candidates: delta ~0.15-0.30 range (OTM 2-10%)
                candidates = otm_calls[
                    (otm_calls['otm_pct'] >= 1) & (otm_calls['otm_pct'] <= 15) &
                    (otm_calls['lastPrice'] > 0.01)
                ].head(5)

                for _, row in candidates.iterrows():
                    results.append({
                        'expiration': exp_str,
                        'dte': dte,
                        'strike': row['strike'],
                        'last_price': row['lastPrice'],
                        'bid': row.get('bid', 0),
                        'ask': row.get('ask', 0),
                        'volume': row.get('volume', 0),
                        'open_interest': row.get('openInterest', 0),
                        'iv': row.get('impliedVolatility', 0),
                        'otm_pct': row['otm_pct'],
                        'premium_pct': row['premium_pct'],
                        'annualized_return': row['annualized_return'],
                        'max_return_pct': row['max_return_pct']
                    })
            except Exception:
                continue

        if not results:
            return None, "適切なOTMコールが見つかりません"

        return pd.DataFrame(results), None

    except Exception as e:
        return None, f"データ取得エラー: {str(e)}"


@st.cache_data(ttl=600)
def fetch_historical_volatility(symbol, days=30):
    """Calculate historical volatility"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3mo")
        if hist.empty or len(hist) < 20:
            return None
        log_returns = np.log(hist['Close'] / hist['Close'].shift(1)).dropna()
        hv = log_returns.tail(days).std() * np.sqrt(252) * 100
        return round(hv, 2)
    except:
        return None


# ===== MAIN UI =====

# --- CSV Upload ---
st.subheader("📁 IBポートフォリオCSVをアップロード")
uploaded_file = st.file_uploader("Interactive Brokers Flex CSV", type=["csv"], key="cc_csv")

if uploaded_file:
    parsed, error = parse_ib_csv(uploaded_file)

    if error:
        st.error(f"CSV解析エラー: {error}")
        st.stop()

    df = parsed['df']
    sym_col = parsed['symbol_col']
    qty_col = parsed['qty_col']
    price_col = parsed['price_col']
    cur_col = parsed['currency_col']

    # Filter: USD stocks with 100+ shares (CC requires 100 shares per contract)
    if cur_col:
        usd_df = df[df[cur_col] == 'USD'].copy()
    else:
        usd_df = df.copy()

    if qty_col:
        usd_df[qty_col] = pd.to_numeric(usd_df[qty_col], errors='coerce')
        cc_eligible = usd_df[usd_df[qty_col] >= 100].copy()
    else:
        cc_eligible = usd_df.copy()

    if cc_eligible.empty:
        st.warning("⚠️ CC対象銘柄がありません（USD銘柄で100株以上が必要）")
        st.info("保有全銘柄:")
        st.dataframe(df)
        st.stop()

    # Display eligible positions
    st.subheader("🎯 カバードコール対象銘柄")
    st.caption("100株以上保有のUSD銘柄")

    eligible_display = []
    for _, row in cc_eligible.iterrows():
        symbol = str(row[sym_col]).strip()
        qty = int(row[qty_col]) if qty_col else 0
        price = float(row[price_col]) if price_col and pd.notna(row.get(price_col)) else 0
        contracts = qty // 100
        eligible_display.append({
            '銘柄': symbol,
            '保有数': qty,
            '現在価格': f"${price:.2f}" if price > 0 else "N/A",
            '売却可能枚数': contracts,
            '時価': f"${qty * price:,.0f}" if price > 0 else "N/A"
        })

    eligible_df = pd.DataFrame(eligible_display)
    st.dataframe(eligible_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # --- Simulation ---
    st.subheader("🔍 プレミアム収入シミュレーション")

    symbols = [str(row[sym_col]).strip() for _, row in cc_eligible.iterrows()]
    selected_symbols = st.multiselect(
        "シミュレーション対象を選択",
        symbols,
        default=symbols[:5],
        max_selections=10
    )

    if st.button("📊 シミュレーション実行", type="primary", use_container_width=True):
        if not selected_symbols:
            st.warning("銘柄を選択してください")
            st.stop()

        all_results = []
        summary_data = []

        progress = st.progress(0, text="オプションデータ取得中...")

        for idx, symbol in enumerate(selected_symbols):
            progress.progress(
                (idx + 1) / len(selected_symbols),
                text=f"📡 {symbol} のオプションチェーン取得中... ({idx+1}/{len(selected_symbols)})"
            )

            row = cc_eligible[cc_eligible[sym_col] == symbol].iloc[0]
            qty = int(row[qty_col]) if qty_col else 100
            price = float(row[price_col]) if price_col and pd.notna(row.get(price_col)) else 0
            contracts = qty // 100

            if price <= 0:
                # Fetch current price from yfinance
                try:
                    t = yf.Ticker(symbol)
                    info = t.info
                    price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                except:
                    pass

            if price <= 0:
                st.warning(f"⚠️ {symbol}: 価格データ取得失敗")
                continue

            # Fetch options chain
            options_df, opt_error = fetch_options_data(symbol, price)
            hv = fetch_historical_volatility(symbol)

            if opt_error:
                st.warning(f"⚠️ {symbol}: {opt_error}")
                continue

            # Add position context
            options_df['symbol'] = symbol
            options_df['shares'] = qty
            options_df['contracts'] = contracts
            options_df['current_price'] = price
            options_df['monthly_income'] = (options_df['last_price'] * contracts * 100).round(2)
            options_df['hv'] = hv

            all_results.append(options_df)

            # Best candidate per expiration
            for exp in options_df['expiration'].unique():
                exp_data = options_df[options_df['expiration'] == exp]
                # Pick the one with best annualized return in 2-8% OTM range
                sweet_spot = exp_data[(exp_data['otm_pct'] >= 2) & (exp_data['otm_pct'] <= 8)]
                if sweet_spot.empty:
                    sweet_spot = exp_data
                best = sweet_spot.sort_values('annualized_return', ascending=False).iloc[0]
                summary_data.append({
                    '銘柄': symbol,
                    '満期日': best['expiration'],
                    'DTE': best['dte'],
                    'ストライク': f"${best['strike']:.2f}",
                    'OTM%': f"{best['otm_pct']:.1f}%",
                    'プレミアム': f"${best['last_price']:.2f}",
                    'Bid/Ask': f"${best['bid']:.2f}/{best['ask']:.2f}",
                    'IV': f"{best['iv']*100:.1f}%" if best['iv'] else "N/A",
                    'HV': f"{hv:.1f}%" if hv else "N/A",
                    '枚数': contracts,
                    '月間収入': f"${best['last_price'] * contracts * 100:,.0f}",
                    '年率リターン': f"{best['annualized_return']:.1f}%",
                    '最大利益率': f"{best['max_return_pct']:.1f}%"
                })

            time.sleep(0.5)  # Rate limit

        progress.empty()

        if not all_results:
            st.error("オプションデータを取得できた銘柄がありません")
            st.stop()

        combined = pd.concat(all_results, ignore_index=True)
        summary_df = pd.DataFrame(summary_data)

        # === Results Display ===
        st.markdown("---")
        st.subheader("💰 シミュレーション結果")

        # Summary metrics
        total_monthly = combined.groupby('symbol').apply(
            lambda x: x.sort_values('annualized_return', ascending=False).iloc[0]['monthly_income']
        ).sum()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("月間プレミアム収入（概算）", f"${total_monthly:,.0f}")
        with col2:
            st.metric("年間換算", f"${total_monthly * 12:,.0f}")
        with col3:
            total_value = sum(
                float(row[price_col]) * int(row[qty_col])
                for _, row in cc_eligible[cc_eligible[sym_col].isin(selected_symbols)].iterrows()
                if pd.notna(row.get(price_col)) and pd.notna(row.get(qty_col))
            )
            if total_value > 0:
                annual_yield = (total_monthly * 12 / total_value * 100)
                st.metric("ポートフォリオ利回り", f"{annual_yield:.1f}%")

        # Detailed table
        st.subheader("📋 推奨ストライク一覧")
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        # Chart: Monthly income by symbol
        income_by_symbol = combined.groupby('symbol').apply(
            lambda x: x.sort_values('annualized_return', ascending=False).iloc[0]
        )[['monthly_income', 'annualized_return', 'otm_pct']].reset_index()

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=income_by_symbol['symbol'],
            y=income_by_symbol['monthly_income'],
            marker_color='#00C853',
            text=[f"${v:,.0f}" for v in income_by_symbol['monthly_income']],
            textposition='outside',
            name='月間収入'
        ))
        fig.update_layout(
            title="銘柄別 月間プレミアム収入",
            xaxis_title="銘柄",
            yaxis_title="月間収入 ($)",
            template="plotly_dark",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

        # Risk/Return scatter
        fig2 = px.scatter(
            combined,
            x='otm_pct',
            y='annualized_return',
            color='symbol',
            size='monthly_income',
            hover_data=['strike', 'expiration', 'dte', 'iv'],
            labels={
                'otm_pct': 'OTM距離 (%)',
                'annualized_return': '年率リターン (%)',
                'symbol': '銘柄',
                'monthly_income': '月間収入'
            },
            title="リスク vs リターン（OTM距離 vs 年率リターン）"
        )
        fig2.update_layout(template="plotly_dark", height=450)
        st.plotly_chart(fig2, use_container_width=True)

        # Store results in session for AI analysis
        st.session_state['cc_results'] = combined
        st.session_state['cc_summary'] = summary_df
        st.session_state['cc_eligible'] = cc_eligible
        st.session_state['cc_total_monthly'] = total_monthly

        # === AI Analysis ===
        st.markdown("---")
        st.subheader("🤖 AI戦略アドバイス")

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            api_key = st.text_input("Anthropic API Key", type="password")

        if api_key and st.button("🧠 AIにCC戦略を分析させる", type="secondary", use_container_width=True):
            with st.spinner("Claude が分析中..."):
                # Build context
                portfolio_summary = []
                for _, row in summary_df.iterrows():
                    portfolio_summary.append(
                        f"{row['銘柄']}: ストライク{row['ストライク']} ({row['OTM%']} OTM), "
                        f"プレミアム{row['プレミアム']}, IV={row['IV']}, HV={row['HV']}, "
                        f"年率{row['年率リターン']}, 月間{row['月間収入']}"
                    )

                prompt = f"""あなたはオプション戦略の専門家です。以下のカバードコールシミュレーション結果を分析し、実践的なアドバイスを提供してください。

現在の日付は2026年3月です。

## ポートフォリオCC候補:
{chr(10).join(portfolio_summary)}

## 月間プレミアム収入合計: ${total_monthly:,.0f}

以下の形式でJSON回答してください:
{{
  "overall_assessment": "ポートフォリオ全体のCC戦略評価（2-3文）",
  "recommendations": [
    {{
      "symbol": "銘柄名",
      "action": "推奨アクション（売る/見送り/ストライク変更）",
      "reason": "理由（IV vs HV比較、決算リスク、セクターリスクなど）",
      "suggested_strike": "推奨ストライク価格",
      "timing": "エントリータイミングのアドバイス"
    }}
  ],
  "risk_warnings": ["リスク警告1", "リスク警告2"],
  "monthly_target": "現実的な月間収入目標",
  "improvement_tips": ["改善提案1", "改善提案2"]
}}"""

                headers = {
                    "x-api-key": api_key,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01"
                }
                payload = {
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 2000,
                    "system": "あなたはプロのオプション戦略アドバイザーです。常にJSON形式で回答してください。",
                    "messages": [{"role": "user", "content": prompt}]
                }

                result, api_error = call_anthropic_api(headers, payload)

                if api_error:
                    st.error(f"❌ {api_error}")
                else:
                    # Display AI analysis
                    if isinstance(result, dict):
                        # Overall assessment
                        if 'overall_assessment' in result:
                            st.info(f"📊 **総合評価:** {result['overall_assessment']}")

                        # Per-symbol recommendations
                        if 'recommendations' in result:
                            st.markdown("#### 📋 銘柄別推奨")
                            for rec in result['recommendations']:
                                action = rec.get('action', '')
                                emoji = "✅" if "売" in action else "⏸️" if "見送" in action else "🔄"
                                with st.expander(f"{emoji} {rec.get('symbol', '')} — {action}"):
                                    st.write(f"**理由:** {rec.get('reason', '')}")
                                    st.write(f"**推奨ストライク:** {rec.get('suggested_strike', '')}")
                                    st.write(f"**タイミング:** {rec.get('timing', '')}")

                        # Risk warnings
                        if 'risk_warnings' in result:
                            st.markdown("#### ⚠️ リスク警告")
                            for warn in result['risk_warnings']:
                                st.warning(warn)

                        # Monthly target
                        if 'monthly_target' in result:
                            st.success(f"🎯 **現実的な月間収入目標:** {result['monthly_target']}")

                        # Improvement tips
                        if 'improvement_tips' in result:
                            st.markdown("#### 💡 改善提案")
                            for tip in result['improvement_tips']:
                                st.markdown(f"• {tip}")
                    else:
                        st.write(result)

else:
    st.info("👆 IBポートフォリオCSVをアップロードしてください")
    st.markdown("---")

    st.markdown("""
### 📋 カバードコール戦略とは

保有株100株につき1枚のコールオプションを売却し、プレミアム収入を得る戦略です。

**メリット:**
- 保有株から追加収入（年3-10%程度）
- 下落時のバッファー（プレミアム分の損失軽減）
- 株の売却指値を設定しつつ報酬を受け取る

**デメリット:**
- ストライク以上の上昇利益を放棄
- 大幅上昇時に機会損失
- 急落時はプレミアムだけでは損失をカバーできない

### 🎯 このシミュレーターの機能

1. **IBポートフォリオ読み込み** — 100株以上の保有銘柄を自動抽出
2. **オプションチェーン取得** — 20-60日後の満期のOTMコールを検索
3. **プレミアム収入計算** — 月間/年間の想定収入を算出
4. **AI戦略分析** — Claude がIV/HV比較、決算リスクを考慮して助言
    """)

    st.markdown("---")
    st.caption("⚡ データ: yfinance | AI: Claude claude-sonnet-4-20250514 | 対象: 米国株オプション")
