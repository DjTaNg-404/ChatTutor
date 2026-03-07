from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.history import router as history_router
from app.api.kg import router as kg_router
from app.api.notes import router as notes_router
from app.api.task_plan import router as task_plan_router
from app.api.tasks import router as tasks_router

app = FastAPI(
    title="ChatTutor API",
    description="Backend API for ChatTutor Desktop Pet",
    version="1.0.0"
)

# 配置 CORS，允许前端跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 在生产环境中应该限制为特定的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
app.include_router(history_router, prefix="/api/v1/history", tags=["History"])
app.include_router(notes_router, prefix="/api/v1/notes", tags=["Notes"])
app.include_router(task_plan_router, prefix="/api/v1/agent", tags=["Task Plan"])
app.include_router(tasks_router, prefix="/api/v1", tags=["Tasks"])
app.include_router(kg_router, prefix="/api/v1/kg", tags=["Knowledge Graph"])

@app.get("/")
async def root():
    return {"message": "Welcome to ChatTutor API"}
