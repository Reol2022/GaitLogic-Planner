# GaitLogic 开源与项目治理规则

## v0.10.2 Open Source Boundary

Community:
evidence source schema, rule version model, lifecycle state machine, review
workflow, release and rollback services, anonymous rule test case format,
regression runner, impact analysis, coverage statistics, conflict diagnostics,
rule package manifest format, public evidence index, admin governance API,
basic governance page, audit mechanism, tests, and documentation.

Official / Private:
official advanced rule packages, commercial coach rule bundles, private
training-strategy evidence interpretation, internal elite-runner thresholds,
production prompts, private rule weights, real-user historical replay results,
personalized tuning data, user-behavior-derived recommendation policy, Coach
Engine proprietary logic, official cloud release strategy, commercial approval
records, and third-party restricted content.

Community edition requirements:
the community edition can independently create rules, review rules, test rules,
publish basic rules, rollback rules, and run without private services.

## v0.10.1 Open Source Boundary

Community:
unified training facts schema, plan analyzer, plan validation flow, daily rule
evaluation, workout rule review, weekly rule review, structured adjustment
drafts, user confirmation mechanism, basic rule set, Chinese action/severity
labels, API schemas, tests, docs, and example-safe data structures.

Official / Private:
advanced training strategy combinations, official premium period templates,
private runner-level weights, proprietary adjustment magnitude models,
production prompts, user-behavior-derived recommendation policy, commercial
coach rules, cloud risk control, real user training data, third-party platform
secrets, and future private Coach Engine logic.

## v0.10.0 Open Source Boundary

Community:
general knowledge structure, rule DSL, deterministic rule engine, basic product
rules, safety boundaries, API schemas, tests, docs, and public science boundary
notes.

Official / Private:
advanced training strategy, private rule combinations, personalized tuning,
cloud risk-control parameters, production prompts, real user training data,
tokens, provider credentials, and future private Coach Engine logic.

## v0.9.5 开源边界补充

进入公开仓库：极简训练闭环信息架构、待办中心实时聚合、训练计划中心、数据管理入口、今日聚合 API、快速恢复打卡 API、数据同步偏好字段、`device_prefilled` 通用完成上下文、灰度开关、迁移脚本、统一版本号展示、版本发布同步规范、测试和文档。

不进入公开仓库：真实用户待办数据、真实训练日志、真实设备同步活动、生产自动同步调度凭据、私有匹配权重、私有训练建议策略、生产数据库备份、任何未脱敏用户训练历史、生产环境 `.env`、私有构建服务信息、CI Token、部署凭据、未公开 Commit 元数据和生产内部版本说明。

## v0.9.4 开源边界补充

进入公开仓库：Data Sync provider 注册表、能力描述、Facade、Pipeline、Garmin adapter 迁移入口、Mock provider 占位、通用 API、前端“数据同步”页面、测试和文档。

不进入公开仓库：真实用户 Garmin 账号、真实 token/cookie/session、生产数据库备份、真实活动原始数据、完整 GPS 轨迹、私有匹配权重、生产同步凭据和任何未脱敏用户训练历史。

## 1. 项目定位

GaitLogic Planner 是面向严肃跑者的训练计划、训练执行、训练日志与复盘系统。

当前社区仓库聚焦：

- 登录注册与多用户数据隔离；
- AI 训练计划草稿生成；
- Excel 标准模板下载与导入；
- 我的训练计划、今日训练、训练日历和训练日志；
- VDOT / 丹尼尔斯配速计算器；
- 配速规则、训练统计和反馈收集；
- 管理后台中的用户管理、系统设置和 AI 模型配置。

项目可以采用 Open Core 模式：

- GaitLogic Planner Community 为开源社区版；
- GaitLogic Coach Engine 为未来可能建设的私有训练决策服务；
- GaitLogic Cloud 为未来可能提供的官方托管、运维和商业服务。

开源社区版应保持真实可用，不得仅作为无法独立运行的展示外壳。

---

## 2. 开源范围

以下能力属于当前社区仓库的开源范围：

