import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import ssl
import json
import requests

# --- 🚨 通信エラー回避 ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ----------------------

# ページ設定
st.set_page_config(page_title="海運サイクル", page_icon="🚢", layout="wide")
st.title("海運サイクル & バルチック指数 🚢")
st.markdown("鉄鉱石や穀物を運ぶ「バラ積み船」の運賃指数（BDI）と、日本の海運株の連動性をチェックします。")


# --- AI要約機能 ---
def call_shipping_ai(df_current, df_chart):
    """海運・バルチック指数データをClaude APIで分析"""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        st.error("ANTHROPIC_API_KEYが設定されていません")
        return None

    data_text = "## 海運・バルチック指数データ\n\n"
    for _, row in df_current.iterrows():
        price_str = f"${row['Price']:.2f}" if "BDRY" in row['Name'] else f"¥{row['Price']:,.0f}"
        diff = row['Price'] - row['PrevPrice']
        data_text += f"- {row['Name']}: 価格={price_str}, 前日比={diff:+.2f}, トレンド={row['Trend']}, MA50={'上' if row['Price'] > row['MA50'] else '下'}\n"

    if not df_chart.empty:
        data_text += "\n## 過去1年パフォーマンス (1年前=100)\n"
        latest = df_chart.iloc[-1]
        earliest = df_chart.iloc[0]
        for col in df_chart.columns:
            data_text += f"- {col}: 現在={latest[col]:.1f}, 1年前=100, 変動={latest[col]-100:+.1f}%\n"
        # 直近1ヶ月の動き
        if len(df_chart) > 20:
            month_ago = df_chart.iloc[-20]
            data_text += "\n## 直近1ヶ月の変化\n"
            for col in df_chart.columns:
                chg = latest[col] - month_ago[col]
                data_text += f"- {col}: {chg:+.1f}%\n"

    system_prompt = """あなたは世界最大級の海運ヘッジファンドで20年の経験を持つシニアポートフォリオマネージャーです。
バルチック海運指数(BDI)と日本海運株を専門としています。

【重要】現在の日付は2026年2月です。全ての予測・見通しは2026年2月時点からの未来について述べてください。

提供されたデータを分析し、以下のJSON形式で回答してください。
ファンドの投資委員会に提出するレポートのように、具体的な数値と因果関係を明確にしてください。

【分析ルール】
1. 必ず具体的な数値を引用（BDRYの価格、各社株価、変動率）
2. バルチック指数と海運株の連動性・乖離を分析
3. 世界貿易・マクロ経済との関連を踏まえる
4. 季節性（穀物輸送シーズン、中国鉄鉱石需要）も考慮
5. データにない事実を捏造しない

{
    "cycle_position": {
        "total_stages": 5,
        "current_stage": 3,
        "stage_name": "現在のステージ名",
        "stages_map": [
            {"stage": 1, "name": "運賃底打ち・船腹過剰", "description": "BDI低迷、船会社赤字、スクラップ増"},
            {"stage": 2, "name": "運賃回復・需要増加", "description": "中国需要増、穀物輸送増で運賃上昇開始"},
            {"stage": 3, "name": "運賃高騰・好況", "description": "船腹不足、運賃急騰、海運株高配当"},
            {"stage": 4, "name": "ピークアウト・新造船投入", "description": "新造船増加で供給圧力、運賃反落"},
            {"stage": 5, "name": "運賃下落・供給過剰", "description": "船腹過剰で運賃低迷、減配リスク"}
        ],
        "evidence": "現在のステージだと判断した根拠を2-3文で。具体数値必須"
    },
    "current_diagnosis": {
        "headline": "1行の見出し",
        "summary": "現在の海運市況を4-5文で詳細に説明。BDRY価格、各社株価を引用",
        "bdi_vs_stocks": "バルチック指数と海運株の連動性/乖離の分析を2文で",
        "macro_driver": "現在の運賃を動かしている主なマクロ要因を2文で"
    },
    "forward_scenarios": {
        "base_case": {
            "probability": 50,
            "title": "メインシナリオのタイトル",
            "next_3months": "今後3ヶ月に起きること",
            "next_6months": "その後3-6ヶ月に起きること",
            "next_12months": "6-12ヶ月後の状態",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "bull_case": {
            "probability": 25,
            "title": "楽観シナリオのタイトル",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        },
        "bear_case": {
            "probability": 25,
            "title": "悲観シナリオのタイトル",
            "narrative": "何が起きて、どう展開して、結果どうなるか。3-4文",
            "triggers": ["実現条件1", "条件2"],
            "investment_action": "具体的な投資アクション"
        }
    },
    "stock_positioning": [
        {
            "company": "企業名",
            "status": "最有望/有望/中立/注意/危険",
            "assessment": "株価とBDIの連動性、配当利回り、バリュエーションの評価を1-2文",
            "action": "買い/保有/売り/様子見"
        }
    ],
    "seasonal_outlook": {
        "current_season": "現在の季節要因とその影響",
        "next_event": "次に来る季節イベントと予想される影響"
    },
    "risk_monitor": {
        "watch_items": ["監視すべき指標やイベント1", "2", "3"],
        "next_inflection": "次の転換点はいつ・何がきっかけか"
    }
}"""

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": data_text}]
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=90
        )
        response.raise_for_status()
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
        return json.loads(text.strip())
    except Exception as e:
        st.error(f"AI分析エラー: {e}")
        return None


