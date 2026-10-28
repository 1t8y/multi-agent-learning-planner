# -*- coding: utf-8 -*-
"""
后端API服务
提供资源反馈和提交的REST API接口

核心功能：
- 接收用户反馈
- 接收资源提交
- 获取知识库统计
"""

import os
import json
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from fastapi.middleware.cors import CORSMiddleware
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("[api_server] 警告: fastapi未安装")


if FASTAPI_AVAILABLE:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        init_services()
        init_orchestrator()
        yield

    app = FastAPI(title="学习规划助手API", version="2.6.4", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class FeedbackData(BaseModel):
        resource_id: str
        resource_title: str
        resource_url: str
        feedback_type: str
        rating: int
        comment: str
        learning_objective: str

    class ResourceSubmissionData(BaseModel):
        title: str
        description: str
        url: str
        resource_type: str
        field: str
        tags: list = []
        level: str = "intermediate"

    # 知识库只识别这三类领域（_detect_field 的实现限制），写别的领域资源永远检索不到；
    # 资源类型同样受限于检索与前端图标映射
    ALLOWED_RESOURCE_TYPES = {"视频教程", "文字教程", "实战项目", "文档资料"}
    ALLOWED_FIELDS = {"AI", "编程", "数学"}
    ALLOWED_LEVELS = {"beginner", "intermediate", "advanced"}

    class PlanRequest(BaseModel):
        userInput: str

rag_recommender = None
feedback_manager = None
orchestrator = None


def init_services():
    """初始化服务"""
    global rag_recommender, feedback_manager

    try:
        from self_rag_recommender import init_self_rag
        from feedback_manager import init_feedback_manager

        rag_recommender = init_self_rag()

        if rag_recommender and rag_recommender.vector_store:
            feedback_manager = init_feedback_manager(
                vector_store=rag_recommender.vector_store
            )

        print("[api_server] 服务初始化完成")
    except Exception as e:
        print(f"[api_server] 服务初始化失败: {e}")


def init_orchestrator():
    """初始化LangGraph编排器"""
    global orchestrator, rag_recommender, feedback_manager

    try:
        from graph_orchestrator import GraphOrchestrator

        orchestrator = GraphOrchestrator()
        orchestrator.compile()

        # 将 RAG 和反馈管理器注入推荐Agent
        if rag_recommender:
            orchestrator.recommender.rag_recommender = rag_recommender
            orchestrator.recommender.feedback_manager = feedback_manager
            orchestrator.recommender._rag_initialized = True

        orchestrator.print_status()
        print("[api_server] LangGraph编排器初始化完成")
    except Exception as e:
        print(f"[api_server] 编排器初始化失败: {e}")
        import traceback
        traceback.print_exc()


if FASTAPI_AVAILABLE:
    @app.post("/api/plan")
    async def generate_plan(request: PlanRequest):
        """生成学习规划（LangGraph编排）"""
        if not orchestrator:
            raise HTTPException(status_code=500, detail="编排器未初始化")

        print(f"[API] 收到请求: {request.userInput}")

        try:
            result = orchestrator.invoke(request.userInput)
            print(f"[API] 返回结果: 学习目标={result.get('requirement_data', {}).get('learning_objective', 'N/A')}")
            return result
        except Exception as e:
            print(f"[API] 错误: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.post("/api/feedback")
    async def submit_feedback(feedback: FeedbackData):
        """提交用户反馈"""
        if not feedback_manager:
            raise HTTPException(status_code=500, detail="反馈系统未初始化")
        
        try:
            result = feedback_manager.submit_feedback(
                resource_id=feedback.resource_id,
                resource_title=feedback.resource_title,
                resource_url=feedback.resource_url,
                feedback_type=feedback.feedback_type,
                rating=feedback.rating,
                comment=feedback.comment,
                learning_objective=feedback.learning_objective
            )
            
            if result:
                return {"success": True, "feedback_id": result.id}
            raise HTTPException(status_code=400, detail="反馈提交失败")
        except HTTPException:
            # 上面的 400 不能被下面的兜底吞成 500
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.post("/api/resources/submit")
    async def submit_resource(submission: ResourceSubmissionData):
        """提交新资源，进入待审核队列"""
        if not feedback_manager:
            raise HTTPException(status_code=500, detail="反馈系统未初始化")

        title = (submission.title or "").strip()
        url = (submission.url or "").strip()
        if not title or not url:
            raise HTTPException(status_code=400, detail="标题和 URL 不能为空")
        if not url.lower().startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="URL 必须以 http:// 或 https:// 开头")
        if submission.resource_type not in ALLOWED_RESOURCE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"资源类型必须是 {'/'.join(sorted(ALLOWED_RESOURCE_TYPES))} 之一",
            )
        if submission.field not in ALLOWED_FIELDS:
            raise HTTPException(
                status_code=400,
                detail=f"领域必须是 {'/'.join(sorted(ALLOWED_FIELDS))} 之一",
            )
        if submission.level not in ALLOWED_LEVELS:
            raise HTTPException(
                status_code=400,
                detail=f"难度必须是 {'/'.join(sorted(ALLOWED_LEVELS))} 之一",
            )

        try:
            result = feedback_manager.submit_resource(
                title=title,
                description=(submission.description or "").strip(),
                url=url,
                resource_type=submission.resource_type,
                field=submission.field,
                tags=[str(tag).strip() for tag in (submission.tags or []) if str(tag).strip()],
                level=submission.level,
            )

            if result:
                return {"success": True, "submission_id": result.id, "status": result.status}
            raise HTTPException(status_code=400, detail="资源提交失败")
        except HTTPException:
            # 上面的 400 不能被下面的兜底吞成 500
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.get("/api/stats")
    async def get_stats():
        """获取系统统计"""
        stats = {}
        
        if rag_recommender and rag_recommender.vector_store:
            stats["vector_store"] = rag_recommender.vector_store.get_stats()
        
        if feedback_manager:
            stats["feedback"] = feedback_manager.get_feedback_stats()
        
        return stats
    
    
    @app.get("/api/resources/pending")
    async def get_pending_resources():
        """获取待审核资源"""
        if not feedback_manager:
            raise HTTPException(status_code=500, detail="反馈系统未初始化")
        
        return feedback_manager.get_pending_submissions()

    @app.get("/api/resources/{resource_id}/stats")
    async def get_resource_stats(resource_id: str):
        """
        获取单个资源的评分与反馈数。

        反馈提交成功后前端用它回填该资源的评分展示；页面刷新后也可以直接查。
        """
        if not rag_recommender or not rag_recommender.vector_store:
            raise HTTPException(status_code=503, detail="向量库未初始化")

        stats = rag_recommender.vector_store.get_resource_stats(resource_id)
        if not stats:
            raise HTTPException(status_code=404, detail=f"资源不存在: {resource_id}")
        return stats

    @app.get("/api/health")
    async def health():
        """
        健康检查：同时暴露知识库规模、检索缓存命中率和模型加载状态。

        预热是否完成、模型是否只加载了一份，都可以在这里直接看到，
        排查"冷启动慢"和"检索变慢"时不用再翻进程日志。
        """
        from model_loader import get_loader_stats
        from vector_store import get_cache_stats

        payload = {
            "status": "ok",
            "version": app.version,
            "vector_store_ready": bool(rag_recommender and rag_recommender.vector_store),
            "models": get_loader_stats(),
            "caches": get_cache_stats(),
        }
        if rag_recommender and rag_recommender.vector_store:
            store_stats = rag_recommender.vector_store.get_stats()
            payload["knowledge_base"] = {
                "total_count": store_stats.get("total_count", 0),
                "fields": store_stats.get("fields", {}),
                "levels": store_stats.get("levels", {}),
            }
            payload["retrieval"] = store_stats.get("retrieval", {})
        return payload


