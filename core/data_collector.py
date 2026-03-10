"""
core/data_collector.py
全ページの主要指標を一括収集するモジュール（拡張版 v2）
11カテゴリ → 20カテゴリに拡張
Phase 2でFastAPIにそのまま移行可能な設計
"""

import yfinance as yf
import pandas as pd
import ssl

# SSL証明書エラー回避（Streamlit Cloud対応）
try:
    _create_unverified_https_context = ssl._create_unverified_https_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
import numpy as np
import requests
import json
from datetime import datetime, timedelta


def safe_fetch(func, name):
    """安全にデータ取得（エラーでも他の指標に影響しない）"""
    try:
        return func()
    except Exception as e:
        return {"error": str(e), "source": name}


def get_price_change(ticker, period="1mo"):
    """ティッカーの価格と変動率を取得"""
    data = yf.download(ticker, period=period, progress=False)
    if data.empty:
        return None
    # Handle MultiIndex columns
    if isinstance(data.columns, pd.MultiIndex):
        close = data[("Close", ticker)] if ("Close", ticker) in data.columns else data["Close"].iloc[:, 0]
    else:
        close = data["Close"]
    current = float(close.iloc[-1])
    prev = float(close.iloc[0])
    change_pct = ((current - prev) / prev) * 100
    return {"price": round(current, 2), "change_1m_pct": round(change_pct, 2)}


def get_price_with_ma(ticker, ma_periods=[50, 200], period="1y"):
    """ティッカーの価格と移動平均線、1ヶ月変動率を取得"""
    data = yf.download(ticker, period=period, progress=False)
    if data.empty:
        return None
    if isinstance(data.columns, pd.MultiIndex):
        close = data[("Close", ticker)] if ("Close", ticker) in data.columns else data["Close"].iloc[:, 0]
    else:
        close = data["Close"]

    current = float(close.iloc[-1])

    # 1ヶ月前の価格（約21営業日前）
    lookback = min(21, len(close) - 1)
    prev = float(close.iloc[-lookback - 1]) if len(close) > lookback else float(close.iloc[0])
    change_1m_pct = ((current - prev) / prev) * 100

    result = {
        "price": round(current, 2),
        "change_1m_pct": round(change_1m_pct, 2),
    }
    for p in ma_periods:
        if len(close) >= p:
            ma_val = float(close.rolling(p).mean().iloc[-1])
            result[f"MA{p}"] = round(ma_val, 2)
            result[f"vs_MA{p}_pct"] = round(((current - ma_val) / ma_val) * 100, 2)
    return result


# ============================================================
# 既存11カテゴリ（改善含む）
# ============================================================

def collect_market_indices():
    """【1】主要市場指数"""
    def _fetch():
        tickers = {
            "S&P500": "^GSPC",
            "NASDAQ": "^IXIC",
            "日経225": "^N225",
            "VIX": "^VIX",
            "DXY(ドル指数)": "DX-Y.NYB",
            "Russell2000": "^RUT",
            "TOPIX": "1306.T",
        }
        results = {}
        for name, ticker in tickers.items():
            info = get_price_change(ticker)
            if info:
                results[name] = info
        return results
    return safe_fetch(_fetch, "market_indices")


def collect_bond_yields():
    """【2】金利・債券"""
    def _fetch():
        tickers = {
            "米国2年債": "^IRX",
            "米国10年債": "^TNX",
            "米国30年債": "^TYX",
        }
        results = {}
        for name, ticker in tickers.items():
            info = get_price_change(ticker)
            if info:
                results[name] = info

        # イールドカーブ（10年-2年）
        if "米国10年債" in results and "米国2年債" in results:
            spread = results["米国10年債"]["price"] - results["米国2年債"]["price"]
            results["イールドスプレッド(10Y-2Y)"] = {
                "value": round(spread, 3),
                "inverted": spread < 0
            }
        return results
    return safe_fetch(_fetch, "bond_yields")


def collect_forex():
    """【3】為替"""
    def _fetch():
        tickers = {
            "USD/JPY": "USDJPY=X",
            "EUR/USD": "EURUSD=X",
            "GBP/USD": "GBPUSD=X",
            "USD/CNY": "USDCNY=X",
        }
        results = {}
        for name, ticker in tickers.items():
            info = get_price_change(ticker)
            if info:
                results[name] = info
        return results
    return safe_fetch(_fetch, "forex")


def collect_commodities():
    """【4】商品・インフレ指標"""
    def _fetch():
        tickers = {
            "金(Gold)": "GC=F",
            "銅(Copper)": "HG=F",
            "原油(WTI)": "CL=F",
            "天然ガス": "NG=F",
        }
        results = {}
        for name, ticker in tickers.items():
            info = get_price_change(ticker)
            if info:
                results[name] = info

        # 銅金レシオ（Dr. Copper）
        if "金(Gold)" in results and "銅(Copper)" in results:
            ratio = results["銅(Copper)"]["price"] / results["金(Gold)"]["price"]
            results["銅金レシオ"] = {"value": round(ratio, 6)}
        return results
    return safe_fetch(_fetch, "commodities")


