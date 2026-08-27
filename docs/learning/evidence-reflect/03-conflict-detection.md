# Conflict Detection

冲突要求证据位于同一 domain、共享 semantic key、时间范围重叠且 semantic value 不一致。例如用户主观恢复良好，而 Garmin-normalized recovery signal 较弱，系统生成 `recovery_signal_conflict`。

Judge 不设全局 `Garmin > User` 或 `User > Garmin` 顺序，也不绕过现有 Garmin merge/manual override policy。冲突结果映射为 `PARTIAL` readiness。Validator 阻止“恢复状态明确很差”这类确定性结论，但允许“主观感受与设备信号不完全一致，暂不做确定判断”。
