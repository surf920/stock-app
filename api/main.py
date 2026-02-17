
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# パス追加
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.market_indicators import market_indicators
from core.agent_analysis import agent_analysis

app = FastAPI(
    title="Stock App API",
    description="市場指標・ポートフォリオ分析API",
    version="1.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    """ヘルスチェック"""
    return {
        "status": "healthy",
        "service": "Stock App API",
        "endpoints": [
            "/api/dai",
            "/api/cycle",
            "/api/bubble",
            "/api/indicators"
        ]
    }

@app.get("/api/dai")
def get_dai():
    """DAI (Derivative Anomaly Index) 取得"""
    try:
        result = market_indicators.calculate_dai()
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cycle")
def get_cycle():
    """経済サイクル分析取得"""
    try:
        result = market_indicators.calculate_cycle()
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bubble")
def get_bubble():
    """バブルスコア取得"""
    try:
        result = market_indicators.calculate_bubble()
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/indicators")
def get_all_indicators():
    """全市場指標を一括取得"""
    try:
        return market_indicators.get_all_indicators()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/agent/analyze")
def get_agent_analysis():
    """Agent Teams市場分析取得"""
    try:
        # 市場指標取得
        # 注意: market_indicators モジュールが利用可能であることを確認してください
        indicators = market_indicators.get_all_indicators()
        
        # Agent分析実行
        analysis = agent_analysis.analyze_market(indicators)
        
        if not analysis.get("success"):
            raise HTTPException(status_code=500, detail=analysis.get("error"))
        
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
