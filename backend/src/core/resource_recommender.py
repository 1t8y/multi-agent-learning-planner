"""
资源推荐子Agent（增强版）
支持Agentic RAG智能检索、网络搜索和用户反馈

核心功能：
- 基于Chroma向量数据库的本地知识库检索
- Tavily网络搜索补充资源
- Self-RAG智能判断策略（知识库→网络→反馈）
- 用户反馈收集和资源入库
"""

import json
from typing import Optional, Dict
from src.core.base_agent import BaseAgent

try:
    from src.rag.self_rag_recommender import SelfRAGRecommender, init_self_rag
    from src.feedback.feedback_manager import FeedbackManager, init_feedback_manager
    RAG_ENABLED = True
except ImportError as e:
    print(f"[resource-recommender] RAG模块加载警告: {e}")
    RAG_ENABLED = False


class ResourceRecommenderAgent(BaseAgent):
    """
    增强版资源推荐子Agent
    
    输入：
    - requirement_info: 学习需求信息
    - learning_plan: 学习计划
    
    输出：
    - resources: 资源列表（包含阶段、类型、标题、描述、时长、难度、推荐理由、URL）
    - rag_info: RAG检索信息（来源、相似度等）
    """
    
    AGENT_NAME = "resource-recommender"
    
    RESOURCE_TYPES = ["视频教程", "文字教程", "实战项目", "文档资料"]
    
    def __init__(self, agent_config: Optional[Dict] = None):
        """初始化推荐 Agent，并尽力启用 Self-RAG 与反馈管理器。

        RAG 初始化失败不会中断构造：记录日志后回退到「只用 LLM 推荐」的路径，
        保证接口在向量库不可用时仍能返回计划（少了资源链接）。
        """
        super().__init__(agent_config)
        
        self.rag_recommender = None
        self.feedback_manager = None
        self._rag_initialized = False
        
        if RAG_ENABLED:
            try:
                self.rag_recommender = init_self_rag()
                self.feedback_manager = init_feedback_manager(
                    vector_store=self.rag_recommender.vector_store
                )
                self._rag_initialized = True
                print(f"[{self.AGENT_NAME}] Self-RAG功能已启用")
            except Exception as e:
                print(f"[{self.AGENT_NAME}] RAG初始化失败: {e}")
    
    def _get_default_prompt(self) -> str:
        """返回本 Agent 的系统提示词。

        提示词只有这一份来源（不做外置文件加载），
        输出格式段落是硬约束，下游按该 JSON 结构解析，改动需同步解析代码。
        """
        return """你是专业学习资源推荐专家，根据学习需求和学习计划推荐最合适的学习资源。

## 核心职责
根据学习目标、现有基础、学习偏好和学习阶段，推荐相应的学习资源，输出结构化资源列表。

## 输入信息
- requirement_info: 学习需求信息
- learning_plan: 学习计划（包含学习路径、阶段信息）

## 资源类型
- 视频教程：适合视觉学习和入门
- 文字教程：适合深入理解和查阅
- 实战项目：适合技能巩固和实践
- 文档资料：适合专业知识学习

## 推荐原则
1. 匹配学习阶段：为每个阶段推荐适合的资源
2. 考虑学习偏好：优先推荐用户偏好的资源类型
3. 平衡难度：根据用户基础推荐合适难度的资源
4. 多样性：同一阶段推荐不同类型的资源供选择

## 输出格式（固定不可修改）
{
  "resources": [
    {
      "phase": "",
      "type": "",
      "title": "",
      "description": "",
      "duration": "",
      "difficulty": "",
      "recommendation_reason": "",
      "url": ""
    }
  ]
}"""
    
    def _get_default_result(self, reason: str = "资源推荐服务暂时不可用") -> Dict:
        """所有通道都失败时的降级结果：非空、带明确标记，不再返回空列表。

        resources 里是一条「说明条目」而不是伪造的学习资源，前端能显示失败原因；
        rag_info.degraded=True 让调用方能区分降级结果与正常结果。
        仍返回 dict 而不是抛异常，编排层可以把计划和评估结果交回前端。
        """
        return {
            "resources": [{
                "id": "",
                "phase": "资源推荐",
                "type": "说明",
                "title": "暂时无法获取推荐资源",
                "description": (
                    f"{reason}。请检查 backend/.env 中的 DEEPSEEK_API_KEY / "
                    "TAVILY_API_KEY 与网络连通性后重试；学习计划与评估结果不受影响。"
                ),
                "duration": "",
                "difficulty": "",
                "recommendation_reason": reason,
                "url": "",
                "source": "fallback_notice",
            }],
            "rag_info": {
                "source_info": "所有资源通道均失败，返回降级说明",
                "degraded": True,
                "reason": reason,
                "used_web_search": False,
                "kb_count": 0,
                "web_count": 0,
                "llm_count": 0,
            },
        }
    
    def recommend(self, requirement_info: Dict, learning_plan: Dict) -> Dict:
        """
        执行资源推荐（增强版）

        优先级：
        1. 本地知识库检索 (ChromaDB) — 最可靠，相似度≥阈值直接使用
        2. 网络搜索 (Tavily) — 知识库不足时补充，明确标注来源
        3. LLM生成 — 以上均不足时兜底，标注为"AI生成参考"
        """
        if not isinstance(requirement_info, dict) or not isinstance(learning_plan, dict):
            raise ValueError("输入必须是字典类型")

        learning_objective = requirement_info.get("learning_objective", "")
        current_foundation = requirement_info.get("current_foundation", "零基础")

        if not learning_objective:
            print(f"[{self.AGENT_NAME}] 警告：缺少学习目标，返回降级说明")
            return self._get_default_result("缺少学习目标，无法生成资源推荐")

        print(f"[{self.AGENT_NAME}] 开始推荐学习资源: {learning_objective}")

        if self._rag_initialized and self.rag_recommender:
            return self._recommend_with_rag(requirement_info, learning_plan)
        else:
            print(f"[{self.AGENT_NAME}] Self-RAG未启用，使用传统LLM推荐（标注来源）")
            return self._recommend_with_llm(requirement_info, learning_plan)

    def _recommend_with_rag(self, requirement_info: Dict, learning_plan: Dict) -> Dict:
        """使用Self-RAG智能推荐，如果结果不足则回退LLM生成"""
        print(f"[{self.AGENT_NAME}] 启用Self-RAG智能检索")

        rag_result = self.rag_recommender.recommend(
            learning_objective=requirement_info.get("learning_objective", ""),
            current_foundation=requirement_info.get("current_foundation", "零基础"),
            learning_plan=learning_plan,
            learning_preference=requirement_info.get("learning_preference"),
            time_expectation=requirement_info.get("time_expectation"),
        )

        rag_resources = rag_result.get("resources", [])
        kb_relevance = rag_result.get("kb_relevance", 0)

        # 统计各来源数量
        kb_count = sum(1 for r in rag_resources if r.get("source") == "knowledge_base")
        web_count = sum(1 for r in rag_resources if r.get("source") == "web_search")

        # 知识库质量分低 ≠ 联网兜底失败。只要拿到了网络资源就保留，
        # 否则会被 LLM 分支整体覆盖，配了 TAVILY_API_KEY 也看不到联网结果。
        quality_passed = rag_result.get("quality", {}).get("passed", True)
        rag_usable = bool(rag_resources) and (quality_passed or web_count > 0)
        if not rag_usable:
            print(f"[{self.AGENT_NAME}] RAG无可用结果 (KB相似度: {kb_relevance:.2f}, "
                  f"网络资源: {web_count})，使用LLM生成")
            llm_result = self._recommend_with_llm(
                requirement_info,
                learning_plan
            )
            # 保留RAG来源信息；若 LLM 也降级了，不要把它伪装成"AI生成成功"
            base_rag_info = llm_result.get("rag_info", {}) or {}
            degraded = bool(base_rag_info.get("degraded"))
            llm_result["rag_info"] = {
                **base_rag_info,
                "source_info": (base_rag_info.get("source_info")
                                if degraded else
                                f"本地知识库无相关资源 → AI生成, 知识库相似度: {kb_relevance:.2f}"),
                "kb_relevance": kb_relevance,
                "rewrite_count": rag_result.get("rewrite_count", 0),
                "used_web_search": rag_result.get("used_web_search", False),
                "kb_count": 0,
                "web_count": 0,
                "llm_count": 0 if degraded else len(llm_result.get("resources", [])),
                "quality": rag_result.get("quality", {}),
                "rerank": rag_result.get("rerank", {}),
                "candidate_count": rag_result.get("candidate_count", 0),
                "filters": rag_result.get("filters", {}),
                "search_query": rag_result.get("search_query", ""),
                "quality_fallback": not quality_passed,
                "degraded": degraded,
                "web_error": rag_result.get("web_error", ""),
                "web_search_status": rag_result.get("web_search_status", {}),
                "decision": rag_result.get("decision", ""),
                "no_hit_reason": rag_result.get("no_hit_reason", ""),
            }
            return llm_result

        print(f"[{self.AGENT_NAME}] RAG推荐 {len(rag_resources)} 个资源 (知识库: {kb_count}, 网络: {web_count})")

        return {
            "resources": rag_resources,
            "rag_info": {
                "source_info": rag_result.get("source_info", ""),
                "kb_relevance": kb_relevance,
                "rewrite_count": rag_result.get("rewrite_count", 0),
                "used_web_search": rag_result.get("used_web_search", False),
                "kb_count": kb_count,
                "web_count": web_count,
                "quality": rag_result.get("quality", {}),
                "rerank": rag_result.get("rerank", {}),
                "candidate_count": rag_result.get("candidate_count", 0),
                "filters": rag_result.get("filters", {}),
                "search_query": rag_result.get("search_query", ""),
                "web_error": rag_result.get("web_error", ""),
                "web_search_status": rag_result.get("web_search_status", {}),
                "decision": rag_result.get("decision", ""),
                "no_hit_reason": rag_result.get("no_hit_reason", ""),
                "degraded": False,
            }
        }
    
    def _recommend_with_llm(self, requirement_info: Dict, learning_plan: Dict) -> Dict:
        """使用传统LLM推荐（明确标注来源）"""
        try:
            input_data = {
                "requirement_info": requirement_info,
                "learning_plan": learning_plan
            }
            input_json = json.dumps(input_data, ensure_ascii=False)

            result = self._call_api(input_json)

            # _call_api 熔断/解析失败时会直接返回 _get_default_result()：
            # 保留它的 degraded 标记，不要伪装成"AI生成成功"
            if not isinstance(result, dict):
                return self._get_default_result("LLM 返回了无法解析的结果")
            if (result.get("rag_info") or {}).get("degraded"):
                return result

            resources = result.get("resources", [])
            if not resources:
                return self._get_default_result("LLM 未返回任何学习资源")

            # 为 LLM 生成的每个资源标注来源
            for r in resources:
                if not r.get("source"):
                    r["source"] = "llm_generated"

            print(f"[{self.AGENT_NAME}] LLM推荐完成，共推荐 {len(resources)} 个资源 (来源: AI生成)")

            result["resources"] = resources
            result["rag_info"] = {
                "source_info": "基于AI模型直接生成，未经本地知识库验证",
                "used_web_search": False,
                "kb_count": 0,
                "web_count": 0,
                "llm_count": len(resources),
            }
            return result

        except Exception as e:
            print(f"[{self.AGENT_NAME}] LLM推荐失败: {e}")
            return self._get_default_result(f"LLM 资源生成失败: {e}")
    
    def submit_feedback(self,
                        resource_id: str,
                        resource_title: str,
                        resource_url: str,
                        feedback_type: str,
                        rating: int,
                        comment: str,
                        learning_objective: str,
                        user_id: str = "anonymous"):
        """
        提交用户反馈
        
        Args:
            resource_id: 资源ID
            resource_title: 资源标题
            resource_url: 资源URL
            feedback_type: 反馈类型（useful/not_useful/add_new）
            rating: 评分（1-5）
            comment: 评论
            learning_objective: 学习目标
            user_id: 用户ID
        """
        if not self._rag_initialized or not self.feedback_manager:
            print(f"[{self.AGENT_NAME}] 反馈系统未启用")
            return None
        
        return self.feedback_manager.submit_feedback(
            resource_id=resource_id,
            resource_title=resource_title,
            resource_url=resource_url,
            feedback_type=feedback_type,
            rating=rating,
            comment=comment,
            learning_objective=learning_objective,
            user_id=user_id
        )
    
    def submit_new_resource(self,
                           title: str,
                           description: str,
                           url: str,
                           resource_type: str,
                           field: str,
                           tags: list,
                           submitted_by: str = "anonymous"):
        """
        提交新资源到待审核队列
        
        Args:
            title: 资源标题
            description: 资源描述
            url: 资源URL
            resource_type: 资源类型
            field: 领域
            tags: 标签列表
            submitted_by: 提交者
        """
        if not self._rag_initialized or not self.feedback_manager:
            print(f"[{self.AGENT_NAME}] 反馈系统未启用")
            return None
        
        return self.feedback_manager.submit_resource(
            title=title,
            description=description,
            url=url,
            resource_type=resource_type,
            field=field,
            tags=tags,
            submitted_by=submitted_by
        )
    
    def get_rag_stats(self) -> Dict:
        """获取RAG系统统计信息（存储分布 + 检索计数）"""
        stats = {}

        if self._rag_initialized and self.rag_recommender and self.rag_recommender.vector_store:
            stats["vector_store"] = {
                **self.rag_recommender.vector_store.get_stats(),
                "retrieval": (self.rag_recommender.retriever.get_retrieval_stats()
                              if getattr(self.rag_recommender, "retriever", None) else {}),
            }
        
        if self._rag_initialized and self.feedback_manager:
            stats["feedback"] = self.feedback_manager.get_feedback_stats()
        
        return stats
    
    def process(self, requirement_info: Dict, learning_plan: Dict) -> Dict:
        """编排层调用的统一入口，等价于 recommend()。

        保留这一层薄封装是为了让四个 Agent 对外都有 `process(输入) -> 结果`
        的统一签名，编排器不必关心每个 Agent 内部方法叫什么。
        """
        return self.recommend(requirement_info, learning_plan)
    
    def validate_result(self, result: Dict) -> bool:
        """验证结果有效性"""
        if not isinstance(result, dict):
            return False
        
        if "resources" not in result:
            return False
        
        if not isinstance(result["resources"], list):
            return False
        
        return True


