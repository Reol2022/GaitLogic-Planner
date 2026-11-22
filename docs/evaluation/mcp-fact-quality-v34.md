# MCP 训练事实质量修复 v3.4

日期：2026-11-13。状态：本地实现与验收，未提交、未推送、未部署。代码标识 `0.16.8-facts-v3.4-quality` 为本地候选，不代表线上已升级。

## 基线与边界

- 运行代码基线 `a82d94f`，文档基线 `ec6f7d6`，当前分支 `codex/mcp-fact-quality-v34`。
- 保留上一轮系统设置后台整合的未提交修改；不将其纳入本轮事实修复范围，不改动受保护的 `scripts/upgrade_v0130_adaptive_plan.py` 或已有架构图目录。
- 只修复分段存储、分类来源与覆盖率、新鲜度语义及 MCP 发现契约。未新增 MCP Tools，未修改风险阈值、计划审批、正式计划或个人同步开关。
- 未发起真实 Garmin 请求，未读写生产数据库。真实训练案例只提供问题形状，公开测试完全使用合成数据。

## 已核实的根因

1. `_replace_laps` 原先只保护空结果，非空候选会删除全部旧圈再插入；分类汇总或不完整明细存在覆盖较细数据的代码风险。没有历史快照对照证据，不能断言某次真实活动已经因此丢失明细。
2. 近期训练旧链路的关键课计数在实际分类缺失时回退到计划类型；“计划是强度课”不代表实际完成强度课。分页 MCP 与旧式请求可能采用不同计数依据。
3. 新鲜度的 FRESH/STALE 被自动同步开关、排队或失败状态覆盖，无法直接区分“关闭同步”与“数据过期”。
4. 服务端原先已声明新增顶层字段，但分段校验和分类使用自由 dict；宿主仍可能缓存旧声明。单凭宿主未列出字段，不能认定线上服务端遗漏 Schema。

## 分段防降级与私有快照

- 替换前比较旧/新结构的独立明细数、距离时间一致性、重叠/冲突、时间边界、心率和步频覆盖。汇总、较少明细、结构退化或可选指标覆盖减少时保留旧圈，候选进入私有证据存储，不做任意拼接。
- 比较旧圈时使用写入前的活动汇总，避免新汇总先覆盖后改变旧结构的完整性判断。
- 复用 `ExternalActivityRaw` 保存白名单化 `lap_snapshot_v1`，遵循既有保留时间。每快照最多 1000 圈，超限明确标记；不存 GPS、聊天、备注或凭据，不向 MCP 暴露原始载荷或内容哈希。
- 数字按语义规范化后哈希，避免 Decimal 小数位变化造成无意义版本递增。相同候选不重复删除/插入，版本和快照与业务写入共同提交、共同回滚。
- `field_sources_json.lap_sync` 保留当前版本、候选摘要和接收/拒绝原因。MCP `segment_storage` 仅输出受控状态、数量和检查时间，拒绝退化时增加 `LAP_DOWNGRADE_REJECTED`。
- 保守拒绝也可能挡住合法的上游圈合并或修订。这些候选需审查，不提供静默强制覆盖入口。

## 上游补充检查

现有 garminconnect SDK 的 `/splits`、`/typedsplits` 都不保证每种活动具备独立训练组。详情读取只有在第一响应没有可识别明细时，才对现有 typed-splits 方法增加一次受限调用，保留两种响应，不增加新 Provider 或猜测新接口。

typed-splits 只有出现明确 lap index 和时间边界时，才作为明细候选，之后仍须完整性与重叠校验；分类汇总仍不可反推组数。失败不影响活动汇总/RPE 成功。该改动每次详情最多增加一次受限请求，不由 MCP 读取直接调用 Garmin。

尚未验证真实账户是否能从 typed-splits 取回缺失分组，也未执行重同步或自动历史恢复。

## 分类与统计语义