def collect_crypto():
    """【5】暗号資産"""
    def _fetch():
        tickers = {
            "Bitcoin": "BTC-USD",
            "Ethereum": "ETH-USD",
            "Solana": "SOL-USD",
        }
        results = {}
        for name, ticker in tickers.items():
            info = get_price_change(ticker)
            if info:
                results[name] = info
        return results
    return safe_fetch(_fetch, "crypto")


def collect_sectors():
    """【6】セクターETF（ローテーション分析用）"""
    def _fetch():
        tickers = {
            "テクノロジー(XLK)": "XLK",
            "金融(XLF)": "XLF",
            "ヘルスケア(XLV)": "XLV",
            "エネルギー(XLE)": "XLE",
            "生活必需品(XLP)": "XLP",
            "一般消費財(XLY)": "XLY",
            "公益(XLU)": "XLU",
            "不動産(XLRE)": "XLRE",
            "素材(XLB)": "XLB",
            "資本財(XLI)": "XLI",
            "通信(XLC)": "XLC",
        }
        results = {}
        for name, ticker in tickers.items():
            info = get_price_change(ticker)
            if info:
                results[name] = info

        # サイクル判定ヒント
        if results:
            sorted_sectors = sorted(results.items(), key=lambda x: x[1].get("change_1m_pct", 0), reverse=True)
            results["_top3"] = [s[0] for s in sorted_sectors[:3]]
            results["_bottom3"] = [s[0] for s in sorted_sectors[-3:]]
        return results
    return safe_fetch(_fetch, "sectors")


def collect_semiconductor():
    """【7】半導体指標"""
    def _fetch():
        results = {}
        sox = get_price_change("^SOX")
        if sox:
            results["SOX指数"] = sox
        smh = get_price_change("SMH")
        if smh:
            results["SMH(半導体ETF)"] = smh
        return results
    return safe_fetch(_fetch, "semiconductor")


def collect_shipping():
    """【8】海運・バルチック指数"""
    def _fetch():
        results = {}
        bdry = get_price_change("BDRY")
        if bdry:
            results["BDRY(海運ETF)"] = bdry
        sblk = get_price_change("SBLK")
        if sblk:
            results["SBLK(海運株)"] = sblk
        return results
    return safe_fetch(_fetch, "shipping")


def collect_real_estate():
    """【9】不動産・住宅"""
    def _fetch():
        tickers = {
            "XLRE(不動産ETF)": "XLRE",
            "ITB(住宅建設ETF)": "ITB",
            "MBB(住宅ローン証券)": "MBB",
        }
        results = {}
        for name, ticker in tickers.items():
            info = get_price_change(ticker)
            if info:
                results[name] = info
        return results
    return safe_fetch(_fetch, "real_estate")


def collect_options_volatility():
    """【10】オプション・ボラティリティ"""
    def _fetch():
        results = {}
        vix = get_price_change("^VIX", period="5d")
        if vix:
            results["VIX"] = vix
            level = vix["price"]
            if level < 15:
                results["VIX_signal"] = "極端な楽観（警戒）"
            elif level < 20:
                results["VIX_signal"] = "通常"
            elif level < 30:
                results["VIX_signal"] = "やや不安"
            else:
                results["VIX_signal"] = "恐怖（買い場の可能性）"
        return results
    return safe_fetch(_fetch, "options_volatility")


def collect_polymarket():
    """【11】Polymarket予測市場データ"""
    def _fetch():
        url = "https://gamma-api.polymarket.com/events"
        headers = {"User-Agent": "Mozilla/5.0"}
        all_items = []

        for offset in [0, 20]:
            params = {"limit": 20, "active": "true", "closed": "false", "offset": offset}
            try:
                r = requests.get(url, params=params, headers=headers, timeout=10)
                events = r.json()
                if not isinstance(events, list):
                    continue
                for event in events:
                    for m in event.get("markets", []):
                        op = m.get("outcomePrices", "")
                        if isinstance(op, str):
                            try:
                                op = json.loads(op)
                            except:
                                continue
                        if not op:
                            continue
                        outcomes = m.get("outcomes", [])
                        if isinstance(outcomes, str):
                            try:
                                outcomes = json.loads(outcomes)
                            except:
                                continue
                        try:
                            floats = [float(p) for p in op]
                        except:
                            continue
                        if max(floats) >= 0.99 or max(floats) <= 0.01:
                            continue
                        max_idx = floats.index(max(floats))
                        all_items.append({
                            "question": m.get("question", ""),
                            "top_outcome": outcomes[max_idx] if max_idx < len(outcomes) else "?",
                            "probability": round(floats[max_idx] * 100, 1),
                            "volume": float(m.get("volume", 0) or 0),
                        })
            except:
                continue

        # Volume上位10件だけ返す
        sorted_items = sorted(all_items, key=lambda x: x["volume"], reverse=True)
        return sorted_items[:10]
    return safe_fetch(_fetch, "polymarket")