def init_resource_recommender() -> ResourceRecommenderAgent:
    """初始化资源推荐Agent"""
    return ResourceRecommenderAgent()


if __name__ == "__main__":
    print("=" * 60)
    print("增强版资源推荐Agent测试")
    print("=" * 60)
    
    agent = init_resource_recommender()
    print(f"\nRAG功能: {'已启用' if agent._rag_initialized else '未启用'}")
    
    test_requirement = {
        "learning_objective": "学习Python编程",
        "current_foundation": "零基础",
        "daily_available_time": "2小时",
        "learning_preference": "视频",
        "time_expectation": "快速入门"
    }
    
    test_plan = {
        "goal_feasibility": "可行",
        "estimated_duration": "1周",
        "learning_path": {
            "stage_count": 2,
            "stages": [
                {
                    "stage_name": "第一阶段：基础入门",
                    "study_content": "Python基础语法",
                    "time_allocation": "3天",
                    "milestone": "掌握基础语法"
                }
            ]
        }
    }
    
    print("\n执行推荐测试...")
    result = agent.recommend(test_requirement, test_plan)
    
    print(f"\n推荐结果:")
    print(f"资源数量: {len(result.get('resources', []))}")
    
    if "rag_info" in result:
        rag_info = result["rag_info"]
        print(f"RAG来源: {rag_info.get('source_info', 'N/A')}")
        print(f"知识库相似度: {rag_info.get('kb_relevance', 0):.2f}")
        print(f"使用网络搜索: {'是' if rag_info.get('used_web_search') else '否'}")
    
    for i, r in enumerate(result.get("resources", [])[:3], 1):
        print(f"\n{i}. [{r.get('type', 'N/A')}] {r.get('title', 'N/A')}")
        print(f"   难度: {r.get('difficulty', 'N/A')}")
        print(f"   URL: {r.get('url', 'N/A')}")
        print(f"   来源: {r.get('source', 'LLM生成')}")
