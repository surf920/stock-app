import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
import ssl

# --- 🚨 通信エラー回避 ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ----------------------

st.set_page_config(page_title="ポートフォリオ診断", page_icon="📁", layout="wide")
st.title("📁 ポートフォリオ AI診断 & 配当くん (Japan Pro)")
st.markdown("保有銘柄の「トレンド」と「配当金（不労所得）」を自動計算します。日本株の配当も実績ベースで正確に算出します。")

# --- サイドバー設定 ---
with st.sidebar:
    st.header("⚙️ 生活費設定")
    monthly_cost = st.number_input("プーケットの月間生活費 (円)", value=300000, step=10000, format="%d")

# --- 1. ファイルアップロード機能 ---
uploaded_file = st.file_uploader("ポートフォリオのCSVファイル (IB証券 / Flex Query形式)", type=["csv"])

def load_portfolio_csv(file):
    try:
        lines = file.getvalue().decode("utf-8", errors='replace').splitlines()
        header_row_index = -1
        for i, line in enumerate(lines):
            # IB証券の形式が変わっても柔軟に対応
            if "Symbol" in line and ("ClientAccountID" in line or "Account" in line):
                header_row_index = i
                break
        
        if header_row_index == -1:
            st.error("エラー: CSVのヘッダーが見つかりませんでした。")
            return None

        file.seek(0)
        df = pd.read_csv(file, skiprows=header_row_index)
        
        if "Symbol" not in df.columns:
            st.error("エラー: 'Symbol' 列が見つかりません。")
            return None
            
        return df
    except Exception as e:
        st.error(f"ファイル読み込みエラー: {e}")
        return None

# --- 為替 & 市場データ取得 ---
@st.cache_data(ttl=3600)
def get_market_data():
    data = {}
    try:
        ticker_jpy = yf.Ticker("JPY=X")
        hist_jpy = ticker_jpy.history(period="1d")
        data["USDJPY"] = hist_jpy["Close"].iloc[-1] if not hist_jpy.empty else 150.0
        
        ticker_sp500 = yf.Ticker("^GSPC")
        hist_sp = ticker_sp500.history(period="6mo")
        if not hist_sp.empty:
            start = hist_sp["Close"].iloc[0]
            end = hist_sp["Close"].iloc[-1]
            data["SP500_Change"] = (end - start) / start * 100
        else:
            data["SP500_Change"] = 0.0
    except:
        data["USDJPY"] = 150.0
        data["SP500_Change"] = 0.0
    return data

