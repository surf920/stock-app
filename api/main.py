
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# パス追加
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.market_indicators import market_indicators

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

from core.agent_analysis import agent_analysis

@app.get("/api/agent/analyze")
def get_agent_analysis():
    """Agent Teams市場分析取得"""
    import json as _json
    try:
        indicators = market_indicators.get_all_indicators()
        analysis = agent_analysis.analyze_market(indicators)
        if not analysis.get("success"):
            return JSONResponse(status_code=500, content={"error": str(analysis.get("error", "unknown"))}, media_type="application/json; charset=utf-8")
        return JSONResponse(content=_json.loads(_json.dumps(analysis, ensure_ascii=False, default=str)), media_type="application/json; charset=utf-8")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)}, media_type="application/json; charset=utf-8")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
