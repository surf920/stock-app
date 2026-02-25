import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import ssl

# --- 🚨 通信エラー回避 ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# ページ設定
st.set_page_config(page_title="DAI: 市場異常度指数", page_icon="🦁", layout="wide")
st.title("🦁 DAI: Derivative Anomaly Index")
st.markdown("市場の「不信感・金利・恐怖・歪み」を統合監視するプロ仕様ダッシュボード")

# キャッシュ設定
@st.cache_data(ttl=60)
def get_dai_data():
    tickers = {
        "HYG": "HYG", "LQD": "LQD",
        "TNX": "^TNX", "VIX": "^VIX", "SKEW": "^SKEW"
    }
    
    data_list = []
    
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1y")
            
            if not hist.empty:
                s = hist["Close"]
                s.name = name
                # ⚠️重要: タイムゾーンを削除して日付を強制的に合わせる
                s.index = s.index.tz_localize(None)
                data_list.append(s)
        except:
            pass
            
    if data_list:
        # データを結合し、欠損を前日の値で埋める
        df = pd.concat(data_list, axis=1)
        df = df.ffill().dropna()
        return df
    return pd.DataFrame()

df = get_dai_data()

# 安全な計算用関数
def safe_z(series):
    if series is None or len(series) < 5: return 0
    std = series.std()
    if std == 0: return 0
    return (series.iloc[-1] - series.mean()) / std

def safe_val(series):
    return series.iloc[-1] if series is not None and not series.empty else 0

if df.empty:
    st.error("⏳ データ取得中... 少し待ってからリロードしてください")
