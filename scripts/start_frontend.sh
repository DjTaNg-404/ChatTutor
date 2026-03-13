#!/bin/bash

# ChatTutor 前端启动脚本
# 启动 React + Vite 开发服务器

echo "🎨 启动 ChatTutor 前端服务..."

# 进入前端目录
cd "$(dirname "$0")/../Design_Web_Dashboard"

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo "⚠️  未找到 node_modules"
    echo ""
    read -p "是否自动安装依赖？(yes/no): " CONFIRM
    if [ "$CONFIRM" = "yes" ]; then
        echo ""
        echo "🔧 正在安装前端依赖..."
        npm install
        echo ""
        echo "✅ 依赖安装完成!"
    else
        echo "❌ 已取消"
        exit 1
    fi
fi

# 启动开发服务器
npm run dev -- --host 127.0.0.1 --port 5173
