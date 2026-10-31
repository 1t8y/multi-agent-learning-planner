"""离线脚本：数据构建与模型下载，不参与线上运行。

- rebuild_knowledge_base  校验资源 jsonl 并按需重建 ChromaDB
- build_testset           从知识库派生评测集
- compare_ragas           新旧评测结果的同题对照
- download_chroma_model   预下载 Chroma 默认 Embedding 模型
- manual_download_model   手动下载模型到本地缓存

统一以 `python -m scripts.xxx` 在 backend/ 目录下运行。
"""
