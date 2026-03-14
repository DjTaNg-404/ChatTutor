import requests
import json
import uuid
from PyQt6.QtCore import QThread, pyqtSignal


class AgentWorker(QThread):
    stream_started = pyqtSignal(str)
    chunk_ready = pyqtSignal(str, str)
    stream_finished = pyqtSignal(str)
    response_ready = pyqtSignal(str, bool)
    session_ready = pyqtSignal(str)
    node_changed = pyqtSignal(str, str)  # (message_id, node_name)
    intent_changed = pyqtSignal(str)  # (intent_text)
    plan_ready = pyqtSignal(object, object)  # (plan_proposal, plan_status)
    
    def __init__(self, api_base_url, session_id, topic, user_input, task_id=None):
        super().__init__()
        self.api_base_url = api_base_url.rstrip("/")
        self.session_id = session_id
        self.topic = topic
        self.user_input = user_input
        self.task_id = task_id
        
        # ====== 【核心修复】：生成绝对唯一的任务标识 ======
        # 替代原来容易被内存复用导致串台的 id(self)
        self.worker_id = uuid.uuid4().hex 
        # ==================================================

    def _plan_hint(self) -> bool:
        return False

    def _fallback_chat(self):
        response = requests.post(
            f"{self.api_base_url}/chat",
            json={
                "task_id": self.task_id,
                "session_id": self.session_id, 
                "message": self.user_input, 
                "topic": self.topic,
                "plan_hint": self._plan_hint(),
                "client": "pet"
            },
            timeout=120,
        )
        if response.status_code != 200:
            self.response_ready.emit(f"接口失败：{response.status_code}", False)
            return
        data = response.json()
        session_id = data.get("session_id")
        if session_id:
            self.session_id = session_id
            self.session_ready.emit(session_id)
        plan_proposal = data.get("plan_proposal")
        plan_status = data.get("plan_status")
        if plan_proposal is not None or (plan_status not in (None, "", "idle")):
            self.plan_ready.emit(plan_proposal, plan_status)
        self.response_ready.emit(data.get("reply", ""), bool(data.get("is_concluded", False)))

    def run(self):
        try:
            response = requests.post(
                f"{self.api_base_url}/chat/stream",
                json={
                    "task_id": self.task_id,
                    "session_id": self.session_id, 
                    "message": self.user_input, 
                    "topic": self.topic,
                    "plan_hint": self._plan_hint(),
                    "client": "pet"
                },
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
                    # ====== 【核心修复】：使用刚生成的唯一 UUID ======
                    stream_message_id = f"ai-{data.get('session_id', self.session_id)}-{self.worker_id}"
                    session_id = data.get("session_id")
                    if session_id:
                        self.session_id = session_id
                        self.session_ready.emit(session_id)
                    # ================================================
                    self.stream_started.emit(stream_message_id)
                elif event_type == "delta":
                    chunk = str(data.get("text", ""))
                    if chunk:
                        final_text += chunk
                        if stream_message_id:
                            self.chunk_ready.emit(stream_message_id, chunk)
                elif event_type == "done":
                    is_concluded = bool(data.get("is_concluded", False))
                    plan_proposal = data.get("plan_proposal")
                    plan_status = data.get("plan_status")
                    if plan_proposal is not None or (plan_status not in (None, "", "idle")):
                        self.plan_ready.emit(plan_proposal, plan_status)
                elif event_type == "node":
                    # 节点变更事件，更新思考状态显示
                    node_name = data.get("node_name", "")
                    if stream_message_id and node_name:
                        self.node_changed.emit(stream_message_id, node_name)
                elif event_type == "intent":
                    # 意图识别结果
                    intent_text = data.get("text", "")
                    if intent_text:
                        self.intent_changed.emit(intent_text)
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
