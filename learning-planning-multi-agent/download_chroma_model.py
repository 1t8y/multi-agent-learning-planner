# -*- coding: utf-8 -*-
"""
触发 Chroma embedding 模型下载
"""

import chromadb
from chromadb.config import Settings
import tempfile
import shutil
import os

print("=" * 60)
print("Chroma Embedding 模型下载")
print("=" * 60)

temp_dir = tempfile.mkdtemp()
print(f"临时目录: {temp_dir}")

try:
    print("\n初始化 Chroma 客户端...")
    client = chromadb.PersistentClient(
        path=temp_dir,
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
    )
    print("[OK] 客户端初始化成功")

    print("\n创建集合（将触发模型下载）...")
    collection = client.get_or_create_collection(
        name='test_model_download',
        metadata={'description': '用于触发模型下载'}
    )
    print("[OK] 集合创建成功")

    print("\n添加数据...")
    collection.add(
        ids=['test_1'],
        documents=['这是一个测试文档，用于触发 embedding 模型下载'],
        metadatas=[{'title': '测试'}]
    )
    print("[OK] 数据添加成功")

    print("\n执行搜索（触发模型加载）...")
    results = collection.query(
        query_texts=['测试搜索'],
        n_results=1
    )
    print(f"[OK] 搜索成功，返回 {len(results['documents'][0])} 个结果")

    print("\n" + "=" * 60)
    print("模型下载和验证完成！")
    print("=" * 60)

except Exception as e:
    print(f"[ERROR] 发生错误: {e}")
    import traceback
    traceback.print_exc()

finally:
    try:
        shutil.rmtree(temp_dir)
        print(f"[OK] 清理临时目录: {temp_dir}")
    except Exception as e:
        print(f"清理临时目录失败: {e}")
