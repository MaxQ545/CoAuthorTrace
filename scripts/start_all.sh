#!/bin/bash

# 启动论文合作者追踪系统 - 前后端

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "📚 启动论文合作者追踪系统"
echo "=========================="
echo ""

# 检查虚拟环境
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "❌ 未找到虚拟环境，请先运行: python3 -m venv venv"
    exit 1
fi

# 检查 node_modules
if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
    echo "📦 安装前端依赖..."
    cd "$PROJECT_DIR/frontend"
    npm install
fi

# 启动后端
echo "🚀 启动后端服务 (端口 8000)..."
cd "$PROJECT_DIR"
source venv/bin/activate
python scripts/start_server.py &
BACKEND_PID=$!

# 等待后端启动
sleep 2

# 启动前端
echo "🎨 启动前端服务 (端口 3000)..."
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=========================="
echo "✅ 服务已启动!"
echo ""
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:8000"
echo "   API文档: http://localhost:8000/api/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "=========================="

# 等待并处理退出
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM

wait
