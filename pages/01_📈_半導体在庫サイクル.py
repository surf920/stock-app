import streamlit as st
import pandas as pd
import yfinance as yf
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

# ページ設定
st.set_page_config(page_title="半導体在庫サイクル", page_icon="📈", layout="wide")
st.title("半導体サイクル & 在庫トラッカー 2026 🚀")
st.markdown("現在値だけでなく、**「在庫が増えているか（悪化）」**、**「減っているか（改善）」**のトレンドを確認してください。")

# キャッシュ設定
@st.cache_data(ttl=3600)
def get_semiconductor_data():
    tickers = {
        "NVIDIA": "NVDA", "Micron": "MU", "TSMC": "TSM", 
        "Samsung": "005930.KS", "Intel": "INTC", "AMD": "AMD",
        "Qualcomm": "QCOM", "Texas Instruments": "TXN"
    }
    
    current_data_list = []
    doi_history_list = [] # 過去の推移用データ
    stock_history_list = {} 
    
    # プログレスバー
    progress_text = "財務データと過去のトレンドを取得中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(tickers)

    for name, ticker in tickers.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} のデータを分析中...")
            
            stock = yf.Ticker(ticker)
            
            # 1. 株価チャート用データ (1ヶ月)
            hist = stock.history(period="1mo")
            if not hist.empty:
                norm_price = (hist['Close'] / hist['Close'].iloc[0]) * 100
                stock_history_list[name] = norm_price
                price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else price
            else:
                price = None; prev_price = None
            
            # 2. 財務データ（過去のDOI推移も取得）
            current_doi = None
            current_inv = None
            
            try:
                # 四半期ごとのデータを取得
                q_bs = stock.quarterly_balance_sheet
                q_fin = stock.quarterly_financials
                
                if not q_bs.empty and not q_fin.empty:
                    # 共通の日付（カラム）を探す
                    valid_dates = q_bs.columns.intersection(q_fin.columns)
                    
                    # 各四半期のDOIを計算してリストに追加
                    for date in valid_dates:
                        try:
                            inv_val = q_bs.loc["Inventory", date] if "Inventory" in q_bs.index else 0
                            
                            cogs = 0
                            if "Cost Of Revenue" in q_fin.index:
                                cogs = q_fin.loc["Cost Of Revenue", date]
                            elif "Cost Of Goods Sold" in q_fin.index:
                                cogs = q_fin.loc["Cost Of Goods Sold", date]
                            
                            if cogs > 0:
                                doi_val = (inv_val / cogs) * 90
                                # 推移データに追加
                                doi_history_list.append({
                                    "Company": name,
                                    "Date": date,
                                    "DOI": doi_val
                                })
                                
                                # 最新の日付なら現在値として保持
                                if date == valid_dates[0]: # 列の最初が最新
                                    current_doi = doi_val
                                    current_inv = inv_val
                        except:
                            pass
                            
            except:
                pass

            current_data_list.append({
                "Company": name, "Ticker": ticker,
                "Price": price, "PrevPrice": prev_price,
                "DOI": current_doi, "Inventory": current_inv
            })
            
        except Exception:
            pass
            
    my_bar.empty()
    
    # DataFrame化
    df_current = pd.DataFrame(current_data_list)
    df_doi_hist = pd.DataFrame(doi_history_list)
    df_stock_hist = pd.DataFrame(stock_history_list) if stock_history_list else pd.DataFrame()
    
    return df_current, df_doi_hist, df_stock_hist

# --- メイン処理 ---
df, df_doi_hist, df_stock_chart = get_semiconductor_data()

if df.empty:
    st.warning("データが取得できませんでした。")
