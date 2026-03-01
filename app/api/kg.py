"""
知识图谱 REST API。

提供从会话历史构建知识图谱 / 列举已生成图谱文件的接口。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os

router = APIRouter()


class KGBuildRequest(BaseModel):
    session_id: str                         # 从哪个会话的历史构建 KG
    output_dir: str = "kg_output"           # KG 文件输出目录
    html_filename: Optional[str] = None     # 可选自定义文件名（不含扩展名）


class KGBuildResponse(BaseModel):
    status: str
    html_path: Optional[str] = None
    json_path: Optional[str] = None
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
        raise HTTPException(status_code=500, detail=f"KG 依赖未安装: {str(e)}")

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
        )
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
        raise HTTPException(status_code=500, detail=f"知识图谱构建失败: {str(e)}")

    return KGBuildResponse(
        status="success",
        html_path=html_path,
        json_path=json_path,
        message=f"知识图谱已从 session '{request.session_id}' 构建完成",
    )


@router.get("/list")
async def list_kg_files(output_dir: str = "kg_output"):
    """列出已生成的知识图谱文件。"""
    if not os.path.exists(output_dir):
        return {"files": []}
    files = [f for f in os.listdir(output_dir) if f.endswith((".html", ".json"))]
    return {"files": sorted(files, reverse=True)}
