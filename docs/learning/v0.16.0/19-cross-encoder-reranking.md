# Cross-Encoder 重排序

Embedding 检索预先把查询和文档各自向量化，适合大范围候选召回；Cross-Encoder 同时阅读一条查询和一条候选文本，相关性通常更精细但延迟更高。因此 GaitLogic 只对最多 16 个候选调用它。