# ============================================================
# 新規9カテゴリ（合計20カテゴリ）
# ============================================================

def collect_interest_rate_cycle():
    """【12】金利サイクル・FRB政策指標
    → 為替と金利サイクル ページ用
    FRBの政策方向を読むための追加指標群"""
    def _fetch():
        results = {}

        # TIPS（インフレ連動債）→ 実質金利の代理変数
        tip = get_price_change("TIP")
        if tip:
            results["TIP(インフレ連動債ETF)"] = tip

        # 5年ブレークイーブンインフレ率の代理（T5YIFR → yfinanceではETFで代替）
        # RINF: ProShares Inflation Expectations ETF
        rinf = get_price_change("RINF")
        if rinf:
            results["RINF(インフレ期待ETF)"] = rinf

        # 短期金利 → FF金利の代理（SHV: 短期国債ETF）
        shv = get_price_change("SHV")
        if shv:
            results["SHV(短期国債ETF)"] = shv

        # 2年債-FF金利スプレッド = 利下げ期待の温度計
        # BIL: 1-3ヶ月 T-Bill ETF
        bil = get_price_change("BIL")
        if bil:
            results["BIL(T-Bill ETF)"] = bil

        # 金利方向の判定ロジック
        if tip and shv:
            # TIPが上昇 → インフレ期待上昇 → 引き締め的
            # SHVが安定 → 短期金利据え置き
            tip_chg = tip.get("change_1m_pct", 0)
            if tip_chg > 1:
                results["_rate_cycle_signal"] = "インフレ期待上昇 → 利下げ後退リスク"
            elif tip_chg < -1:
                results["_rate_cycle_signal"] = "インフレ期待低下 → 利下げ接近の可能性"
            else:
                results["_rate_cycle_signal"] = "インフレ期待安定 → 様子見"

        return results
    return safe_fetch(_fetch, "interest_rate_cycle")


def collect_credit_stress():
    """【13】信用市場ストレス指標
    → Alice Diagnosis ページ（ドミノ Step 3: Credit Crack）用
    信用市場の亀裂を早期検知する"""
    def _fetch():
        results = {}

        # HYG: ハイイールド社債ETF（信用リスクの温度計）
        hyg = get_price_change("HYG")
        if hyg:
            results["HYG(ハイイールド社債)"] = hyg

        # LQD: 投資適格社債ETF
        lqd = get_price_change("LQD")
        if lqd:
            results["LQD(投資適格社債)"] = lqd

        # JNK: SPDRハイイールドETF（HYGと合わせて確認）
        jnk = get_price_change("JNK")
        if jnk:
            results["JNK(ハイイールドETF)"] = jnk

        # 信用スプレッドの代理指標: HYG/LQD比率
        if hyg and lqd:
            spread_ratio = hyg["price"] / lqd["price"]
            hyg_chg = hyg.get("change_1m_pct", 0)
            lqd_chg = lqd.get("change_1m_pct", 0)
            spread_widening = lqd_chg - hyg_chg  # HYGがLQDより下落 = スプレッド拡大

            results["信用スプレッド代理(HYG/LQD)"] = {
                "value": round(spread_ratio, 4),
                "spread_change": round(spread_widening, 2),
            }

            # 信用ストレス判定
            if spread_widening > 2:
                results["_credit_signal"] = "🔴 信用スプレッド急拡大 → 信用収縮リスク"
            elif spread_widening > 0.5:
                results["_credit_signal"] = "🟡 信用スプレッドやや拡大 → 要監視"
            else:
                results["_credit_signal"] = "🟢 信用市場安定"

        return results
    return safe_fetch(_fetch, "credit_stress")


def collect_ai_bubble():
    """【14】AIバブル・テック指標
    → AIバブル崩壊シナリオ ページ用
    → Alice Diagnosis（SaaS Erosion Tracker）用"""
    def _fetch():
        results = {}

        # IGV: iShares Expanded Tech-Software Sector ETF
        igv = get_price_change("IGV")
        if igv:
            results["IGV(ソフトウェアETF)"] = igv

        # ARKK: ARK Innovation ETF（投機的テック指標）
        arkk = get_price_change("ARKK")
        if arkk:
            results["ARKK(イノベーションETF)"] = arkk

        # BOTZ: Global X Robotics & AI ETF
        botz = get_price_change("BOTZ")
        if botz:
            results["BOTZ(AI・ロボティクスETF)"] = botz

        # QQQ: NASDAQ100 ETF
        qqq = get_price_change("QQQ")
        if qqq:
            results["QQQ(NASDAQ100)"] = qqq

        # IGV/SPY比率 → SaaS Erosion Tracker
        spy = get_price_change("SPY")
        if igv and spy:
            igv_spy_ratio = igv["price"] / spy["price"]
            results["IGV/SPY比率(SaaS侵食度)"] = {
                "value": round(igv_spy_ratio, 4),
            }
            # IGVがSPYをアンダーパフォーム → AI/SaaS株の優位性崩壊
            relative_perf = igv.get("change_1m_pct", 0) - spy.get("change_1m_pct", 0)
            results["IGV対SPY相対パフォーマンス"] = {
                "value": round(relative_perf, 2),
            }
            if relative_perf < -5:
                results["_ai_bubble_signal"] = "🔴 SaaS/AIセクター急落 → バブル崩壊リスク"
            elif relative_perf < -2:
                results["_ai_bubble_signal"] = "🟡 SaaS/AIセクター弱含み → 警戒"
            else:
                results["_ai_bubble_signal"] = "🟢 SaaS/AIセクター堅調"

        return results
    return safe_fetch(_fetch, "ai_bubble")