- `actual_type_source` 区分 USER_REPORTED_FACT、PROVIDER_RECORDED、RECORDED_UNVERIFIED、UNKNOWN；`actual_type_confirmation` 区分用户确认、Provider 声明和未确认。普通记录有类型值，不自动等同用户确认，更不等同独立验证。
- `completed_key_sessions` 只计实际记录类型，不再将计划类型作为实际关键课依据；保留计划类型用于对照。
- `classified_sessions`、`unclassified_sessions`、`classification_coverage` 和 `key_session_count_status` 覆盖整个统计窗口，而不是当前分页。无记录的覆盖率是 null，不填零；计数完整度也不代表竞技判断正确率。
- 活动结构分类标明 SELECTED_ACTIVITY 和 DETERMINISTIC_DERIVATION，不把一个活动的分段分类升级为整堂多活动训练的已确认分类。
- 仍无整堂课确认界面、个人 HRV 基线或 Runner State v2；LOW 不代表恢复充分。Runner State 限制提示按代码/内容去重，并补充相关中文说明。

## 时间与同步状态

- 保留旧 `status` 供已有客户端使用，新增独立 `sync_status`、`data_freshness`、`data_freshness_by_scope`。
- 新鲜度按现有 15 分钟窗口保守判断；无成功时间返回 UNKNOWN，超出窗口返回 STALE，不因自动同步关闭而隐藏。
- `facts_read_at` 是读取开始时间，`last_success_at` 是成功抓取时间，`as_of` 是查询日期；均不能保证设备端已上传全部数据。
- Coach 近期事实工具可只读获取同一新鲜度，不提交同步任务；检查失败不污染原有业务 Session。
- Garmin 设置页独立显示“自动同步已关闭”和“已有数据已过期”，不自动开启用户开关。

## MCP Schema 与客户端刷新

`SegmentValidation`、`ActivityClassification`、`SegmentStorage` 使用明确 TypedDict 输出定义，同时保留原有 dict 消费方式。旧 `segments_complete` 明确只描述原始存储行返回是否截断，新增 `raw_segments_complete` 与 `normalized_structure_complete`，截断 Coach 上下文时同步撤下结构完整标记。

capabilities 不再将全部服务声明为无副作用；正式计划仍只读，设备缓存更新可能发生，权限仍由 OAuth 与业务层检查。

```powershell
python -B -m scripts.check_mcp_contract
```

该检查通过独立 MCP SDK Client 执行 tools/list，对比六个工具、原输入参数集、输出字段及嵌套 Schema，并输出公开 Schema 哈希。不需要用户凭据，不访问数据库或 Provider。

宿主应刷新或重新发现工具定义，再比对实际线上 tools/list 的版本与 Schema。刷新定义不意味着获得恢复数据权限，不能替用户重新授权。当前没有执行线上实时发现验收，不把本地检查写成线上通过。

## 不在本批内

- RAG 无答案相关性校准与拒绝阈值：需要单独的正/负样本评测，不能随意增加分数阈值。
- Runner State 多维风险、个人 HRV 基线、正式计划分段 Schema，以及整堂训练结构确认 UI。
- 真实历史数据回填、上游 FIT 恢复、生产迁移或部署。本批复用既有表，不要求数据库结构迁移。

## 测试记录

已执行的定向验收：纯规则/SDK 发现及相关单元组 56 passed，Provider/Coach/Validator 定向组 86 passed；隔离 MySQL 分段版本、覆盖率、权限和 Smart Sync 组合组 50 passed、0 skipped（12.03 秒）。分组有重叠，不能直接累加为不同用例总数。

前端 Typecheck 通过；完整 Vitest 44 文件、230 项通过（17.39 秒），生产构建通过。已有组件桩及包体积警告仍存在，不将其描述为新功能错误。

相关后端主组最终 660 passed、0 skipped（140.96 秒），覆盖 MCP/OAuth、Coach、Garmin、Runner State、Weekly Review、AI Plan、事实与分段链路；这不是全仓所有测试的数量。原失败项为旧 RecordingSession 缺少新增读锁/读取方法，补齐测试替身并保留独立 MySQL 集成证据后重跑通过，没有关闭生产保护。

