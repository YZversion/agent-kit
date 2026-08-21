# Cross-tool agent system

`.agents/` 是本仓库与具体 Agent 工具无关的协作层：

- `skills/`：Cursor、Codex、Claude Code、OpenCode 共用的唯一 Skill 权威源；
  Claude Code 通过 `.claude/skills/project-skill-router/` 薄路由读取；
- `templates/`：Agent 内部生成任务合同和交接时使用的固定格式；不要求用户填写。

根级 `AGENTS.md` 保存不可协商规则，`CONTRIBUTING.md` 保存并发、交接和验收流程。
工具专有目录只能做发现适配，不能复制工作流正文。

## 维护不变量

1. 每个 `skills/<name>/SKILL.md` 都有唯一、明确的触发范围，且 frontmatter 的
   `name` 与目录名一致。
2. `.claude/skills/project-skill-router/` 负责自动选择 canonical Skill；
   `.claude/commands/` 提供同名显式入口，description 必须与 canonical Skill 逐字一致。
3. 临时状态统一放 gitignored 的 `.agent-work/`，不放 `.agents/`。
4. 用户的唯一万用提示词位于 `skills/decide-and-deliver/assets/universal-prompt.md`。
5. Skill 正文只在这里改。工具目录下的副本由安装脚本生成，手改会在下次重装时丢失。
6. 修改入口、适配器或 Skill 后运行：

```powershell
python scripts\validate_agent_system.py
```