def collect_advanced_volatility():
    """【15】高度なボラティリティ指標
    → オプション市場 ページ用
    → 市場の歪みとデリバティブ ページ用"""
    def _fetch():
        results = {}

        # MOVE指数の代理（債券ボラティリティ）→ 直接取得不可のためTLT ATRで代替
        tlt = get_price_change("TLT", period="5d")
        if tlt:
            results["TLT(長期債ETF/5日)"] = tlt

        # UVXY: ProShares Ultra VIX Short-Term Futures ETF（VIX先物構造の代理）
        uvxy = get_price_change("UVXY", period="5d")
        if uvxy:
            results["UVXY(VIX先物ETF/5日)"] = uvxy

        # SVXY: ProShares Short VIX（VIXショート → コンタンゴ/バックワーデーション判定）
        svxy = get_price_change("SVXY", period="5d")
        if svxy:
            results["SVXY(VIXショートETF/5日)"] = svxy

        # VIXターム構造の代理: UVXY/SVXY比率
        if uvxy and svxy:
            vix_term = uvxy["price"] / svxy["price"]
            results["VIXターム構造(UVXY/SVXY)"] = {"value": round(vix_term, 4)}

            uvxy_chg = uvxy.get("change_1m_pct", 0)
            svxy_chg = svxy.get("change_1m_pct", 0)
            if uvxy_chg > 10 and svxy_chg < -5:
                results["_vol_signal"] = "🔴 VIXバックワーデーション → パニック的状況"
            elif uvxy_chg > 5:
                results["_vol_signal"] = "🟡 短期VIX上昇 → 不安定"
            else:
                results["_vol_signal"] = "🟢 VIXコンタンゴ → 通常"

        return results
    return safe_fetch(_fetch, "advanced_volatility")


def collect_currency_strength():
    """【16】世界の通貨強弱
    → 世界の通貨強弱 ページ用"""
    def _fetch():
        tickers = {
            "AUD/USD": "AUDUSD=X",
            "NZD/USD": "NZDUSD=X",
            "USD/CHF": "USDCHF=X",
            "USD/CAD": "USDCAD=X",
            "USD/MXN": "USDMXN=X",
            "USD/ZAR": "USDZAR=X",
            "USD/TRY": "USDTRY=X",
            "USD/BRL": "USDBRL=X",
            "USD/KRW": "USDKRW=X",
        }
        results = {}
        for name, ticker in tickers.items():
            info = get_price_change(ticker)
            if info:
                results[name] = info

        # ドル強弱判定: 主要通貨に対するドルの平均変動
        usd_changes = []
        for name, val in results.items():
            chg = val.get("change_1m_pct", 0)
            if name.startswith("USD/"):
                usd_changes.append(chg)  # ドル高 = プラス
            else:
                usd_changes.append(-chg)  # ドル高 = 相手通貨安 = マイナス反転

        if usd_changes:
            avg_usd = np.mean(usd_changes)
            results["_dollar_strength"] = {
                "avg_change_pct": round(avg_usd, 2),
                "signal": "ドル高" if avg_usd > 1 else "ドル安" if avg_usd < -1 else "中立",
            }

        return results
    return safe_fetch(_fetch, "currency_strength")