# --- 2. AI解析 & 配当データ取得 ---
def analyze_holdings(df_portfolio, usdjpy_rate):
    results = []
    total_score = 0
    analyzed_count = 0
    error_logs = []
    
    progress_bar = st.progress(0, text="市場データと配当情報を収集中...")
    
    for i, row in df_portfolio.iterrows():
        symbol = str(row.get("Symbol", ""))
        currency = str(row.get("CurrencyPrimary", "JPY"))
        quantity = pd.to_numeric(row.get("Quantity", 0), errors='coerce')

        # 日本株対応（数字だけなら.Tをつける）
        if symbol.isdigit() and (currency == "JPY" or currency == "nan"):
            ticker_symbol = f"{symbol}.T"
        else:
            ticker_symbol = symbol

        # 日本株かどうかのフラグ
        is_japan_stock = ticker_symbol.endswith(".T")

        progress_bar.progress((i + 1) / len(df_portfolio), text=f"解析中: {ticker_symbol}")
        
        try:
            t = yf.Ticker(ticker_symbol)
            hist_1y = t.history(period="1y") # 1年分取得
            
            current_price = 0
            if not hist_1y.empty:
                current_price = hist_1y["Close"].iloc[-1]
            
            # --- 配当計算ロジック (日本株特別対応) ---
            div_rate = 0.0
            div_yield_percent = 0.0
            
            # 戦略:
            # 1. 日本株 (.T) の場合は、.info を信用せず、最初から「履歴の合計」を使う
            # 2. 米国株などは、まず .info を見て、ダメなら履歴を見る
            
            calc_from_history = False
            
            if is_japan_stock:
                calc_from_history = True # 日本株は強制的に履歴から計算
            else:
                # 米国株などは info からトライ
                try:
                    info = t.info
                    if info:
                        div_rate = info.get('dividendRate', 0)
                        raw_yield = info.get('dividendYield', 0)
                        if raw_yield:
                            div_yield_percent = raw_yield * 100
                except:
                    pass
                
                # 米国株でも取れなかったら履歴へ
                if div_rate is None or div_rate == 0:
                    calc_from_history = True

            # 履歴から計算するルート
            if calc_from_history:
                if not hist_1y.empty and 'Dividends' in hist_1y.columns:
                    # 過去1年間の配当合計
                    total_dividends_1y = hist_1y['Dividends'].sum()
                    
                    if total_dividends_1y > 0:
                        div_rate = total_dividends_1y
                        if current_price > 0:
                            div_yield_percent = (div_rate / current_price) * 100

            # 最終チェック
            if div_rate is None: div_rate = 0
            if div_yield_percent is None: div_yield_percent = 0

            # 年間受取配当金
            annual_div_income_raw = quantity * div_rate
            
            # 通貨換算
            if currency == "USD":
                annual_div_income_jpy = annual_div_income_raw * usdjpy_rate
            else:
                annual_div_income_jpy = annual_div_income_raw

            # トレンド判定
            trend_status = "不明"
            trend_score = 50
            pct_change_percent = 0.0
            
            if not hist_1y.empty:
                if len(hist_1y) >= 50:
                    ma50 = hist_1y["Close"].rolling(window=50).mean().iloc[-1]
                else:
                    ma50 = hist_1y["Close"].mean()

                if not pd.isna(ma50) and ma50 != 0:
                    diff = (current_price - ma50) / ma50
                    trend_score = min(max(50 + (diff * 500), 0), 100)
                
                if len(hist_1y) > 125:
                    start_price = hist_1y["Close"].iloc[-125]
                else:
                    start_price = hist_1y["Close"].iloc[0]
                    
                if start_price != 0:
                    pct_change_percent = (current_price - start_price) / start_price * 100
                
                if trend_score >= 60: trend_status = "📈 上昇"
                elif trend_score <= 40: trend_status = "📉 下落"
                else: trend_status = "➡️ 中立"
                
                analyzed_count += 1
                total_score += trend_score
            else:
                trend_status = "データなし"

            results.append({
                "Symbol": symbol,
                "Ticker": ticker_symbol,
                "Trend": trend_status,
                "Score": trend_score,
                "6M Change": pct_change_percent,
                "DivYield": div_yield_percent,
                "AnnualDivJPY": annual_div_income_jpy
            })
            
        except Exception as e:
            error_logs.append(f"{ticker_symbol}: {str(e)}")
            results.append({
                "Symbol": symbol, "Ticker": ticker_symbol,
                "Trend": "エラー", "Score": 50, "6M Change": 0,
                "DivYield": 0, "AnnualDivJPY": 0
            })
            
    progress_bar.empty()
    
    if error_logs:
        with st.expander("⚠️ データ取得警告", expanded=False):
            st.write(error_logs)
            
    avg_score = total_score / analyzed_count if analyzed_count > 0 else 50
    return pd.DataFrame(results), avg_score

