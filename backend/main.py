"""FastAPI 应用入口"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routers import matches, predictions, teams, backtest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 足彩分析 App 启动中...")
    init_db()
    logger.info("✅ 数据库初始化完成")
    yield
    logger.info("👋 应用关闭")


app = FastAPI(
    title="足彩分析 API",
    description="基于历史数据和预测模型的足球比赛分析系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置（允许 Streamlit 前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(matches.router, prefix="/api/matches", tags=["比赛数据"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["预测"])
app.include_router(teams.router, prefix="/api/teams", tags=["球队"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["回测"])


@app.get("/")
async def root():
    return {
        "app": "足彩分析 App",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
