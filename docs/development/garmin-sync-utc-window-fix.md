# Garmin活动同步：UTC窗口修复（2026-11-10）

## 根因

同步服务的增量窗口是naive UTC，而Garmin Provider曾将start_time_local直接去掉时区，与UTC窗口比较。中国区当日晚间已上传的活动可能被误认为晚于查询截止时间，直到数小时后才进入窗口。训练状态历史的DUPLICATE_PAYLOAD仅表示快照去重，不能证明最新活动已被获取。

## 修复

- 查询窗口统一为naive UTC；明确带offset的输入先转换UTC，不能仅移除tzinfo。
- 优先使用startTimeGMT/startTimeUTC。带offset的GMT值转换UTC后再存储。
- 缺失GMT时按活动IANA时区转换，兼容timeZoneUnitDTO字符串及timeZone/unitKey对象。无效时区不猜测；维持已有活动解析失败的跳过处理。
- 活动本地时间与日期仍用于现有日志匹配，不改变展示日期、训练规则或用户隔离。
- 不改变Garmin登录、请求参数、分页大小、额度或恢复指标计算；不重新生成历史训练记录。

## 测试与发布

使用纯合成活动覆盖晚间训练、naive/Z/offset形式UTC、缺失GMT、时区对象、跨午夜、窗口边界、负时差和无效时区。

定向组：39 passed、13 skipped（隔离数据库未配置）；跳过项不视为通过。发布前核对线上原文件与本地HEAD基线一致，备份后只覆盖Garmin Provider，保留环境配置及权限，以www用户预检导入后重载已核实的Gunicorn主进程。

已发布至当前release `20261109-a78e773b`，仅变更一个Provider源码文件。www用户合成晚间活动预检PASS，重载后内部和公网HTTPS健康均PASS，环境文件哈希未变。备份为服务器 `shared/deployments/garmin-sync-utc-20261110-v1/garmin.py.before`，同目录保留safe-receipt.json。未执行数据库写入或真实Garmin同步；新活动补拉尚待用户操作验收。

代码发布不等于补拉成功。发布后需由用户重新执行一次“最近7天”同步，核对新活动及任务计数；不能只看训练状态是否增加历史记录。未经单独授权，不触发真实Garmin请求或修改业务训练数据。