# --- メイン処理 ---
if uploaded_file is not None:
    df_raw = load_portfolio_csv(uploaded_file)
    
    if df_raw is not None:
        if "PositionValue" in df_raw.columns:
            df_raw["PositionValue"] = pd.to_numeric(df_raw["PositionValue"], errors='coerce').fillna(0)
            df_raw = df_raw[df_raw["PositionValue"] > 0]
        else:
            st.error("CSVエラー: PositionValue列がありません")
            st.stop()

        if "Quantity" in df_raw.columns:
            df_raw["Quantity"] = pd.to_numeric(df_raw["Quantity"], errors='coerce').fillna(0)
        else:
            df_raw["Quantity"] = 0

        if "CurrencyPrimary" not in df_raw.columns:
             df_raw["CurrencyPrimary"] = "JPY"
        
        market_data = get_market_data()
        usdjpy = market_data["USDJPY"]
        sp500_change = market_data["SP500_Change"]
        
        st.caption(f"ℹ️ 参考レート: 1ドル = {usdjpy:.2f} 円")
        
        def convert_to_jpy(row):
            currency = str(row.get("CurrencyPrimary", "JPY"))
            val = row["PositionValue"]
            if currency == "USD":
                return val * usdjpy
            return val
            
        df_raw["ValueJPY"] = df_raw.apply(convert_to_jpy, axis=1)
        total_assets = df_raw["ValueJPY"].sum()
        
        with st.spinner("AIが配当金(日本株は実績ベース)とトレンドを計算中..."):
            df_analyzed, portfolio_health_score = analyze_holdings(df_raw, usdjpy)
        
        df_merged = pd.merge(df_raw, df_analyzed[["Symbol", "Trend", "Score", "6M Change", "DivYield", "AnnualDivJPY"]], on="Symbol")
        
        if total_assets > 0:
            df_merged["Weight"] = (df_merged["ValueJPY"] / total_assets) * 100
            perf_weight = df_merged["Weight"] / 100
        else:
            df_merged["Weight"] = 0
            perf_weight = 0
        
        portfolio_performance = (df_merged["6M Change"] * perf_weight).sum()
        total_annual_dividend = df_merged["AnnualDivJPY"].sum()
        monthly_dividend = total_annual_dividend / 12
        
        if total_assets > 0:
            portfolio_yield = (total_annual_dividend / total_assets) * 100
        else:
            portfolio_yield = 0

        # --- 表示エリア ---
        st.divider()
        st.subheader("💰 配当金生活シミュレーション")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("年間 受取配当金 (予想)", f"¥{total_annual_dividend:,.0f}", f"利回り {portfolio_yield:.2f}%")
        with c2:
            st.metric("月間 不労所得", f"¥{monthly_dividend:,.0f}")
        with c3:
            if monthly_cost > 0:
                coverage = (monthly_dividend / monthly_cost) * 100
            else:
                coverage = 0
            st.metric("生活費カバー率", f"{coverage:.1f}%", f"目標: {monthly_cost:,.0f}円")
            
        st.write(f"**プーケット生活費 ({monthly_cost:,.0f}円) の {coverage:.1f}% を配当でカバーしています。**")
        st.progress(min(coverage / 100, 1.0))
        if coverage >= 100:
            st.balloons()
            st.success("🎉 FIRE達成！おめでとうございます！")
        
        st.divider()

        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = portfolio_health_score,
                title = {'text': "<b>ポートフォリオ健康度</b>"},
                gauge = {
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "rgba(0,0,0,0)"},
                    'steps': [
                        {'range': [0, 40], 'color': "#EF553B"},
                        {'range': [40, 60], 'color': "#FFA15A"},
                        {'range': [60, 100], 'color': "#00CC96"}
                    ],
                    'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': portfolio_health_score}
                }
            ))
            fig_gauge.update_layout(height=250, margin=dict(t=30, b=20, l=20, r=20))
            st.plotly_chart(fig_gauge, use_container_width=True)
            
        with col2:
            st.subheader("🆚 vs S&P500")
            diff = portfolio_performance - sp500_change
            res_text = "🏆 WIN" if diff > 0 else "💀 LOSE"
            res_color = "green" if diff > 0 else "red"
            st.metric("あなたの成績 (半年)", f"{portfolio_performance:+.2f}%")
            st.metric("S&P500 (半年)", f"{sp500_change:+.2f}%", delta=f"{diff:+.2f}%")
            st.markdown(f"**判定: :{res_color}[{res_text}]**")

        with col3:
            st.subheader("📊 資産サマリー")
            st.write(f"**総資産:** ¥{total_assets:,.0f}")
            if not df_merged.empty:
                max_pos = df_merged.loc[df_merged["Weight"].idxmax()]
                if max_pos["Weight"] > 20:
                    st.warning(f"⚠️ **集中:** {max_pos['Symbol']} ({max_pos['Weight']:.1f}%)")
                else:
                    st.success(f"✅ **分散:** OK")

        st.subheader("📝 保有銘柄 詳細リスト")
        display_df = df_merged[["Symbol", "ValueJPY", "Weight", "Trend", "Score", "6M Change", "DivYield", "AnnualDivJPY"]]
        
        def color_score(val):
            if val == "📈 上昇": return 'background-color: #d4edda; color: #155724' 
            if val == "📉 下落": return 'background-color: #f8d7da; color: #721c24' 
            return ''

        st.dataframe(
            display_df.style.applymap(color_score, subset=['Trend']),
            use_container_width=True,
            column_config={
                "ValueJPY": st.column_config.NumberColumn("評価額 (円)", format="¥%d"),
                "Weight": st.column_config.ProgressColumn(
                    "保有比率", 
                    format="%.1f%%", 
                    min_value=0, 
                    max_value=100
                ),
                "6M Change": st.column_config.NumberColumn("半年騰落率", format="%.2f%%"),
                "Score": st.column_config.NumberColumn("AIスコア", format="%d点"),
                "DivYield": st.column_config.NumberColumn("配当利回り", format="%.2f%%"),
                "AnnualDivJPY": st.column_config.NumberColumn("年間配当 (円)", format="¥%d"),
            }
        )

else:
    st.info("👆 CSVファイルをアップロードしてください。")