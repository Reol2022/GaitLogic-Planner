# Training Knowledge Evaluation Dataset Guide v1

## 两个公开数据集

- `cases/retrieval-eval-v1.json`：60 条检索案例；
- `cases/rag-answer-eval-v1.json`：36 条 Agent/RAG 案例。

二者均使用严格 Pydantic Schema、唯一 case ID、固定版本和内容 SHA-256。
未知字段、重复 ID、缺失文档、非法 Tool、abstain 与相关性冲突都会拒绝加载。

## Retrieval 标注

`relevant_documents` 的相关性只允许 1、2、3：

- 3：直接回答查询的核心文档；
- 2：提供重要辅助原则；
- 1：有帮助但非必要。

`forbidden_document_ids` 用于 hard negative；`should_abstain` 表示当前语料
不应返回知识。`acceptable_chunk_ids` 可用于需要精确 section 的后续案例。
标注不得根据当前 Retriever 输出反向修改。

新增案例时：

1. 先以产品问题定义查询；
2. 独立阅读语料后标注文档；
3. 检查所有文档 ID 和 chunk ID；
4. 更新内容 SHA-256；
5. 运行 dataset 与 metrics 测试；
6. 保留失败结果，禁止为绿灯删除案例。

## RAG 案例

`fictional_context` 是固定 Fixture 名称，不是用户数据。`expected_tools`
只能引用正式 Registry 工具。`canonical_today_facts` 只允许 TODAY 使用，
用于比较启用与关闭 RAG 时 decision、risk 和 planned status 是否不变。

`forbidden_claims`、`required_limitations` 与 `citation_required` 形成安全断言。
案例中不得存储真实模型回答、完整 Prompt、完整 Tool Result、用户标识或凭据。

## 版本与 Hash

修改任一案例都必须提升数据集版本或按维护策略记录变更，并重新计算规范化
JSON 的 SHA-256。Hash 输入排除 `content_sha256` 自身，JSON 使用 UTF-8、
稳定键排序和紧凑分隔符。

## Public / Private

公开仓库仅放虚构、可审查的固定案例。真实用户分布、竞赛盲测、
人工打分、Provider 对比和失败原文保留在私有竞赛仓库。两个仓库之间仅通过
标准脱敏 JSON 导出衔接，不建立代码依赖。
