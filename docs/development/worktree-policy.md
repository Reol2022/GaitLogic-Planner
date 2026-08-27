# GaitLogic 单主工作区开发政策

GaitLogic Planner 当前采用单主工作区开发策略。唯一用于日常开发、调试、启动服务、
运行测试和修复缺陷的目录是：

```text
E:\我的项目\Gaitlogic-planner
```

旧 worktree 只作为历史残留或临时只读检查使用。除非维护者明确要求，不得在旧
worktree 中继续开发，也不得创建版本专属、agent、release 或 validation worktree。

每次开始工作前先在目标终端执行：

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse --short HEAD
git status --short
```

如果仓库根目录不是上述主工作区，应停止启动、调试或写入操作并切回主工作区。
启动脚本必须从自身位置解析仓库根目录，不能硬编码旧 worktree 路径。

旧 worktree 的处理规则：

- Dirty worktree 必须保留，禁止强制删除、reset 或覆盖。
- Clean worktree 只有在 HEAD 已被主分支包含后，才能标记为可移除。
- 删除操作由维护者人工执行；自动化任务只输出建议命令，不执行删除。
- 禁止在 worktree 之间整库复制，只允许经过文件级 diff 审核的定向迁移。

