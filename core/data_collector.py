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
                        chg = val.get('change_1m_pct', 0)
                        arrow = '↑' if chg > 0 else '↓' if chg < 0 else '→'
                        lines.append(f"  {name}: {val['price']} ({arrow}{chg:+.2f}%)")
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
    """ポートフォリオの保有銘柄を分析してAI用テキストを生成"""
    results = []
    symbols = df_portfolio["Symbol"].dropna().unique()

    # USD/JPYレート取得
    try:
        jpy_data = yf.download("JPY=X", period="1d", progress=False)
        if not jpy_data.empty:
            close = jpy_data["Close"]
            if isinstance(close, pd.DataFrame):
                usdjpy = float(close.iloc[-1, 0])
            else:
                usdjpy = float(close.iloc[-1])
        else:
            usdjpy = 150.0
    except:
        usdjpy = 150.0

    for symbol in symbols:
        if not isinstance(symbol, str) or symbol.strip() == "":
            continue
        symbol = symbol.strip()

        # 日本株判定（CSVが 1489.T 形式の場合も対応）
        is_japan = False
        ticker_symbol = symbol
        if symbol.endswith(".T"):
            is_japan = True
            ticker_symbol = symbol
        elif symbol.isdigit():
            ticker_symbol = f"{symbol}.T"
            is_japan = True

        try:
            t = yf.Ticker(ticker_symbol)
            info = t.info or {}
            hist = t.history(period="6mo")
            if hist.empty:
                continue

            current_price = float(hist["Close"].iloc[-1])
            price_6m_ago = float(hist["Close"].iloc[0])
            change_6m = ((current_price - price_6m_ago) / price_6m_ago) * 100

            # トレンド判定
            sma20 = hist["Close"].rolling(20).mean()
            sma50 = hist["Close"].rolling(50).mean()
            if len(sma20.dropna()) > 0 and len(sma50.dropna()) > 0:
                if float(sma20.iloc[-1]) > float(sma50.iloc[-1]):
                    trend = "上昇"
                else:
                    trend = "下降"
            else:
                trend = "不明"

            # 配当
            div_yield = info.get("dividendYield", 0) or 0

            # セクター
            sector = info.get("sector", "不明")

            # 配当金額の取得
            annual_div_per_share = 0
            try:
                divs = t.dividends
                if divs is not None and len(divs) > 0:
                    # タイムゾーン対応
                    now = pd.Timestamp.now()
                    if divs.index.tz is not None:
                        now = now.tz_localize(divs.index.tz)
                    one_year_ago = now - pd.DateOffset(years=1)
                    recent_divs = divs[divs.index >= one_year_ago]
                    if len(recent_divs) > 0:
                        annual_div_per_share = float(recent_divs.sum())
            except:
                pass

            # CSVから保有数量を取得
            symbol_rows = df_portfolio[df_portfolio["Symbol"].astype(str).str.strip() == symbol]
            quantity = 0
            if "Quantity" in df_portfolio.columns:
                quantity = float(symbol_rows["Quantity"].sum()) if len(symbol_rows) > 0 else 0
            elif "Position" in df_portfolio.columns:
                quantity = float(symbol_rows["Position"].sum()) if len(symbol_rows) > 0 else 0

            annual_dividend = annual_div_per_share * abs(quantity)

            results.append({
                "symbol": symbol,
                "ticker": ticker_symbol,
                "name": info.get("shortName", symbol),
                "price": round(current_price, 2),
                "change_6m_pct": round(change_6m, 1),
                "trend": trend,
                "div_yield": round(div_yield * 100, 2) if div_yield else 0,
                "sector": sector,
                "is_japan": is_japan,
                "quantity": quantity,
                "annual_dividend": round(annual_dividend, 2),
                "annual_div_per_share": round(annual_div_per_share, 4),
            })
        except Exception as e:
            results.append({
                "symbol": symbol,
                "ticker": ticker_symbol,
                "error": str(e),
            })

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
