# ChatTutor-main/start.py
import subprocess
import sys
import time

def main():
    # 获取当前运行的 Python 解释器路径 (也就是你虚拟环境的 python.exe)
    python_exe = sys.executable
    
    # 强制指定项目根目录
    project_dir = r"c:\Users\38839\Desktop\ChatTutor-main"

    print("🚀 [1/2] 正在唤醒后台 API 思考引擎 (FastAPI)...")
    
    # 启动后端的命令
    backend_cmd = [python_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
    # 启动后端，并强制在项目根目录下运行
    backend_process = subprocess.Popen(backend_cmd, cwd=project_dir)

    # 稍微等 2 秒钟，让服务器先启动完毕
    time.sleep(2)

    print("🚀 [2/2] 正在召唤桌面宠物 UI...")
    
    # 【直接使用你提供的绝对路径】
    frontend_path = r"c:\Users\38839\Desktop\ChatTutor-main\desk_pet\code\main.py"
    
    # 启动前端
    frontend_cmd = [python_exe, frontend_path]
    frontend_process = subprocess.Popen(frontend_cmd, cwd=project_dir)

    print("\n✅ 启动完成！您可以开始和 Tutor 聊天了。")
    print("💡 提示：当您退出桌面宠物或按 Ctrl+C 时，后台服务会自动关闭。\n")

    try:
        # 让脚本停在这里，等待前端桌宠被关闭
        frontend_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 收到强行终止信号...")
    finally:
        # 无论如何，最后都把后端服务杀掉
        print("🛑 正在清理并关闭后台 API 引擎...")
        backend_process.terminate()
        backend_process.wait()
        print("✨ ChatTutor 已完全退出，期待下次相见！")

if __name__ == "__main__":
    main()