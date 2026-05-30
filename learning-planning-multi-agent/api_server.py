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

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from fastapi.middleware.cors import CORSMiddleware
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("[api_server] 警告: fastapi未安装")


if FASTAPI_AVAILABLE:
    app = FastAPI(title="学习规划助手API", version="1.0.0")
    
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

    class PlanRequest(BaseModel):
        userInput: str

rag_recommender = None
feedback_manager = None
coordinator = None


def init_services():
    """初始化服务"""
    global rag_recommender, feedback_manager, coordinator
    
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

def init_coordinator():
    """初始化协调器"""
    global coordinator, rag_recommender, feedback_manager
    
    try:
        from agent_coordinator import LearningPlanningCoordinator
        
        coordinator = LearningPlanningCoordinator(enable_hermes_sync=False)
        
        if rag_recommender:
            coordinator.recommender.rag_recommender = rag_recommender
        
        print("[api_server] 协调器初始化完成")
    except Exception as e:
        print(f"[api_server] 协调器初始化失败: {e}")


if FASTAPI_AVAILABLE:
    @app.on_event("startup")
    async def startup_event():
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        init_services()
        init_coordinator()
    
    @app.post("/api/plan")
    async def generate_plan(request: PlanRequest):
        """生成学习规划"""
        if not coordinator:
            raise HTTPException(status_code=500, detail="协调器未初始化")
        
        print(f"[API] 收到请求: {request.userInput}")
        
        try:
            result = coordinator.process(request.userInput)
            print(f"[API] 返回结果: {json.dumps(result, ensure_ascii=False)[:500]}...")
            return result
        except Exception as e:
            print(f"[API] 错误: {e}")
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
            else:
                raise HTTPException(status_code=400, detail="反馈提交失败")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.post("/api/resources/submit")
    async def submit_resource(submission: ResourceSubmissionData):
        """提交新资源"""
        if not feedback_manager:
            raise HTTPException(status_code=500, detail="反馈系统未初始化")
        
        try:
            result = feedback_manager.submit_resource(
                title=submission.title,
                description=submission.description,
                url=submission.url,
                resource_type=submission.resource_type,
                field=submission.field,
                tags=submission.tags
            )
            
            if result:
                return {"success": True, "submission_id": result.id}
            else:
                raise HTTPException(status_code=400, detail="资源提交失败")
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


if __name__ == "__main__":
    if not FASTAPI_AVAILABLE:
        print("请安装依赖: pip install fastapi uvicorn pydantic")
        exit(1)
    
    import uvicorn
    print("=" * 60)
    print("学习规划助手API服务")
    print("=" * 60)
    print("\n启动服务: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    print("=" * 60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