# キャッシュ設定
@st.cache_data(ttl=3600)
def get_shipping_data():
    # BDRY: バルチック指数に連動するETF（指数の代用として優秀）
    tickers = {
        "BDRY (バルチックETF)": "BDRY",
        "日本郵船 (9101)": "9101.T",
        "商船三井 (9104)": "9104.T",
        "川崎汽船 (9107)": "9107.T"
    }
    
    data_list = []
    hist_data = {}
    
    progress_text = "海運データを取得中..."
    my_bar = st.progress(0, text=progress_text)
    
    count = 0
    total = len(tickers)

    for name, ticker in tickers.items():
        try:
            count += 1
            my_bar.progress(count / total, text=f"{name} のデータを取得中...")
            
            t = yf.Ticker(ticker)
            
            # 1年分のデータ取得
            hist = t.history(period="1y")
            
            if not hist.empty:
                # 最新価格
                price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else price
                
                # トレンド判定 (50日移動平均線)
                ma50 = hist['Close'].rolling(window=50).mean().iloc[-1]
                if price > ma50:
                    trend = "上昇 📈"
                    trend_color = "normal" # 緑
                else:
                    trend = "下落 📉"
                    trend_color = "inverse" # 赤
                
                # チャート用データ（正規化：1年前を100とする）
                # 最初の有効な値で正規化する
                first_valid_price = hist['Close'].dropna().iloc[0]
                norm_price = (hist['Close'] / first_valid_price) * 100
                hist_data[name] = norm_price

                data_list.append({
                    "Name": name,
                    "Price": price,
                    "PrevPrice": prev_price,
                    "Trend": trend,
                    "TrendColor": trend_color,
                    "MA50": ma50
                })
        except:
            pass
            
    my_bar.empty()
    
    # チャート用DataFrame作成と整形
    if hist_data:
        df_chart = pd.DataFrame(hist_data)
        # 【重要】データの隙間を埋める（前日データを引き継ぐ）ことで線を繋げる
        df_chart = df_chart.ffill()
        # 全銘柄のデータが揃う最初の時点までカットして、スタートラインを合わせる
        df_chart = df_chart.dropna()
    else:
        df_chart = pd.DataFrame()
        
    return pd.DataFrame(data_list), df_chart

# --- メイン処理 ---
df, df_chart = get_shipping_data()

if df.empty:
    st.error("データの取得に失敗しました。")