def collect_liquidity_domino():
    """【17】流動性ドミノ指標（Alice Diagnosis入力）
    → Alice Diagnosis ページ用
    DXY → BTC → Credit → S&P500 のドミノ連鎖を監視"""
    def _fetch():
        results = {}

        # Step 1: DXYスパイク判定
        dxy = get_price_with_ma("DX-Y.NYB", ma_periods=[50, 200])
        if dxy:
            results["DXY"] = dxy
            dxy_price = dxy["price"]
            if dxy_price > 105:
                results["_domino_step1"] = "🔴 DXY高水準 → 流動性吸収中"
            elif dxy_price > 100:
                results["_domino_step1"] = "🟡 DXY上昇傾向 → 要警戒"
            else:
                results["_domino_step1"] = "🟢 DXY正常範囲"

        # Step 2: BTC カナリア（BTCがMA50を下回っているか）
        btc = get_price_with_ma("BTC-USD", ma_periods=[50, 200])
        if btc:
            results["BTC(MA分析)"] = btc
            if "vs_MA50_pct" in btc:
                if btc["vs_MA50_pct"] < -10:
                    results["_domino_step2"] = "🔴 BTC MA50大幅下回り → リスク資産崩壊中"
                elif btc["vs_MA50_pct"] < 0:
                    results["_domino_step2"] = "🟡 BTC MA50下回り → カナリア警告"
                else:
                    results["_domino_step2"] = "🟢 BTC MA50上 → 正常"

        # Step 3: 信用クラック（HYGの急落）
        hyg = get_price_with_ma("HYG", ma_periods=[50])
        if hyg:
            results["HYG(MA分析)"] = hyg
            if "vs_MA50_pct" in hyg:
                if hyg["vs_MA50_pct"] < -3:
                    results["_domino_step3"] = "🔴 信用市場クラック → HYG急落中"
                elif hyg["vs_MA50_pct"] < -1:
                    results["_domino_step3"] = "🟡 信用市場にストレス"
                else:
                    results["_domino_step3"] = "🟢 信用市場安定"

        # Step 4: S&P500メルトダウン
        spy = get_price_with_ma("SPY", ma_periods=[50, 200])
        if spy:
            results["SPY(MA分析)"] = spy
            if "vs_MA200_pct" in spy:
                if spy["vs_MA200_pct"] < -10:
                    results["_domino_step4"] = "🔴 S&P500メルトダウン → MA200大幅下回り"
                elif spy["vs_MA200_pct"] < 0:
                    results["_domino_step4"] = "🟡 S&P500 MA200割れ → ベアマーケット警戒"
                else:
                    results["_domino_step4"] = "🟢 S&P500 MA200上 → 強気継続"

        # ドミノ総合判定
        domino_count = 0
        for key in ["_domino_step1", "_domino_step2", "_domino_step3", "_domino_step4"]:
            if key in results and "🔴" in results[key]:
                domino_count += 1

        results["_domino_total"] = {
            "active": domino_count,
            "total": 4,
            "signal": f"ドミノ {domino_count}/4 点灯",
            "severity": "CRITICAL" if domino_count >= 3 else "WARNING" if domino_count >= 2 else "CAUTION" if domino_count >= 1 else "NORMAL"
        }

        return results
    return safe_fetch(_fetch, "liquidity_domino")


def collect_sector_rotation():
    """【18】セクターローテーション分析
    → セクターローテーション ページ用
    攻撃的 vs 防御的セクターの相対強度"""
    def _fetch():
        results = {}

        # 攻撃的セクター
        offensive = {"XLK": "テクノロジー", "XLY": "一般消費財", "XLI": "資本財", "XLF": "金融"}
        # 防御的セクター
        defensive = {"XLU": "公益", "XLP": "生活必需品", "XLV": "ヘルスケア", "XLRE": "不動産"}

        off_changes = []
        def_changes = []

        for ticker, name in offensive.items():
            info = get_price_change(ticker)
            if info:
                results[f"攻撃_{name}({ticker})"] = info
                off_changes.append(info.get("change_1m_pct", 0))

        for ticker, name in defensive.items():
            info = get_price_change(ticker)
            if info:
                results[f"防御_{name}({ticker})"] = info
                def_changes.append(info.get("change_1m_pct", 0))

        if off_changes and def_changes:
            off_avg = np.mean(off_changes)
            def_avg = np.mean(def_changes)
            rotation = off_avg - def_avg

            results["_rotation_analysis"] = {
                "offensive_avg": round(off_avg, 2),
                "defensive_avg": round(def_avg, 2),
                "rotation_score": round(rotation, 2),
            }

            if rotation > 3:
                results["_rotation_signal"] = "強いリスクオン（攻撃的セクター優勢）"
                results["_cycle_hint"] = "Early〜Mid サイクル"
            elif rotation > 0:
                results["_rotation_signal"] = "やや攻撃的（緩やかなリスクオン）"
                results["_cycle_hint"] = "Mid サイクル"
            elif rotation > -3:
                results["_rotation_signal"] = "やや防御的（緩やかなリスクオフ）"
                results["_cycle_hint"] = "Late サイクル"
            else:
                results["_rotation_signal"] = "強いリスクオフ（防御的セクター優勢）"
                results["_cycle_hint"] = "Late〜Recession サイクル"

        return results
    return safe_fetch(_fetch, "sector_rotation")


