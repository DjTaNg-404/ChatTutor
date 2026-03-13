"""
知识图谱 REST API。

提供从会话历史构建知识图谱 / 列举已生成图谱文件的接口。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import os
import glob
import json

from app.core import memory as mem
from app.core.memory import MEMORY_DIR

router = APIRouter()


class KGBuildRequest(BaseModel):
    session_id: str                         # 从哪个会话的历史构建 KG
    output_dir: str = "kg_output"           # KG 文件输出目录
    html_filename: Optional[str] = None     # 可选自定义文件名（不含扩展名）
    # DeepSeek 配置
    use_deepseek: bool = True               # 默认使用 DeepSeek LLM 提取
    deepseek_model: str = "deepseek-chat"   # DeepSeek 模型名称
    deepseek_api_key: Optional[str] = None  # DeepSeek API 密钥（None 则使用环境变量）


class KGBuildResponse(BaseModel):
    status: str
    html_path: Optional[str] = None
    json_path: Optional[str] = None
    message: str


class KGTaskRequest(BaseModel):
    task_id: str                            # 任务 ID
    output_dir: str = "kg_output"           # KG 文件输出目录
    force_rebuild: bool = False             # 是否强制重新生成（即使已存在）
    # DeepSeek 配置
    use_deepseek: bool = True               # 默认使用 DeepSeek LLM 提取
    deepseek_model: str = "deepseek-chat"   # DeepSeek 模型名称
    deepseek_api_key: Optional[str] = None  # DeepSeek API 密钥（None 则使用环境变量）


class KGTaskResponse(BaseModel):
    status: str
    json_path: Optional[str] = None
    kg_exists: bool = False                 # 是否已存在知识图谱
    message: str


@router.post("/build", response_model=KGBuildResponse)
async def build_kg_from_session(request: KGBuildRequest):
    """
    从指定 session 的对话历史提取并构建知识图谱。
    同步执行，返回输出文件路径。
    """
    try:
        from app.core import memory as mem
        from app.kg.kg_builder import KnowledgeGraphBuilder
        from langchain_core.messages import HumanMessage, AIMessage
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"KG 依赖未安装：{str(e)}")

    # 1. 加载会话历史
    session_state = mem.load_session(request.session_id)
    if not session_state:
        raise HTTPException(status_code=404, detail=f"Session '{request.session_id}' 不存在")

    messages = session_state.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="会话历史为空，无法构建知识图谱")

    # 2. 将消息拼成纯文本
    text_chunks = []
    for msg in messages:
        if isinstance(msg, (HumanMessage, AIMessage)):
            content = getattr(msg, "content", "") or ""
            if content.strip():
                text_chunks.append(content)

    full_text = "\n".join(text_chunks)
    if not full_text.strip():
        raise HTTPException(status_code=400, detail="消息内容为空，无法构建知识图谱")

    # 3. 构建知识图谱
    try:
        builder = KnowledgeGraphBuilder(
            use_advanced_extractor=True,
            use_keybert=True,
            use_spacy=True,
            use_lexicon=True,
            use_deepseek=request.use_deepseek,
            deepseek_model=request.deepseek_model,
            deepseek_api_key=request.deepseek_api_key
        )
        # 只有在使用 DeepSeek 时才不需要加载 NER 模型
        if not request.use_deepseek:
            builder.load_models()
        builder.build_graph(full_text)

        # 4. 写出文件
        os.makedirs(request.output_dir, exist_ok=True)
        base_name = request.html_filename or f"kg_{request.session_id}"
        html_path = os.path.join(request.output_dir, f"{base_name}.html")
        json_path = os.path.join(request.output_dir, f"{base_name}.json")

        builder.visualize_graph(html_path)
        builder.export_graph_data(json_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识图谱构建失败：{str(e)}")

    return KGBuildResponse(
        status="success",
        html_path=html_path,
        json_path=json_path,
        message=f"知识图谱已从 session '{request.session_id}' 构建完成",
    )


@router.post("/build-from-task", response_model=KGTaskResponse)
async def build_kg_from_task(request: KGTaskRequest):
    """
    从指定 task_id 的会话历史提取并构建知识图谱。
    如果知识图谱已存在，则直接返回路径。
    """
    try:
        from app.kg.kg_builder import KnowledgeGraphBuilder
        from langchain_core.messages import HumanMessage, AIMessage
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"KG 依赖未安装：{str(e)}")

    # 检查是否已存在知识图谱（支持带时间戳的文件名）
    os.makedirs(request.output_dir, exist_ok=True)
    pattern1 = os.path.join(request.output_dir, f"kg_task_{request.task_id}*.json")
    pattern2 = os.path.join(request.output_dir, f"kg_{request.task_id}*.json")
    matching_files = glob.glob(pattern1) + glob.glob(pattern2)

    if matching_files and not request.force_rebuild:
        # 选择最新修改的文件
        matching_files.sort(key=os.path.getmtime, reverse=True)
        json_path = matching_files[0]
        return KGTaskResponse(
            status="success",
            json_path=json_path,
            kg_exists=True,
            message=f"知识图谱已存在",
        )

    # 1. 加载会话历史 - 查找 task_id 匹配的最新会话
    # 会话文件名格式：task_{task_id}__{date}__{time}.json
    # 注意：task_id 可能已经包含 "task_" 前缀，需要正确处理
    session_state = mem.load_session(request.task_id)
    if not session_state:
        # 尝试查找匹配 task_id 的最新会话文件
        # request.task_id 可能已经是完整前缀（如 "task_mmj3eqxr"），直接用 glob 查找
        pattern = os.path.join(MEMORY_DIR, f"{request.task_id}__*.json")
        matching_files = glob.glob(pattern)
        if matching_files:
            # 按修改时间排序，选择最新的
            matching_files.sort(key=os.path.getmtime, reverse=True)
            latest_file = matching_files[0]
            latest_session_id = os.path.basename(latest_file)[:-5]  # 去掉 .json 后缀
            session_state = mem.load_session(latest_session_id)

    if not session_state:
        raise HTTPException(status_code=404, detail=f"Task '{request.task_id}' 的会话历史不存在")

    messages = session_state.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="会话历史为空，无法构建知识图谱")

    # 2. 将消息拼成纯文本
    text_chunks = []
    for msg in messages:
        if isinstance(msg, (HumanMessage, AIMessage)):
            content = getattr(msg, "content", "") or ""
            if content.strip():
                text_chunks.append(content)

    full_text = "\n".join(text_chunks)
    if not full_text.strip():
        raise HTTPException(status_code=400, detail="消息内容为空，无法构建知识图谱")

    # 3. 构建知识图谱
    try:
        builder = KnowledgeGraphBuilder(
            use_advanced_extractor=True,
            use_keybert=True,
            use_spacy=True,
            use_lexicon=True,
            use_deepseek=request.use_deepseek,
            deepseek_model=request.deepseek_model,
            deepseek_api_key=request.deepseek_api_key
        )
        if not request.use_deepseek:
            builder.load_models()
        builder.build_graph(full_text)

        # 4. 写出文件（带时间戳的文件名）
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # task_id 已经包含 "task_" 前缀，直接使用
        base_name = f"kg_{request.task_id}__{timestamp}"
        html_path = os.path.join(request.output_dir, f"{base_name}.html")
        json_path = os.path.join(request.output_dir, f"{base_name}.json")

        builder.visualize_graph(html_path)
        builder.export_graph_data(json_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识图谱构建失败：{str(e)}")

    return KGTaskResponse(
        status="success",
        json_path=json_path,
        kg_exists=False,
        message=f"知识图谱已构建完成",
    )


@router.get("/get-task-kg")
async def get_task_kg(task_id: str, output_dir: str = "kg_output"):
    """获取指定 task_id 的知识图谱数据。"""
    # 查找匹配的文件：kg_task_{task_id}*.json 或 kg_{task_id}*.json
    pattern1 = os.path.join(output_dir, f"kg_task_{task_id}*.json")
    pattern2 = os.path.join(output_dir, f"kg_{task_id}*.json")

    matching_files = glob.glob(pattern1) + glob.glob(pattern2)

    if not matching_files:
        return {"exists": False, "data": None, "path": None}

    # 选择最新修改的文件
    matching_files.sort(key=os.path.getmtime, reverse=True)
    json_path = matching_files[0]

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {"exists": True, "data": data, "path": json_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取知识图谱失败：{str(e)}")


@router.get("/list")
async def list_kg_files(output_dir: str = "kg_output"):
    """列出已生成的知识图谱文件。"""
    if not os.path.exists(output_dir):
        return {"files": []}
    files = [f for f in glob.glob(os.path.join(output_dir, "*.json")) if f.endswith(".json")]
    return {"files": sorted(files, reverse=True)}
