import streamlit as st
import pandas as pd
import yfinance as yf
import json
import requests
import ssl

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

st.set_page_config(page_title="オプション戦略AI", page_icon="🎯", layout="wide")
st.title("🎯 オプション戦略AI (Options Strategy Advisor)")
st.caption("IBポートフォリオCSVをアップロード → AIが最適なオプション戦略を提案")

# --- Market Context ---
@st.cache_data(ttl=300)
def fetch_market_context():
    context = {}
    try:
        for name, ticker in [("VIX", "^VIX"), ("SPY", "SPY"), ("QQQ", "QQQ"), ("TLT", "TLT"), ("GLD", "GLD")]:
            hist = yf.Ticker(ticker).history(period="5d")
            if not hist.empty and len(hist) >= 2:
                context[name] = {
                    "price": round(float(hist["Close"].iloc[-1]), 2),
                    "change_pct": round(((float(hist["Close"].iloc[-1]) - float(hist["Close"].iloc[-2])) / float(hist["Close"].iloc[-2])) * 100, 2)
                }
    except Exception as e:
        st.warning(f"市場データ取得エラー: {e}")
    return context

market_ctx = fetch_market_context()

# Market Context Display
if market_ctx:
    cols = st.columns(len(market_ctx))
    for i, (name, data) in enumerate(market_ctx.items()):
        emoji = "😰" if name == "VIX" else "📊"
        cols[i].metric(f"{emoji} {name}", f"{data['price']:.2f}", f"{data['change_pct']:+.2f}%",
                       delta_color="inverse" if name == "VIX" else "normal")

st.markdown("---")

# --- CSV Upload ---
st.subheader("📁 IBポートフォリオCSVをアップロード")

uploaded_file = st.file_uploader("Interactive Brokers のポートフォリオCSVファイル", type=["csv"])