def collect_btc_vs_financials():
    """【19】BTC vs 金融株
    → BTCと金融株の対決 ページ用"""
    def _fetch():
        results = {}

        btc = get_price_change("BTC-USD")
        xlf = get_price_change("XLF")

        if btc:
            results["Bitcoin"] = btc
        if xlf:
            results["XLF(金融ETF)"] = xlf

        if btc and xlf:
            btc_chg = btc.get("change_1m_pct", 0)
            xlf_chg = xlf.get("change_1m_pct", 0)
            relative = btc_chg - xlf_chg
            results["BTC対金融_相対パフォーマンス"] = {
                "value": round(relative, 2),
            }
            if relative > 10:
                results["_btc_fin_signal"] = "BTC圧倒的優勢 → リスクオン/投機的"
            elif relative > 0:
                results["_btc_fin_signal"] = "BTC優勢 → デジタル資産への資金流入"
            elif relative > -10:
                results["_btc_fin_signal"] = "金融株優勢 → 伝統的資産回帰"
            else:
                results["_btc_fin_signal"] = "金融株圧倒的優勢 → リスクオフ/暗号資産離れ"

        # GBTC（Grayscale Bitcoin Trust）も追跡
        gbtc = get_price_change("GBTC")
        if gbtc:
            results["GBTC(ビットコイン信託)"] = gbtc

        return results
    return safe_fetch(_fetch, "btc_vs_financials")


def collect_market_distortions():
    """【20】市場の歪み・デリバティブ
    → 市場の歪みとデリバティブ ページ用"""
    def _fetch():
        results = {}

        # TAIL: Cambria Tail Risk ETF（テールリスクヘッジの価格）
        tail = get_price_change("TAIL")
        if tail:
            results["TAIL(テールリスクETF)"] = tail

        # CDS代理: EMB（新興国債ETF）vs AGG（米国総合債券ETF）
        emb = get_price_change("EMB")
        if emb:
            results["EMB(新興国債券ETF)"] = emb

        agg = get_price_change("AGG")
        if agg:
            results["AGG(米国総合債券ETF)"] = agg

        # 新興国スプレッド代理
        if emb and agg:
            em_spread = emb.get("change_1m_pct", 0) - agg.get("change_1m_pct", 0)
            results["新興国スプレッド変化"] = {
                "value": round(em_spread, 2),
            }
            if em_spread < -3:
                results["_distortion_signal"] = "🔴 新興国債からの資金流出加速"
            elif em_spread < -1:
                results["_distortion_signal"] = "🟡 新興国に若干のストレス"
            else:
                results["_distortion_signal"] = "🟢 新興国債券市場安定"

        # BKLN: 変動金利ローンETF（信用リスクのもう一つの温度計）
        bkln = get_price_change("BKLN")
        if bkln:
            results["BKLN(変動金利ローンETF)"] = bkln

        return results
    return safe_fetch(_fetch, "market_distortions")


# ============================================================
# collect_all() — 全20カテゴリを一括収集
# ============================================================

def collect_all():
    """全データを一括収集（20カテゴリ）"""
    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        # --- 既存11カテゴリ ---
        "market_indices": collect_market_indices(),         # 1
        "bond_yields": collect_bond_yields(),               # 2
        "forex": collect_forex(),                           # 3
        "commodities": collect_commodities(),               # 4
        "crypto": collect_crypto(),                         # 5
        "sectors": collect_sectors(),                       # 6
        "semiconductor": collect_semiconductor(),           # 7
        "shipping": collect_shipping(),                     # 8
        "real_estate": collect_real_estate(),               # 9
        "options_volatility": collect_options_volatility(),  # 10
        "polymarket": collect_polymarket(),                 # 11

        # --- 新規9カテゴリ ---
        "interest_rate_cycle": collect_interest_rate_cycle(),  # 12
        "credit_stress": collect_credit_stress(),              # 13
        "ai_bubble": collect_ai_bubble(),                      # 14
        "advanced_volatility": collect_advanced_volatility(),  # 15
        "currency_strength": collect_currency_strength(),      # 16
        "liquidity_domino": collect_liquidity_domino(),        # 17
        "sector_rotation": collect_sector_rotation(),          # 18
        "btc_vs_financials": collect_btc_vs_financials(),      # 19
        "market_distortions": collect_market_distortions(),    # 20
    }
    return data


# ============================================================
# format_for_prompt() — 全20カテゴリをテキスト化
# ============================================================

