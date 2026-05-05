# ChatTutor 桌宠 - macOS 使用指南

## 功能说明

ChatTutor 桌宠是一款**智能学习伴侣**桌面应用，具有以下特点：

- 🎮 **虚拟宠物互动**：可爱的桌宠在屏幕上自由活动
- 💬 **AI 学习答疑**：随时提问，AI  Tutor 一对一解答
- 📊 **知识图谱**：自动构建学习内容的知识网络
- 🎤 **语音输入**：支持语音提问（需麦克风权限）
- 📝 **学习计划**：智能生成个性化学习计划

## macOS 安装步骤

### 1. 安装依赖

运行 macOS 安装脚本：

```bash
cd desk_pet
./install_macos.sh
```

或者手动安装：

```bash
# 安装 PyQt6
pip3 install PyQt6 PyQt6-WebEngine

# 安装 macOS 窗口管理框架
pip3 install pyobjc pyobjc-framework-Quartz pyobjc-framework-Cocoa pyobjc-framework-AppKit

# 安装语音输入（可选）
brew install portaudio
pip3 install pyaudio
```

### 2. 启动后端服务

桌宠需要后端 API 服务支持：

```bash
# 在另一个终端窗口
cd /Users/yuejiaxuan/Downloads/ChatTutor-Demo-feature
python3 -m uvicorn app.api.chat:app --reload --port 8000
```

### 3. 启动桌宠

```bash
cd desk_pet/code
python3 main.py
```

## 使用说明

### 基本操作

| 操作 | 效果 |
|------|------|
| **双击桌宠** | 打开/关闭聊天界面 |
| **拖拽桌宠** | 移动位置，松手后会掉落 |
| **右键点击** | 打开菜单（创建任务、选择任务、退出） |
| **回车发送** | 发送输入框中的消息 |
| **按住麦克风** | 语音输入（松开手发送） |

### 窗口透明问题

如果桌宠背景不透明，尝试：

1. 确保安装了最新的 pyobjc-framework
2. 重启应用
3. 检查 macOS 系统偏好设置 → 安全性与隐私 → 辅助功能权限

### 语音输入问题

如果语音输入不可用：

1. 检查麦克风权限：系统偏好设置 → 安全性与隐私 → 隐私 → 麦克风
2. 确保安装了 PyAudio 和 portaudio
3. 检查默认麦克风设备

## 常见问题

### Q: 桌宠无法置顶？

A: macOS 的窗口管理机制与 Windows 不同。确保：
- 已安装 pyobjc-framework-Quartz
- 没有在系统偏好设置中限制应用权限

### Q: 拖拽时桌宠闪烁？

A: 这是正常的。macOS 的透明窗口渲染有限制，拖拽时可能会有轻微闪烁。

### Q: 语音输入没有反应？

A: 检查：
- PyAudio 是否正确安装：`pip3 list | grep -i pyaudio`
- 麦克风权限是否授予
- 默认输入设备是否正确设置

### Q: 后端 API 连接失败？

A: 确保：
- 后端服务在 `http://127.0.0.1:8000` 运行
- 防火墙没有阻止本地连接
- 检查终端是否有报错信息

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      ChatTutor 桌宠                          │
├─────────────────────────────────────────────────────────────┤
│  前端界面：PyQt6 + PyQt6-WebEngine                          │
│  窗口管理：pyobjc-framework-Quartz (macOS)                  │
│  音频处理：PyAudio                                          │
├─────────────────────────────────────────────────────────────┤
│  后端 API：FastAPI + Uvicorn                                │
│  AI 引擎：LangChain + LangGraph + DeepSeek                   │
│  知识图谱：NetworkX + pyvis + transformers                   │
└─────────────────────────────────────────────────────────────┘
```

## 平台差异说明

| 功能 | Windows | macOS | Linux |
|------|---------|-------|-------|
| 窗口置顶 | ✅ | ✅ | ✅ |
| 透明背景 | ✅ | ✅ | ✅ |
| 窗口检测 | ✅ (完整) | ⚠️ (Quartz) | ❌ |
| 语音输入 | ✅ | ✅ | ✅ |
| 桌宠走动 | ✅ | ✅ | ✅ |

**说明**：
- macOS 的窗口检测功能使用 Quartz 框架，可能无法检测所有窗口
- Linux 暂不支持窗口检测，桌宠只能在屏幕底部移动

## 卸载

```bash
# 删除应用
rm -rf desk_pet

# 删除依赖（可选）
pip3 uninstall PyQt6 PyQt6-WebEngine pyobjc pyaudio
```

## 反馈与支持

如有问题，请提交 Issue 或联系开发团队。