- 用户注册、登录与基础权限控制；
- 多用户训练数据隔离；
- 训练周期、训练块和每日训练计划；
- 今日训练与快速打卡；
- 训练日历；
- 训练日志；
- 基础训练统计；
- Excel 标准模板下载与上传导入；
- VDOT 与训练配速计算；
- 配速规则；
- 基础 AI 模型接入框架；
- AI 课表草稿数据结构、草稿预览和确认应用流程；
- AI 教练偏好配置；
- 通用训练安全校验；
- 反馈收集；
- 管理后台中的用户管理、系统设置和 AI 设置；
- 本地运行、部署说明、测试框架和演示数据；
- 对外公开的 API 数据结构。

### v0.8 社区版公开能力

- 周训练确定性统计与 `block_reviews` 汇总复用；
- 通用训练状态规则（数据不足、正常、关注恢复、建议降负荷）；
- 可独立运行的基础 AI 周复盘 Prompt 与严格 JSON Schema；
- 下一周调整草稿、原计划对比、用户逐项确认和事务应用；
- 通用调整安全校验、权限隔离、迁移、前端页面和 Mock 测试。

### v0.9 社区版公开能力

- 恢复打卡数据库结构、迁移、API 和页面；
- session-RPE、7 天滚动负荷、28 天个人基线和数据质量规则；
- 五维信号框架、四档训练状态、默认启发式阈值和疼痛优先规则；
- 确定性原因、模板化训练建议和与 v0.8 周复盘的规则集成；
- 功能灰度表 `feature_access`、安全 CLI、权限隔离和聚合产品指标；
- 单元测试、接口结构测试、虚构测试数据和科学设计文档。

### v0.9.1 社区版公开能力

- 统一课表导入 DTO、JSON 解析、Excel 和 CSV 解析、规范 TXT 和 Markdown 解析；
- 课表导入草稿流程、差异预览、冲突检查、已完成计划保护和合并策略；
- 基于 `plan_adjustment_draft` / `plan_adjustment_item` 的草稿扩展；
- 事务应用、幂等机制、权限隔离和导入审计摘要；
- 课表导入 API、前端页面、Excel 模板生成逻辑、测试和虚构示例数据。

### v0.9.2 社区版公开能力

- 训练记录导入统一 DTO、JSON、Excel、CSV、规范 TXT 和 Markdown 解析；
- 训练记录导入草稿、计划匹配、已有日志冲突检测、字段级差异和合并策略；
- `workout_import_batch` / `workout_import_item` / `workout_import_audit` 数据结构；
- `WorkoutLog` 来源、计划外训练、活动指纹和字段来源记录；
- 事务应用、幂等机制、权限隔离、功能开关和灰度；
- 训练记录导入 API、前端页面、Excel 模板、测试、用户文档和架构文档。

### v0.9.3 社区版公开能力

- Garmin 多用户同步的数据结构、API、队列任务、Worker 和前端页面；
- `ActivityProvider` 抽象、基于 `garminconnect/garth` 的 Garmin Provider、Mock Provider 和虚构测试数据；
- 用户级令牌加密接口、密文 envelope、key version 和安全失败码；
- 脱敏原始活动、标准活动、活动分段、训练日志关联和人工处理审计；
- 去重、幂等、手动同步、计划匹配、计划外日志和待处理状态；
- Garmin 同步原则、字段定义、分段规则、API、用户指南、架构和部署文档。

---

## 3. 非开源范围

以下内容不属于社区仓库必须公开的范围：

- 生产环境 API Key、Token 和密钥；
- 生产环境完整 AI Prompt；
- 高质量 few-shot 示例库；
- 私有训练计划模板库；
- 动态训练调整决策引擎；
- 跑者画像与个性化权重算法；
- 训练计划质量评分器；
- 用户行为和真实训练数据；
- 官方云服务的防刷、风控和成本控制策略；
- 支付、会员、赞助和商业合作后台；
- Garmin、Coros、Huawei 等受协议限制的正式商业接口；
- 跑团和教练工作台的商业增强功能；
- 服务器、数据库和生产环境私密配置。

v0.8 官方服务可能保留私有的内容包括：生产 Prompt、私有训练模板、用户画像、
私有评分和调参、基于真实用户数据形成的动态调整策略，以及云端模型路由和成本控制。
社区默认实现不得依赖这些私有能力才能运行。

