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
st.set_page_config(page_title="セクターローテーション", page_icon="🔄", layout="wide")
st.title("セクターローテーション & 景気サイクル 🔄")
st.markdown("「資金はどこへ向かっているか？」 米国株11セクターの強弱を分析し、**現在の景気サイクル（回復・好況・後退・不況）** を読み解きます。")

# セクター定義（SPDR ETFを使用）
SECTORS = {
    "テクノロジー (XLK)": "XLK",
    "一般消費財 (XLY)": "XLY",     # Amazon, Teslaなど（好況で強い）
    "通信サービス (XLC)": "XLC",   # Google, Metaなど
    "金融 (XLF)": "XLF",           # 金利上昇で強い
    "資本財 (XLI)": "XLI",         # 工場・防衛
    "エネルギー (XLE)": "XLE",     # 原油高で強い
    "素材 (XLB)": "XLB",
    "ヘルスケア (XLV)": "XLV",     # 不況に強い
    "生活必需品 (XLP)": "XLP",     # 不況に強い（P&G, CocaCola）
    "公益事業 (XLU)": "XLU",       # 不況に強い（電力）
    "不動産 (XLRE)": "XLRE"
}

# キャッシュ設定
@st.cache_data(ttl=3600)
def get_sector_data(period="3mo"):
    data_list = []
    hist_data = {}
    
    progress_text = "セクターデータを分析中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(SECTORS)

    for name, ticker in SECTORS.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} を取得中...")
            
            t = yf.Ticker(ticker)
            # 指定期間のデータを取得
            hist = t.history(period=period)
            
            if not hist.empty:
                # パフォーマンス計算（期間騰落率）
                start_price = hist['Close'].iloc[0]
                end_price = hist['Close'].iloc[-1]
                change_pct = ((end_price / start_price) - 1) * 100
                
                # チャート用データ（正規化）
                norm_price = (hist['Close'] / start_price) * 100
                hist_data[name] = norm_price

                data_list.append({
                    "Sector": name,
                    "Ticker": ticker,
                    "Change": change_pct,
                    "Price": end_price
                })
        except:
            pass
            
    my_bar.empty()
    return pd.DataFrame(data_list), pd.DataFrame(hist_data)

# --- サイドバーで期間選択 ---
with st.sidebar:
    st.header("⚙️ 分析期間")
    period_opt = st.selectbox(
        "期間を選択", 
        ["1mo", "3mo", "6mo", "1y", "ytd"], 
        index=1,
        format_func=lambda x: {
            "1mo": "過去1ヶ月 (短期トレンド)",
            "3mo": "過去3ヶ月 (中期トレンド)", 
            "6mo": "過去6ヶ月 (長期トレンド)",
            "1y": "過去1年",
            "ytd": "年初来"
        }[x]
    )

# --- メイン処理 ---
df, df_chart = get_sector_data(period_opt)

if df.empty:
    st.error("データ取得失敗")
else:
    # 1. サイクル診断 (簡易ロジック)
    st.subheader("🤖 AI景気サイクル診断")
    
    # 上位3セクターと下位3セクターを抽出
    df_sorted = df.sort_values(by="Change", ascending=False)
    top_sectors = df_sorted.head(3)["Sector"].tolist()
    
    # 診断ロジック
    cycle_status = "不明"
    cycle_msg = ""
    cycle_color = "blue"
    
    # キーワード判定
    is_defensive_strong = any(s in str(top_sectors) for s in ["ヘルスケア", "生活必需品", "公益事業"])
    is_tech_strong = any(s in str(top_sectors) for s in ["テクノロジー", "一般消費財", "通信"])
    is_energy_strong = any(s in str(top_sectors) for s in ["エネルギー", "素材"])
    
    if is_tech_strong and not is_defensive_strong:
        cycle_status = "好況 (Early/Mid Cycle) 🚀"
        cycle_msg = "リスクオン相場です。投資家は成長を求めてテクノロジーや消費財を買っています。"
        cycle_color = "green"
    elif is_energy_strong:
        cycle_status = "インフレ / 後期 (Late Cycle) 🔥"
        cycle_msg = "景気サイクルの終盤、またはインフレ懸念があります。実物資産（エネルギー・素材）が強いです。"
        cycle_color = "orange"
    elif is_defensive_strong:
        cycle_status = "後退 / 防衛 (Recession Fear) 🛡️"
        cycle_msg = "リスクオフ相場です。投資家は不況を警戒し、ディフェンシブ銘柄（生活必需品・ヘルスケア）に逃げています。"
        cycle_color = "red"
    else:
        cycle_status = "循環物色 / 混在 🔄"
        cycle_msg = "明確なトレンドがなく、セクターが循環しています。"

    st.markdown(f"""
    <div style="padding: 15px; border-radius: 10px; border: 2px solid {cycle_color}; background-color: rgba(0,0,0,0.2);">
        <h3 style="color: {cycle_color}; margin:0;">現在のフェーズ: {cycle_status}</h3>
        <p style="margin-top: 10px;">{cycle_msg}</p>
        <p><b>現在の勝ち組セクター:</b> {', '.join([s.split(' ')[0] for s in top_sectors])}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # 2. パフォーマンスランキング (横棒グラフ)
    st.subheader(f"📊 セクター別パフォーマンス ({period_opt})")
    
    # 色分け（プラスは緑、マイナスは赤）
    df_sorted["Color"] = df_sorted["Change"].apply(lambda x: "#00CC96" if x >= 0 else "#EF553B")
    
    fig_bar = px.bar(
        df_sorted, 
        x="Change", 
        y="Sector", 
        orientation='h',
        text_auto='.2f',
        title="騰落率ランキング (%)"
    )
    fig_bar.update_traces(marker_color=df_sorted["Color"], textposition="outside")
    fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="騰落率 (%)")
    st.plotly_chart(fig_bar, use_container_width=True)

    # 3. 比較チャート
    st.subheader("📈 トレンド推移チャート")
    st.markdown("どのセクターが勢いよく伸びているか（角度）を確認してください。")
    
    if not df_chart.empty:
        # データ量が多いので、見やすくするために線は細めに
        fig_line = px.line(
            df_chart, 
            x=df_chart.index, 
            y=df_chart.columns,
            title="セクター相対比較 (開始日=100)"
        )
        fig_line.update_layout(hovermode="x unified", yaxis_title="正規化価格")
        st.plotly_chart(fig_line, use_container_width=True)

    # 4. セクター分類表
    with st.expander("📚 セクター分類の基礎知識 (クリックで開く)"):
        st.markdown("""
        | 分類 | セクター | 特徴 | 強い時期 |
        | :--- | :--- | :--- | :--- |
        | **シクリカル (景気敏感)** | **テクノロジー (XLK)**<br>**一般消費財 (XLY)**<br>**資本財 (XLI)**<br>**素材 (XLB)** | 景気が良いと業績が伸びる。<br>金利上昇には弱いことが多い。 | **不況からの回復期**<br>**好景気** |
        | **ディフェンシブ (安定)** | **ヘルスケア (XLV)**<br>**生活必需品 (XLP)**<br>**公益事業 (XLU)** | 不況でも薬や電気は使うため安定。<br>配当利回りが高い。 | **景気後退期**<br>**暴落時** |
        | **インフレヘッジ** | **エネルギー (XLE)**<br>**金融 (XLF)** | 原油高や金利上昇が利益になる。 | **景気過熱期 (インフレ)**<br>**利上げ局面** |
        """)