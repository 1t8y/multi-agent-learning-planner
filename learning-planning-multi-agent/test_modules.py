# -*- coding: utf-8 -*-
"""
模块测试脚本
依次测试各核心模块功能
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv('.env')

def test_tavily():
    """测试Tavily网络搜索"""
    print("\n" + "="*60)
    print("测试1: Tavily网络搜索")
    print("="*60)
    
    try:
        from tavily import TavilyClient
        print("[OK] Tavily SDK可用")
    except ImportError as e:
        print(f"[FAIL] Tavily SDK未安装: {e}")
        return False
    
    api_key = os.getenv('TAVILY_API_KEY')
    try:
        client = TavilyClient(api_key=api_key)
        print("[OK] Tavily客户端初始化成功")
    except Exception as e:
        print(f"[FAIL] 客户端初始化失败: {e}")
        return False
    
    print("\n测试搜索: Python编程入门教程")
    try:
        response = client.search(
            query='Python编程入门教程',
            search_depth='basic',
            max_results=3,
            include_answer=False
        )
        
        results = response.get('results', [])
        print(f"[OK] 搜索成功，返回 {len(results)} 个结果")
        print()
        
        for i, r in enumerate(results[:2], 1):
            title = r.get('title', '')
            url = r.get('url', '')
            content = r.get('content', '')[:80]
            print(f"{i}. {title}")
            print(f"   URL: {url}")
            print(f"   内容: {content}...")
            print()
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feedback_manager():
    """测试反馈管理器"""
    print("\n" + "="*60)
    print("测试2: 反馈管理器")
    print("="*60)
    
    try:
        from feedback_manager import FeedbackManager, init_feedback_manager
        print("[OK] 反馈管理器模块加载成功")
    except ImportError as e:
        print(f"[FAIL] 模块加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        fm = init_feedback_manager(vector_store=None)
        print("[OK] 反馈管理器初始化成功")
    except Exception as e:
        print(f"[FAIL] 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n测试提交反馈...")
    try:
        feedback = fm.submit_feedback(
            resource_id='test_001',
            resource_title='Python基础教程',
            resource_url='https://example.com/python',
            feedback_type='useful',
            rating=5,
            comment='非常好的入门教程',
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
        import traceback
        traceback.print_exc()
        return False
    
    print("\n测试提交新资源...")
    try:
        submission = fm.submit_resource(
            title='LangGraph官方文档',
            description='LangGraph官方学习资源',
            url='https://langchain-ai.github.io/langgraph/',
            resource_type='文档资料',
            field='AI',
            tags=['LangGraph', 'Agent'],
            submitted_by='test_user'
        )
        
        if submission:
            print(f"[OK] 资源提交成功，ID: {submission.id}")
        else:
            print("[FAIL] 资源提交失败")
            return False
    except Exception as e:
        print(f"[FAIL] 资源提交失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n获取统计信息...")
    try:
        stats = fm.get_feedback_stats()
        print(f"[OK] 统计信息获取成功:")
        for k, v in stats.items():
            print(f"   - {k}: {v}")
    except Exception as e:
        print(f"[FAIL] 统计信息获取失败: {e}")
        return False
    
    return True


def test_vector_store_light():
    """轻量级向量数据库测试（不下载模型）"""
    print("\n" + "="*60)
    print("测试3: 向量数据库（轻量级）")
    print("="*60)
    
    try:
        import chromadb
        from chromadb.config import Settings
        print("[OK] ChromaDB SDK可用")
    except ImportError as e:
        print(f"[FAIL] ChromaDB未安装: {e}")
        return False
    
    try:
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        client = chromadb.PersistentClient(
            path=temp_dir,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        print("[OK] ChromaDB客户端初始化成功")
        
        collection = client.get_or_create_collection(
            name='test_resources',
            metadata={'description': '测试资源库'}
        )
        print("[OK] 集合创建成功")
        
        collection.add(
            ids=['test_1', 'test_2'],
            documents=['Python编程基础入门', '机器学习算法概述'],
            metadatas=[
                {'title': 'Python基础', 'field': '编程'},
                {'title': '机器学习', 'field': 'AI'}
            ]
        )
        print("[OK] 数据添加成功")
        
        results = collection.query(
            query_texts=['Python入门'],
            n_results=2
        )
        print(f"[OK] 检索成功，返回 {len(results['documents'][0])} 个结果")
        
        for i, doc in enumerate(results['documents'][0]):
            print(f"   {i+1}. {doc}")
        
        shutil.rmtree(temp_dir)
        print("[OK] 测试完成，清理临时目录")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("="*60)
    print("模块测试套件")
    print("="*60)
    
    results = {}
    
    results['Tavily网络搜索'] = test_tavily()
    results['反馈管理器'] = test_feedback_manager()
    results['向量数据库'] = test_vector_store_light()
    
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
        print("所有测试通过！")
        sys.exit(0)
    else:
        print("部分测试失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
