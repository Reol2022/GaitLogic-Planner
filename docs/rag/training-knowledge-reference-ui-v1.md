# Training Knowledge Reference UI v1

## 目标

Coach 页面把回答拆成六层：确定性训练建议、AI 解释、训练知识依据、风险提示、数据与能力限制、工具安全摘要。训练知识只解释公开训练原则，不参与或覆盖 TODAY 的确定性 Decision。

## 公共字段

前端只读取 `CoachQueryResponse.knowledge_references` 中已经由服务端物化的字段：

- `document_id`：仅用于组件稳定渲染键，不展示；
- `title`、`section`；
- `source_id`：不展示；
- `source_title`；
- `knowledge_version`；
- `evidence_level`；
- `excerpt`；
- `limitations`。

不展示内部 Reference ID、Chunk ID、文件路径、检索分数、Index ID、Corpus Hash、向量、Provider 信息或原始 Tool Result。

## 状态推导

前端不解析内部异常，仅从公共响应推导：

| 状态 | 公共信号 | 用户文案 |
| --- | --- | --- |
| USED | 存在物化引用 | 已使用训练知识 |
| EMPTY | 检索工具成功且引用为空 | 当前知识库未找到直接依据 |
| UNAVAILABLE | 检索工具失败或安全 limitation | 训练知识暂时不可用 |
| DISABLED | 新响应明确返回空数组且没有检索调用 | 训练知识功能未启用 |
| 不显示 | 旧响应没有该字段 | 保持向后兼容，不猜测 |

## Evidence Level

`PRIMARY`、`SECONDARY`、`EXPERT_CONSENSUS`、`INTERNAL` 和 `UNKNOWN` 分别显示为一手来源、二手资料、专家共识、系统内部说明和证据等级未知。

## 安全与布局

- 摘录使用 Vue 文本插值，不使用 `v-html`；
- 长标题、摘录、来源和限制允许自动换行；
- 摘录使用原生 `details/summary`，支持键盘操作；
- 没有引用时不渲染空引用卡；
- 移动端标题、计数和正文改为纵向布局；
- 引用不能被描述为医疗证据。

## 当前限制

E1 不改变 Retriever、排序、Embedding、Validator 或知识库内容。状态来自现有公共信号；如果后续需要区分更多内部阶段，应先设计新的受控公共契约。