DEFAULT_API_PORT = 8001


def load_env_file() -> None:
    """尽力加载同目录 .env，让 API_PORT 等配置可以直接写在 .env 里"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path, override=False)


def resolve_api_port() -> int:
    """
    输入环境变量 API_PORT，返回后端监听端口。

    默认 8001 而不是 8000：本机 8000 常被 Docker 等服务占用，
    打到别的服务上只会返回看不懂的 404，排查成本很高。
    """
    raw = (os.getenv("API_PORT") or "").strip()
    if not raw:
        return DEFAULT_API_PORT

    try:
        port = int(raw)
    except ValueError:
        print(f"[api_server] API_PORT={raw!r} 不是整数，回退到 {DEFAULT_API_PORT}")
        return DEFAULT_API_PORT

    if not 1 <= port <= 65535:
        print(f"[api_server] API_PORT={port} 超出范围，回退到 {DEFAULT_API_PORT}")
        return DEFAULT_API_PORT
    return port


if __name__ == "__main__":
    if not FASTAPI_AVAILABLE:
        print("请安装依赖: pip install fastapi uvicorn pydantic")
        exit(1)
    
    import uvicorn
    load_env_file()
    port = resolve_api_port()
    print("=" * 60)
    print("学习规划助手API服务")
    print("=" * 60)
    print(f"\n启动服务: http://localhost:{port}")
    print(f"API文档: http://localhost:{port}/docs")
    print("=" * 60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