v0.9 官方服务不得把真实用户恢复数据、真实疼痛数据、HRV 原始明细、私有个体化阈值、
用户分群模型、生产异常检测模型、教练人工标注数据或 A/B 测试明细提交到公开仓库。

v0.9.1 官方服务不得把生产访问令牌、真实用户课表、自由文本 AI 解析生产 Prompt、私有 few-shot 课表、
个性化课表调整策略、生产模型路由、外部工具认证信息、服务器地址、密钥或生产数据库备份提交到公开仓库。

v0.9.2 官方服务不得把真实用户训练记录、用户上传原始文件、真实导入历史、佳明账号信息、
佳明 Cookie、Token、Session、私有设备同步规则、基于真实用户调优的匹配权重或生产模型路由提交到公开仓库。

v0.9.3 官方服务不得把真实 Garmin 账号、密码、MFA、Token、Cookie、Session、完整 GPS 轨迹、
设备序列号、真实活动原始 JSON、生产加密密钥、生产同步日志、基于真实用户调优的合并权重或私有 Provider 凭据提交到公开仓库。

开源仓库中的基础 AI Prompt 应确保项目可以运行，但不承诺与官方线上服务使用完全相同的生产 Prompt。

---

## 4. 许可证

当前仓库采用 `AGPL-3.0-only` 开源许可证，完整条款以根目录 [LICENSE](LICENSE) 文件为准。

GNU Affero General Public License v3.0 的核心含义包括：

- 可以使用、学习和修改代码；
- 可以进行商业使用，但必须遵守许可证条件；
- 分发修改版本时必须保留相应版权与许可证信息；
- 修改后的版本通过网络向用户提供服务时，应按照许可证要求向相应用户提供源代码；
- 不得通过附加条款取消许可证已经授予的自由。

第三方依赖仍适用其各自许可证，不因本项目许可证而自动改变。

---

## 5. 商标与品牌

软件许可证不自动授予对以下标识的品牌使用权：

- GaitLogic；
- GaitLogic Planner；
- GaitLogic Coach；
- 官方 Logo；
- 官方界面视觉标识；
- 官方域名和社交媒体账号标识。

允许的使用：

- 如实说明“基于 GaitLogic Planner 修改”；
- 在技术文章中介绍 GaitLogic Planner；
- 在合规的 Fork 中说明上游项目来源；
- 使用文字链接指向官方仓库。

未经明确授权，不允许：

- 声称修改版是 GaitLogic 官方版本；
- 使用近似名称、Logo 或域名使用户误认为与官方存在合作；
- 使用 GaitLogic 品牌销售未经官方确认的训练、医疗或教练服务；
- 在宣传中暗示获得官方背书；
- 移除原项目归属后冒充原创产品。

Fork 或二次发行版本应使用可明确区分的新名称和新 Logo。详细规则见 [TRADEMARK.md](TRADEMARK.md)。

---

## 6. 贡献规则

欢迎提交：

- Bug 修复；
- 测试补充；
- 文档改进；
- 移动端体验优化；
- 无障碍改进；
- 数据导入导出能力；
- 合理的训练统计功能；
- 经过说明和验证的训练规则改进。

提交贡献前应：

1. 先搜索已有 Issue；
2. 较大功能先提交 Feature Request；
3. 一个 Pull Request 只解决一个主要问题；
4. 补充必要测试；
5. 更新相关文档；
6. 不提交格式无关的大面积改动；
7. 不提交真实用户数据；
8. 不提交密钥、Token、密码或数据库备份。

Pull Request 应说明：

- 解决了什么问题；
- 为什么需要这样修改；
- 如何测试；
- 是否影响数据库；
- 是否影响 API；
- 是否影响移动端；
- 是否涉及训练安全逻辑。

---

## 7. AI 辅助代码规则

允许使用 AI 工具辅助开发，但提交者必须对最终代码负责。

使用 AI 生成或大幅修改代码时：

- 必须人工阅读和理解；
- 必须运行测试；
- 不得提交无法解释的代码；
- 不得将生产密钥、真实用户数据或私有 Prompt 发送给第三方模型；
- 不得复制来源和许可证不明确的代码；
- Pull Request 中应说明 AI 是否参与了核心实现；
- AI 生成内容不能替代安全审查和训练逻辑审查。

