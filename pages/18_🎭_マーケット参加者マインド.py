from core.auth import require_auth
require_auth()

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import time
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="マーケット参加者マインド", page_icon="🎭", layout="wide")

# ─────────────────────────────────────────────
# API Helper (inline with retry)
# ─────────────────────────────────────────────
def call_claude_api(system_prompt: str, user_prompt: str, max_retries: int = 3) -> tuple:
    """Claude API呼び出し（リトライ付き）"""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None, "APIキーが設定されていません"
    
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}]
    }
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers, json=payload, timeout=120
            )
            if resp.status_code == 529:
                wait = (attempt + 1) * 10
                st.warning(f"⏳ API過負荷。{wait}秒後にリトライ... ({attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                return None, f"APIエラー: {resp.status_code} - {resp.text[:300]}"
            
            data = resp.json()
            text = data["content"][0]["text"]
            # JSON抽出
            text = re.sub(r'^```json\s*', '', text.strip())
            text = re.sub(r'\s*```$', '', text.strip())
            try:
                return json.loads(text), None
            except json.JSONDecodeError:
                m = re.search(r'\{[\s\S]*\}', text)
                if m:
                    return json.loads(m.group()), None
                return {"raw_text": text}, None
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return None, "タイムアウト"
        except Exception as e:
            return None, str(e)
    return None, "リトライ上限到達"


# ─────────────────────────────────────────────
# データ取得
# ─────────────────────────────────────────────
TICKERS = {
    # 米国主要指数
    "^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^RUT": "Russell 2000",
    # ボラティリティ
    "^VIX": "VIX", "^VIX3M": "VIX3M",
    # 日本
    "^N225": "日経225",
    # 欧州
    "^STOXX50E": "Euro Stoxx 50", "^GDAXI": "DAX",
    # 米国債
    "^TNX": "米10年金利", "^TYX": "米30年金利", "^IRX": "米3ヶ月金利",
    # 為替
    "USDJPY=X": "USD/JPY", "EURUSD=X": "EUR/USD", "DX-Y.NYB": "ドルインデックス",
    # コモディティ
    "GC=F": "金", "CL=F": "原油WTI", "SI=F": "銀",
    # セクターETF
    "XLK": "テクノロジー", "XLF": "金融", "XLE": "エネルギー",
    "XLU": "公益", "XLP": "生活必需品", "XLY": "一般消費財",
    "XLV": "ヘルスケア", "XLI": "資本財",
    # リスク指標
    "HYG": "ハイイールド債", "LQD": "投資適格債", "TLT": "米長期国債ETF",
    # レバレッジ/リテール指標
    "TQQQ": "TQQQ(レバナス)", "ARKK": "ARKK(イノベーション)",
    "IWM": "IWM(小型株)",
    # ゴールド・ソブリン指標
    "GLD": "GLD(金ETF)", "IAU": "IAU(金ETF)",
}

@st.cache_data(ttl=900)  # 15分キャッシュ
def fetch_all_market_data():
    """全マーケットデータを取得"""
    results = {}
    tickers_str = " ".join(TICKERS.keys())
    
    try:
        # 一括取得（3ヶ月分）
        data = yf.download(tickers_str, period="3mo", group_by="ticker", progress=False)
        
        for ticker, name in TICKERS.items():
            try:
                if len(TICKERS) > 1:
                    if ticker in data.columns.get_level_values(0):
                        df = data[ticker].dropna(how='all')
                    else:
                        continue
                else:
                    df = data
                
                if df.empty or len(df) < 5:
                    continue
                
                close = df["Close"]
                latest = float(close.iloc[-1])
                
                # 各期間のリターン
                chg_1d = float((close.iloc[-1] / close.iloc[-2] - 1) * 100) if len(close) >= 2 else 0
                chg_1w = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) >= 6 else 0
                chg_1m = float((close.iloc[-1] / close.iloc[-22] - 1) * 100) if len(close) >= 22 else 0
                
                # テクニカル
                ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else latest
                ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else latest
                
                # 実現ボラティリティ（20日）
                returns = close.pct_change().dropna()
                realized_vol = float(returns.tail(20).std() * np.sqrt(252) * 100) if len(returns) >= 20 else 0
                
                # 出来高変化（可能な場合）
                vol_ratio = 1.0
                if "Volume" in df.columns:
                    vol = df["Volume"].dropna()
                    if len(vol) >= 20:
                        avg_vol = vol.tail(20).mean()
                        if avg_vol > 0:
                            vol_ratio = float(vol.iloc[-1] / avg_vol)
                
                results[ticker] = {
                    "name": name,
                    "price": round(latest, 2),
                    "chg_1d": round(chg_1d, 2),
                    "chg_1w": round(chg_1w, 2),
                    "chg_1m": round(chg_1m, 2),
                    "above_ma20": latest > ma20,
                    "above_ma50": latest > ma50,
                    "realized_vol": round(realized_vol, 1),
                    "vol_ratio": round(vol_ratio, 2),
                }
            except Exception:
                continue
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
    
    return results


