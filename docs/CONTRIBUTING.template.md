# Contribution and multi-agent collaboration

本文定义人类贡献者与 Cursor、Codex、Claude Code、OpenCode 的共同交付流程。
强制工程与安全规则只在 [`AGENTS.md`](AGENTS.md) 维护；
本文件只定义怎样拆分、并行、交接和验收工作。

## 权威源

| 内容 | 唯一权威源 |
|---|---|
| 强制规则与验证入口 | `AGENTS.md` |
| 可复用 Agent 工作流 | `.agents/skills/*/SKILL.md` |
| 个人工作风格与万用提示词 | `.agents/skills/decide-and-deliver/` |
| Agent 内部任务与交接模板 | `.agents/templates/` |

`CLAUDE.md`、`opencode.json` 和 `.cursor/rules/cross-tool-contract.mdc` 都只是
工具适配层，不得在其中新增工程规则。不要另建"现状汇总 / memory"类长文；
现状以 `git status`、`git log` 和 handoff 为准。

## 你的极简入口

你只需要做三件事：

1. 加载 `$decide-and-deliver`；Claude Code 也可以使用 `/decide-and-deliver`。
2. 可选：把其他 Agent 的答案或资料直接粘贴进来。
3. 粘贴[极简万用提示词](.agents/skills/decide-and-deliver/assets/universal-prompt.md)，
   最后只写一句自己的需求。

不用填写任务编号、角色、文件范围、HEAD、验收命令或 handoff。协调 Agent 必须从
仓库状态自动推导这些内部信息；只有缺失选择会实质改变方向、风险或不可逆结果时
才能询问你。

对你唯一需要记住的协作边界是：**同一工作树一次只让一个 Agent 写入。**
需要多种意见时，让其他 Agent 只读分析；需要真正并行修改时，
让协调 Agent 自动建立互不重叠的 worktree/branch。

## 并发模型

默认模型是"一名写入 Agent，一个 worktree，一条 branch"。同一工作树同时只能有一个
写入者；研究、审查和验证 Agent 可以并行，但必须保持只读。

固定角色只有四种：**协调者**维护任务图、范围和合并顺序；**研究 Agent** 只读并交付
证据；**写入 Agent** 只改契约允许的文件；**验证 Agent** 在独立上下文中复跑门禁并
核对 handoff。一个任务可以少用角色，但不得让多个角色同时取得同一工作树的写权限。

- 协调 Agent 根据用户的一句话需求和仓库现状自动填写内部
  [task contract](.agents/templates/task-contract.md)，不得要求用户逐项填写。
- 两个写入任务的 `Allowed files` 不得相交。公共接口文件先由一个任务定稿并合并，
  再启动依赖它的任务。
- 每个写入 Agent 开工前记录 HEAD 和 `git status --short`。基线已有改动不属于新任务，
  不得回滚、暂存、格式化或顺手修复。
- 不在共享工作树使用 `git stash`、`git reset`、`git checkout --` 或全仓格式化
  来制造"干净状态"。
- 发现文件范围重叠、前置接口变化或来源不明的修改时，停止修改冲突文件并交回
  协调者重新划分。
- Agent 的临时计划、日志、快照和 ledger 放在 gitignored 的 `.agent-work/`；
  不得把会话记忆当作仓库事实。

需要真正并行写入时，为每个任务创建独立 worktree。分支名使用 `<tool>/<task-slug>`。
合并顺序由依赖关系决定，不按完成时间决定。

## 标准工作流

### 1. 接单

协调 Agent 自动生成任务契约。执行 Agent 必须确认：目标可以验收、写入范围没有重叠、
禁止文件明确、依赖已满足。能从仓库读取的内容自行补全；只有缺失选择会实质改变方向、
风险或不可逆结果时才询问用户。

### 2. 基线

记录以下信息到任务或交接消息，不提交机器私有值：

```text
Tool / agent:
Task id:
Branch / worktree:
Baseline HEAD:
Pre-existing changes:
Allowed files:
Required checks:
```

### 3. 实现

- 只修改任务契约允许的文件，使用最小差异补丁。
- 新发现的工作若超出目标，记录为 follow-up，不擅自扩大范围。
- 修改共享 schema、CLI、公共接口时，先更新契约/测试，再通知下游任务基线已变化。
- 使用仓库 Skill 时，以 `.agents/skills/` 下的内容为准；工具适配器只负责发现，
  不产生新步骤。

### 4. 验证

先运行与修改直接相关的最小测试，再运行 `AGENTS.md` 中要求的公共验证。
报告必须逐条区分：

- `PASS`：实际运行且通过；
- `FAIL`：实际运行但失败，附首个可操作错误；
- `NOT RUN`：未运行并说明原因；
- `BLOCKED`：缺少外部条件。

测试通过不能替代真实数据、人工验收或上线门禁。

### 5. 交接与合并

按 [handoff template](.agents/templates/handoff.md) 交付。协调者核对允许范围、diff、
验证证据、依赖和风险后决定合并；下游 Agent 必须基于合并后的 commit 继续，
不基于聊天中的未落盘描述猜接口。

**handoff 是一种格式，不是一个文件。** 落点按是否有 PR 区分：

| 情况 | handoff 落在哪 |
|---|---|
| 有 PR | PR 描述的 `## Agent handoff` 段，**并且** commit message 正文带实跑的验证结果与未验证项 |
| 无 PR | commit message 正文承载全部 handoff 字段；同时在给用户的回复里附 handoff template 的三列 Verification 表 |

理由是可达性：commit message 进 `git log`，clone 到任何机器、任何工具都读得到。
**不要把 handoff 写进 `.agent-work/`**——该目录是 gitignored 的临时区，
写进去等于没有交接出去。

commit message 正文至少要能回答：基线 commit、改了哪些文件、跑了哪些验证及其结果、
哪些没验证、剩余风险。只写"已修复"而不给验证证据的 commit 视为未完成。

## 完成定义

任务只有同时满足以下条件才算完成：

- 任务契约中的交付物全部存在，且没有越界文件；
- 相关测试及公共验证有明确结果；
- 没有覆盖或夹带其他贡献者的改动；
- 没有凭据、私有主机/部署/账号等信息泄漏；
- 文档、schema、CLI 或公共接口随行为变更同步更新；
- handoff 列出未验证项、剩余风险和建议合并顺序；
- `python scripts/validate_agent_system.py` 通过。

## 工具入口

| 工具 | 自动入口 | Skill 入口 |
|---|---|---|
| Cursor | `.cursor/rules/cross-tool-contract.mdc` → 公共规则 | `.agents/skills/` |
| Codex | `AGENTS.md` | `.agents/skills/` |
| Claude Code | `CLAUDE.md` 导入公共规则 | `.claude/skills/project-skill-router/` + `.claude/commands/` → `.agents/skills/` |
| OpenCode | `AGENTS.md` + `opencode.json` | `.agents/skills/` |

任何适配层失效、重复定义或 Skill 漂移都由 `scripts/validate_agent_system.py` 拒绝。

## 首次启用或更新后

1. 结束旧的 Agent 会话并从仓库根重新启动，使各工具重建规则与 Skill 发现结果。
2. 运行 `python scripts/validate_agent_system.py`。
3. Cursor 确认 always-apply 的 `cross-tool-contract` 可见；
   Claude Code 用 `/memory` 确认 `CLAUDE.md` 导入；
   Codex 让新会话列出活动 `AGENTS.md` 与项目 Skills。
4. 只有上述入口正常后，才开始创建并行写入任务。