else:
    # --- 1. Credit Score (不信感) ---
    # 行を短く分割してエラーを防止
    has_lqd = "LQD" in df.columns
    has_hyg = "HYG" in df.columns
    
    if has_lqd and has_hyg:
        credit_ratio = df["LQD"] / df["HYG"]
        score_c = min(max(30 + safe_z(credit_ratio) * 25, 0), 100)
        val_c = safe_val(credit_ratio)
    else:
        credit_ratio = pd.Series(dtype=float)
        score_c, val_c = 0, 0

    # --- 2. Rate Score (金利) ---
    if "TNX" in df.columns:
        score_r = min(max(30 + safe_z(df["TNX"]) * 20, 0), 100)
        val_r = safe_val(df["TNX"])
    else:
        score_r, val_r = 0, 0

    # --- 3. Volatility Score (恐怖) ---
    if "VIX" in df.columns:
        vix = safe_val(df["VIX"])
        score_v = min((vix / 50) * 100, 100)
    else:
        vix, score_v = 0, 0
    
    # --- 4. Skew Score (歪み) ---
    if "SKEW" in df.columns:
        skew = safe_val(df["SKEW"])
        score_s = min(max((skew - 100) * 2, 0), 100)
    else:
        skew, score_s = 0, 0

    # 🏆 DAI 総合指数
    dai = (score_c * 0.3) + (score_r * 0.25) + (score_v * 0.25) + (score_s * 0.2)

    # --- 表示エリア ---
    c_main, c_detail = st.columns([1, 2])
    
    with c_main:
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=dai,
            title={'text': "<b>DAI 総合異常度</b>"},
            gauge={
                'axis': {'range': [None, 100]},
                'steps': [
                    {'range': [0, 40], 'color': "#00CC96"},
                    {'range': [40, 60], 'color': "#FFA15A"},
                    {'range': [60, 80], 'color': "#FF6692"},
                    {'range': [80, 100], 'color': "#EF553B"}
                ],
                'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': dai}
            }
        ))
        fig.update_layout(height=300, margin=dict(l=20,r=20,t=50,b=20))
        st.plotly_chart(fig, use_container_width=True)
        
        if dai < 40: st.success("✅ 市場は正常です")
        elif dai < 60: st.warning("⚠️ 緊張感が出ています")
        else: st.error("🔥 警戒・危険レベルです")

    with c_detail:
        st.subheader("🔍 詳細スコア (0-100)")
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        
        def show_gauge(title, val, raw_text):
            st.markdown(f"**{title}**")
            st.progress(int(min(max(val, 0), 100)) / 100)
            st.caption(f"{raw_text}")

        with c1: show_gauge("🏦 Credit (信用)", score_c, f"LQD/HYG Ratio: {val_c:.2f}")
        with c2: show_gauge("📈 Rate (金利)", score_r, f"US 10Y: {val_r:.2f}%")
        with c3: show_gauge("📉 Volatility (恐怖)", score_v, f"VIX: {vix:.2f}")
        with c4: show_gauge("🦢 Skew (歪み)", score_s, f"SKEW: {skew:.2f}")

    st.markdown("---")
    st.subheader("📊 時系列チャート")
    
    t1, t2 = st.tabs(["信用リスク (LQD/HYG)", "金利 & 恐怖 (TNX/VIX)"])
    with t1:
        if not credit_ratio.empty:
            st.caption("上昇すると「信用リスク（不信感）」が高まっています")
            st.line_chart(credit_ratio)
        else:
            st.info("データ待機中...")
            
    with t2:
        if "TNX" in df.columns and "VIX" in df.columns:
            st.caption("金利(TNX)と恐怖指数(VIX)の推移")
            st.line_chart(pd.DataFrame({"US 10Y": df["TNX"], "VIX/10": df["VIX"]/10}))

    # --- AIデリバティブ分析セクション ---
    st.markdown("---")
    st.subheader("🤖 AIデリバティブ・リスク分析")
    st.caption("デリバティブ専門リスクマネージャー視点の分析")
    
    if st.button("🧠 AIで市場ストレスを分析", use_container_width=True):
        with st.spinner("🔄 Claude AIがデリバティブ市場を分析中..."):
            ai_result = call_dai_ai(dai, score_c, score_r, score_v, score_s, val_c, val_r, vix, skew)
        
        if ai_result:
            cp = ai_result.get("cycle_position", {})
            current = cp.get("current_stage", 1)
            total = cp.get("total_stages", 5)
            stage_name = cp.get("stage_name", "")
            stages = cp.get("stages_map", [])
            st.markdown("### 📍 ボラティリティサイクル 現在地")
            cols_cycle = st.columns(total)
            for i, stage in enumerate(stages):
                with cols_cycle[i]:
                    is_current = (i + 1 == current)
                    if is_current:
                        st.markdown(f"""<div style="background: linear-gradient(135deg, #3d0a5c, #6a1a8e); padding: 10px; border-radius: 8px; text-align: center; border: 2px solid #af7ac5;"><div style="font-size: 1.4em; font-weight: bold;">🦁</div><div style="font-size: 0.75em; font-weight: bold; color: #fff;">Stage {i+1}</div><div style="font-size: 0.65em; color: #ddd;">{stage.get('name', '')}</div></div>""", unsafe_allow_html=True)
                    else:
                        opacity = "0.4" if abs(i + 1 - current) > 1 else "0.7"
                        st.markdown(f"""<div style="background: #262730; padding: 10px; border-radius: 8px; text-align: center; opacity: {opacity}; border: 1px solid #41444C;"><div style="font-size: 1.2em;">{"✅" if i + 1 < current else "⬜"}</div><div style="font-size: 0.7em; color: #888;">Stage {i+1}</div><div style="font-size: 0.6em; color: #888;">{stage.get('name', '')}</div></div>""", unsafe_allow_html=True)
            st.progress(current / total, text=f"ボラサイクル: Stage {current}/{total} - {stage_name}")
            evidence = cp.get("evidence", "")
            if evidence:
                st.info(f"📋 **判断根拠:** {evidence}")
            st.markdown("---")
            diag = ai_result.get("current_diagnosis", {})
            st.markdown(f"### 🔍 現状診断: {diag.get('headline', '')}")
            st.markdown(diag.get("summary", ""))
            col_vix, col_skew2 = st.columns(2)
            with col_vix:
                st.markdown("**📉 VIX解釈:**")
                st.markdown(diag.get("vix_interpretation", ""))
            with col_skew2:
                st.markdown("**🦢 SKEWシグナル:**")
                st.markdown(diag.get("skew_signal", ""))
            st.markdown("---")
            comp = ai_result.get("component_analysis", {})
            if comp:
                st.markdown("### 📊 コンポーネント別分析")
                cols_comp = st.columns(4)
                comp_items = [("🏦 信用", "credit", "#3498db"), ("📈 金利", "rates", "#e74c3c"), ("📉 恐怖", "volatility", "#f39c12"), ("🦢 歪み", "skew", "#9b59b6")]
                for cidx, (clabel, ckey, ccolor) in enumerate(comp_items):
                    with cols_comp[cidx]:
                        citem = comp.get(ckey, {})
                        cstatus = citem.get("status", "正常")
                        cemoji = {"正常": "🟢", "注意": "🟡", "警戒": "🟠", "危険": "🔴"}.get(cstatus, "⚪")
                        st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-top: 3px solid {ccolor};"><h4 style="color: {ccolor}; margin: 0 0 5px 0;">{clabel}</h4><p style="margin: 0 0 5px 0;">{cemoji} <b>{cstatus}</b></p><p style="color: #ddd; font-size: 0.8em; margin: 0;">{citem.get('interpretation', '')}</p></div>""", unsafe_allow_html=True)
            st.markdown("---")
            st.markdown("### 🔮 フォワードシナリオ分析")
            scenarios = ai_result.get("forward_scenarios", {})
            base = scenarios.get("base_case", {})
            st.markdown(f"""<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 20px; border-radius: 10px; border-left: 4px solid #af7ac5; margin-bottom: 15px;"><h4 style="color: #af7ac5; margin-top: 0;">🦁 メイン ({base.get('probability', 50)}%): {base.get('title', '')}</h4><p style="color: #F7C948;">📊 VIX予想: <b>{base.get('vix_range', '')}</b></p><table style="width: 100%;"><tr><td style="padding: 8px; color: #888;">3ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_3months', '')}</td></tr><tr><td style="padding: 8px; color: #888;">6ヶ月後</td><td style="padding: 8px; color: #ddd;">→ {base.get('next_6months', '')}</td></tr></table><p style="color: #af7ac5; margin-bottom: 0;">💼 {base.get('investment_action', '')}</p></div>""", unsafe_allow_html=True)
            col_bull, col_bear = st.columns(2)
            bull = scenarios.get("bull_case", {})
            with col_bull:
                st.markdown(f"""<div style="background: #0a2a1a; padding: 15px; border-radius: 10px; border-left: 4px solid #09AB3B;"><h4 style="color: #09AB3B; margin-top: 0;">🟢 低ボラ ({bull.get('probability', 25)}%): {bull.get('title', '')}</h4><p style="color: #ddd; font-size: 0.9em;">{bull.get('narrative', '')}</p><p style="color: #09AB3B; font-size: 0.85em;">💼 {bull.get('investment_action', '')}</p></div>""", unsafe_allow_html=True)
            bear = scenarios.get("bear_case", {})
            with col_bear:
                st.markdown(f"""<div style="background: #2a0a0a; padding: 15px; border-radius: 10px; border-left: 4px solid #FF4B4B;"><h4 style="color: #FF4B4B; margin-top: 0;">🔴 急騰 ({bear.get('probability', 25)}%): {bear.get('title', '')}</h4><p style="color: #ddd; font-size: 0.9em;">{bear.get('narrative', '')}</p><p style="color: #F7C948;">📈 VIX: <b>{bear.get('vix_target', '')}</b></p><p style="color: #FF4B4B; font-size: 0.85em;">💼 {bear.get('investment_action', '')}</p></div>""", unsafe_allow_html=True)
            st.markdown("---")
            playbook = ai_result.get("options_playbook", {})
            if playbook:
                st.markdown("### 🎯 オプション・プレイブック")
                col_o1, col_o2, col_o3 = st.columns(3)
                with col_o1:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #3498db;"><p style="color: #3498db; font-weight: bold; margin: 0 0 5px 0;">📊 現在の環境</p><p style="color: #ddd; font-size: 0.85em; margin: 0;">{playbook.get('current_regime', '')}</p></div>""", unsafe_allow_html=True)
                with col_o2:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #09AB3B;"><p style="color: #09AB3B; font-weight: bold; margin: 0 0 5px 0;">✅ 推奨戦略</p><p style="color: #ddd; font-size: 0.85em; margin: 0;">{playbook.get('recommended_structures', '')}</p></div>""", unsafe_allow_html=True)
                with col_o3:
                    st.markdown(f"""<div style="background: #1a1a2e; padding: 12px; border-radius: 8px; border-left: 3px solid #e74c3c;"><p style="color: #e74c3c; font-weight: bold; margin: 0 0 5px 0;">🚫 避けるべき</p><p style="color: #ddd; font-size: 0.85em; margin: 0;">{playbook.get('avoid', '')}</p></div>""", unsafe_allow_html=True)
            st.markdown("---")
            rm = ai_result.get("risk_monitor", {})
            st.markdown("### ⚠️ リスクモニター")
            watch = rm.get("watch_items", [])
            if watch:
                for w in watch:
                    st.markdown(f"- 👁️ {w}")
            inflection = rm.get("next_inflection", "")
            if inflection:
                st.error(f"🔄 **次の転換点:** {inflection}")
