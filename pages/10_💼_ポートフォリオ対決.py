import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import ssl

# --- 🚨 Avoid SSL Errors ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ----------------------

st.set_page_config(page_title="ポートフォリオ対決", page_icon="💼", layout="wide")

st.title("💼 実ポートフォリオ vs 🤖 Agent Teams")
st.markdown("Interactive Brokersのポジションデータを分析")

# CSVアップロード
st.header("📂 IBポジションデータ読み込み")

uploaded_file = st.file_uploader("Interactive Brokers Daily Positions CSV", type="csv")

if uploaded_file:
    # CSV読み込み
    content = uploaded_file.read().decode('utf-8')
    lines = content.split('\n')
    
    # ポジション行を探す
    position_start = None
    for i, line in enumerate(lines):
        if 'Symbol' in line and 'Quantity' in line:
            position_start = i
            break
    
    if position_start is None:
        st.error("ポジションデータが見つかりません")
        st.stop()
    
    # ポジションデータを抽出
    position_lines = [line for line in lines[position_start+1:] if line.strip()]
    
    # DataFrameに変換
    positions_data = []
    for line in position_lines:
        parts = line.replace('"', '').split(',')
        if len(parts) >= 6:
            positions_data.append({
                'Account': parts[0],
                'Currency': parts[1],
                'Symbol': parts[2],
                'Quantity': parts[3],
                'MarkPrice': parts[4],
                'PositionValue': parts[5]
            })
    
    positions_df = pd.DataFrame(positions_data)
    
    # 数値型に変換
    positions_df['Quantity'] = pd.to_numeric(positions_df['Quantity'], errors='coerce')
    positions_df['MarkPrice'] = pd.to_numeric(positions_df['MarkPrice'], errors='coerce')
    positions_df['PositionValue'] = pd.to_numeric(positions_df['PositionValue'], errors='coerce')
    
    # 米国株のみ抽出
    us_stocks = positions_df[
        (positions_df['Currency'] == 'USD') & 
        (~positions_df['Symbol'].str.contains('.T', na=False))
    ].copy()
    
    if len(us_stocks) == 0:
        st.warning("米国株のポジションが見つかりません")
        st.stop()
    
    # サマリー表示
    st.success(f"✅ {len(us_stocks)}銘柄の米国株を検出")
    
    total_value = us_stocks['PositionValue'].sum()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("米国株総額", f"${total_value:,.2f}")
    with col2:
        st.metric("保有銘柄数", len(us_stocks))
    with col3:
        max_position = us_stocks.loc[us_stocks['PositionValue'].idxmax()]
        st.metric("最大ポジション", f"{max_position['Symbol']} (${max_position['PositionValue']:,.0f})")
    
    # 現在価格・セクター情報取得
    st.subheader("📊 保有ポジション詳細")
    
    enriched_data = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, (i, row) in enumerate(us_stocks.iterrows()):
        ticker = row['Symbol']
        progress = (idx + 1) / len(us_stocks)
        progress_bar.progress(progress)
        status_text.text(f"取得中... {ticker} ({idx+1}/{len(us_stocks)})")
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            current_price = info.get('currentPrice', row['MarkPrice'])
            current_value = row['Quantity'] * current_price
            
            enriched_data.append({
                'Symbol': ticker,
                'Shares': row['Quantity'],
                'Avg Cost': row['MarkPrice'],
                'Current Price': current_price,
                'Value': current_value,
                'P/L': current_value - row['PositionValue'],
                'P/L %': ((current_price - row['MarkPrice']) / row['MarkPrice']) * 100 if row['MarkPrice'] > 0 else 0,
                'Sector': info.get('sector', 'Unknown'),
                'Industry': info.get('industry', 'Unknown'),
                'Weight': (current_value / total_value) * 100
            })
        except Exception as e:
            enriched_data.append({
                'Symbol': ticker,
                'Shares': row['Quantity'],
                'Avg Cost': row['MarkPrice'],
                'Current Price': row['MarkPrice'],
                'Value': row['PositionValue'],
                'P/L': 0,
                'P/L %': 0,
                'Sector': 'Unknown',
                'Industry': 'Unknown',
                'Weight': (row['PositionValue'] / total_value) * 100
            })
    
    progress_bar.empty()
    status_text.empty()
    
    enriched_df = pd.DataFrame(enriched_data)
    
    # ポジション一覧
    st.dataframe(
        enriched_df.style.format({
            'Shares': '{:.2f}',
            'Avg Cost': '${:.2f}',
            'Current Price': '${:.2f}',
            'Value': '${:,.2f}',
            'P/L': '${:,.2f}',
            'P/L %': '{:.2f}%',
            'Weight': '{:.1f}%'
        }).background_gradient(subset=['P/L %'], cmap='RdYlGn', vmin=-20, vmax=20),
        use_container_width=True,
        height=400
    )
    
    # チャート表示
    tab1, tab2, tab3 = st.tabs(["セクター配分", "Top 10", "P/L分析"])
    
    with tab1:
        st.subheader("📈 セクター配分")
        
        sector_allocation = enriched_df.groupby('Sector').agg({
            'Value': 'sum',
            'Symbol': 'count'
        }).reset_index()
        sector_allocation.columns = ['Sector', 'Value', 'Count']
        sector_allocation['Percentage'] = (sector_allocation['Value'] / total_value) * 100
        sector_allocation = sector_allocation.sort_values('Value', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(
                sector_allocation,
                values='Value',
                names='Sector',
                title='セクター配分（金額ベース）'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig2 = px.bar(
                sector_allocation,
                x='Sector',
                y='Value',
                color='Sector',
                title='セクター別評価額'
            )
            st.plotly_chart(fig2, use_container_width=True)
    
    with tab2:
        st.subheader("🏆 Top 10 ポジション")
        
        top10 = enriched_df.nlargest(10, 'Value')
        
        fig3 = px.bar(
            top10,
            x='Symbol',
            y='Value',
            color='Sector',
            title='Top 10 保有銘柄',
            text='Value'
        )
        fig3.update_traces(texttemplate='$%{text:.2s}', textposition='outside')
        st.plotly_chart(fig3, use_container_width=True)
    
    with tab3:
        st.subheader("💰 損益分析")
        
        total_pl = enriched_df['P/L'].sum()
        avg_pl_pct = enriched_df['P/L %'].mean()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("総損益", f"${total_pl:,.2f}", delta=f"{avg_pl_pct:.2f}%")
        with col2:
            winners = len(enriched_df[enriched_df['P/L'] > 0])
            st.metric("勝率", f"{(winners/len(enriched_df))*100:.1f}%", delta=f"{winners}/{len(enriched_df)}")
        
        # P/Lチャート
        fig4 = px.bar(
            enriched_df.sort_values('P/L', ascending=True),
            x='P/L',
            y='Symbol',
            orientation='h',
            color='P/L',
            color_continuous_scale=['red', 'yellow', 'green'],
            title='銘柄別損益'
        )
        st.plotly_chart(fig4, use_container_width=True)
    
    # 次のステップ
    st.info("""
    **📌 現在の機能:**
    ✅ IBポジションデータの可視化
    ✅ セクター分析
    ✅ 損益分析
    
    **🚀 次のステップ（明日以降）:**
    - Agent Teamsによる自動分析
    - リアルタイム比較ダッシュボード
    - 仮想トレーディング
    - パフォーマンス追跡
    """)
    
    # データエクスポート
    st.download_button(
        label="📥 分析結果をダウンロード (CSV)",
        data=enriched_df.to_csv(index=False),
        file_name=f"portfolio_analysis_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

else:
    st.info("👆 Interactive BrokersのポジションCSVをアップロードしてください")
    
    st.markdown("""
    **📋 対応フォーマット:**
    - Interactive Brokers Flex Query
    - Daily Positions CSV
    
    **📝 CSVの取得方法:**
    1. IB Portal にログイン
    2. Reports → Flex Queries
    3. Daily Positions を選択
    4. CSVダウンロード
    """)
