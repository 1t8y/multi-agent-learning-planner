"""记忆层。

- model_loader      本地 Embedding / Cross-Encoder 模型加载，优先读缓存避免联网
- vector_store_core Chroma 客户端、BM25 索引、Dense/Sparse/Hybrid 检索与 RRF 融合
- vector_store      对外的统一入口，转发到 vector_store_core 并做初始化

长期记忆存在 ChromaDB，短期上下文存在编排层的 state 里。
"""
