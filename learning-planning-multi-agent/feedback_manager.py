# -*- coding: utf-8 -*-
"""
用户反馈收集与资源入库模块
提供用户反馈通道，有效反馈自动加入知识库

核心功能：
- 收集用户对推荐资源的反馈（有用/没用）
- 验证反馈有效性
- 自动将优质资源加入知识库
- 资源评分更新机制
"""

import os
import json
import uuid
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum


class FeedbackType(Enum):
    """反馈类型"""
    USEFUL = "useful"
    NOT_USEFUL = "not_useful"
    ADD_NEW = "add_new"


class FeedbackStatus(Enum):
    """反馈处理状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ADDED_TO_KB = "added_to_kb"


@dataclass
class UserFeedback:
    """用户反馈数据结构"""
    id: str
    resource_id: str
    resource_title: str
    resource_url: str
    feedback_type: str
    rating: int
    comment: str
    learning_objective: str
    user_id: str
    created_at: str
    status: str = "pending"
    processed_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResourceSubmission:
    """用户提交的新资源"""
    id: str
    title: str
    description: str
    url: str
    resource_type: str
    field: str
    level: str
    tags: List[str]
    rating: int
    submitted_by: str
    created_at: str
    status: str = "pending"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FeedbackManager:
    """
    用户反馈管理器
    
    负责收集、验证、处理用户反馈
    """
    
    FEEDBACK_FILE = "./data/feedback_records.json"
    SUBMISSION_FILE = "./data/resource_submissions.json"
    
    MIN_USEFUL_COUNT = 2
    MIN_RATING_FOR_APPROVAL = 4
    
    def __init__(self, vector_store=None):
        """
        初始化反馈管理器
        
        Args:
            vector_store: 向量数据库实例
        """
        self.vector_store = vector_store
        self.feedback_records: List[UserFeedback] = []
        self.submissions: List[ResourceSubmission] = []
        
        self._ensure_data_dir()
        self._load_records()
        
        print("[FeedbackManager] 反馈管理器初始化完成")
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        os.makedirs("./data", exist_ok=True)
    
    def _load_records(self):
        """加载历史记录"""
        if os.path.exists(self.FEEDBACK_FILE):
            try:
                with open(self.FEEDBACK_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.feedback_records = [UserFeedback(**item) for item in data]
                print(f"[FeedbackManager] 已加载 {len(self.feedback_records)} 条反馈记录")
            except Exception as e:
                print(f"[FeedbackManager] 加载反馈记录失败: {e}")
        
        if os.path.exists(self.SUBMISSION_FILE):
            try:
                with open(self.SUBMISSION_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.submissions = [ResourceSubmission(**item) for item in data]
                print(f"[FeedbackManager] 已加载 {len(self.submissions)} 个资源提交")
            except Exception as e:
                print(f"[FeedbackManager] 加载资源提交失败: {e}")
    
    def _save_records(self):
        """保存记录"""
        try:
            with open(self.FEEDBACK_FILE, "w", encoding="utf-8") as f:
                json.dump([f.to_dict() for f in self.feedback_records], f, ensure_ascii=False, indent=2)
            
            with open(self.SUBMISSION_FILE, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in self.submissions], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[FeedbackManager] 保存记录失败: {e}")
    
    def submit_feedback(self,
                        resource_id: str,
                        resource_title: str,
                        resource_url: str,
                        feedback_type: str,
                        rating: int,
                        comment: str,
                        learning_objective: str,
                        user_id: str = "anonymous") -> Optional[UserFeedback]:
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
            
        Returns:
            反馈记录对象
        """
        if rating < 1 or rating > 5:
            print(f"[FeedbackManager] 无效评分: {rating}，应为1-5")
            return None
        
        feedback = UserFeedback(
            id=str(uuid.uuid4()),
            resource_id=resource_id,
            resource_title=resource_title,
            resource_url=resource_url,
            feedback_type=feedback_type,
            rating=rating,
            comment=comment,
            learning_objective=learning_objective,
            user_id=user_id,
            created_at=datetime.now().isoformat(),
            status=FeedbackStatus.PENDING.value
        )
        
        self.feedback_records.append(feedback)
        self._save_records()
        
        print(f"[FeedbackManager] 反馈已提交: {resource_title} (类型: {feedback_type}, 评分: {rating})")
        
        self._process_feedback(feedback)
        
        return feedback
    
    def _process_feedback(self, feedback: UserFeedback):
        """处理反馈"""
        if feedback.feedback_type == FeedbackType.USEFUL.value:
            self._update_resource_rating(feedback)
            feedback.status = FeedbackStatus.APPROVED.value
            feedback.processed_at = datetime.now().isoformat()
            self._save_records()
        
        elif feedback.feedback_type == FeedbackType.NOT_USEFUL.value:
            feedback.status = FeedbackStatus.REJECTED.value
            feedback.processed_at = datetime.now().isoformat()
            self._save_records()
    
    def _update_resource_rating(self, feedback: UserFeedback):
        """更新资源评分"""
        if self.vector_store and feedback.resource_id:
            success = self.vector_store.update_feedback(
                resource_id=feedback.resource_id,
                rating=feedback.rating
            )
            if success:
                print(f"[FeedbackManager] 资源评分已更新")
    
    def submit_resource(self,
                        title: str,
                        description: str,
                        url: str,
                        resource_type: str,
                        field: str,
                        tags: List[str],
                        submitted_by: str = "anonymous") -> Optional[ResourceSubmission]:
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
            
        Returns:
            资源提交对象
        """
        if not title or not url:
            print("[FeedbackManager] 标题和URL不能为空")
            return None
        
        submission = ResourceSubmission(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            url=url,
            resource_type=resource_type,
            field=field,
            level="intermediate",
            tags=tags,
            rating=0,
            submitted_by=submitted_by,
            created_at=datetime.now().isoformat(),
            status=FeedbackStatus.PENDING.value
        )
        
        self.submissions.append(submission)
        self._save_records()
        
        print(f"[FeedbackManager] 资源已提交待审核: {title}")
        
        return submission
    
    def approve_and_add_to_kb(self, submission_id: str, rating: int = 5) -> bool:
        """
        审核通过并加入知识库
        
        Args:
            submission_id: 提交ID
            rating: 初始评分
            
        Returns:
            是否成功
        """
        submission = next((s for s in self.submissions if s.id == submission_id), None)
        if not submission:
            print(f"[FeedbackManager] 未找到提交: {submission_id}")
            return False
        
        if not self.vector_store:
            print("[FeedbackManager] 向量数据库不可用")
            return False
        
        resource_id = self.vector_store.add_resource(
            title=submission.title,
            description=submission.description,
            resource_type=submission.resource_type,
            field=submission.field,
            level=submission.level,
            url=submission.url,
            tags=submission.tags,
            source="user_contribution"
        )
        
        if resource_id:
            submission.status = FeedbackStatus.ADDED_TO_KB.value
            submission.rating = rating
            self._save_records()
            print(f"[FeedbackManager] 资源已加入知识库: {submission.title}")
            return True
        
        return False
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """获取反馈统计"""
        total = len(self.feedback_records)
        useful = sum(1 for f in self.feedback_records if f.feedback_type == "useful")
        not_useful = sum(1 for f in self.feedback_records if f.feedback_type == "not_useful")
        approved = sum(1 for f in self.feedback_records if f.status == "approved")
        pending_submissions = sum(1 for s in self.submissions if s.status == "pending")
        added_to_kb = sum(1 for s in self.submissions if s.status == "added_to_kb")
        
        return {
            "total_feedback": total,
            "useful_count": useful,
            "not_useful_count": not_useful,
            "approval_rate": approved / total if total > 0 else 0,
            "pending_submissions": pending_submissions,
            "added_to_kb": added_to_kb,
            "total_submissions": len(self.submissions)
        }
    
    def get_pending_submissions(self) -> List[Dict]:
        """获取待审核的资源提交"""
        return [
            s.to_dict() 
            for s in self.submissions 
            if s.status == FeedbackStatus.PENDING.value
        ]
    
    def auto_approve_high_quality(self) -> int:
        """
        自动审核高质量资源
        条件：包含有效的URL、描述完整、非重复
        
        Returns:
            自动通过的数量
        """
        approved_count = 0
        
        for submission in self.submissions:
            if submission.status != FeedbackStatus.PENDING.value:
                continue
            
            if self._is_high_quality(submission):
                if self.approve_and_add_to_kb(submission.id):
                    approved_count += 1
        
        print(f"[FeedbackManager] 自动审核通过 {approved_count} 个资源")
        return approved_count
    
    def _is_high_quality(self, submission: ResourceSubmission) -> bool:
        """判断资源是否高质量"""
        if not submission.url or len(submission.url) < 10:
            return False
        
        if not submission.description or len(submission.description) < 20:
            return False
        
        for existing in self.submissions:
            if existing.id != submission.id and existing.url == submission.url:
                return False
        
        return True


def init_feedback_manager(vector_store=None) -> FeedbackManager:
    """初始化反馈管理器"""
    return FeedbackManager(vector_store=vector_store)


if __name__ == "__main__":
    print("=" * 60)
    print("反馈管理器测试")
    print("=" * 60)
    
    from vector_store import init_vector_store_with_seed_data
    
    vector_store = init_vector_store_with_seed_data()
    fm = init_feedback_manager(vector_store=vector_store)
    
    print("\n提交反馈测试...")
    feedback = fm.submit_feedback(
        resource_id="test_001",
        resource_title="Python基础教程",
        resource_url="https://example.com/python",
        feedback_type="useful",
        rating=5,
        comment="非常好的入门教程，讲解清晰",
        learning_objective="学习Python编程",
        user_id="test_user"
    )
    
    print("\n提交新资源测试...")
    submission = fm.submit_resource(
        title="LangGraph官方文档",
        description="LangGraph官方学习资源，包含完整的Agent开发教程",
        url="https://langchain-ai.github.io/langgraph/",
        resource_type="文档资料",
        field="AI",
        tags=["LangGraph", "Agent", "多智能体"]
    )
    
    print("\n统计信息:")
    stats = fm.get_feedback_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    print("\n待审核资源:")
    pending = fm.get_pending_submissions()
    for s in pending:
        print(f"  - {s['title']}: {s['url']}")