def compute_derived_signals(data: dict) -> dict:
    """参加者別に重要な派生シグナルを計算"""
    signals = {}
    
    # VIXタームストラクチャー
    vix = data.get("^VIX", {}).get("price", 0)
    vix3m = data.get("^VIX3M", {}).get("price", 0)
    if vix > 0 and vix3m > 0:
        signals["vix_term_structure"] = "バックワーデーション（恐怖）" if vix > vix3m else "コンタンゴ（正常）"
        signals["vix_ratio"] = round(vix / vix3m, 3)
    else:
        signals["vix_term_structure"] = "データなし"
        signals["vix_ratio"] = 1.0
    
    signals["vix_level"] = vix
    
    # VIX vs 実現ボラティリティ（S&P500）
    sp_rvol = data.get("^GSPC", {}).get("realized_vol", 0)
    if vix > 0 and sp_rvol > 0:
        signals["vol_risk_premium"] = round(vix - sp_rvol, 1)
    else:
        signals["vol_risk_premium"] = 0
    
    # イールドカーブ（10年-3ヶ月）
    y10 = data.get("^TNX", {}).get("price", 0)
    y3m = data.get("^IRX", {}).get("price", 0)
    if y10 > 0 and y3m > 0:
        signals["yield_curve_slope"] = round(y10 - y3m, 2)
        signals["yield_curve_status"] = "順イールド" if y10 > y3m else "逆イールド"
    else:
        signals["yield_curve_slope"] = 0
        signals["yield_curve_status"] = "データなし"
    
    # リスクオン/オフ指標
    sp_1m = data.get("^GSPC", {}).get("chg_1m", 0)
    tlt_1m = data.get("TLT", {}).get("chg_1m", 0)
    gold_1m = data.get("GC=F", {}).get("chg_1m", 0)
    signals["risk_appetite"] = "リスクオン" if sp_1m > 0 and tlt_1m < 0 else (
        "リスクオフ" if sp_1m < 0 and (tlt_1m > 0 or gold_1m > 0) else "混合"
    )
    
    # グロース vs バリュー（NASDAQ vs Russell）
    nq_1m = data.get("^IXIC", {}).get("chg_1m", 0)
    rut_1m = data.get("^RUT", {}).get("chg_1m", 0)
    signals["growth_vs_value"] = round(nq_1m - rut_1m, 2)
    signals["rotation_direction"] = "グロース優位" if nq_1m > rut_1m else "バリュー/小型優位"
    
    # 信用スプレッド（HYG vs LQD の相対パフォーマンス）
    hyg_1m = data.get("HYG", {}).get("chg_1m", 0)
    lqd_1m = data.get("LQD", {}).get("chg_1m", 0)
    signals["credit_spread_direction"] = "タイトニング" if hyg_1m > lqd_1m else "ワイドニング"
    
    # リテール活動指標（TQQQ、ARKKの出来高比率）
    tqqq_vol = data.get("TQQQ", {}).get("vol_ratio", 1.0)
    arkk_vol = data.get("ARKK", {}).get("vol_ratio", 1.0)
    signals["retail_activity"] = round((tqqq_vol + arkk_vol) / 2, 2)
    
    # ドル強弱
    dxy_1m = data.get("DX-Y.NYB", {}).get("chg_1m", 0)
    signals["dollar_trend"] = "ドル高" if dxy_1m > 0.5 else ("ドル安" if dxy_1m < -0.5 else "横ばい")
    
    # セクターモメンタム（上位・下位）
    sectors = {}
    for t in ["XLK", "XLF", "XLE", "XLU", "XLP", "XLY", "XLV", "XLI"]:
        if t in data:
            sectors[data[t]["name"]] = data[t]["chg_1m"]
    if sectors:
        sorted_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)
        signals["top_sectors"] = sorted_sectors[:3]
        signals["bottom_sectors"] = sorted_sectors[-3:]
    
    # 日米欧の相対パフォーマンス
    signals["us_1m"] = sp_1m
    signals["japan_1m"] = data.get("^N225", {}).get("chg_1m", 0)
    signals["europe_1m"] = data.get("^STOXX50E", {}).get("chg_1m", 0)
    
    return signals