else:
    # 1. 上部カードセクション
    st.subheader("🔥 主要企業の在庫状況 (最新)")
    cols = st.columns(4)
    for index, row in df.iterrows():
        with cols[index % 4]:
            p_str = f"${row['Price']:.2f}" if row['Price'] else "N/A"
            
            # --- 色分け & トレンド判定 ---
            trend_arrow = ""
            if row['DOI']:
                doi_val = row['DOI']
                
                # 直近のトレンドを確認（もし履歴があれば）
                if not df_doi_hist.empty:
                    company_hist = df_doi_hist[df_doi_hist["Company"] == row["Company"]].sort_values("Date")
                    # ここがエラーのあった箇所です。修正済みです。
                    if len(company_hist) >= 2:
                        prev_doi = company_hist.iloc[-2]["DOI"] # 前回のDOI
                        if doi_val > prev_doi:
                            trend_arrow = " ↗︎(増)" # 悪化
                        else:
                            trend_arrow = " ↘︎(減)" # 改善

                if doi_val > 120:
                    delta_msg = f"在庫過多{trend_arrow}"; color = "inverse" # 赤
                elif doi_val < 80:
                    delta_msg = f"在庫不足{trend_arrow}"; color = "normal" # 緑
                else:
                    delta_msg = f"適正{trend_arrow}"; color = "off"
                
                doi_str = f"{doi_val:.1f}日"
            else:
                doi_str = "-"
                delta_msg = None
                color = "off"
            
            st.metric(label=row['Company'], value=doi_str, delta=delta_msg, delta_color=color)
            st.caption(f"株価: {p_str}")
            st.markdown("---")

    # 2. 在庫サイクルの推移チャート
    st.subheader("📊 在庫サイクル (DOI) の推移")
    st.markdown("線の向きに注目してください。**右肩下がり（↘︎）なら在庫がはけている良い兆候**です。")
    
    if not df_doi_hist.empty:
        # 日付でソート
        df_doi_hist = df_doi_hist.sort_values("Date")
        
        # 折れ線グラフ
        fig_doi = px.line(
            df_doi_hist, 
            x="Date", 
            y="DOI", 
            color="Company",
            markers=True,
            title="過去1年の在庫日数 (DOI) の変化"
        )
        # 危険ラインと好機ラインを描画
        fig_doi.add_hline(y=120, line_dash="dot", line_color="red", annotation_text="警戒ライン (120日)")
        fig_doi.add_hline(y=80, line_dash="dot", line_color="green", annotation_text="好機ライン (80日)")
        
        st.plotly_chart(fig_doi, use_container_width=True)
    else:
        st.info("過去の財務データが取得できませんでした。")

    # 3. 株価パフォーマンス
    with st.expander("📈 株価の推移を見る (過去1ヶ月)", expanded=False):
        if not df_stock_chart.empty:
            fig_stock = px.line(df_stock_chart, x=df_stock_chart.index, y=df_stock_chart.columns)
            st.plotly_chart(fig_stock, use_container_width=True)

    # 4. データテーブル
    st.subheader("📊 詳細データ一覧")
    
    # 色付けロジック
    def highlight_doi(val):
        if val is None or pd.isna(val): return None
        if val > 120: return 'color: #FF4B4B; font-weight: bold;'
        elif val < 80: return 'color: #09AB3B; font-weight: bold;'
        return None

    # 並び替え
    df_display = df.sort_values(by="DOI", ascending=False)[['Company', 'Price', 'DOI', 'Inventory']]
    
    # テーブル表示
    st.dataframe(
        df_display.style.map(highlight_doi, subset=['DOI']).format({
            "Price": "${:.2f}", 
            "DOI": "{:.1f} 日", 
            "Inventory": "${:.2e}"
        }),
        hide_index=True,
        use_container_width=True
    )

    # 凡例（Markdownで安全に表示）
    st.markdown("""
    <div style="background-color: #262730; padding: 15px; border-radius: 5px; border: 1px solid #41444C;">
        <b>💡 チャートの見方</b>
        <ul>
            <li><b>グラフが右肩上がり (↗︎)</b>: 在庫が積み上がっています。売れ残りリスク上昇（警戒）。</li>
            <li><b>グラフが右肩下がり (↘︎)</b>: 在庫が消化されています。需要回復のサイン（好感）。</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)