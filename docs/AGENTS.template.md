# AGENTS.md — <PROJECT_NAME>

本文件是 Cursor、Codex、Claude Code 与 OpenCode 共用的唯一规则入口。
协作与并发流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。
任何工具适配文件只能导入或指向这些公共文件，不得复制出第二套规则。

## 唯一主线

<!-- 用两三句写清这个仓库只做什么。范围之外的东西写成 follow-up，不要顺手做。 -->

## 当前状态

<!-- 只写会影响下一步动作的事实。不要写成流水账；现状以 git status 和 handoff 为准。 -->

## 多 Agent 协作

- 执行改动前先读 [CONTRIBUTING.md](CONTRIBUTING.md)，明确任务契约、允许文件、
  禁止文件、依赖和验收命令。
- 默认一个写入 Agent 对应一个 Git worktree/branch；同一工作树同时只能有一个
  写入者，其他 Agent 只读。
- 开工前记录 `git status --short` 和当前 HEAD；既有改动归原作者所有，
  不得顺手覆盖、回滚、暂存或提交。
- 不允许两个 Agent 同时修改同一文件。发现范围重叠或前置接口未稳定时，
  停止写入并交回协调者重新划分。
- 子任务只交付任务契约内的文件；公共接口由协调者先定稿，再让下游 Agent 适配。
- 完成时按 [`.agents/templates/handoff.md`](.agents/templates/handoff.md) 汇报改动、
  验证、未验证项、风险和建议合并顺序。落点见 CONTRIBUTING.md：有 PR 写进 PR 描述的
  `## Agent handoff` 段，无 PR 由 commit message 正文承载；两种情况下 commit message
  都必须带实跑的验证结果，不写进 gitignored 的 `.agent-work/`。

## 写码纪律

- 使用当前工具支持的最小差异补丁机制编辑文本；保留用户未授权的无关改动。
- 不提交真实 IP、主机名、部署路径、账号、设备号或客户名——文档写
  `<LAN_IP>` / `<DB_HOST>` 之类占位符，实际值留在本地 `.env*` 或未跟踪笔记。
- 凭据、token、密钥一律不入库；即使是私有仓库也照此执行。
- 每个事实 claim 必须可追溯到实跑证据；"应该能跑"不算验证通过。

<!-- 下面按项目补充：技术栈约束、禁止修改的文件、平台托管文件等 -->

## 验证

```
<!-- 写成可直接复制执行的命令块；CI 与人工验收都用这一份 -->
```
