import os
from anthropic import Anthropic
import json
from datetime import datetime
from dotenv import load_dotenv

# .env読み込み
load_dotenv()

class AgentAnalysis:
    """Agent Teams市場分析クラス"""
    
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            # APIキーがない場合はNoneにしておく（エラーハンドリングはメソッド内で）
            self.client = None
        else:
            self.client = Anthropic(api_key=api_key)
        
        # モデルは最新のSonnetを使用（必要に応じて変更）
        self.model = "claude-3-5-sonnet-20241022"
    
    def analyze_market(self, indicators_data, portfolio_data=None):
        """
        市場指標を総合分析し、推奨アクションを生成
        """
        if not self.client:
            return {
                "success": False,
                "error": "ANTHROPIC_API_KEY not found in environment",
                "timestamp": datetime.now().isoformat()
            }
        
        # プロンプト構築
        prompt = self._build_prompt(indicators_data, portfolio_data)
        
        try:
            # Claude API呼び出し
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # レスポンス解析
            analysis_text = response.content[0].text
            
            # JSON部分を抽出
            analysis_result = self._parse_response(analysis_text)
            
            return {
                "success": True,
                "analysis": analysis_result,
                "raw_response": analysis_text,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _build_prompt(self, indicators_data, portfolio_data):
        """プロンプト構築"""
        
        dai = indicators_data.get("dai", {})
        cycle = indicators_data.get("cycle", {})
        bubble = indicators_data.get("bubble", {})
        
        prompt = f"""あなたはプロのヘッジファンドマネージャーです。以下の市場指標を総合的に分析し、具体的な投資推奨を提供してください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
市場指標データ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【DAI（デリバティブ異常指数）】
- スコア: {dai.get('dai_score', 'N/A')}
- VIX: {dai.get('vix', 'N/A')}
- 解釈: {dai.get('interpretation', 'N/A')}

【経済サイクル】
- フェーズ: {cycle.get('phase', 'N/A')}
- 米10年債利回り: {cycle.get('yield_10y', 'N/A')}%
- 推奨: {cycle.get('recommendation', 'N/A')}

【バブルスコア】
- スコア: {bubble.get('bubble_score', 'N/A')}
- S&P500 P/E: {bubble.get('sp500_pe', 'N/A')}
- 解釈: {bubble.get('interpretation', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
分析タスク
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

以下の形式でJSONを返してください：

{{
  "market_assessment": {{
    "overall_risk": "低/中/高/極高",
    "confidence": 0-100,
    "key_concerns": ["懸念点1", "懸念点2"],
    "opportunities": ["機会1", "機会2"]
  }},
  "portfolio_recommendations": [
    {{
      "action": "買い/売り/ホールド/リバランス",
      "asset_class": "米国株/債券/現金/コモディティ",
      "target_allocation": "推奨比率（%）",
      "reasoning": "理由",
      "urgency": "低/中/高"
    }}
  ],
  "specific_actions": [
    {{
      "action": "具体的なアクション",
      "ticker": "ティッカー（あれば）",
      "rationale": "根拠",
      "confidence": 0-100
    }}
  ],
  "risk_management": {{
    "stop_loss_level": "損切りレベル（%）",
    "position_sizing": "ポジションサイズ推奨",
    "hedge_recommendation": "ヘッジ推奨"
  }},
  "summary": "100文字程度のサマリー"
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
重要な注意事項
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 指標を総合的に判断してください
2. リスク管理を最優先してください
3. 具体的で実行可能な推奨を提供してください
4. 必ずJSON形式で返してください
"""
        
        if portfolio_data:
            prompt += f"\n\n【現在のポートフォリオ】\n{json.dumps(portfolio_data, indent=2, ensure_ascii=False)}"
        
        return prompt
    
    def _parse_response(self, response_text):
        """レスポンスからJSON抽出"""
        try:
            # JSONブロックを探す
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = response_text[start:end]
                return json.loads(json_str)
            else:
                return {
                    "summary": response_text[:500],
                    "note": "JSON形式ではありません"
                }
        except Exception as e:
            return {
                "error": f"JSON解析エラー: {str(e)}",
                "raw_text": response_text[:500]
            }

# シングルトンインスタンス
agent_analysis = AgentAnalysis()
