#!/bin/bash

# ChatTutor 后端启动脚本
# 启动 FastAPI 服务

echo "🚀 启动 ChatTutor 后端服务..."

# 进入项目根目录
cd "$(dirname "$0")/.."

# 检查虚拟环境 tutor
# 检测顺序：1) VIRTUAL_ENV 包含 tutor  2) CONDA_PREFIX 包含 tutor  3) 项目目录有 tutor
if [ -n "$VIRTUAL_ENV" ] && [[ "$VIRTUAL_ENV" == *"tutor" ]]; then
    echo "✅ 已激活虚拟环境：tutor"
elif [ -n "$CONDA_PREFIX" ] && [[ "$CONDA_PREFIX" == *"tutor" ]]; then
    echo "✅ 已激活 conda 环境：tutor"
elif [ -d "tutor" ]; then
    VENV_DIR="tutor"
    echo "✅ 找到虚拟环境：tutor/"
    source "$VENV_DIR/bin/activate"
else
    echo "⚠️  未找到虚拟环境 tutor"
    echo ""
    read -p "是否自动配置虚拟环境？(yes/no): " CONFIRM
    if [ "$CONFIRM" = "yes" ]; then
        echo ""
        echo "🔧 正在创建虚拟环境..."
        python3 -m venv tutor

        echo "🔧 激活虚拟环境..."
        source tutor/bin/activate

        echo "🔧 安装 Python 依赖..."
        pip install -r requirements.txt

        echo ""
        echo "✅ 虚拟环境配置完成!"
    else
        echo "❌ 已取消"
        exit 1
    fi
fi

# 启动 FastAPI 服务
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
