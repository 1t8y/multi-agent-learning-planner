"""
资源推荐子Agent（增强版）
支持Agentic RAG智能检索、网络搜索和用户反馈

核心功能：
- 基于Chroma向量数据库的本地知识库检索
- Tavily网络搜索补充资源
- Self-RAG智能判断策略（知识库→网络→反馈）
- 用户反馈收集和资源入库
"""

import os
import json
from typing import Optional, Dict
from base_agent import BaseAgent

try:
    from self_rag_recommender import SelfRAGRecommender, init_self_rag
    from feedback_manager import FeedbackManager, init_feedback_manager
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
    PROMPT_FILE = "resource-recommender-agent.md"
    
    RESOURCE_TYPES = ["视频教程", "文字教程", "实战项目", "文档资料"]
    
    def __init__(self, agent_config: Optional[Dict] = None):
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
    
    def _get_prompt_path(self) -> Optional[str]:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(project_root, ".trae", "agents", self.PROMPT_FILE)
    
    def _get_default_prompt(self) -> str:
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
    
    def _get_default_result(self) -> Dict:
        return {"resources": [], "rag_info": {}}
    
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
            print(f"[{self.AGENT_NAME}] 警告：缺少学习目标，返回空资源列表")
            return self._get_default_result()

        print(f"[{self.AGENT_NAME}] 开始推荐学习资源: {learning_objective}")

        if self._rag_initialized and self.rag_recommender:
            return self._recommend_with_rag(learning_objective, current_foundation, learning_plan)
        else:
            print(f"[{self.AGENT_NAME}] Self-RAG未启用，使用传统LLM推荐（标注来源）")
            return self._recommend_with_llm(requirement_info, learning_plan)

    def _recommend_with_rag(self,
                            learning_objective: str,
                            current_foundation: str,
                            learning_plan: Dict) -> Dict:
        """使用Self-RAG智能推荐，如果结果不足则回退LLM生成"""
        print(f"[{self.AGENT_NAME}] 启用Self-RAG智能检索")

        rag_result = self.rag_recommender.recommend(
            learning_objective=learning_objective,
            current_foundation=current_foundation,
            learning_plan=learning_plan
        )

        rag_resources = rag_result.get("resources", [])
        kb_relevance = rag_result.get("kb_relevance", 0)

        # 统计各来源数量
        kb_count = sum(1 for r in rag_resources if r.get("source") == "knowledge_base")
        web_count = sum(1 for r in rag_resources if r.get("source") == "web_search")

        # 如果RAG结果不足（无资源或相关性太低），回退LLM
        if not rag_resources:
            print(f"[{self.AGENT_NAME}] RAG无相关结果 (KB相似度: {kb_relevance:.2f})，使用LLM生成")
            llm_result = self._recommend_with_llm(
                {"learning_objective": learning_objective, "current_foundation": current_foundation},
                learning_plan
            )
            # 保留RAG来源信息
            llm_result["rag_info"] = {
                "source_info": f"本地知识库无相关资源 → AI生成, 知识库相似度: {kb_relevance:.2f}",
                "kb_relevance": kb_relevance,
                "rewrite_count": rag_result.get("rewrite_count", 0),
                "used_web_search": rag_result.get("used_web_search", False),
                "kb_count": 0,
                "web_count": 0,
                "llm_count": len(llm_result.get("resources", [])),
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

            # 为 LLM 生成的每个资源标注来源
            resources = result.get("resources", [])
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
            return self._get_default_result()
    
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
        """获取RAG系统统计信息"""
        stats = {}
        
        if self._rag_initialized and self.rag_recommender and self.rag_recommender.vector_store:
            stats["vector_store"] = self.rag_recommender.vector_store.get_stats()
        
        if self._rag_initialized and self.feedback_manager:
            stats["feedback"] = self.feedback_manager.get_feedback_stats()
        
        return stats
    
    def process(self, requirement_info: Dict, learning_plan: Dict) -> Dict:
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
