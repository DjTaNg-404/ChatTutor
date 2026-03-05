# desk_pet/code/worker.py
import requests
from PyQt6.QtCore import QThread, pyqtSignal

class AgentWorker(QThread):
    response_ready = pyqtSignal(str, bool)
    
    def __init__(self, api_base_url, session_id, topic, user_input):
        super().__init__()
        self.api_base_url = api_base_url.rstrip("/")
        self.session_id = session_id
        self.topic = topic
        self.user_input = user_input

    def run(self):
        try:
            response = requests.post(
                f"{self.api_base_url}/chat",
                json={"session_id": self.session_id, "message": self.user_input, "topic": self.topic},
                timeout=120,
            )
            if response.status_code != 200:
                self.response_ready.emit(f"接口失败：{response.status_code}", False)
                return
            data = response.json()
            self.response_ready.emit(data.get("reply", ""), bool(data.get("is_concluded", False)))
        except Exception as e:
            self.response_ready.emit(f"错误：{str(e)}", False)