最终来源一致性与 MySQL 定向组 52 passed、0 skipped（26.93 秒），包括人工修订类型的来源保护和 Coach 新鲜度只读检查。该组最初在受限账号下有 13 项旧夹具因需要自行创建测试库而 skipped，随后在明确的本机测试管理权限下完整补跑；跳过不计作通过。

四个需要特殊空库/独立连接环境的既有 Coach Chat、AI Plan、OAuth 历史迁移和 Recovery 迁移模块不在该主组中，本批未改数据库结构且未宣称重新执行这些模块。没有执行真实 Garmin 上游数据恢复、线上 Schema 刷新或生产部署验收。

独立 SDK tools/list 契约检查 PASS，六个工具输入保持不变，最终输出 Schema 哈希：`3e674288e19de573170baf927ce6804dfb37c6d4c74e464d90a9d62b49aa2c13`。`git diff --check` 通过，受保护脚本 SHA256 保持不变。

## 2026年11月22日 半马活动分段复核

本轮分支 `codex/garmin-race-laps`，继承此前全部本地未提交修改。线上只读核实仍为 `0.16.8-facts-v3.3-smart-sync`，运行发布目录对应 `a82d94f46bb3`，没有部署本地 v3.4 防降级代码。以下真实核验只输出结构数量与校验结果，不将个人活动原始响应作为公开 Fixture。

### 链路证据

| 层次 | 只读核验与代码结论 |
| --- | --- |
| Garmin Provider | 已保存的详情响应 `garmin_splits.lapDTOs` 含 22 条真实圈；不是只能取得两条活动汇总。同期列表响应的 `splitSummaries` 为两条分类汇总，不能等价于独立圈。 |
| 原始响应 | 两种粒度的版本均保存在原始记录中；带 22 圈的版本较早，之后出现仅汇总版本。当前详情同步时间已有后续更新。 |
| Lap 持久化 | 线上 `_replace_laps` 在非空候选时整体替换旧圈，未使用 `prepare_replacement`。列表候选包含汇总圈时可以把详细圈降级；本地已有防降级实现尚未发布。本轮复用并加强真实形状回归，而不是再写一套存储链路。 |
| Normalizer | 两条分类汇总被排除，返回空规范化列表是正确的保守行为；不能由活动总距离/时间或 summary 的数量字段推算公里成绩。当前已存 22 圈经过同一线上 Normalizer 后，距离和时间均一致。 |
| MCP 投影 | 旧 `LAP_ACTIVITY_DISTANCE_MISMATCH` 比较全部原始行之和，两种重叠汇总会造成误导。候选改为规范化可加总明细的覆盖检查；原始行比较另放 `raw_segment_distance_consistent`。 |

原报告的“两条汇总”状态在本轮首次只读查询时已不再存在：当前数据库与线上共享详情投影均返回 22 条圈、22 条规范化明细、21 条约一公里圈，`structure_complete=true`，距离/时间一致，无 fact issues。本轮没有执行真实 Garmin 调用、重同步或生产数据修复，不能将这次恢复归因于本轮操作。v3.3 没有逐次 Lap 版本快照，无法复原每一次中间写入；但上述降级机制可用相同响应形状稳定复现。

### 最小修复与契约

