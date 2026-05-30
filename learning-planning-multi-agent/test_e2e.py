# -*- coding: utf-8 -*-
"""
端到端测试脚本
测试完整的学习规划推荐流程
"""

import os
import sys
import json
from dotenv import load_dotenv

load_dotenv('.env')

def test_agentic_rag():
    """测试Agentic RAG完整流程"""
    print("\n" + "="*60)
    print("测试: Agentic RAG智能资源推荐")
    print("="*60)
    
    try:
        from self_rag_recommender import init_self_rag
    except ImportError as e:
        print(f"[FAIL] 模块导入失败: {e}")
        return False
    
    try:
        recommender = init_self_rag()
        print("[OK] Self-RAG推荐器初始化成功")
    except Exception as e:
        print(f"[FAIL] 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    test_cases = [
        {"objective": "Python编程", "foundation": "零基础"},
        {"objective": "机器学习入门", "foundation": "有数学基础"},
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n--- 测试用例 {i}: {case['objective']} ({case['foundation']}) ---")
        
        try:
            result = recommender.recommend(
                learning_objective=case['objective'],
                current_foundation=case['foundation']
            )
            
            resources = result.get('resources', [])
            rag_info = result.get('rag_info', {})
            
            print(f"[OK] 推荐完成，资源数量: {len(resources)}")
            print(f"     来源信息: {rag_info.get('source_info', 'N/A')}")
            print(f"     知识库匹配度: {rag_info.get('kb_relevance', 0):.2f}")
            print(f"     使用网络搜索: {'是' if rag_info.get('used_web_search') else '否'}")
            
            if resources:
                print(f"\n     前2个资源:")
                for j, r in enumerate(resources[:2], 1):
                    print(f"     {j}. [{r.get('type', 'N/A')}] {r.get('title', 'N/A')}")
                    print(f"        来源: {r.get('source', 'N/A')}")
                    print(f"        URL: {r.get('url', 'N/A')}")
            
        except Exception as e:
            print(f"[FAIL] 推荐失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True


def test_feedback_integration():
    """测试反馈系统与RAG集成"""
    print("\n" + "="*60)
    print("测试: 反馈系统集成")
    print("="*60)
    
    try:
        from self_rag_recommender import init_self_rag
        from feedback_manager import init_feedback_manager
    except ImportError as e:
        print(f"[FAIL] 模块导入失败: {e}")
        return False
    
    try:
        recommender = init_self_rag()
        fm = init_feedback_manager(
            vector_store=recommender.vector_store if hasattr(recommender, 'vector_store') else None
        )
        print("[OK] 反馈系统初始化成功")
    except Exception as e:
        print(f"[FAIL] 初始化失败: {e}")
        return False
    
    print("\n--- 测试反馈提交 ---")
    try:
        feedback = fm.submit_feedback(
            resource_id='test_resource_001',
            resource_title='Python基础教程',
            resource_url='https://example.com/python',
            feedback_type='useful',
            rating=5,
            comment='对零基础非常有帮助',
            learning_objective='学习Python编程',
            user_id='test_user'
        )
        
        if feedback:
            print(f"[OK] 反馈提交成功，ID: {feedback.id}")
        else:
            print("[FAIL] 反馈提交失败")
            return False
    except Exception as e:
        print(f"[FAIL] 反馈提交失败: {e}")
        return False
    
    print("\n--- 测试资源提交 ---")
    try:
        submission = fm.submit_resource(
            title='DeepSeek API文档',
            description='DeepSeek大模型API官方文档',
            url='https://api-docs.deepseek.com/',
            resource_type='文档资料',
            field='AI',
            tags=['DeepSeek', 'API', '大模型'],
            submitted_by='test_user'
        )
        
        if submission:
            print(f"[OK] 资源提交成功，ID: {submission.id}")
        else:
            print("[FAIL] 资源提交失败")
            return False
    except Exception as e:
        print(f"[FAIL] 资源提交失败: {e}")
        return False
    
    print("\n--- 获取统计信息 ---")
    try:
        stats = fm.get_feedback_stats()
        print(f"[OK] 统计信息:")
        print(f"     总反馈数: {stats.get('total_feedback', 0)}")
        print(f"     有用反馈: {stats.get('useful_count', 0)}")
        print(f"     待审核资源: {stats.get('pending_submissions', 0)}")
    except Exception as e:
        print(f"[FAIL] 统计信息获取失败: {e}")
        return False
    
    return True


def test_resource_recommender_agent():
    """测试完整的资源推荐Agent"""
    print("\n" + "="*60)
    print("测试: 完整资源推荐Agent")
    print("="*60)
    
    try:
        from resource_recommender import init_resource_recommender
    except ImportError as e:
        print(f"[FAIL] 模块导入失败: {e}")
        return False
    
    try:
        agent = init_resource_recommender()
        print(f"[OK] Agent初始化成功")
        print(f"     RAG功能: {'已启用' if agent._rag_initialized else '未启用'}")
    except Exception as e:
        print(f"[FAIL] Agent初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
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
                },
                {
                    "stage_name": "第二阶段：实战演练",
                    "study_content": "函数和项目实践",
                    "time_allocation": "4天",
                    "milestone": "完成简单项目"
                }
            ]
        }
    }
    
    print("\n--- 执行资源推荐 ---")
    try:
        result = agent.recommend(test_requirement, test_plan)
        
        resources = result.get('resources', [])
        rag_info = result.get('rag_info', {})
        
        print(f"[OK] 推荐完成")
        print(f"     资源数量: {len(resources)}")
        
        if rag_info:
            print(f"     RAG来源: {rag_info.get('source_info', 'N/A')}")
            print(f"     知识库匹配度: {rag_info.get('kb_relevance', 0):.2f}")
        
        if resources:
            print(f"\n     推荐资源列表:")
            for i, r in enumerate(resources, 1):
                print(f"     {i}. [{r.get('type', 'N/A')}] {r.get('title', 'N/A')}")
                print(f"        难度: {r.get('difficulty', 'N/A')}")
                print(f"        来源: {r.get('source', 'N/A')}")
        else:
            print("[WARN] 未推荐到资源，可能需要检查RAG配置")
        
    except Exception as e:
        print(f"[FAIL] 推荐失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def main():
    """主测试函数"""
    print("="*60)
    print("端到端测试套件")
    print("="*60)
    
    results = {}
    
    results['Agentic RAG'] = test_agentic_rag()
    results['反馈系统集成'] = test_feedback_integration()
    results['资源推荐Agent'] = test_resource_recommender_agent()
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    all_passed = True
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        print("\n所有测试通过！系统可以正常运行。")
        print("\n下一步:")
        print("  1. 启动前端: cd c:\\ai学习 && npm run dev")
        print("  2. 启动后端API: python api_server.py")
        sys.exit(0)
    else:
        print("\n部分测试失败，请检查上述错误信息。")
        sys.exit(1)


if __name__ == "__main__":
    main()
