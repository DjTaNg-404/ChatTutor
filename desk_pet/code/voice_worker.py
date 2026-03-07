import os
import wave
import requests
import pyaudio
from PyQt6.QtCore import QThread, pyqtSignal


class AudioRecorder(QThread):
    def __init__(self, output_path):
        super().__init__()
        self.output_path = output_path
        self.is_recording = False

    def run(self):
        self.is_recording = True
        chunk = 1024
        format = pyaudio.paInt16
        channels = 1
        rate = 16000 # 16kHz 是后端语音识别最喜欢的采样率

        p = pyaudio.PyAudio()
        stream = p.open(format=format, channels=channels, rate=rate, input=True, frames_per_buffer=chunk)
        frames = []

        while self.is_recording:
            data = stream.read(chunk)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        p.terminate()

        wf = wave.open(self.output_path, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(format))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))
        wf.close()

    def stop(self):
        self.is_recording = False


class VoiceAgentWorker(QThread):
    response_ready = pyqtSignal(str, bool)
    
    def __init__(self, api_base_url, session_id, topic, audio_path, task_id=None):
        super().__init__()
        self.api_base_url = api_base_url.rstrip("/")
        self.session_id = session_id
        self.topic = topic
        self.audio_path = audio_path
        self.task_id = task_id

    def run(self):
        try:
            with open(self.audio_path, "rb") as f:
                files = {"file": ("audio.wav", f, "audio/wav")}
                # ======== 【修改】：在此处新增 "client": "pet" 标识 ========
                data = {
                    "task_id": self.task_id,
                    "session_id": self.session_id, 
                    "topic": self.topic,
                    "client": "pet"  # 告诉后端我是桌宠，需要简短回答
                }
                
                response = requests.post(
                    f"{self.api_base_url}/voice_chat", 
                    files=files,
                    data=data,
                    timeout=120,
                )
            
            # ======== 【新增：无痕模式】上传完毕后立即删除本地文件 ========
            if os.path.exists(self.audio_path):
                try:
                    os.remove(self.audio_path)
                except Exception as e:
                    print(f"删除临时音频文件失败: {e}")
            # ==============================================================
                
            if response.status_code != 200:
                self.response_ready.emit(f"语音接口失败：{response.status_code}", False)
                return
                
            res_data = response.json()
            self.response_ready.emit(res_data.get("reply", ""), bool(res_data.get("is_concluded", False)))
            
        except Exception as e:
            self.response_ready.emit(f"网络错误：{str(e)}", False)
            
            # ======== 【新增：无痕模式】就算网络报错，也要把没发出去的音频删掉 ========
            if os.path.exists(self.audio_path):
                try:
                    os.remove(self.audio_path)
                except Exception as del_e:
                    print(f"清理临时音频文件失败: {del_e}")