“代码由 AI 生成”不能作为错误、侵权或安全问题的免责理由。

---

## 8. 跑步训练与安全规则

涉及训练计划、训练强度、负荷或恢复建议的贡献，需要遵守：

- 不承诺用户一定 PB、达标或避免受伤；
- 不把软件描述为医疗诊断工具；
- 不鼓励带伤硬撑；
- 不使用单一指标直接判断受伤概率；
- 训练强度必须有明确目的；
- 不默认连续安排高强度训练；
- 跑量和负荷增长需要合理边界；
- 有持续疼痛或异常身体反应时，应建议降低训练并寻求专业评估；
- AI 输出必须经过结构和安全规则校验；
- AI 计划默认作为草稿，由用户确认后采用。

涉及重大训练方法变更的 Pull Request，应提供理论依据、适用范围和潜在风险说明。

---

## 9. 用户数据与隐私

禁止向仓库、Issue、Discussion 或 Pull Request 提交：

- 真实用户姓名和联系方式；
- 邮箱、手机号和精确位置；
- 访问令牌和会话信息；
- 未经匿名处理的训练日志；
- 健康、伤病和身体指标原始数据；
- 生产数据库导出；
- 服务器日志中的敏感字段。

用于测试的数据必须：

- 完全虚构；
- 或经过不可逆匿名化；
- 不包含可识别个人身份的信息。

项目默认遵循数据最小化原则，只收集实现功能所必要的数据。

---

## 10. 安全问题报告

发现以下问题时，不要直接公开详细利用方法：

- 登录绕过；
- 越权访问；
- 用户数据泄露；
- API Key 或密钥泄露；
- 任意文件读取或上传；
- SQL 注入；
- 远程代码执行；
- 高成本 AI 接口滥用；
- 可造成生产服务严重中断的问题。

请按照 [SECURITY.md](SECURITY.md) 中提供的私密渠道报告。

维护者确认并修复前，应避免公开可以直接复现攻击的完整步骤。

---

## 11. Issue 与讨论规范

Issue 应包含：

- 问题描述；
- 复现步骤；
- 预期结果；
- 实际结果；
- 系统和浏览器环境；
- 必要的脱敏日志；
- 截图或录屏，可选。

以下内容可能被关闭：

- 无法复现且长期不补充信息；
- 与项目无关；
- 重复 Issue；
- 广告和推广；
- 索要真实用户数据；
- 要求绕过第三方服务条款；
- 直接要求加入未经验证的“神奇训练算法”；
- 带有侮辱、骚扰或人身攻击的内容。

---

## 12. 版本与发布

项目采用语义化版本：

- MAJOR：存在不兼容的架构或 API 变化；
- MINOR：新增向后兼容功能；
- PATCH：Bug 修复和小型体验优化。

每次正式发布应：

- 更新 `docs/更新历史.md`；
- 标注数据库迁移步骤；
- 标注配置项变化；
- 标注已知风险；
- 确认 `.env.example` 已同步；
- 确认文档中的启动命令有效；
- 运行后端测试和前端构建。

---

## 13. 项目治理

当前项目由核心维护者负责最终决策。

维护者有权：

- 接受或拒绝 Pull Request；
- 调整路线图和版本优先级；
- 拒绝明显扩大维护成本的功能；
- 拒绝缺少测试或安全边界的训练算法；
- 管理版本发布；
- 处理安全问题；
- 保护项目品牌和用户数据。

拒绝某项贡献不代表否定贡献者，而可能是因为：

- 当前版本不在该方向；
- 功能过于复杂；
- 与产品定位冲突；
- 缺少维护资源；
- 安全或训练风险不可控。

---

## 14. 免责声明

GaitLogic Planner 提供的是训练计划管理、记录和参考工具。

软件输出：

- 不构成医疗诊断；
- 不构成康复建议；
- 不构成专业教练服务承诺；
- 不能替代医生、康复师或具备资质的专业人员意见；
- 不能保证训练成绩或避免伤病。

用户应根据自身身体状态、环境、天气、训练经验和专业建议决定是否执行训练内容。