# ─────────────────────────────────────────────
# 参加者タイプ定義
# ─────────────────────────────────────────────
PARTICIPANT_TYPES = {
    "institutional": {
        "icon": "🏛️",
        "name": "機関投資家（年金・投信・保険）",
        "short": "機関投資家",
        "color": "#1a5276",
        "description": "長期視点、ベンチマーク意識、リスク分散重視。四半期リバランスの影響大。",
        "key_signals": ["イールドカーブ", "セクターローテーション", "信用スプレッド", "ボラティリティレジーム"],
    },
    "hedge_fund": {
        "icon": "🦈",
        "name": "ヘッジファンド / CTA・システマティック",
        "short": "HF/CTA",
        "color": "#922b21",
        "description": "モメンタム追随、レバレッジ活用、ボラティリティターゲティング。トレンドの加速装置。",
        "key_signals": ["トレンドシグナル", "VIXタームストラクチャー", "クロスアセットモメンタム", "ポジション集中度"],
    },
    "retail": {
        "icon": "🎰",
        "name": "リテール（個人投資家）/ ミーム株トレーダー",
        "short": "リテール",
        "color": "#117864",
        "description": "FOMO駆動、オプション重用、ソーシャルメディア影響大。逆指標としても重要。",
        "key_signals": ["レバレッジETF出来高", "小型株パフォーマンス", "VIX水準", "ARKK動向"],
    },
    "market_maker": {
        "icon": "⚙️",
        "name": "マーケットメーカー / ディーラー",
        "short": "MM/ディーラー",
        "color": "#6c3483",
        "description": "デルタニュートラル志向、ガンマエクスポージャー管理。流動性の源泉かつ短期価格の支配者。",
        "key_signals": ["VIX vs 実現ボラティリティ", "出来高パターン", "ボラティリティリスクプレミアム"],
    },
    "sovereign": {
        "icon": "🏦",
        "name": "中央銀行 / ソブリン / 企業インサイダー",
        "short": "中銀/ソブリン",
        "color": "#7d6608",
        "description": "政策目的、通貨防衛、準備資産管理。最も長期的で市場インパクト最大。",
        "key_signals": ["為替動向", "金価格", "国債利回り", "ドルインデックス"],
    },
}


