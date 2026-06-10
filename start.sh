#!/bin/bash
# 足彩分析系统 - 一键启动脚本
# 启动 FastAPI 后端 + Streamlit 前端

echo "⚽ 足彩分析系统启动中..."
echo ""

# 检查虚拟环境
if [ -d "venv" ]; then
    echo "📦 使用虚拟环境 venv"
    source venv/bin/activate
fi

# 启动后端
echo "🚀 启动 FastAPI 后端 (端口 8000)..."
cd "$(dirname "$0")"
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "   后端 PID: $BACKEND_PID"

# 等待后端启动
sleep 2

# 启动前端
echo "🎨 启动 Streamlit 前端 (端口 8501)..."
python3 -m streamlit run app.py --server.port 8501 --server.headless true &
FRONTEND_PID=$!
echo "   前端 PID: $FRONTEND_PID"

echo ""
echo "========================================"
echo "✅ 系统启动完成！"
echo "   后端 API:  http://localhost:8000"
echo "   API 文档:  http://localhost:8000/docs"
echo "   前端页面:  http://localhost:8501"
echo "========================================"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 优雅退出
trap "echo '🛑 停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# 等待子进程
wait
