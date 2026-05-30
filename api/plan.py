# -*- coding: utf-8 -*-
"""
Vercel Serverless Function: /api/plan
轻量级多智能体学习规划 API（不含 ChromaDB/LangGraph/评估Agent）

工作流（串行，~8-15s）：
  用户输入 → 需求提取 → 课程规划 → 资源推荐(LLM) → 返回结果

设计要点：
  - 跳过评估Agent（节省3-5s），前端mock数据兜底
  - 资源推荐自动回退LLM生成（ChromaDB在Serverless中不可用）
  - 模块级Agent单例：暖容器复用，减少冷启动开销
"""

import sys
import os
import json
import traceback
from http.server import BaseHTTPRequestHandler

# ── 将 learning-planning-multi-agent/ 加入模块搜索路径 ──
_HERE = os.path.dirname(os.path.abspath(__file__))
_AGENT_DIR = os.path.join(_HERE, "..", "learning-planning-multi-agent")
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_AGENT_DIR))

# ── 延迟导入（模块级单例，暖容器复用） ──
_extractor = None
_planner = None
_recommender = None


def _get_extractor():
    global _extractor
    if _extractor is None:
        from requirement_extractor import RequirementExtractorAgent
        _extractor = RequirementExtractorAgent()
    return _extractor


def _get_planner():
    global _planner
    if _planner is None:
        from course_planner import CoursePlannerAgent
        _planner = CoursePlannerAgent()
    return _planner


def _get_recommender():
    global _recommender
    if _recommender is None:
        from resource_recommender import ResourceRecommenderAgent
        _recommender = ResourceRecommenderAgent()
    return _recommender


def run_agent_chain(user_input: str) -> dict:
    """
    执行 Agent 流水线（串行，跳过评估）

    Returns:
        包含 requirement_data, plan, resources, assessment 的字典
    """
    # 1. 需求提取
    extractor = _get_extractor()
    requirement_data = extractor.extract(user_input)
    if not requirement_data.get("learning_objective"):
        return {"error": "无法提取有效学习目标", "requirement_data": requirement_data}

    # 2. 课程规划
    planner = _get_planner()
    plan_data = planner.plan(requirement_data)

    # 3. 资源推荐（自动回退LLM，因为ChromaDB不可用）
    recommender = _get_recommender()
    resource_data = recommender.recommend(requirement_data, plan_data)

    # 4. 生成简化评估（跳过LLM评估Agent，节省时间）
    rag_info = resource_data.get("rag_info", {})
    source_hint = rag_info.get("source_info", "AI生成") if rag_info else "AI生成"
    assessment_data = {
        "assessment_summary": {
            "overall_rating": "良好（快速模式）",
            "feasibility_rating": 7,
            "content_rating": 7,
            "time_rating": 7,
            "method_rating": 7,
            "progression_rating": 7,
            "personalization_rating": 7,
            "score_average": 7.0,
        },
        "assessment_metrics": [],
        "adjustment_suggestions": [
            {
                "area": "演示模式",
                "issue": "Vercel Serverless 跳过完整评估以控制响应时间",
                "suggestion": "本地完整版支持6维度评估和自动再生",
                "priority": "低",
            }
        ],
        "recommendations": [
            f"资源来源: {source_hint}",
            "完整版支持ChromaDB知识库检索 + Tavily网络搜索",
        ],
    }

    return {
        "requirement_data": requirement_data,
        "plan": plan_data,
        "resources": resource_data,
        "assessment": assessment_data,
    }


class handler(BaseHTTPRequestHandler):
    """
    Vercel Python Serverless HTTP Handler

    处理:
      - OPTIONS → CORS preflight
      - POST   → 执行 Agent 流水线
    """

    # 跳过每次请求的日志打印（减少IO开销）
    def log_message(self, format, *args):
        pass

    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors()
        self.end_headers()

    def do_POST(self):
        try:
            # 读取请求体
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length else b"{}"
            data = json.loads(body.decode("utf-8"))

            user_input = data.get("userInput", "").strip()
            if not user_input:
                self._send_json(400, {"error": "userInput 不能为空"})
                return

            # 执行 Agent 链
            result = run_agent_chain(user_input)

            self._send_json(200, result)

        except json.JSONDecodeError:
            self._send_json(400, {"error": "无效的JSON格式"})
        except Exception:
            traceback.print_exc()
            self._send_json(500, {
                "error": "服务器内部错误",
                "detail": traceback.format_exc()[:500],
            })

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self._set_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
