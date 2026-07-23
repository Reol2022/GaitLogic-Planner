# Training Knowledge Authoring Guide v1

## 1. 建立来源

先在 `knowledge/sources/*.yaml` 登记来源。来源 ID 必须全局唯一并使用小写 kebab-case。若参考受版权保护材料，只能保存书目信息和自己撰写的摘要：

```yaml
- source_id: example-book-summary
  title: Example Training Book
  source_type: BOOK_SUMMARY
  authors:
    - Example Author
  publication_year: 2025
  license_status: SUMMARY_ONLY
  usage_policy: SELF_WRITTEN_SUMMARY
  notes: Independent summary; no original book text is stored.
```

不要复制章节、训练表或付费课程内容。

## 2. 创建 document ID

ID 描述稳定主题，不绑定文件名、用户或日期。例如：

```text
threshold-session-placement
```

文件可以移动，但 `document_id` 一旦公开应保持稳定。主题语义发生根本变化时应建立新文档，而不是复用旧 ID。

## 3. 编写 Front Matter

```yaml
---
document_id: threshold-session-placement
title: 阈值训练的周内安排
category: THRESHOLD
tags:
  - threshold
  - scheduling
applicable_phases:
  - BASE
  - BUILD
  - SPECIFIC
source_id: example-book-summary
source_type: BOOK_SUMMARY
evidence_level: SECONDARY
knowledge_version: "1.0.0"
language: zh-CN
status: DRAFT
reviewed_at: 2026-07-23
limitations:
  - 本文为独立撰写摘要
---
```

只能使用代码中定义的分类、来源类型、证据等级、状态和训练阶段。不要增加 Loader 未知字段。

## 4. 编写五个必需章节

每篇文档必须使用二级标题：

```markdown
## 适用场景
## 核心原则
## 判断条件
## 推荐策略
## 注意事项
```

内容应是普适训练教育材料，不写成某位用户的个人课表。不提供医疗诊断，不承诺表现，不用知识文档发明运动科学阈值。

## 5. 本地验证

```powershell
python scripts/knowledge_corpus.py validate
python scripts/knowledge_corpus.py build --dry-run
python scripts/knowledge_corpus.py list
```

校验失败时先修正文档或来源。不要通过放宽 Schema、跳过未知字段或删除安全检查绕过问题。

## 6. 检查切分结果

```powershell
python scripts/knowledge_corpus.py inspect --document-id threshold-session-placement
python scripts/knowledge_corpus.py inspect --chunk-id threshold-session-placement#applicable-scenarios#001
```

确认标题、列表、表格和代码块没有被破坏；Chunk 不含 Front Matter；输出不含本机绝对路径。

## 7. 评审与激活

新内容先使用 `DRAFT`，完成事实、版权、语言和安全评审后改为 `ACTIVE`。已不建议检索的内容可标记为 `DEPRECATED`；仅留档内容标记为 `ARCHIVED`。

## 8. 更新版本

- 文字纠错、不改变语义：patch，例如 `1.0.0 -> 1.0.1`。
- 增加兼容解释或限制：minor，例如 `1.0.0 -> 1.1.0`。
- 训练原则发生不兼容变化：major，例如 `1.0.0 -> 2.0.0`。

版本更新后运行 `validate`、`build --dry-run`、评审 Manifest 差异，再使用 `build --force` 更新派生 Manifest。不得手工编辑 Manifest。

## 9. 发布前清单

- [ ] 来源存在且许可状态明确。
- [ ] 没有复制受版权保护的原文。
- [ ] 没有真实用户数据、身份或凭据。
- [ ] 五个必需章节齐全。
- [ ] 分类、阶段和状态均为受控枚举。
- [ ] 限制和非医疗边界清楚。
- [ ] `validate` 通过。
- [ ] `inspect` 内容结构正确。
- [ ] Manifest 只包含仓库相对路径。
