# desk_pet/code/worker.py
import requests
import json
from PyQt6.QtCore import QThread, pyqtSignal

class AgentWorker(QThread):
    stream_started = pyqtSignal(str)
    chunk_ready = pyqtSignal(str, str)
    stream_finished = pyqtSignal(str)
    response_ready = pyqtSignal(str, bool)
    
    def __init__(self, api_base_url, session_id, topic, user_input):
        super().__init__()
        self.api_base_url = api_base_url.rstrip("/")
        self.session_id = session_id
        self.topic = topic
        self.user_input = user_input

    def _fallback_chat(self):
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

    def run(self):
        try:
            response = requests.post(
                f"{self.api_base_url}/chat/stream",
                json={"session_id": self.session_id, "message": self.user_input, "topic": self.topic},
                timeout=120,
                stream=True,
            )
            if response.status_code != 200:
                self._fallback_chat()
                return

            final_text = ""
            is_concluded = False
            stream_message_id = None

            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                evt = json.loads(raw_line)
                event_type = evt.get("event")
                data = evt.get("data", {})

                if event_type == "start":
                    stream_message_id = f"ai-{data.get('session_id', self.session_id)}-{id(self)}"
                    self.stream_started.emit(stream_message_id)
                elif event_type == "delta":
                    chunk = str(data.get("text", ""))
                    if chunk:
                        final_text += chunk
                        if stream_message_id:
                            self.chunk_ready.emit(stream_message_id, chunk)
                elif event_type == "done":
                    is_concluded = bool(data.get("is_concluded", False))
                elif event_type == "error":
                    self._fallback_chat()
                    return

            if stream_message_id:
                self.stream_finished.emit(stream_message_id)
            self.response_ready.emit(final_text, is_concluded)
        except Exception as e:
            try:
                self._fallback_chat()
            except Exception:
                self.response_ready.emit(f"错误：{str(e)}", False)