def format_for_prompt(data):
    """Claude APIに送るためにデータをテキスト化（20カテゴリ対応）"""
    lines = []
    lines.append(f"=== 市場データ収集結果 ({data['timestamp']}) ===\n")

    sections = {
        # 既存
        "market_indices": "📊 主要市場指数",
        "bond_yields": "📈 金利・債券",
        "forex": "💱 為替（主要通貨）",
        "commodities": "🛢 商品・インフレ",
        "crypto": "🪙 暗号資産",
        "sectors": "🔄 セクターETF (1ヶ月変動)",
        "semiconductor": "💾 半導体",
        "shipping": "🚢 海運",
        "real_estate": "🏠 不動産",
        "options_volatility": "📉 オプション・ボラティリティ",
        # 新規
        "interest_rate_cycle": "🏦 金利サイクル・FRB政策",
        "credit_stress": "💳 信用市場ストレス",
        "ai_bubble": "🤖 AI/テックバブル指標",
        "advanced_volatility": "📊 高度ボラティリティ分析",
        "currency_strength": "🌍 世界の通貨強弱",
        "liquidity_domino": "🎯 流動性ドミノ（Alice Diagnosis入力）",
        "sector_rotation": "🔀 セクターローテーション分析",
        "btc_vs_financials": "⚔️ BTC vs 金融株",
        "market_distortions": "⚠️ 市場の歪み・デリバティブ",
    }

    for key, title in sections.items():
        section_data = data.get(key, {})
        if isinstance(section_data, dict) and "error" not in section_data:
            lines.append(f"\n{title}")
            for name, val in section_data.items():
                if name.startswith("_"):
                    # シグナル情報はそのまま表示
                    if isinstance(val, dict):
                        for sk, sv in val.items():
                            lines.append(f"  [{name}] {sk}: {sv}")
                    else:
                        lines.append(f"  {name}: {val}")
                elif isinstance(val, dict):
                    if "price" in val:
                        chg = val.get('change_1m_pct', 0)
                        arrow = '↑' if chg > 0 else '↓' if chg < 0 else '→'
                        # MA情報があれば追加
                        ma_info = ""
                        for mk, mv in val.items():
                            if mk.startswith("vs_MA"):
                                period = mk.replace("vs_MA", "").replace("_pct", "")
                                ma_info += f" [MA{period}: {mv:+.1f}%]"
                        lines.append(f"  {name}: {val['price']} ({arrow}{chg:+.2f}%){ma_info}")
                    elif "value" in val:
                        extra = ""
                        for ek, ev in val.items():
                            if ek != "value":
                                extra += f" ({ek}: {ev})"
                        lines.append(f"  {name}: {val['value']}{extra}")
                    else:
                        lines.append(f"  {name}: {val}")
                else:
                    lines.append(f"  {name}: {val}")

    # Polymarket
    poly = data.get("polymarket", [])
    if isinstance(poly, list) and poly:
        lines.append("\n🔮 Polymarket予測市場 (Volume上位)")
        for p in poly:
            lines.append(f"  Q: {p['question']}")
            lines.append(f"    → {p['top_outcome']}: {p['probability']}% (Vol: ${p['volume']:,.0f})")

    return "\n".join(lines)


# ============================================================
# ポートフォリオ関連（変更なし）
# ============================================================

def parse_portfolio_csv(uploaded_file):
    """IB証券CSVからポートフォリオデータを解析"""
    import io
    try:
        lines = uploaded_file.getvalue().decode("utf-8", errors='replace').splitlines()
        header_row_index = -1
        for i, line in enumerate(lines):
            if "Symbol" in line and ("ClientAccountID" in line or "Account" in line):
                header_row_index = i
                break
        if header_row_index == -1:
            return None, "CSVのヘッダーが見つかりません"

        csv_text = "\n".join(lines[header_row_index:])
        df = pd.read_csv(io.StringIO(csv_text))
        if "Symbol" not in df.columns:
            return None, "'Symbol' 列が見つかりません"
        return df, None
    except Exception as e:
        return None, str(e)