def build_analysis_prompt(market_data: dict, signals: dict) -> tuple:
    """Claude API用のプロンプトを構築"""
    
    # マーケットデータサマリー
    data_lines = []
    for ticker, info in market_data.items():
        trend = "↑" if info.get("above_ma50") else "↓"
        data_lines.append(
            f"  {info['name']}({ticker}): {info['price']} | "
            f"1D:{info['chg_1d']:+.1f}% 1W:{info['chg_1w']:+.1f}% 1M:{info['chg_1m']:+.1f}% | "
            f"トレンド:{trend} | RV:{info['realized_vol']}% | 出来高比:{info['vol_ratio']}x"
        )
    
    # シグナルサマリー
    signal_lines = [
        f"VIX水準: {signals.get('vix_level', 'N/A')}",
        f"VIXタームストラクチャー: {signals.get('vix_term_structure', 'N/A')} (比率:{signals.get('vix_ratio', 'N/A')})",
        f"ボラティリティリスクプレミアム: {signals.get('vol_risk_premium', 'N/A')}pt",
        f"イールドカーブ: {signals.get('yield_curve_status', 'N/A')} ({signals.get('yield_curve_slope', 'N/A')}%)",
        f"リスク選好: {signals.get('risk_appetite', 'N/A')}",
        f"グロースvsバリュー: {signals.get('rotation_direction', 'N/A')} (差:{signals.get('growth_vs_value', 'N/A')}%)",
        f"信用スプレッド: {signals.get('credit_spread_direction', 'N/A')}",
        f"リテール活動指標: {signals.get('retail_activity', 'N/A')}x (1.0が平均)",
        f"ドル動向: {signals.get('dollar_trend', 'N/A')}",
        f"米国1M:{signals.get('us_1m', 0):+.1f}% / 日本1M:{signals.get('japan_1m', 0):+.1f}% / 欧州1M:{signals.get('europe_1m', 0):+.1f}%",
    ]
    
    top = signals.get("top_sectors", [])
    bottom = signals.get("bottom_sectors", [])
    if top:
        signal_lines.append(f"セクター上位: {', '.join(f'{s[0]}({s[1]:+.1f}%)' for s in top)}")
    if bottom:
        signal_lines.append(f"セクター下位: {', '.join(f'{s[0]}({s[1]:+.1f}%)' for s in bottom)}")
    
    system_prompt = f"""あなたはグローバルマクロストラテジストであり、市場参加者の行動分析の専門家です。
現在の日付は2026年3月です。

あなたの任務は、提供されるリアルタイムの市場データと派生シグナルに基づいて、
5つの市場参加者タイプそれぞれが今何を考え、どう行動しているかを推定することです。

重要なルール：
1. 推測ではなく、提供されたデータから論理的に導ける行動パターンのみを述べること
2. 各参加者の「ポジショニング推定」「心理状態」「次のアクション」を具体的に述べること
3. データが示していることと、そこからの推論を明確に区別すること
4. 参加者間の相互作用（誰が誰にリクイディティを提供しているか等）にも言及すること
5. 反対意見や見落としリスクも必ず含めること

回答はJSON形式で。以下の構造に厳密に従うこと：
{{
  "market_regime": {{
    "label": "現在のレジーム名（例：リスクオン拡大期、ボラティリティ圧縮期など）",
    "description": "レジームの特徴を2-3文で",
    "confidence": "high/medium/low"
  }},
  "participants": {{
    "institutional": {{
      "sentiment_score": -100から100の数値,
      "sentiment_label": "強気/やや強気/中立/やや弱気/弱気",
      "positioning": "現在の推定ポジショニングを具体的に",
      "psychology": "今の心理状態と懸念事項",
      "next_action": "今後1-4週間の想定アクション",
      "key_data_points": ["根拠となるデータポイントを3つ"]
    }},
    "hedge_fund": {{ 同上の構造 }},
    "retail": {{ 同上の構造 }},
    "market_maker": {{ 同上の構造 }},
    "sovereign": {{ 同上の構造 }}
  }},
  "interactions": "参加者間のダイナミクス（誰が売り手で誰が買い手か、フローの方向性）を3-4文で",
  "poker_table": {{
    "patsy": "institutional/hedge_fund/retail/market_maker/sovereign のうち、今最も不利なポジションにいる参加者タイプのキー",
    "patsy_reason": "なぜこの参加者が今『カモ』なのか。具体的なデータ根拠とともに3-4文で。バフェットの言葉を借りれば、ポーカーテーブルで30分経ってもカモが誰かわからなければ、カモは自分だ。この参加者は今、自分が不利な立場にいることに気づいていない。",
    "who_profits": "この『カモ』から利益を得ているのは誰か。そのメカニズムを具体的に",
    "smart_money_doing": "最も有利なポジションにいる参加者は誰で、何をしているか",
    "your_position": "個人投資家（このツールのユーザー）へのメッセージ。あなたがカモにならないために、今すべきこと・すべきでないことを率直に"
  }},
  "contrarian_warning": "現在のコンセンサスに対する逆張り警告。全員が同じ方向を向いている場合の危険性",
  "biggest_risk": "市場参加者の大多数が見落としている最大のリスク"
}}"""

    user_prompt = f"""以下の最新マーケットデータと派生シグナルを分析し、各参加者の現在のマインドを推定してください。

═══ マーケットデータ ═══
{chr(10).join(data_lines)}

═══ 派生シグナル ═══
{chr(10).join(signal_lines)}

上記データに基づき、5つの参加者タイプそれぞれの思考・ポジショニング・次のアクションを分析してください。
データが明確に示していること（事実）と、そこからの推論（仮説）を区別してください。"""

    return system_prompt, user_prompt


