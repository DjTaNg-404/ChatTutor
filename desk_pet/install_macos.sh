#!/bin/bash
# macOS 桌宠依赖安装脚本

echo "======================================"
echo "  ChatTutor 桌宠 - macOS 依赖安装"
echo "======================================"

# 检查 Python 版本
echo ""
echo "1. 检查 Python 环境..."
python3 --version

# 安装 PyQt6
echo ""
echo "2. 安装 PyQt6 和 WebEngine..."
pip3 install PyQt6 PyQt6-WebEngine

# 安装 pyobjc 系列（macOS 窗口管理必需）
echo ""
echo "3. 安装 pyobjc 框架（macOS 窗口管理）..."
pip3 install pyobjc pyobjc-framework-Quartz pyobjc-framework-Cocoa pyobjc-framework-AppKit

# 安装 pyaudio（语音输入）
echo ""
echo "4. 安装 PyAudio（语音输入）..."
# macOS 需要先安装 portaudio
if ! command -v brew &> /dev/null; then
    echo "警告：Homebrew 未安装，PyAudio 可能需要手动安装"
    echo "请先安装 Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
else
    brew install portaudio
    pip3 install pyaudio
fi

echo ""
echo "======================================"
echo "  安装完成！"
echo "======================================"
echo ""
echo "运行桌宠："
echo "  cd desk_pet/code"
echo "  python3 main.py"
echo ""
