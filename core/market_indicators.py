import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class MarketIndicators:
    """市場指標計算クラス"""
    
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 300  # 5分キャッシュ
    
    def calculate_dai(self):
        """DAI (Derivative Anomaly Index) 計算"""
        try:
            # VIX
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period="1y")
            current_vix = vix_data['Close'].iloc[-1]
            vix_ma = vix_data['Close'].rolling(window=50).mean().iloc[-1]
            vix_score = (current_vix - vix_ma) / vix_ma * 100
            
            # SKEW
            skew = yf.Ticker("^SKEW")
            skew_data = skew.history(period="6mo")
            current_skew = skew_data['Close'].iloc[-1] if len(skew_data) > 0 else 120
            skew_threshold = 135
            skew_score = max(0, (current_skew - skew_threshold) / 10 * 100)
            
            # Put/Call Ratio（VIXベースで推定）
            put_call_score = max(0, min(100, (current_vix - 15) / 0.3 * 100))
            
            # 統合スコア
            dai_score = (vix_score * 0.4 + skew_score * 0.3 + put_call_score * 0.3)
            dai_score = max(-100, min(100, dai_score))
            
            return {
                "dai_score": round(dai_score, 2),
                "vix": round(current_vix, 2),
                "vix_ma50": round(vix_ma, 2),
                "skew": round(current_skew, 2),
                "interpretation": self._interpret_dai(dai_score),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e), "dai_score": 0}
    
    def _interpret_dai(self, score):
        """DAI解釈"""
        if score > 50:
            return "極度の警戒（テールリスク高）"
        elif score > 20:
            return "警戒（リスク上昇）"
        elif score > -20:
            return "中立"
        else:
            return "安心（リスク低下）"
    
    def calculate_cycle(self):
        """経済サイクル判定"""
        try:
            # 米10年債利回り
            tnx = yf.Ticker("^TNX")
            tnx_data = tnx.history(period="1y")
            current_yield = tnx_data['Close'].iloc[-1]
            yield_ma = tnx_data['Close'].rolling(window=50).mean().iloc[-1]
            yield_trend = "上昇" if current_yield > yield_ma else "下落"
            
            # S&P500
            spy = yf.Ticker("SPY")
            spy_data = spy.history(period="1y")
            current_spy = spy_data['Close'].iloc[-1]
            spy_ma200 = spy_data['Close'].rolling(window=200).mean().iloc[-1]
            equity_trend = "強気" if current_spy > spy_ma200 else "弱気"
            
            # サイクル判定
            if yield_trend == "上昇" and equity_trend == "強気":
                phase = "拡張期（Early/Mid Cycle）"
                recommendation = "リスク資産+、グロース株有利"
            elif yield_trend == "上昇" and equity_trend == "弱気":
                phase = "後期拡張（Late Cycle）"
                recommendation = "防御的セクターへシフト開始"
            elif yield_trend == "下落" and equity_trend == "弱気":
                phase = "景気後退（Recession）"
                recommendation = "キャッシュ・債券、リスク資産回避"
            else:
                phase = "回復期（Recovery）"
                recommendation = "リスク資産買い場、バリュー株有利"
            
            return {
                "phase": phase,
                "yield_10y": round(current_yield, 2),
                "yield_trend": yield_trend,
                "equity_trend": equity_trend,
                "recommendation": recommendation,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e), "phase": "不明"}
    
    def calculate_bubble(self):
        """バブルスコア計算"""
        try:
            # S&P500 P/E Ratio
            spy = yf.Ticker("SPY")
            spy_info = spy.info
            pe_ratio = spy_info.get('trailingPE', 20)
            
            # 過去平均との比較（歴史的平均 ~16）
            historical_avg = 16
            pe_premium = (pe_ratio - historical_avg) / historical_avg * 100
            
            # VIX（低VIX = 過度な楽観）
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period="1mo")
            current_vix = vix_data['Close'].iloc[-1]
            vix_score = max(0, (20 - current_vix) / 20 * 100)
            
            # バブルスコア統合
            bubble_score = (pe_premium * 0.6 + vix_score * 0.4)
            bubble_score = max(0, min(100, bubble_score))
            
            return {
                "bubble_score": round(bubble_score, 2),
                "sp500_pe": round(pe_ratio, 2),
                "historical_pe": historical_avg,
                "vix": round(current_vix, 2),
                "interpretation": self._interpret_bubble(bubble_score),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e), "bubble_score": 0}
    
    def _interpret_bubble(self, score):
        """バブル解釈"""
        if score > 70:
            return "極度のバブル懸念"
        elif score > 40:
            return "バブル的様相"
        elif score > 10:
            return "やや割高"
        else:
            return "妥当な水準"
    
    def get_all_indicators(self):
        """全指標を一括取得"""
        return {
            "dai": self.calculate_dai(),
            "cycle": self.calculate_cycle(),
            "bubble": self.calculate_bubble(),
            "generated_at": datetime.now().isoformat()
        }

# シングルトンインスタンス
market_indicators = MarketIndicators()
