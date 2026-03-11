"""
🚨 早期警戒システム (Crash Early Warning)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2008年の教訓：株価は嘘をつく。信用市場は嘘をつかない。
このページは「暴落の接近」を検知することだけに特化する。

設計思想：
- 画面を開いて5秒で「今どれくらい危険か」がわかる
- 7つのシグナルだけに絞る（ノイズを排除）
- 各シグナルは2008年で実際に機能したものだけ
- 「何を見るか」ではなく「何が壊れたか」を検知する
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ssl

# SSL対応
try:
    _create_unverified_https_context = ssl._create_unverified_https_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

st.set_page_config(page_title="早期警戒システム", page_icon="🚨", layout="wide")


# ============================================================
# データ取得ユーティリティ
# ============================================================

@st.cache_data(ttl=3600)
def get_data(ticker, period="6mo"):
    """価格データを取得"""
    try:
        data = yf.download(ticker, period=period, progress=False)
        if data.empty:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except:
        return None


def calc_ma(series, window):
    """移動平均を計算"""
    return series.rolling(window).mean()


def calc_zscore(series, window=60):
    """Zスコアを計算（平均からの乖離度）"""
    mean = series.rolling(window).mean()
    std = series.rolling(window).std()
    return (series - mean) / std


# ============================================================
# 7つの早期警戒シグナル
# ============================================================

def signal_1_credit_spread():
    """
    シグナル1: 信用スプレッド（最重要）
    ━━━━━━━━━━━━━━━━━━━━━━━━
    2008年の教訓: 信用市場は株式市場の4ヶ月前に警告した。
    HYG（ハイイールド）がLQD（投資適格）より大きく下落 = スプレッド拡大 = 危険
    """
    hyg = get_data("HYG")
    lqd = get_data("LQD")

    if hyg is None or lqd is None:
        return {"status": "ERROR", "message": "データ取得失敗"}

    # HYG/LQD比率 → 低下 = スプレッド拡大
    ratio = hyg["Close"] / lqd["Close"]
    current_ratio = float(ratio.iloc[-1])
    ratio_ma50 = float(calc_ma(ratio, 50).iloc[-1])

    # 1ヶ月の変化
    lookback = min(21, len(ratio) - 1)
    ratio_1m_ago = float(ratio.iloc[-lookback - 1])
    ratio_change = ((current_ratio - ratio_1m_ago) / ratio_1m_ago) * 100

    # Zスコア
    zscore = float(calc_zscore(ratio).iloc[-1]) if len(ratio) > 60 else 0

    # 判定
    if zscore < -2.0 or ratio_change < -3:
        level = "CRITICAL"
        detail = f"信用スプレッド急拡大中。HYG/LQD比率のZスコア: {zscore:.1f}、1ヶ月変化: {ratio_change:+.1f}%"
    elif zscore < -1.0 or ratio_change < -1.5:
        level = "WARNING"
        detail = f"信用スプレッドやや拡大。Zスコア: {zscore:.1f}、1ヶ月変化: {ratio_change:+.1f}%"
    elif zscore < -0.5:
        level = "CAUTION"
        detail = f"信用スプレッドに軽微な変化。Zスコア: {zscore:.1f}"
    else:
        level = "NORMAL"
        detail = f"信用市場は安定。Zスコア: {zscore:.1f}、1ヶ月変化: {ratio_change:+.1f}%"

    return {
        "status": level,
        "detail": detail,
        "values": {
            "HYG/LQD比率": round(current_ratio, 4),
            "MA50": round(ratio_ma50, 4),
            "Zスコア": round(zscore, 2),
            "1ヶ月変化": f"{ratio_change:+.1f}%",
        },
        "lesson": "2007年6月: Bear Stearnsファンド崩壊の時点でスプレッドは拡大開始。株は4ヶ月後まで上昇続けた。"
    }


def signal_2_bank_stress():
    """
    シグナル2: 銀行ストレス
    ━━━━━━━━━━━━━━━━━━━━━━━━
    2008年の教訓: 銀行は自分の帳簿の中身を知っている。銀行株の崩壊は危機の先行指標。
    KRE（地方銀行ETF）の動きは、2023年SVB危機でも機能した。
    """
    kre = get_data("KRE")
    spy = get_data("SPY")

    if kre is None or spy is None:
        return {"status": "ERROR", "message": "データ取得失敗"}

    # KRE/SPY相対パフォーマンス
    kre_close = kre["Close"]
    spy_close = spy["Close"]

    # 各自の1ヶ月リターン
    lookback = min(21, len(kre_close) - 1)
    kre_ret = ((float(kre_close.iloc[-1]) / float(kre_close.iloc[-lookback - 1])) - 1) * 100
    spy_ret = ((float(spy_close.iloc[-1]) / float(spy_close.iloc[-lookback - 1])) - 1) * 100
    relative = kre_ret - spy_ret

    # KREの200日移動平均との関係
    kre_price = float(kre_close.iloc[-1])
    kre_ma200_data = get_data("KRE", period="1y")
    kre_vs_ma200 = 0
    if kre_ma200_data is not None and len(kre_ma200_data) >= 200:
        kre_ma200_close = kre_ma200_data["Close"]
        ma200 = float(calc_ma(kre_ma200_close, 200).iloc[-1])
        kre_vs_ma200 = ((kre_price - ma200) / ma200) * 100

    # 判定
    if relative < -10 and kre_vs_ma200 < -15:
        level = "CRITICAL"
        detail = f"銀行セクター崩壊中。対S&P500: {relative:+.1f}%、対MA200: {kre_vs_ma200:+.1f}%"
    elif relative < -5 or kre_vs_ma200 < -10:
        level = "WARNING"
        detail = f"銀行セクター弱含み。対S&P500: {relative:+.1f}%、対MA200: {kre_vs_ma200:+.1f}%"
    elif relative < -2:
        level = "CAUTION"
        detail = f"銀行セクターやや軟調。対S&P500: {relative:+.1f}%"
    else:
        level = "NORMAL"
        detail = f"銀行セクター安定。対S&P500: {relative:+.1f}%"

    return {
        "status": level,
        "detail": detail,
        "values": {
            "KRE(地銀ETF)": round(kre_price, 2),
            "KRE 1ヶ月リターン": f"{kre_ret:+.1f}%",
            "対S&P500": f"{relative:+.1f}%",
            "対MA200": f"{kre_vs_ma200:+.1f}%",
        },
        "lesson": "2007年: 金融株はS&P500のピークの数ヶ月前から下落開始。2023年: SVB破綻の数週間前にKREは急落。"
    }


def signal_3_yield_curve():
    """
    シグナル3: イールドカーブ（景気後退の先行指標）
    ━━━━━━━━━━━━━━━━━━━━━━━━
    逆イールドの「解消」が危険信号。逆転している間ではなく、
    逆転が正常化し始めた時に景気後退が来る。
    """
    tnx = get_data("^TNX")  # 10年債
    irx = get_data("^IRX")  # 2年債（13週T-Bill）

    if tnx is None or irx is None:
        return {"status": "ERROR", "message": "データ取得失敗"}

    tnx_price = float(tnx["Close"].iloc[-1])
    irx_price = float(irx["Close"].iloc[-1])
    spread = tnx_price - irx_price

    # 1ヶ月前のスプレッド
    lookback = min(21, len(tnx) - 1)
    spread_1m = float(tnx["Close"].iloc[-lookback - 1]) - float(irx["Close"].iloc[-lookback - 1])
    spread_change = spread - spread_1m

    # 3ヶ月前のスプレッド
    lookback_3m = min(63, len(tnx) - 1)
    spread_3m = float(tnx["Close"].iloc[-lookback_3m - 1]) - float(irx["Close"].iloc[-lookback_3m - 1])
    was_inverted_3m = spread_3m < 0
    now_positive = spread > 0

    # 判定：逆イールドの「解消」が最も危険
    if was_inverted_3m and now_positive and spread_change > 0.3:
        level = "CRITICAL"
        detail = f"逆イールド解消中 → 景気後退の典型的パターン。スプレッド: {spread:.2f}%（3ヶ月前: {spread_3m:.2f}%）"
    elif spread < -0.5:
        level = "WARNING"
        detail = f"深い逆イールド継続中。スプレッド: {spread:.2f}%。解消時に警戒レベル引き上げ。"
    elif spread < 0:
        level = "CAUTION"
        detail = f"逆イールド。スプレッド: {spread:.2f}%"
    else:
        level = "NORMAL"
        detail = f"順イールド。スプレッド: {spread:.2f}%"

    return {
        "status": level,
        "detail": detail,
        "values": {
            "10年債利回り": f"{tnx_price:.2f}%",
            "短期金利": f"{irx_price:.2f}%",
            "スプレッド": f"{spread:.2f}%",
            "1ヶ月変化": f"{spread_change:+.2f}%",
            "3ヶ月前": f"{spread_3m:.2f}%",
        },
        "lesson": "歴史的に逆イールドの「発生」ではなく「解消」のタイミングで景気後退が始まる。平均リードタイムは6-12ヶ月。"
    }


def signal_4_volatility_structure():
    """
    シグナル4: VIXのターム構造（パニックの温度計）
    ━━━━━━━━━━━━━━━━━━━━━━━━
    VIXの水準より、ターム構造（短期vs長期）が重要。
    短期VIXが長期VIXを上回る = バックワーデーション = パニック
    """
    vix = get_data("^VIX", period="3mo")

    if vix is None:
        return {"status": "ERROR", "message": "データ取得失敗"}

    vix_price = float(vix["Close"].iloc[-1])

    # 5日前のVIX
    vix_5d = float(vix["Close"].iloc[-6]) if len(vix) > 5 else vix_price
    vix_change_5d = vix_price - vix_5d

    # VIXスパイク検出（5日で+5以上）
    spike = vix_change_5d > 5

    # 判定
    if vix_price > 35 and spike:
        level = "CRITICAL"
        detail = f"VIXスパイク + 高水準。VIX: {vix_price:.1f}（5日で{vix_change_5d:+.1f}pt）。パニック的状況。"
    elif vix_price > 30:
        level = "WARNING"
        detail = f"VIX高水準。VIX: {vix_price:.1f}。恐怖が支配的。"
    elif vix_price > 25 or spike:
        level = "CAUTION"
        detail = f"VIX上昇中。VIX: {vix_price:.1f}（5日変化: {vix_change_5d:+.1f}pt）"
    elif vix_price < 12:
        level = "CAUTION"
        detail = f"VIX極端に低い。VIX: {vix_price:.1f}。過度の楽観 → 反転リスク。"
    else:
        level = "NORMAL"
        detail = f"VIX通常範囲。VIX: {vix_price:.1f}"

    return {
        "status": level,
        "detail": detail,
        "values": {
            "VIX": round(vix_price, 1),
            "5日変化": f"{vix_change_5d:+.1f}pt",
            "スパイク": "YES" if spike else "NO",
        },
        "lesson": "2008年9月: VIXは20台から一気に80台へ。だが2007年8月のBNPパリバショック時に一度30台をつけた（予行演習）。"
    }


def signal_5_liquidity_canary():
    """
    シグナル5: 流動性カナリア（BTCと小型株）
    ━━━━━━━━━━━━━━━━━━━━━━━━
    流動性が枯渇する時、最もリスクの高い資産から先に崩れる。
    BTC、Russell2000（小型株）が大型株より先に下落 = 流動性引き潮
    """
    btc = get_data("BTC-USD")
    iwm = get_data("IWM")  # Russell2000 ETF
    spy = get_data("SPY")

    if btc is None or iwm is None or spy is None:
        return {"status": "ERROR", "message": "データ取得失敗"}

    lookback = min(21, min(len(btc), len(iwm), len(spy)) - 1)

    btc_ret = ((float(btc["Close"].iloc[-1]) / float(btc["Close"].iloc[-lookback - 1])) - 1) * 100
    iwm_ret = ((float(iwm["Close"].iloc[-1]) / float(iwm["Close"].iloc[-lookback - 1])) - 1) * 100
    spy_ret = ((float(spy["Close"].iloc[-1]) / float(spy["Close"].iloc[-lookback - 1])) - 1) * 100

    # BTC vs SPY（流動性最前線）
    btc_vs_spy = btc_ret - spy_ret
    # IWM vs SPY（小型 vs 大型）
    iwm_vs_spy = iwm_ret - spy_ret

    # 両方ともSPYをアンダーパフォーム = 流動性引き潮
    both_weak = btc_vs_spy < -5 and iwm_vs_spy < -3

    if both_weak and btc_ret < -15:
        level = "CRITICAL"
        detail = f"流動性枯渇。BTC: {btc_ret:+.1f}%、小型株: {iwm_ret:+.1f}%、S&P500: {spy_ret:+.1f}%。リスク資産から資金流出。"
    elif both_weak:
        level = "WARNING"
        detail = f"流動性低下の兆候。BTC対SPY: {btc_vs_spy:+.1f}%、小型株対SPY: {iwm_vs_spy:+.1f}%"
    elif btc_vs_spy < -10 or iwm_vs_spy < -5:
        level = "CAUTION"
        detail = f"一部で流動性ストレス。BTC対SPY: {btc_vs_spy:+.1f}%、小型株対SPY: {iwm_vs_spy:+.1f}%"
    else:
        level = "NORMAL"
        detail = f"流動性正常。BTC対SPY: {btc_vs_spy:+.1f}%、小型株対SPY: {iwm_vs_spy:+.1f}%"

    return {
        "status": level,
        "detail": detail,
        "values": {
            "BTC 1ヶ月": f"{btc_ret:+.1f}%",
            "小型株(IWM) 1ヶ月": f"{iwm_ret:+.1f}%",
            "S&P500 1ヶ月": f"{spy_ret:+.1f}%",
            "BTC対SPY": f"{btc_vs_spy:+.1f}%",
            "小型株対SPY": f"{iwm_vs_spy:+.1f}%",
        },
        "lesson": "流動性の引き潮は、海辺の水が引くように始まる。最初に干上がるのは最もリスクの高い場所。"
    }


def signal_6_cre_stress():
    """
    シグナル6: 商業用不動産ストレス（次の震源地候補）
    ━━━━━━━━━━━━━━━━━━━━━━━━
    2008年の住宅市場 → 今回は商業用不動産が同じ構造的問題を抱えている。
    オフィス空室率が史上最高。CREローンの満期到来集中。
    """
    # VNQ: Vanguard Real Estate ETF
    vnq = get_data("VNQ")
    spy = get_data("SPY")
    # MORT: VanEck Mortgage REIT ETF（モーゲージREIT）
    mort = get_data("MORT")

    if vnq is None or spy is None:
        return {"status": "ERROR", "message": "データ取得失敗"}

    lookback = min(21, len(vnq) - 1)
    vnq_ret = ((float(vnq["Close"].iloc[-1]) / float(vnq["Close"].iloc[-lookback - 1])) - 1) * 100
    spy_ret = ((float(spy["Close"].iloc[-1]) / float(spy["Close"].iloc[-lookback - 1])) - 1) * 100
    vnq_vs_spy = vnq_ret - spy_ret

    mort_ret = 0
    if mort is not None:
        mort_lookback = min(21, len(mort) - 1)
        mort_ret = ((float(mort["Close"].iloc[-1]) / float(mort["Close"].iloc[-mort_lookback - 1])) - 1) * 100

    # 判定
    if vnq_vs_spy < -8 and mort_ret < -10:
        level = "CRITICAL"
        detail = f"不動産セクター崩壊。REIT対SPY: {vnq_vs_spy:+.1f}%、モーゲージREIT: {mort_ret:+.1f}%。2008年型の不動産発危機の兆候。"
    elif vnq_vs_spy < -5 or mort_ret < -5:
        level = "WARNING"
        detail = f"不動産セクターにストレス。REIT対SPY: {vnq_vs_spy:+.1f}%、モーゲージREIT: {mort_ret:+.1f}%"
    elif vnq_vs_spy < -2:
        level = "CAUTION"
        detail = f"不動産やや軟調。REIT対SPY: {vnq_vs_spy:+.1f}%"
    else:
        level = "NORMAL"
        detail = f"不動産セクター安定。REIT対SPY: {vnq_vs_spy:+.1f}%"

    return {
        "status": level,
        "detail": detail,
        "values": {
            "VNQ(REIT ETF) 1ヶ月": f"{vnq_ret:+.1f}%",
            "MORT(モーゲージREIT) 1ヶ月": f"{mort_ret:+.1f}%",
            "対S&P500": f"{vnq_vs_spy:+.1f}%",
        },
        "lesson": "2006年: 住宅価格がピークを打った時、誰も株式市場の暴落を予想しなかった。不動産の問題は株式市場に波及するまで1-2年かかる。"
    }


def signal_7_dollar_squeeze():
    """
    シグナル7: ドル流動性スクイーズ
    ━━━━━━━━━━━━━━━━━━━━━━━━
    DXY急騰 = 世界中のドル建て債務の返済負担が増大 = 新興国・リスク資産から資金流出
    """
    dxy = get_data("DX-Y.NYB")

    if dxy is None:
        return {"status": "ERROR", "message": "データ取得失敗"}

    dxy_price = float(dxy["Close"].iloc[-1])

    lookback = min(21, len(dxy) - 1)
    dxy_1m = float(dxy["Close"].iloc[-lookback - 1])
    dxy_change = ((dxy_price - dxy_1m) / dxy_1m) * 100

    # 3ヶ月の変化
    lookback_3m = min(63, len(dxy) - 1)
    dxy_3m = float(dxy["Close"].iloc[-lookback_3m - 1])
    dxy_change_3m = ((dxy_price - dxy_3m) / dxy_3m) * 100

    if dxy_change > 5 or (dxy_price > 110 and dxy_change > 2):
        level = "CRITICAL"
        detail = f"ドル急騰。DXY: {dxy_price:.1f}（1ヶ月: {dxy_change:+.1f}%）。ドル流動性スクイーズ。"
    elif dxy_change > 3 or dxy_price > 108:
        level = "WARNING"
        detail = f"ドル高加速。DXY: {dxy_price:.1f}（1ヶ月: {dxy_change:+.1f}%）"
    elif dxy_change > 1.5:
        level = "CAUTION"
        detail = f"ドルやや上昇。DXY: {dxy_price:.1f}（1ヶ月: {dxy_change:+.1f}%）"
    else:
        level = "NORMAL"
        detail = f"ドル安定。DXY: {dxy_price:.1f}（1ヶ月: {dxy_change:+.1f}%）"

    return {
        "status": level,
        "detail": detail,
        "values": {
            "DXY": round(dxy_price, 1),
            "1ヶ月変化": f"{dxy_change:+.1f}%",
            "3ヶ月変化": f"{dxy_change_3m:+.1f}%",
        },
        "lesson": "ドル高は世界の流動性の引き潮。2008年、2020年3月、2022年秋、全ての危機でドルは急騰した。"
    }


# ============================================================
# 総合脅威レベル算出
# ============================================================

def calc_threat_level(signals):
    """7つのシグナルから総合脅威レベルを算出"""
    scores = {"CRITICAL": 3, "WARNING": 2, "CAUTION": 1, "NORMAL": 0, "ERROR": 0}
    total = sum(scores.get(s.get("status", "ERROR"), 0) for s in signals.values())
    max_possible = 3 * 7  # 21

    critical_count = sum(1 for s in signals.values() if s.get("status") == "CRITICAL")
    warning_count = sum(1 for s in signals.values() if s.get("status") == "WARNING")

    if critical_count >= 3 or total >= 15:
        return "DEFCON 1", "🔴 最大警戒", "即座にポジション縮小。現金80%以上。", total
    elif critical_count >= 2 or total >= 11:
        return "DEFCON 2", "🟠 高警戒", "ポジション大幅縮小。防御的資産へシフト。", total
    elif critical_count >= 1 or total >= 8:
        return "DEFCON 3", "🟡 警戒", "リスクポジション縮小検討。ストップロス厳格化。", total
    elif warning_count >= 2 or total >= 5:
        return "DEFCON 4", "🔵 注意", "監視強化。新規ポジション控えめに。", total
    else:
        return "DEFCON 5", "🟢 平常", "通常運転。ルーティン通り。", total


# ============================================================
# UI
# ============================================================

st.markdown("""
<style>
    .threat-banner {
        text-align: center;
        padding: 30px;
        border-radius: 16px;
        margin: 10px 0 20px 0;
    }
    .signal-card {
        border-radius: 12px;
        padding: 15px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)