if uploaded_file:
    try:
        raw_lines = uploaded_file.getvalue().decode("utf-8").splitlines()

        # IB Flex CSV: find the row with "Symbol" as header
        header_idx = None
        for i, line in enumerate(raw_lines):
            if '"Symbol"' in line or ',Symbol,' in line or line.strip().startswith('"ClientAccountID"'):
                header_idx = i
                break

        if header_idx is not None:
            header = [h.strip().strip('"') for h in raw_lines[header_idx].split(",")]
            data_rows = []
            for line in raw_lines[header_idx + 1:]:
                if line.strip() == "":
                    continue
                vals = [v.strip().strip('"') for v in line.split(",")]
                if len(vals) >= len(header):
                    data_rows.append(vals[:len(header)])
            df = pd.DataFrame(data_rows, columns=header)
        else:
            # Fallback: simple CSV
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file)

        # Clean numeric columns
        for col in ['Quantity', 'MarkPrice', 'PositionValue', 'Position', 'Market Price', 'Market Value', 'Average Cost', 'Unrealized P&L']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')

        # Find symbol column
        symbol_col = None
        for c in ['Symbol', 'symbol', 'Ticker', 'Financial Instrument']:
            if c in df.columns:
                symbol_col = c
                break

        # Find position/quantity column
        pos_col = None
        for c in ['Quantity', 'Position', 'quantity', 'Shares']:
            if c in df.columns:
                pos_col = c
                break

        # Find price column
        price_col = None
        for c in ['MarkPrice', 'Market Price', 'Current Price']:
            if c in df.columns:
                price_col = c
                break

        # Find value column
        value_col = None
        for c in ['PositionValue', 'Market Value', 'Mkt Value']:
            if c in df.columns:
                value_col = c
                break

        # Find currency column
        currency_col = None
        for c in ['CurrencyPrimary', 'Currency']:
            if c in df.columns:
                currency_col = c
                break

        if symbol_col is None:
            st.error("Symbol列が見つかりません。CSVのフォーマットを確認してください。")
            st.dataframe(df.head())
            st.stop()

        # Filter valid rows
        df = df[df[symbol_col].notna() & (df[symbol_col] != '')]
        df = df[~df[symbol_col].str.contains('Total|Summary|---', na=False)]

        st.success(f"✅ {len(df)}銘柄のポートフォリオを読み込みました")

        # --- USD/JPY rate for conversion ---
        try:
            usdjpy_hist = yf.Ticker("USDJPY=X").history(period="2d")
            usdjpy_rate = float(usdjpy_hist["Close"].iloc[-1]) if not usdjpy_hist.empty else 150.0
        except Exception:
            usdjpy_rate = 150.0

        # Sort by JPY-equivalent PositionValue (descending)
        if value_col and currency_col:
            df["_value_jpy"] = df.apply(
                lambda row: row[value_col] * usdjpy_rate if str(row.get(currency_col, "JPY")) == "USD" else row[value_col],
                axis=1
            )
            df = df.sort_values("_value_jpy", ascending=False).drop(columns=["_value_jpy"])

        st.caption(f"💱 USD/JPY換算レート: ¥{usdjpy_rate:.1f}（PositionValueを円換算してソート）")
        st.dataframe(df, use_container_width=True)

        # --- Build portfolio summary for AI ---
        # Separate JPY and USD positions
        jpy_positions = df[df[currency_col] == 'JPY'] if currency_col else pd.DataFrame()
        usd_positions = df[df[currency_col] == 'USD'] if currency_col else df

        portfolio_lines = []
        for _, row in df.iterrows():
            symbol = str(row[symbol_col]).strip()
            if not symbol or symbol == 'nan':
                continue

            currency = str(row[currency_col]) if currency_col else "USD"
            cur_mark = "¥" if currency == "JPY" else "$"

            parts = [f"銘柄: {symbol} ({currency})"]

            if pos_col and pd.notna(row.get(pos_col)):
                parts.append(f"数量: {row[pos_col]}")
            if price_col and pd.notna(row.get(price_col)):
                parts.append(f"価格: {cur_mark}{row[price_col]:,.2f}")
            if value_col and pd.notna(row.get(value_col)):
                parts.append(f"時価: {cur_mark}{row[value_col]:,.0f}")

            portfolio_lines.append(" | ".join(parts))

        # Portfolio summary stats
        jpy_total = jpy_positions[value_col].sum() if not jpy_positions.empty and value_col else 0
        usd_total = usd_positions[value_col].sum() if not usd_positions.empty and value_col else 0
        usd_total_jpy = usd_total * usdjpy_rate
        grand_total_jpy = jpy_total + usd_total_jpy
        portfolio_lines.insert(0, f"## ポートフォリオ概要: JPY資産 ¥{jpy_total:,.0f} / USD資産 ${usd_total:,.0f}（¥{usd_total_jpy:,.0f}換算） / 合計 ¥{grand_total_jpy:,.0f}")

        portfolio_text = "\n".join(portfolio_lines)

        # --- Fetch additional data for key holdings ---
        symbols = [str(row[symbol_col]).strip() for _, row in df.iterrows() if str(row[symbol_col]).strip() and str(row[symbol_col]).strip() != 'nan']
        # Remove Japanese stock suffixes for yfinance
        yf_symbols = []
        for s in symbols[:15]:  # Limit to 15
            if s.endswith('.T'):
                yf_symbols.append(s)
            elif '.' not in s:
                yf_symbols.append(s)

        iv_data = {}
        if yf_symbols:
            with st.spinner("📊 各銘柄のオプションデータを取得中..."):
                for sym in yf_symbols[:10]:
                    try:
                        tk = yf.Ticker(sym)
                        hist = tk.history(period="6mo")
                        if not hist.empty and len(hist) > 20:
                            returns = hist['Close'].pct_change().dropna()
                            hv = float(returns.std() * (252 ** 0.5) * 100)
                            price = float(hist['Close'].iloc[-1])
                            ma50 = float(hist['Close'].rolling(50).mean().iloc[-1]) if len(hist) >= 50 else price
                            iv_data[sym] = {"hv_annual": round(hv, 1), "price": round(price, 2), "ma50": round(ma50, 2)}
                    except:
                        pass

        iv_text = "\n".join([f"- {s}: HV={d['hv_annual']}%, 価格=${d['price']}, 50MA=${d['ma50']}" for s, d in iv_data.items()])

        # Market context text
        mkt_text = "\n".join([f"- {k}: ${v['price']} ({v['change_pct']:+.1f}%)" for k, v in market_ctx.items()])

        # --- AI Analysis ---
        st.markdown("---")
        st.subheader("🤖 AIオプション戦略提案")

        if st.button("🎯 最適オプション戦略を提案", type="primary", use_container_width=True):
            with st.spinner("🧠 AIがポートフォリオを分析してオプション戦略を設計中..."):
                api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
                if not api_key:
                    st.error("ANTHROPIC_API_KEYが設定されていません")
                    st.stop()

                data_text = f"""## ポートフォリオ
{portfolio_text}

## 各銘柄のボラティリティデータ
{iv_text if iv_text else "取得できませんでした"}

## 市場環境
{mkt_text}"""

                system_prompt = """あなたはゴールドマン・サックスとシタデルで20年の経験を持つデリバティブ戦略のスペシャリストです。
クライアントのポートフォリオを分析し、現在の市場環境に最適なオプション戦略を提案します。

【重要】現在の日付は2026年2月です。

【分析ルール】
1. ポートフォリオの具体的な銘柄・数量・損益を必ず参照すること
2. VIXレベルに応じた戦略選択（高VIX→プレミアム売り有利、低VIX→プレミアム買い有利）
3. 各銘柄のHV(ヒストリカルボラティリティ)を考慮
4. 日本株(.T)にはオプション市場がないため、ETFや先物での代替を提案
5. 実行可能な具体的な行使価格・期限・枚数を提示
6. リスク・リワード比を明示

以下のJSON形式で回答:
{
    "portfolio_assessment": {
        "total_risk_level": "LOW/MODERATE/HIGH/VERY_HIGH",
        "headline": "ポートフォリオの特徴を1行で",
        "sector_concentration": "セクター集中リスクの評価。2文で",
        "volatility_profile": "ポートフォリオ全体のボラティリティ特性。2文で",
        "key_risks": ["主要リスク1", "2", "3"]
    },
    "market_regime": {
        "vix_assessment": "VIXから見たオプション市場の状態。2文で",
        "regime": "低ボラ/通常/高ボラ/パニック",
        "strategy_bias": "この環境で有利な戦略の方向性。2文で"
    },
    "recommended_strategies": [
        {
            "priority": 1,
            "name": "戦略名（例: AAPL カバードコール）",
            "type": "Covered Call/Protective Put/Bull Spread/Bear Spread/Iron Condor/Collar/Straddle/Cash Secured Put等",
            "target_symbol": "対象銘柄",
            "rationale": "なぜこの戦略か。3文で。ポートフォリオの状況に紐づけて。",
            "execution": {
                "legs": [
                    {"action": "SELL/BUY", "type": "CALL/PUT", "strike": "行使価格", "expiry": "期限の目安", "quantity": "枚数", "premium_estimate": "想定プレミアム"}
                ]
            },
            "max_profit": "最大利益",
            "max_loss": "最大損失",
            "breakeven": "損益分岐点",
            "probability_of_profit": "利益確率の目安",
            "risk_reward": "リスクリワード比"
        }
    ],
    "hedging_plan": {
        "overall_hedge": "ポートフォリオ全体のヘッジ方針。2-3文",
        "tail_risk_protection": "テールリスク対策。具体的に。2文",
        "cost_estimate": "ヘッジコストの目安"
    },
    "income_plan": {
        "monthly_target": "月間プレミアム収入目標",
        "strategy": "収入戦略の概要。2-3文",
        "candidates": ["収入戦略に適した銘柄1", "2", "3"]
    },
    "risk_monitor": {
        "watch_items": ["監視項目1", "2", "3"],
        "adjustment_triggers": ["調整トリガー1", "2", "3"],
        "next_review": "次の見直しタイミング"
    }
}"""

                headers = {"x-api-key": api_key, "content-type": "application/json", "anthropic-version": "2023-06-01"}
                payload = {"model": "claude-sonnet-4-20250514", "max_tokens": 4096, "system": system_prompt, "messages": [{"role": "user", "content": data_text}]}
                try:
                    resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=120)
                    resp.raise_for_status()
                    result = resp.json()
                    text = ""
                    for block in result.get("content", []):
                        if block.get("type") == "text":
                            text += block["text"]
                    text = text.strip()
                    if text.startswith("```json"): text = text[7:]
                    if text.startswith("```"): text = text[3:]
                    if text.endswith("```"): text = text[:-3]
                    ai = json.loads(text.strip())

                    # === DISPLAY ===

                    # Portfolio Assessment
                    pa = ai.get("portfolio_assessment", {})
                    risk_level = pa.get("total_risk_level", "")
                    risk_color = {"LOW": "#2ecc71", "MODERATE": "#f39c12", "HIGH": "#e74c3c", "VERY_HIGH": "#8b0000"}.get(risk_level, "#888")
                    risk_emoji = {"LOW": "🟢", "MODERATE": "🟡", "HIGH": "🔴", "VERY_HIGH": "💀"}.get(risk_level, "⚪")
                    st.markdown(f'<div style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:20px;border-radius:10px;border-left:5px solid {risk_color};"><h3 style="color:{risk_color};margin-top:0;">{risk_emoji} ポートフォリオリスク: {risk_level}</h3><p style="color:#ddd;font-size:1.1em;">{pa.get("headline","")}</p><p style="color:#bbb;">{pa.get("sector_concentration","")}</p><p style="color:#bbb;">{pa.get("volatility_profile","")}</p></div>', unsafe_allow_html=True)

                    key_risks = pa.get("key_risks", [])
                    if key_risks:
                        st.markdown("**主要リスク:**")
                        for kr in key_risks:
                            st.markdown(f"- ⚠️ {kr}")
                    st.markdown("---")

                    # Market Regime
                    mr = ai.get("market_regime", {})
                    regime = mr.get("regime", "")
                    regime_color = {"低ボラ": "#2ecc71", "通常": "#3498db", "高ボラ": "#e67e22", "パニック": "#e74c3c"}.get(regime, "#888")
                    st.markdown(f"### 📊 市場レジーム: <span style='color:{regime_color}'>{regime}</span>", unsafe_allow_html=True)
                    st.markdown(mr.get("vix_assessment", ""))
                    st.info(f"💡 **戦略バイアス:** {mr.get('strategy_bias', '')}")
                    st.markdown("---")

                    # Recommended Strategies
                    strategies = ai.get("recommended_strategies", [])
                    if strategies:
                        st.markdown("### 🎯 推奨オプション戦略")
                        for s in strategies:
                            priority = s.get("priority", 0)
                            stype = s.get("type", "")
                            type_color = "#8e44ad"
                            if "Put" in stype and ("Protective" in stype or "Bear" in stype):
                                type_color = "#e74c3c"
                            elif "Call" in stype and ("Covered" in stype or "Bull" in stype):
                                type_color = "#2ecc71"
                            elif "Iron" in stype or "Straddle" in stype:
                                type_color = "#f39c12"

                            st.markdown(f'<div style="background:#1a1a2e;padding:15px;border-radius:10px;border-left:4px solid {type_color};margin-bottom:15px;"><h4 style="color:{type_color};margin-top:0;">#{priority} {s.get("name","")} <span style="font-size:0.7em;background:{type_color}33;padding:2px 8px;border-radius:4px;">{stype}</span></h4><p style="color:#bbb;">📌 対象: <b style="color:#ddd;">{s.get("target_symbol","")}</b></p><p style="color:#ddd;">{s.get("rationale","")}</p></div>', unsafe_allow_html=True)

                            # Execution legs
                            legs = s.get("execution", {}).get("legs", [])
                            if legs:
                                leg_html = '<table style="width:100%;border-collapse:collapse;margin:5px 0 10px 0;">'
                                leg_html += '<tr style="border-bottom:1px solid #333;"><th style="color:#888;text-align:left;padding:5px;">Action</th><th style="color:#888;text-align:left;padding:5px;">Type</th><th style="color:#888;text-align:left;padding:5px;">Strike</th><th style="color:#888;text-align:left;padding:5px;">Expiry</th><th style="color:#888;text-align:left;padding:5px;">Qty</th><th style="color:#888;text-align:left;padding:5px;">Premium</th></tr>'
                                for leg in legs:
                                    action_color = "#e74c3c" if leg.get("action") == "SELL" else "#2ecc71"
                                    leg_html += f'<tr><td style="color:{action_color};padding:5px;">{leg.get("action","")}</td><td style="color:#ddd;padding:5px;">{leg.get("type","")}</td><td style="color:#ddd;padding:5px;">{leg.get("strike","")}</td><td style="color:#ddd;padding:5px;">{leg.get("expiry","")}</td><td style="color:#ddd;padding:5px;">{leg.get("quantity","")}</td><td style="color:#f39c12;padding:5px;">{leg.get("premium_estimate","")}</td></tr>'
                                leg_html += '</table>'
                                st.markdown(leg_html, unsafe_allow_html=True)

                            # P&L Profile
                            metrics = [
                                ("最大利益", s.get("max_profit", "-"), "#2ecc71"),
                                ("最大損失", s.get("max_loss", "-"), "#e74c3c"),
                                ("損益分岐", s.get("breakeven", "-"), "#f39c12"),
                                ("勝率目安", s.get("probability_of_profit", "-"), "#3498db"),
                            ]
                            metric_html = '<div style="display:flex;gap:10px;margin:10px 0;">'
                            for label, value, color in metrics:
                                metric_html += f'''
                                <div style="flex:1;background:#1a1a2e;border-radius:8px;padding:12px 10px;border-top:3px solid {color};min-width:0;">
                                    <div style="color:#888;font-size:0.75em;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{label}</div>
                                    <div style="color:{color};font-size:0.95em;font-weight:bold;word-break:break-all;line-height:1.3;">{value}</div>
                                </div>'''
                            metric_html += '</div>'
                            st.markdown(metric_html, unsafe_allow_html=True)
                            st.markdown("---")

                    # Hedging Plan
                    hp = ai.get("hedging_plan", {})
                    if hp:
                        st.markdown("### 🛡️ ヘッジプラン")
                        st.markdown(f'<div style="background:#0a1a2a;padding:15px;border-radius:10px;border-left:4px solid #3498db;"><p style="color:#ddd;">{hp.get("overall_hedge","")}</p><p style="color:#e74c3c;">🛡️ <b>テールリスク対策:</b> {hp.get("tail_risk_protection","")}</p><p style="color:#f39c12;">💰 <b>ヘッジコスト:</b> {hp.get("cost_estimate","")}</p></div>', unsafe_allow_html=True)
                        st.markdown("---")

                    # Income Plan
                    ip = ai.get("income_plan", {})
                    if ip:
                        st.markdown("### 💰 プレミアム収入プラン")
                        st.metric("月間収入目標", ip.get("monthly_target", "-"))
                        st.markdown(ip.get("strategy", ""))
                        candidates = ip.get("candidates", [])
                        if candidates:
                            st.markdown("**収入戦略候補銘柄:** " + " / ".join([f"**{c}**" for c in candidates]))
                        st.markdown("---")

                    # Risk Monitor
                    rm = ai.get("risk_monitor", {})
                    st.markdown("### ⚠️ リスクモニター")
                    for w in rm.get("watch_items", []):
                        st.markdown(f"- 👁️ {w}")
                    triggers = rm.get("adjustment_triggers", [])
                    if triggers:
                        st.markdown("**調整トリガー:**")
                        for t in triggers:
                            st.markdown(f"- 🔔 {t}")
                    review = rm.get("next_review", "")
                    if review:
                        st.info(f"📅 **次の見直し:** {review}")

                except Exception as e:
                    st.error(f"AI分析エラー: {e}")
                    import traceback
                    st.code(traceback.format_exc())

    except Exception as e:
        st.error(f"CSV読み込みエラー: {e}")
        st.info("CSVのフォーマットを確認してください。")
        import traceback
        st.code(traceback.format_exc())

else:
    st.info("👆 IBポートフォリオCSVをアップロードしてください")
    st.markdown("""
    ### 📋 対応フォーマット
    Interactive Brokers のポートフォリオCSVに対応しています。
    
    **必要な列:** Symbol, Position/Quantity, Market Price, Market Value, Average Cost, Unrealized P&L
    
    ### 🎯 AIが提案する戦略
    - **カバードコール** - 保有株からプレミアム収入
    - **プロテクティブプット** - 下落ヘッジ
    - **ブルスプレッド / ベアスプレッド** - 方向性戦略
    - **アイアンコンドル** - レンジ相場戦略
    - **キャッシュセキュアドプット** - 買い増し戦略
    - **カラー** - コスト0ヘッジ
    """)