# ─────────────────────────────────────────────
# 表示関数
# ─────────────────────────────────────────────
def render_sentiment_gauge(score: int, label: str):
    """センチメントゲージをHTMLで表示"""
    # スコアに応じた色
    if score >= 50:
        color = "#27ae60"
    elif score >= 20:
        color = "#2ecc71"
    elif score >= -20:
        color = "#f39c12"
    elif score >= -50:
        color = "#e67e22"
    else:
        color = "#e74c3c"
    
    # ゲージの位置（-100〜100を0〜100%に変換）
    position = (score + 100) / 2
    
    html = f"""
    <div style="margin: 8px 0;">
        <div style="display:flex; justify-content:space-between; font-size:12px; color:#888;">
            <span>弱気 -100</span>
            <span style="color:{color}; font-weight:bold; font-size:16px;">{label} ({score:+d})</span>
            <span>+100 強気</span>
        </div>
        <div style="background:#2d2d2d; border-radius:10px; height:16px; position:relative; margin-top:4px;">
            <div style="position:absolute; left:50%; top:0; bottom:0; width:2px; background:#555;"></div>
            <div style="position:absolute; left:{position}%; top:50%; transform:translate(-50%,-50%);
                        width:20px; height:20px; background:{color}; border-radius:50%; border:2px solid white;">
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_participant_card(key: str, ptype: dict, analysis: dict):
    """参加者カードを表示"""
    p_data = analysis.get(key, {})
    score = p_data.get("sentiment_score", 0)
    
    st.markdown(f"""
    <div style="background:linear-gradient(135deg, {ptype['color']}22, {ptype['color']}08);
                border-left:4px solid {ptype['color']}; border-radius:8px; padding:20px; margin:10px 0;">
        <h3 style="margin:0 0 4px 0;">{ptype['icon']} {ptype['name']}</h3>
        <p style="color:#999; font-size:13px; margin:0 0 12px 0;">{ptype['description']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    render_sentiment_gauge(score, p_data.get("sentiment_label", "N/A"))
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📍 ポジショニング推定**")
        st.info(p_data.get("positioning", "データなし"))
        st.markdown("**🧠 心理状態**")
        st.warning(p_data.get("psychology", "データなし"))
    with col2:
        st.markdown("**⏭️ 次のアクション**")
        st.success(p_data.get("next_action", "データなし"))
        st.markdown("**📊 根拠データ**")
        for dp in p_data.get("key_data_points", []):
            st.markdown(f"- {dp}")
    
    st.markdown("---")


def render_market_dashboard(data: dict, signals: dict):
    """マーケットデータダッシュボードを表示"""
    
    st.markdown("### 📡 取得済みマーケットシグナル")
    
    # タブでカテゴリ分け
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🇺🇸 米国指数", "🌏 日欧・為替", "📊 セクター", "💰 債券・コモディティ", "📈 派生シグナル"
    ])
    
    def make_df(tickers_list):
        rows = []
        for t in tickers_list:
            if t in data:
                d = data[t]
                trend = "🔼" if d["above_ma50"] else "🔽"
                rows.append({
                    "銘柄": d["name"],
                    "価格": d["price"],
                    "1日": f"{d['chg_1d']:+.1f}%",
                    "1週間": f"{d['chg_1w']:+.1f}%",
                    "1ヶ月": f"{d['chg_1m']:+.1f}%",
                    "トレンド": trend,
                    "RV(%)": d["realized_vol"],
                    "出来高比": f"{d['vol_ratio']:.1f}x",
                })
        return pd.DataFrame(rows)
    
    with tab1:
        st.dataframe(
            make_df(["^GSPC", "^IXIC", "^RUT", "^VIX", "^VIX3M", "TQQQ", "ARKK", "IWM"]),
            use_container_width=True, hide_index=True
        )
    with tab2:
        st.dataframe(
            make_df(["^N225", "^STOXX50E", "^GDAXI", "USDJPY=X", "EURUSD=X", "DX-Y.NYB"]),
            use_container_width=True, hide_index=True
        )
    with tab3:
        st.dataframe(
            make_df(["XLK", "XLF", "XLE", "XLU", "XLP", "XLY", "XLV", "XLI"]),
            use_container_width=True, hide_index=True
        )
    with tab4:
        st.dataframe(
            make_df(["^TNX", "^TYX", "^IRX", "TLT", "HYG", "LQD", "GC=F", "CL=F", "SI=F"]),
            use_container_width=True, hide_index=True
        )
    with tab5:
        st.markdown("#### 🔬 派生シグナル一覧")
        sig_cols = st.columns(3)
        with sig_cols[0]:
            st.metric("VIX水準", f"{signals.get('vix_level', 'N/A')}")
            st.metric("VIXターム", signals.get("vix_term_structure", "N/A"),
                      delta=f"比率: {signals.get('vix_ratio', 'N/A')}")
            st.metric("VolRPプレミアム", f"{signals.get('vol_risk_premium', 'N/A')}pt")
        with sig_cols[1]:
            st.metric("イールドカーブ", signals.get("yield_curve_status", "N/A"),
                      delta=f"{signals.get('yield_curve_slope', 'N/A')}%")
            st.metric("リスク選好", signals.get("risk_appetite", "N/A"))
            st.metric("信用スプレッド", signals.get("credit_spread_direction", "N/A"))
        with sig_cols[2]:
            st.metric("ローテーション", signals.get("rotation_direction", "N/A"),
                      delta=f"差: {signals.get('growth_vs_value', 'N/A')}%")
            st.metric("リテール活動", f"{signals.get('retail_activity', 'N/A')}x")
            st.metric("ドル動向", signals.get("dollar_trend", "N/A"))


