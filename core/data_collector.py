"""
core/data_collector.py
全ページの主要指標を一括収集するモジュール
Phase 2でFastAPIにそのまま移行可能な設計
"""

import yfinance as yf
import pandas as pd
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


def collect_market_indices():
    """主要市場指数"""
    def _fetch():
        tickers = {
            "S&P500": "^GSPC",
            "NASDAQ": "^IXIC",
            "日経225": "^N225",
            "VIX": "^VIX",
            "DXY(ドル指数)": "DX-Y.NYB",
        }
        results = {}
        for name, ticker in tickers.items():
            info = get_price_change(ticker)
            if info:
                results[name] = info
        return results
    return safe_fetch(_fetch, "market_indices")


def collect_bond_yields():
    """金利・債券"""
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
    """為替"""
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
    """商品・インフレ指標"""
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
    """暗号資産"""
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
    """セクターETF（ローテーション分析用）"""
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
    """半導体指標"""
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
    """海運・バルチック指数"""
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
    """不動産・住宅"""
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
    """オプション・ボラティリティ"""
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
    """Polymarket予測市場データ"""
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


def collect_all():
    """全データを一括収集"""
    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_indices": collect_market_indices(),
        "bond_yields": collect_bond_yields(),
        "forex": collect_forex(),
        "commodities": collect_commodities(),
        "crypto": collect_crypto(),
        "sectors": collect_sectors(),
        "semiconductor": collect_semiconductor(),
        "shipping": collect_shipping(),
        "real_estate": collect_real_estate(),
        "options_volatility": collect_options_volatility(),
        "polymarket": collect_polymarket(),
    }
    return data


def format_for_prompt(data):
    """Claude APIに送るためにデータをテキスト化"""
    lines = []
    lines.append(f"=== 市場データ収集結果 ({data['timestamp']}) ===\n")

    sections = {
        "market_indices": "📊 主要市場指数",
        "bond_yields": "📈 金利・債券",
        "forex": "💱 為替",
        "commodities": "🛢 商品・インフレ",
        "crypto": "🪙 暗号資産",
        "sectors": "🔄 セクターETF (1ヶ月変動)",
        "semiconductor": "💾 半導体",
        "shipping": "🚢 海運",
        "real_estate": "🏠 不動産",
        "options_volatility": "📉 オプション・ボラティリティ",
    }

    for key, title in sections.items():
        section_data = data.get(key, {})
        if isinstance(section_data, dict) and "error" not in section_data:
            lines.append(f"\n{title}")
            for name, val in section_data.items():
                if name.startswith("_"):
                    lines.append(f"  {name}: {val}")
                elif isinstance(val, dict):
                    if "price" in val:
                        lines.append(f"  {name}: {val['price']} ({val.get('change_1m_pct', 'N/A')}%)")
                    elif "value" in val:
                        lines.append(f"  {name}: {val['value']}")
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