def analyze_portfolio_for_agent(df_portfolio):
    """ポートフォリオの保有銘柄を分析してAI用テキストを生成（高速版）"""
    results = []
    symbols = df_portfolio["Symbol"].dropna().unique()
    clean_symbols = []
    for s in symbols:
        s = str(s).strip()
        if s:
            clean_symbols.append(s)

    # USD/JPYレート取得
    try:
        jpy_data = yf.download("JPY=X", period="1d", progress=False)
        if not jpy_data.empty:
            close = jpy_data["Close"]
            usdjpy = float(close.iloc[-1, 0]) if isinstance(close, pd.DataFrame) else float(close.iloc[-1])
        else:
            usdjpy = 150.0
    except:
        usdjpy = 150.0

    # 一括ダウンロードで高速化
    all_tickers = " ".join(clean_symbols)
    try:
        hist_data = yf.download(all_tickers, period="6mo", progress=False, group_by="ticker", threads=True)
    except:
        hist_data = pd.DataFrame()

    for symbol in clean_symbols:
        is_japan = symbol.endswith(".T")
        ticker_symbol = symbol

        try:
            # 一括データから取得
            if len(clean_symbols) == 1:
                hist = hist_data
            else:
                try:
                    hist = hist_data[symbol] if symbol in hist_data.columns.get_level_values(0) else pd.DataFrame()
                except:
                    hist = pd.DataFrame()

            if isinstance(hist, pd.DataFrame) and not hist.empty and "Close" in hist.columns:
                hist = hist.dropna(subset=["Close"])

            if isinstance(hist, pd.DataFrame) and not hist.empty and len(hist) > 1:
                current_price = float(hist["Close"].iloc[-1])
                price_6m_ago = float(hist["Close"].iloc[0])
                change_6m = ((current_price - price_6m_ago) / price_6m_ago) * 100
            else:
                current_price = 0
                change_6m = 0

            # トレンド判定
            trend = "不明"
            if isinstance(hist, pd.DataFrame) and len(hist) > 50:
                sma20 = hist["Close"].rolling(20).mean()
                sma50 = hist["Close"].rolling(50).mean()
                if len(sma20.dropna()) > 0 and len(sma50.dropna()) > 0:
                    trend = "上昇" if float(sma20.iloc[-1]) > float(sma50.iloc[-1]) else "下降"

            # 数量とCSV情報を先に取得
            symbol_rows = df_portfolio[df_portfolio["Symbol"].astype(str).str.strip() == symbol]
            quantity = 0
            position_value = 0
            if len(symbol_rows) > 0:
                if "Quantity" in df_portfolio.columns:
                    quantity = float(symbol_rows["Quantity"].sum())
                elif "Position" in df_portfolio.columns:
                    quantity = float(symbol_rows["Position"].sum())
                if "PositionValue" in df_portfolio.columns:
                    position_value = float(symbol_rows["PositionValue"].sum())

            # 個別Tickerで配当・セクター情報取得（タイムアウト対策付き）
            info = {}
            div_yield = 0
            annual_div_per_share = 0
            sector = "不明"
            try:
                t = yf.Ticker(ticker_symbol)
                info = t.info or {}
                div_yield = info.get("dividendYield", 0) or 0
                sector = info.get("sector", "不明")

                # 配当履歴から取得
                try:
                    divs = t.dividends
                    if divs is not None and len(divs) > 0:
                        now = pd.Timestamp.now()
                        if divs.index.tz is not None:
                            now = now.tz_localize(divs.index.tz)
                        one_year_ago = now - pd.DateOffset(years=1)
                        recent_divs = divs[divs.index >= one_year_ago]
                        if len(recent_divs) > 0:
                            annual_div_per_share = float(recent_divs.sum())
                except:
                    pass

                # フォールバック1: dividendRate
                if annual_div_per_share == 0:
                    dr = info.get("dividendRate", 0) or 0
                    if dr > 0:
                        annual_div_per_share = float(dr)
            except:
                pass

            # フォールバック2: dividendYield × 価格から概算
            if annual_div_per_share == 0 and div_yield > 0 and current_price > 0:
                annual_div_per_share = current_price * div_yield

            # フォールバック3: PositionValueとdividendYieldから概算
            if annual_div_per_share == 0 and div_yield > 0 and position_value > 0:
                annual_div_per_share = (position_value / abs(quantity)) * div_yield if quantity != 0 else 0

            annual_dividend = annual_div_per_share * abs(quantity)

            results.append({
                "symbol": symbol,
                "ticker": ticker_symbol,
                "name": info.get("shortName", symbol),
                "price": round(current_price, 2),
                "change_6m_pct": round(change_6m, 1),
                "trend": trend,
                "div_yield": round(div_yield * 100, 2) if div_yield and div_yield < 0.2 else round(div_yield, 2) if div_yield else 0,
                "sector": sector,
                "is_japan": is_japan,
                "quantity": quantity,
                "annual_dividend": round(annual_dividend, 2),
                "annual_div_per_share": round(annual_div_per_share, 4),
            })
        except Exception as e:
            results.append({"symbol": symbol, "ticker": ticker_symbol, "error": str(e)})

    total_annual_div_usd = sum(h.get("annual_dividend", 0) for h in results if "error" not in h and not h.get("is_japan", False))
    total_annual_div_jpy_stocks = sum(h.get("annual_dividend", 0) for h in results if "error" not in h and h.get("is_japan", False))
    total_annual_div_jpy = total_annual_div_usd * usdjpy + total_annual_div_jpy_stocks
    monthly_dividend_jpy = total_annual_div_jpy / 12

    return {
        "holdings": results,
        "usdjpy": usdjpy,
        "count": len(results),
        "total_annual_dividend_jpy": round(total_annual_div_jpy),
        "monthly_dividend_jpy": round(monthly_dividend_jpy),
        "total_annual_dividend_usd": round(total_annual_div_usd, 2),
    }


def format_portfolio_for_prompt(portfolio_data):
    """ポートフォリオデータをプロンプト用テキストに変換"""
    if not portfolio_data or not portfolio_data.get("holdings"):
        return ""

    lines = []
    lines.append(f"\n=== 保有ポートフォリオ (USD/JPY: {portfolio_data['usdjpy']:.1f}) ===")
    lines.append(f"保有銘柄数: {portfolio_data['count']}")

    for h in portfolio_data["holdings"]:
        if "error" in h:
            lines.append(f"  {h['symbol']}: データ取得エラー")
            continue
        arrow = "↑" if h["change_6m_pct"] > 0 else "↓" if h["change_6m_pct"] < 0 else "→"
        trend_icon = "📈" if h["trend"] == "上昇" else "📉"
        div_text = f" 配当{h['div_yield']}%" if h["div_yield"] > 0 else ""
        jp = " [日本株]" if h["is_japan"] else ""
        lines.append(f"  {h['symbol']} ({h['name']}): {h['price']} {arrow}{h['change_6m_pct']:+.1f}% {trend_icon}{h['trend']} {h['sector']}{div_text}{jp}")

    return "\n".join(lines)