# ─────────────────────────────────────────────
# メインUI
# ─────────────────────────────────────────────
st.markdown("""
# 🎭 マーケット参加者マインド

**リアルタイム市場データから、各市場参加者が今何を考え、どう動いているかをAIで推定**

> 🃏 *「ポーカーを始めて30分経っても誰がカモかわからなければ、カモはあなただ」*
> *— ウォーレン・バフェット*
>
> データで観測できる行動パターンから各プレイヤーの手札を推論し、**今誰がテーブルでカモにされているか**を特定します。
""")

st.markdown("---")

# データ取得
with st.spinner("📡 グローバルマーケットデータを取得中..."):
    market_data = fetch_all_market_data()

if not market_data:
    st.error("マーケットデータの取得に失敗しました。しばらく待ってリロードしてください。")
    st.stop()

st.success(f"✅ {len(market_data)}銘柄のデータを取得完了")

# 派生シグナル計算
signals = compute_derived_signals(market_data)

# ダッシュボード表示
render_market_dashboard(market_data, signals)

st.markdown("---")

# AI分析
st.markdown("### 🤖 AI参加者マインド分析")
st.caption("上記のマーケットデータと派生シグナルをClaude APIに送信し、各参加者の思考を推定します")

if st.button("🃏 テーブルのカモを特定する", type="primary", use_container_width=True):
    system_prompt, user_prompt = build_analysis_prompt(market_data, signals)
    
    with st.spinner("🧠 Claude APIで参加者マインドを分析中...（最大2分）"):
        result, error = call_claude_api(system_prompt, user_prompt)
    
    if error:
        st.error(f"❌ API エラー: {error}")
        st.stop()
    
    if not result:
        st.error("分析結果を取得できませんでした")
        st.stop()
    
    # raw_textの場合（JSONパース失敗時）
    if "raw_text" in result:
        st.markdown("#### 分析結果（テキスト）")
        st.markdown(result["raw_text"])
        st.stop()
    
    # マーケットレジーム
    regime = result.get("market_regime", {})
    regime_label = regime.get("label", "不明")
    regime_desc = regime.get("description", "")
    regime_conf = regime.get("confidence", "medium")
    conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(regime_conf, "⚪")
    
    st.markdown(f"""
    <div style="background:linear-gradient(135deg, #1a1a2e, #16213e); border-radius:12px;
                padding:24px; text-align:center; margin:16px 0;">
        <h2 style="margin:0; color:#e94560;">🌍 現在のマーケットレジーム</h2>
        <h1 style="margin:8px 0; color:#fff; font-size:2em;">{regime_label}</h1>
        <p style="color:#ccc; margin:8px 0;">{regime_desc}</p>
        <p style="color:#888;">確信度: {conf_emoji} {regime_conf.upper()}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 各参加者
    st.markdown("### 👥 参加者別マインド")
    
    participants = result.get("participants", {})
    for key, ptype in PARTICIPANT_TYPES.items():
        if key in participants:
            render_participant_card(key, ptype, participants)
    
    # 相互作用
    interactions = result.get("interactions", "")
    if interactions:
        st.markdown("### 🔄 参加者間ダイナミクス")
        st.markdown(f"""
        <div style="background:#1a1a2e; border-radius:8px; padding:20px; border:1px solid #333;">
            <p style="color:#ddd; line-height:1.8;">{interactions}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # ポーカーテーブル分析（バフェットの「カモは誰か」）
    poker = result.get("poker_table", {})
    if poker:
        patsy_key = poker.get("patsy", "")
        patsy_info = PARTICIPANT_TYPES.get(patsy_key, {})
        patsy_icon = patsy_info.get("icon", "❓")
        patsy_name = patsy_info.get("short", patsy_key)
        
        st.markdown("### 🃏 テーブルのカモは誰だ？")
        st.caption("「ポーカーを始めて30分経っても誰がカモかわからなければ、カモはあなただ」— ウォーレン・バフェット")
        
        st.markdown(f"""
        <div style="background:linear-gradient(135deg, #1a0a00, #2d1810); border:2px solid #d4a017;
                    border-radius:12px; padding:28px; margin:16px 0;">
            <div style="text-align:center; margin-bottom:20px;">
                <span style="font-size:3em;">{patsy_icon}</span>
                <h2 style="margin:8px 0; color:#d4a017;">今のカモ: {patsy_name}</h2>
            </div>
            <div style="background:rgba(0,0,0,0.3); border-radius:8px; padding:16px; margin:12px 0;">
                <p style="color:#ff6b6b; font-weight:bold; margin:0 0 8px 0;">🎯 なぜカモなのか</p>
                <p style="color:#ddd; line-height:1.7; margin:0;">{poker.get('patsy_reason', '')}</p>
            </div>
            <div style="background:rgba(0,0,0,0.3); border-radius:8px; padding:16px; margin:12px 0;">
                <p style="color:#ffd93d; font-weight:bold; margin:0 0 8px 0;">💰 誰が利益を得ているか</p>
                <p style="color:#ddd; line-height:1.7; margin:0;">{poker.get('who_profits', '')}</p>
            </div>
            <div style="background:rgba(0,0,0,0.3); border-radius:8px; padding:16px; margin:12px 0;">
                <p style="color:#6bff6b; font-weight:bold; margin:0 0 8px 0;">🦊 スマートマネーの動き</p>
                <p style="color:#ddd; line-height:1.7; margin:0;">{poker.get('smart_money_doing', '')}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        your_position = poker.get("your_position", "")
        if your_position:
            st.markdown(f"""
            <div style="background:linear-gradient(135deg, #0a1628, #162447); border:2px solid #00d2ff;
                        border-radius:12px; padding:24px; margin:16px 0;">
                <h3 style="margin:0 0 12px 0; color:#00d2ff;">🪞 あなたはカモになっていないか？</h3>
                <p style="color:#eee; line-height:1.8; font-size:1.05em; margin:0;">{your_position}</p>
            </div>
            """, unsafe_allow_html=True)
    
    # 逆張り警告
    contrarian = result.get("contrarian_warning", "")
    if contrarian:
        st.markdown("### ⚠️ コントラリアン警告")
        st.error(contrarian)
    
    # 最大リスク
    biggest_risk = result.get("biggest_risk", "")
    if biggest_risk:
        st.markdown("### 💀 見落とされている最大リスク")
        st.markdown(f"""
        <div style="background:#2d1117; border:1px solid #f85149; border-radius:8px; padding:20px;">
            <p style="color:#f85149; font-weight:bold; font-size:1.1em;">{biggest_risk}</p>
        </div>
        """, unsafe_allow_html=True)

# フッター
st.markdown("---")
st.caption("💡 データソース: yfinance（リアルタイム） | AI分析: Claude API (claude-sonnet-4-20250514) | 更新間隔: 15分キャッシュ")
st.caption("⚠️ 本分析は参考情報です。実際のポジショニングデータ（COT等）は含まれていません。AIの推論と市場データの事実を区別してご利用ください。")
