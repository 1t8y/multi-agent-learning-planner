"""检索增强（RAG）层。

- self_rag_recommender   Self-RAG 主流程：改写查询、召回、合并、丢弃不相关
- advanced_self_rag      在 Self-RAG 上叠加元数据过滤、Cross-Encoder 精排、质量门控
- reranker               精排模型封装，含置信度门控
- rag_quality            检索结果质量打分与归因

依赖方向：rag → memory / tools / config，不反向依赖 core 与 api。
"""