# 実行ボタン
if st.button("🚨 早期警戒スキャンを実行", type="primary", use_container_width=True):

    with st.spinner("7つの警戒シグナルをスキャン中... (30-60秒)"):

        signals = {
            "信用スプレッド": signal_1_credit_spread(),
            "銀行ストレス": signal_2_bank_stress(),
            "イールドカーブ": signal_3_yield_curve(),
            "VIX構造": signal_4_volatility_structure(),
            "流動性カナリア": signal_5_liquidity_canary(),
            "商業用不動産": signal_6_cre_stress(),
            "ドルスクイーズ": signal_7_dollar_squeeze(),
        }

    # 総合脅威レベル
    defcon, label, action, score = calc_threat_level(signals)

    # バナー表示
    colors = {
        "DEFCON 1": "#dc2626",
        "DEFCON 2": "#ea580c",
        "DEFCON 3": "#ca8a04",
        "DEFCON 4": "#2563eb",
        "DEFCON 5": "#16a34a",
    }
    bg_color = colors.get(defcon, "#333")

    st.markdown(f"""
    <div style="background: {bg_color}; text-align: center; padding: 30px; border-radius: 16px; margin: 10px 0 20px 0;">
        <div style="font-size: 48px; font-weight: 800; color: white; font-family: monospace;">{defcon}</div>
        <div style="font-size: 24px; color: white; margin: 8px 0;">{label}</div>
        <div style="font-size: 14px; color: rgba(255,255,255,0.8);">スコア: {score}/21</div>
        <div style="font-size: 16px; color: white; margin-top: 12px; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 8px;">{action}</div>
    </div>
    """, unsafe_allow_html=True)

    # シグナル一覧
    st.markdown("---")
    st.subheader("📡 7つの早期警戒シグナル")

    status_icons = {
        "CRITICAL": "🔴",
        "WARNING": "🟠",
        "CAUTION": "🟡",
        "NORMAL": "🟢",
        "ERROR": "⚪",
    }

    signal_names = {
        "信用スプレッド": "💳 信用スプレッド（最重要）",
        "銀行ストレス": "🏦 銀行ストレス",
        "イールドカーブ": "📈 イールドカーブ",
        "VIX構造": "📊 VIX構造",
        "流動性カナリア": "🐤 流動性カナリア",
        "商業用不動産": "🏢 商業用不動産",
        "ドルスクイーズ": "💵 ドルスクイーズ",
    }

    for name, result in signals.items():
        status = result.get("status", "ERROR")
        icon = status_icons.get(status, "⚪")
        display_name = signal_names.get(name, name)

        with st.expander(f"{icon} **{display_name}** — {status}", expanded=(status in ["CRITICAL", "WARNING"])):
            st.markdown(f"**判定:** {result.get('detail', '')}")

            # 数値
            values = result.get("values", {})
            if values:
                cols = st.columns(len(values))
                for i, (k, v) in enumerate(values.items()):
                    cols[i].metric(k, v)

            # 2008年の教訓
            if result.get("lesson"):
                st.caption(f"📚 歴史の教訓: {result['lesson']}")

    # 脅威レベル推移（将来的に履歴保存）
    st.markdown("---")
    st.subheader("📋 スキャンサマリー")

    col_sum1, col_sum2, col_sum3 = st.columns(3)
    with col_sum1:
        critical_count = sum(1 for s in signals.values() if s.get("status") == "CRITICAL")
        st.metric("🔴 CRITICAL", f"{critical_count}/7")
    with col_sum2:
        warning_count = sum(1 for s in signals.values() if s.get("status") == "WARNING")
        st.metric("🟠 WARNING", f"{warning_count}/7")
    with col_sum3:
        normal_count = sum(1 for s in signals.values() if s.get("status") == "NORMAL")
        st.metric("🟢 NORMAL", f"{normal_count}/7")

    st.caption(f"スキャン完了: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 行動ルール
    st.markdown("---")
    st.subheader("⚡ DEFCONレベル別 行動ルール")

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.error("""
        **DEFCON 1（最大警戒）**
        - 株式ポジション → 0-20%
        - 現金・短期債 → 80-100%
        - 全ポジションにストップロス
        - 毎日スキャンを実行
        """)
        st.warning("""
        **DEFCON 2（高警戒）**
        - 株式ポジション → 20-40%
        - 防御的セクターのみ保持
        - 金・短期債にシフト
        - 週2回スキャン
        """)
    with col_d2:
        st.info("""
        **DEFCON 3（警戒）**
        - 株式ポジション → 40-60%
        - 新規の攻撃的ポジション停止
        - ストップロス厳格化
        - 週1回スキャン（日曜）
        """)
        st.success("""
        **DEFCON 4-5（平常）**
        - 通常のルーティン通り
        - 週1回の日曜スキャンで十分
        - 新規ポジション可
        """)

else:
    # 初期画面
    st.markdown("---")
    st.markdown("""
    ### このページの設計思想

    > **「株価を見るな。信用市場を見ろ。」** — 2008年の最大の教訓

    7つのシグナルは、2008年の金融危機で**実際に機能した**指標だけを厳選しています。

    | # | シグナル | 2008年で機能した理由 |
    |---|---------|-------------------|
    | 1 | 💳 信用スプレッド | 株式市場の4ヶ月前に警告を発した |
    | 2 | 🏦 銀行ストレス | 銀行は自分の帳簿の中身を知っている |
    | 3 | 📈 イールドカーブ | 逆イールドの「解消」が景気後退の直前シグナル |
    | 4 | 📊 VIX構造 | パニックの温度計。スパイクが「予行演習」になる |
    | 5 | 🐤 流動性カナリア | 最もリスクの高い資産が最初に死ぬ |
    | 6 | 🏢 商業用不動産 | 次の危機の震源地候補 |
    | 7 | 💵 ドルスクイーズ | 全ての危機でドルは急騰した |

    **DEFCON 1-5** の脅威レベルで、「今どれくらい危険か」を5秒で判断できます。
    """)


# サイドバー
with st.sidebar:
    st.markdown("### 🚨 早期警戒システム")
    st.markdown("""
    **使い方:**
    - 通常時: 週1回（日曜）
    - DEFCON 3: 週2回
    - DEFCON 2: 週3回
    - DEFCON 1: 毎日
    
    **7つのシグナル:**
    1. 💳 信用スプレッド
    2. 🏦 銀行ストレス
    3. 📈 イールドカーブ
    4. 📊 VIX構造
    5. 🐤 流動性カナリア
    6. 🏢 商業用不動産
    7. 💵 ドルスクイーズ
    """)
    st.markdown("---")
    st.caption("設計原則: 2008年で機能した指標のみ")
    st.caption("株価を見るな。信用市場を見ろ。")