- 复用 `lap_storage_policy.prepare_replacement` 对细粒度圈的保护；用完整明细 → 列表汇总 → 再读取的合成 MySQL 用例验证 ID 和数量保持不变。真实数据只在隔离的只读诊断进程中调用候选纯函数，结果为 `COARSER_REPRESENTATION`、保留 22 圈，未调用写入函数。
- `segment_validation.detail_status` 区分 UNAVAILABLE、SUMMARY_ONLY、PARTIAL、COMPLETE、CONFLICTED，并提供当前读取/规范化数量。`raw_segments_complete` / 旧 `segments_complete` 仍只表示已存原始行是否全部返回，不表示 Garmin 上游完整，也不表示独立圈已齐全。
- 只有汇总时，`normalized_segments=[]`、`segment_distance_consistent=null`，增加 `LAP_DETAIL_UNAVAILABLE`；明细确实与活动距离不符才保留 `LAP_ACTIVITY_DISTANCE_MISMATCH`。重叠/冲突增加明确结构问题，不任选一组并拼接。尾圈保留实际距离，不补成一公里。
- `eventTypeDTO.typeKey` 的白名单投影写入现有来源 JSON；历史记录只读取归属匹配的原始记录 JSON 字段，不向 MCP 暴露原始载荷、GPS 或自由文本。Race 是 `PROVIDER_RECORDED` 标签，不是独立验证的比赛成绩，不传播成整堂多活动训练类型。
- 真实样本的 Garmin 事件类型为 `uncategorized`，不是 `race`。UNKNOWN 因此保留；用户自述参加比赛仍可作为自述讨论，但不能静默写入数据库或伪装成 Garmin 已确认。
- 圈完整性与比赛标签独立。即使 Coach 上下文截断超过 24 圈，也只降低结构完整性，不抹去已有可信来源的比赛标签。六个 MCP 工具及输入不变；发布后需刷新客户端工具定义以获取新增字段与枚举，不要求额外 OAuth 权限。

### 可重复验收与运行边界

新增 `scripts/verify_stored_activity_laps.py`，显式指定用户、活动和日期，开启 MySQL READ ONLY 事务，直接读取同一个权限检查后的 Training Detail 投影，不调用可能排队同步的远程 MCP 包装层。输出仅有数量、布尔校验和受控类别；不得用它导出真实圈数据到公开仓库。

真实授权样本已执行只读验收：PASS，22 条原始行、22 条规范化明细、距离/时间/结构检查均通过。候选 Normalizer 在同一私有样本上返回 COMPLETE，候选存储纯策略拒绝两条汇总覆盖详细圈。该结果不等于候选代码已经部署。

本地回归使用独立生成的半马形状数据，数值、时间、活动 ID 与真实比赛不同。Provider → Lap 写入 → Normalizer → MCP、事件标签隔离、汇总误差语义、尾圈、用户隔离和 Coach 截断均有合成回归。无需 Schema 迁移、FIT 解析或新 Garmin Endpoint；未修改正式计划、风险阈值、生产记录或其他用户数据。

本轮实际结果：

| 验收 | 结果 |
| --- | --- |
| Provider、分段规则、事实质量、MCP 契约、Runner State 及安全定向单元组 | 100 passed、0 failed、0 skipped，5.16 秒 |
| 隔离 MySQL 半马链路、既有 facts v3/v3.1/v3.4、MCP server、OAuth MySQL 与真实 TCP | 46 passed、0 failed、0 skipped，31.68 秒 |
| 真实授权活动存储投影只读复核 | PASS，22 条规范化圈，21 条约一公里圈，距离/时间一致；没有 Provider 调用或数据库写入 |
| 候选纯策略在真实样本上复核 | PASS，拒绝汇总降级、保留 22 条明细；不是候选代码已部署 |
| 独立 SDK 六工具契约 | PASS，原输入不变，新增输出语义可发现 |
| 前端 Typecheck / Build | PASS / PASS（11.27 秒，保留既有大包和第三方注释警告） |
| `git diff --check` | PASS，受保护迁移脚本哈希不变 |

两个旧纯单元测试的 Mock 没有提供前一轮新增待关联活动 COUNT 的返回值，最初失败；已补齐明确的零值夹具后重跑通过，没有修改真实查询以迁就 Mock。以上是定向验收，不是全仓 pytest。代码未提交、未推送、未部署；下一次发布必须包含防降级写入保护及新详情契约，不能只刷新客户端来消除服务端覆盖风险。