else:
    # 1. 重要指標カード (BDRY)
    st.subheader("🌊 バルチック海運指数のトレンド (BDRY ETF)")
    
    # BDRYの行を取得
    try:
        bdry_row = df[df["Name"].str.contains("BDRY")].iloc[0]
        diff = bdry_row["Price"] - bdry_row["PrevPrice"]
        trend_color = bdry_row["TrendColor"]
        trend_text = bdry_row["Trend"]
    except:
        # BDRYが取れなかった場合のダミー
        bdry_row = None
        diff = 0
        trend_color = "off"
        trend_text = "不明"

    col1, col2 = st.columns([1, 3])
    with col1:
        if bdry_row is not None:
            st.metric(
                label="BDRY (バルチック指数連動)",
                value=f"${bdry_row['Price']:.2f}",
                delta=f"{diff:+.2f}",
                delta_color=trend_color
            )
            st.caption(f"トレンド判定: **{trend_text}**")
            
            if trend_color == "normal":
                st.success("✅ 運賃上昇中：海運株に追い風")
            elif trend_color == "inverse":
                st.error("⚠️ 運賃下落中：海運株に逆風")
        else:
             st.warning("BDRYデータの取得に失敗しました")

    with col2:
        st.info("💡 **バルチック指数 (BDI)** とは？\n\n鉄鉱石・石炭・穀物などを運ぶ船の運賃価格。**「世界経済の体温計」** とも呼ばれ、これが上がると世界中の物流が活発（好景気）であることを示します。海運株の利益に直結します。")

    st.markdown("---")

    # 2. 日本の海運株カード
    st.subheader("🇯🇵 日本の大手海運 3社")
    cols = st.columns(3)
    
    # BDRY以外のデータ（日本株）を表示
    jp_stocks = df[~df["Name"].str.contains("BDRY")]
    
    for i, (index, row) in enumerate(jp_stocks.iterrows()):
        with cols[i % 3]:
            diff = row["Price"] - row["PrevPrice"]
            st.metric(
                label=row["Name"],
                value=f"¥{row['Price']:,.0f}",
                delta=f"{diff:+,.0f}",
                delta_color=row["TrendColor"]
            )
            st.caption(f"トレンド: {row['Trend']}")

    # 3. 比較チャート（綺麗バージョン）
    st.subheader("📈 株価連動チャート (過去1年・比較)")
    st.markdown("「バルチック指数（青線）」が上がるとき、日本の海運株も遅れて上がることが多いです。")
    
    if not df_chart.empty:
        # Plotlyで描画 (デザイン調整)
        fig = px.line(
            df_chart, 
            x=df_chart.index, 
            y=df_chart.columns,
            title="相対パフォーマンス比較 (1年前 = 100)"
        )
        # レイアウトをスタイリッシュに
        fig.update_layout(
            hovermode="x unified", 
            yaxis_title="騰落率 (スタート=100)",
            xaxis_title="日付",
            legend_title="銘柄",
            plot_bgcolor="rgba(0,0,0,0)", # 背景透明化
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False), # X軸グリッドなし
            yaxis=dict(showgrid=True, gridcolor="#444") # Y軸グリッド薄く
        )
        # 線を少し太くする
        fig.update_traces(line=dict(width=2))
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("チャート表示用のデータが不足しています。")
    

    # 5. AI要約セクション
    st.markdown("---")
    st.subheader("🤖 AI海運サイクル分析")
    st.caption("グローバル海運ファンドマネージャー視点の分析")
    
    if st.button("🧠 AIで海運サイクルを分析", use_container_width=True):
        with st.spinner("🔄 Claude AIが海運市況を分析中..."):
            ai_result = call_shipping_ai(df, df_chart)
        
        if ai_result:
            # --- サイクルポジション ---
            cp = ai_result.get("cycle_position", {})
            current = cp.get("current_stage", 1)
            total = cp.get("total_stages", 5)
            stage_name = cp.get("stage_name", "")
            stages = cp.get("stages_map", [])
            
            st.markdown("### 📍 海運サイクル 現在地")
            
            cols_cycle = st.columns(total)
            for i, stage in enumerate(stages):
                with cols_cycle[i]:
                    is_current = (i + 1 == current)
                    if is_current:
                        st.markdown(f"""<div style="background: linear-gradient(135deg, #1a5276, #2e86c1); padding: 10px; border-radius: 8px; text-align: center; border: 2px solid #3498db;">
                            <div style="font-size: 1.4em; font-weight: bold;">🚢</div>
                            <div style="font-size: 0.75em; font-weight: bold; color: #fff;">Stage {i+1}</div>
                            <div style="font-size: 0.65em; color: #ddd;">{stage.get('name', '')}</div>
                        </div>""", unsafe_allow_html=True)
                    else:
                        opacity = "0.4" if abs(i + 1 - current) > 1 else "0.7"
                        st.markdown(f"""<div style="background: #262730; padding: 10px; border-radius: 8px; text-align: center; opacity: {opacity}; border: 1px solid #41444C;">
                            <div style="font-size: 1.2em;">{"✅" if i + 1 < current else "⬜"}</div>
                            <div style="font-size: 0.7em; color: #888;">Stage {i+1}</div>
                            <div style="font-size: 0.6em; color: #888;">{stage.get('name', '')}</div>
                        </div>""", unsafe_allow_html=True)
            
            progress_pct = current / total
            st.progress(progress_pct, text=f"サイクル進行度: Stage {current}/{total} - {stage_name}")
            
            evidence = cp.get("evidence", "")
            if evidence:
                st.info(f"📋 **判断根拠:** {evidence}")
            
            st.markdown("---")
            
            # --- 現状診断 ---
            diag = ai_result.get("current_diagnosis", {})
            st.markdown(f"### 🔍 現状診断: {diag.get('headline', '')}")
            st.markdown(diag.get("summary", ""))
            
            col_bdi, col_macro = st.columns(2)
            with col_bdi:
                st.markdown("**🔗 BDI vs 海運株:**")
                st.markdown(diag.get("bdi_vs_stocks", ""))
            with col_macro:
                st.markdown("**🌍 マクロドライバー:**")
                st.markdown(diag.get("macro_driver", ""))
            
            st.markdown("---")
            
            # --- シナリオ分析 ---
            st.markdown("### 🔮 フォワードシナリオ分析")
            
            scenarios = ai_result.get("forward_scenarios", {})
            
            base = scenarios.get("base_case", {})
            st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #3498db; margin-bottom: 15px;">
                <h4 style="color: #3498db; margin-top: 0;">🚢 メインシナリオ ({base.get('probability', 50)}%): {base.get('title', '')}</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px; color: #888; width: 120px;">3ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_3months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">6ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_6months', '')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">12ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_12months', '')}</td></tr>
                </table>
                <p style="color: #3498db; margin-bottom: 0;">💼 <b>アクション:</b> {base.get('investment_action', '')}</p>
            </div>""", unsafe_allow_html=True)
            
            col_bull, col_bear = st.columns(2)
            
            bull = scenarios.get("bull_case", {})
            with col_bull:
                st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B; height: 100%;">
                    <h4 style="color: #09AB3B; margin-top: 0;">🟢 楽観 ({bull.get('probability', 25)}%): {bull.get('title', '')}</h4>
                    <p style="color: #ddd; font-size: 0.9em;">{bull.get('narrative', '')}</p>
                    <p style="color: #09AB3B; font-size: 0.85em; margin-bottom: 0;">💼 {bull.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            bear = scenarios.get("bear_case", {})
            with col_bear:
                st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B; height: 100%;">
                    <h4 style="color: #FF4B4B; margin-top: 0;">🔴 悲観 ({bear.get('probability', 25)}%): {bear.get('title', '')}</h4>
                    <p style="color: #ddd; font-size: 0.9em;">{bear.get('narrative', '')}</p>
                    <p style="color: #FF4B4B; font-size: 0.85em; margin-bottom: 0;">💼 {bear.get('investment_action', '')}</p>
                </div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- 銘柄ポジショニング ---
            st.markdown("### 🏢 銘柄別ポジショニング")
            companies = ai_result.get("stock_positioning", [])
            if companies:
                for comp in companies:
                    status = comp.get("status", "")
                    emoji_map = {"最有望": "🟢", "有望": "🟢", "中立": "🟡", "注意": "🟠", "危険": "🔴"}
                    action_map = {"買い": "🟢", "保有": "🟡", "売り": "🔴", "様子見": "⚪"}
                    e = emoji_map.get(status, "⚪")
                    a = action_map.get(comp.get("action", ""), "⚪")
                    st.markdown(f"**{e} {comp.get('company', '')}** | 判定: **{status}** | アクション: {a} **{comp.get('action', '')}**")
                    st.caption(f"📊 {comp.get('assessment', '')}")
            
            st.markdown("---")
            
            # --- 季節性 ---
            seasonal = ai_result.get("seasonal_outlook", {})
            if seasonal:
                st.markdown("### 🗓️ 季節性分析")
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    st.info(f"📅 **現在の季節要因:** {seasonal.get('current_season', '')}")
                with col_s2:
                    st.warning(f"⏭️ **次のイベント:** {seasonal.get('next_event', '')}")
            
            st.markdown("---")
            
            # --- リスクモニター ---
            rm = ai_result.get("risk_monitor", {})
            st.markdown("### ⚠️ リスクモニター")
            watch = rm.get("watch_items", [])
            if watch:
                for w in watch:
                    st.markdown(f"- 👁️ {w}")
            inflection = rm.get("next_inflection", "")
            if inflection:
                st.error(f"🔄 **次の転換点:** {inflection}")


    # 4. 凡例
    st.markdown("""
    <div style="background-color: #262730; padding: 15px; border-radius: 5px; border: 1px solid #41444C;">
        <b>💡 投資のヒント</b>
        <ul>
            <li><b>BDRY（青）が底打ちして上昇</b> ➡ 海運株の買いシグナル</li>
            <li><b>BDRYが急落</b> ➡ 海運株の売りシグナル（利益確定の目安）</li>
            <li>日本の海運株は配当利回りが高いため、権利落ち日（3月・9月）前後に大きく動くことがあります。</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)